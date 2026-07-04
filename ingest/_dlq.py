"""Dead-letter queue for the ingest (FEEDBACK2 §4).

A per-item pull failure is QUEUED, not fatal — the run continues with the rest of the slate. The
next run drains the queue first with capped retries; an item that keeps failing is QUARANTINED
(stop retrying forever) and surfaced to ops.html. One flaky response must not kill a night; a
permanently-broken item must not retry until the heat death of the universe.

Files live under data/dlq/ (gitignored — runner-cached, never committed):
  queue.jsonl       one line per still-failing item: {source, key, endpoint, error, attempt, ts}
  quarantine.jsonl  items that hit MAX_ATTEMPTS
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

DLQ_DIR = Path(os.getenv("MLB_DLQ_DIR", "data/dlq"))
QUEUE = DLQ_DIR / "queue.jsonl"
QUARANTINE = DLQ_DIR / "quarantine.jsonl"
MAX_ATTEMPTS = 5


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] \
        if p.exists() else []


def prior_attempts() -> dict:
    """(source, key) -> max attempt count already recorded (so callers can increment)."""
    m: dict = {}
    for it in _read(QUEUE):
        k = (it["source"], it["key"])
        m[k] = max(m.get(k, 0), it["attempt"])
    return m


def enqueue(source: str, key, endpoint: str, error, attempt: int) -> None:
    DLQ_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"source": source, "key": str(key), "endpoint": endpoint,
           "error": str(error)[:300], "attempt": int(attempt), "ts": _now()}
    with QUEUE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def quarantined_keys() -> set:
    return {(it["source"], it["key"]) for it in _read(QUARANTINE)}


def drain() -> set:
    """Call at ingest start: quarantine items that have hit MAX_ATTEMPTS, compact the queue to the
    latest record per item, and return the set of quarantined (source, key) so the caller skips
    them. Retryable items stay queued and are simply re-attempted by the normal pull loop."""
    latest: dict = {}
    for it in _read(QUEUE):
        k = (it["source"], it["key"])
        if k not in latest or it["attempt"] >= latest[k]["attempt"]:
            latest[k] = it
    keep, quar = [], []
    for it in latest.values():
        (quar if it["attempt"] >= MAX_ATTEMPTS else keep).append(it)
    if quar:
        DLQ_DIR.mkdir(parents=True, exist_ok=True)
        with QUARANTINE.open("a", encoding="utf-8") as f:
            for it in quar:
                f.write(json.dumps({**it, "quarantined_ts": _now()}) + "\n")
    DLQ_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text("".join(json.dumps(it) + "\n" for it in keep), encoding="utf-8")
    return quarantined_keys()


def stats() -> dict:
    """DLQ depth + quarantine count, for ops.html."""
    return {"depth": len(_read(QUEUE)), "quarantined": len(_read(QUARANTINE))}
