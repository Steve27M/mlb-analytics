"""Shared ingestion infrastructure — bronze Parquet, manifest, logging, polite HTTP.

Every pull script imports from here so the invariants live in ONE place:

  * Bronze is date-partitioned Parquet:  <bronze>/<source>/<part_col>=<val>/data.parquet
  * All MLBAM ids are written as BIGINT (nullable Int64) — never float-inferred.
  * Idempotent: a (source, partition) already in bronze + manifest is not re-pulled,
    except under the freshness policy (checksum mismatch -> partition replace).
  * Structured JSON-lines logging (stage, source, range, rows, duration, cache, quota).
  * Config via env vars only (Phase 6 portability); no absolute paths baked in.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

load_dotenv()

# --- config (env-only) ---------------------------------------------------------------------

def bronze_dir() -> Path:
    d = Path(os.getenv("MLB_BRONZE_DIR", "data/bronze"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def results_dir() -> Path:
    d = Path(os.getenv("MLB_RESULTS_DIR", "data/results"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def seasons() -> list[int]:
    raw = os.getenv("MLB_SEASONS", "2023,2024,2025")
    return [int(s) for s in raw.split(",") if s.strip()]


def user_agent() -> str:
    return os.getenv("MLB_USER_AGENT", "mlb-analytics/0.1 (portfolio)")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --- structured logging --------------------------------------------------------------------

def log(stage: str, source: str, **fields) -> None:
    """Emit one JSON line. This exact format is reused verbatim in the AWS Lambda lift."""
    rec = {"ts": now_iso(), "stage": stage, "source": source, **fields}
    sys.stdout.write(json.dumps(rec, default=str) + "\n")
    sys.stdout.flush()


# --- polite HTTP ---------------------------------------------------------------------------

class HttpError(Exception):
    """Raised on a retryable HTTP status (429/5xx)."""


@retry(
    retry=retry_if_exception_type((HttpError, requests.exceptions.ConnectionError,
                                   requests.exceptions.Timeout)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def get_json(url: str, params: dict | None = None, throttle: float = 0.5) -> dict:
    """GET with descriptive UA, exponential backoff on 429/5xx, and a courtesy throttle."""
    time.sleep(throttle)
    resp = requests.get(url, params=params, headers={"User-Agent": user_agent()}, timeout=30)
    if resp.status_code == 429 or resp.status_code >= 500:
        raise HttpError(f"{resp.status_code} for {resp.url}")
    resp.raise_for_status()
    return resp.json()


# --- bronze Parquet + manifest -------------------------------------------------------------

def _partition_path(source: str, part_col: str, part_val: str) -> Path:
    return bronze_dir() / source / f"{part_col}={part_val}" / "data.parquet"


def partition_exists(source: str, part_col: str, part_val: str) -> bool:
    return _partition_path(source, part_col, part_val).exists()


def _manifest_path(source: str) -> Path:
    return bronze_dir() / source / "_manifest.json"


def read_manifest(source: str) -> dict:
    p = _manifest_path(source)
    return json.loads(p.read_text()) if p.exists() else {}


def _write_manifest(source: str, manifest: dict) -> None:
    p = _manifest_path(source)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def content_checksum(df: pd.DataFrame, sort_cols: list[str]) -> str:
    """Order-independent content hash: sort by stable keys, then hash the row hashes.

    Detects Statcast retro-corrections (same partition, changed values -> new checksum).
    """
    cols = [c for c in sort_cols if c in df.columns]
    d = df.sort_values(cols).reset_index(drop=True) if cols else df.reset_index(drop=True)
    row_hashes = pd.util.hash_pandas_object(d, index=False).to_numpy()
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


def cast_ids_bigint(df: pd.DataFrame, id_cols: list[str]) -> pd.DataFrame:
    """Force id columns to nullable Int64 (-> Parquet BIGINT). Guards the cfb float-id bug:
    pandas inferring an 18-digit id as float64 silently collapses distinct keys."""
    out = df.copy()
    for c in id_cols:
        if c in out.columns:
            # Route through float only if needed, then to Int64; raise on genuine fractional ids.
            s = out[c]
            if s.dtype == object or str(s.dtype).startswith("float"):
                s = pd.to_numeric(s, errors="coerce")
            out[c] = s.astype("Int64")
    return out


def write_partition(
    df: pd.DataFrame,
    source: str,
    part_col: str,
    part_val: str,
    id_cols: list[str],
    sort_cols: list[str],
) -> tuple[int, str, bool]:
    """Write one partition to bronze Parquet + update the manifest.

    Returns (rows, checksum, replaced) where `replaced` is True if an existing partition's
    checksum changed (freshness-policy retro-correction) — logged, never silent.
    """
    df = cast_ids_bigint(df, id_cols)
    checksum = content_checksum(df, sort_cols)
    manifest = read_manifest(source)
    prior = manifest.get(part_val)
    replaced = bool(prior and prior.get("checksum") != checksum)

    path = _partition_path(source, part_col, part_val)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False)

    manifest[part_val] = {
        "rows": int(len(df)),
        "checksum": checksum,
        "pulled_at": now_iso(),
    }
    _write_manifest(source, manifest)
    return len(df), checksum, replaced
