"""Pipeline observability + SPC (FEEDBACK2 §2).

Appends one record per run to docs/data/runs.json (committed by the nightly), and computes Shewhart
individuals-chart control limits from a trailing window into docs/data/spc_limits.json. Control
limits come FROM the process (moving-range estimate) — the right tool vs. fixed thresholds, and they
double as data-drift detection on physical canaries (league fastball velocity, pitches per game).

A rule violation WARNS (amber on ops.html) but never blocks — dbt tests + the parity gate are the
gates; blocking on normal cause-variation would turn ordinary noise into an outage.

Run standalone to record the current state (run #1); the nightly passes real timings via env
(MLB_RUN_INGEST_SEC / MLB_RUN_DBT_SEC / MLB_RUN_SHA).
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "data"
RUNS = OUT / "runs.json"
LIMITS = OUT / "spc_limits.json"
RESULTS = REPO / "data" / "results"
DB = os.getenv("MLB_DUCKDB_PATH", str(REPO / "data" / "warehouse.duckdb"))
LIVE_DB = os.getenv("MLB_LIVE_DUCKDB_PATH", str(REPO / "data" / "warehouse_live.duckdb"))
WINDOW = 60          # trailing in-season runs for the control limits
KEEP = 120           # rolling runs.json window
MIN_RUNS = 15        # below this, limits are "collecting baseline"
RELIMIT_DAYS = 7     # recompute limits weekly, not per-run (limits shouldn't chase the data)
# Shewhart individuals chart: UCL/LCL = mean ± 2.66 * MRbar (2.66 = 3/d2 for n=2)
SPC_SERIES = ["rows_ingested", "ingest_sec", "dbt_test_sec", "fastball_velo", "pitches_per_game"]


DLQ_DIR = Path(os.getenv("MLB_DLQ_DIR", str(REPO / "data" / "dlq")))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _dlq_stats() -> dict:
    """DLQ depth + quarantine count (read the files directly to avoid a cross-package import)."""
    def n(p: Path) -> int:
        return len([x for x in p.read_text().splitlines() if x.strip()]) if p.exists() else 0
    return {"depth": n(DLQ_DIR / "queue.jsonl"), "quarantined": n(DLQ_DIR / "quarantine.jsonl")}


def _canaries() -> dict:
    """Physical drift canaries from the live current-season pitches (catch feed/sensor drift that
    row counts miss). Falls back to the frozen warehouse if the live one isn't built."""
    db = LIVE_DB if Path(LIVE_DB).exists() else DB
    con = duckdb.connect(db, read_only=True)
    try:
        velo = con.execute(
            "select round(avg(release_speed),2) from bronze.statcast "
            "where pitch_type in ('FF','FA') and release_speed is not null").fetchone()[0]
        ppg = con.execute(
            "select round(count(*)::double / nullif(count(distinct game_pk),0), 1) "
            "from bronze.statcast").fetchone()[0]
        rows = con.execute("select count(*) from bronze.statcast").fetchone()[0]
    finally:
        con.close()
    return {"fastball_velo": float(velo) if velo is not None else None,
            "pitches_per_game": float(ppg) if ppg is not None else None,
            "rows_ingested": int(rows)}


def _gates() -> dict:
    rr = REPO / "data" / "results" / "frozen_run_results.json"
    tests = {"pass": 0, "total": 0}
    if rr.exists():
        for r in json.loads(rr.read_text()).get("results", []):
            if r.get("unique_id", "").startswith("test."):
                tests["total"] += 1
                tests["pass"] += 1 if r.get("status") == "pass" else 0
    mfile = RESULTS / "metrics.json"
    parity = None
    if mfile.exists():
        m = json.loads(mfile.read_text())
        parity = all(v.get("parity_ok") for v in m.values()) if m else None
    return {"dbt_tests_pass": tests["pass"], "dbt_tests_total": tests["total"], "parity_ok": parity}


def _git_sha() -> str:
    if os.getenv("MLB_RUN_SHA"):
        return os.getenv("MLB_RUN_SHA")[:12]
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=REPO, text=True).strip()
    except Exception:
        return "unknown"


def _read_runs() -> list[dict]:
    return json.loads(RUNS.read_text()) if RUNS.exists() else []


def _we_violations(series: list[float], cl: float, sd: float) -> list[str]:
    """Western Electric rules on the recent tail: 1 beyond 3σ; 2 of 3 beyond 2σ same side;
    8 consecutive same side. Returns rule IDs triggered by the LAST point."""
    if not series or sd == 0:
        return []
    z = [(x - cl) / sd for x in series]
    hits = []
    if abs(z[-1]) > 3:
        hits.append("WE1: beyond 3σ")
    if len(z) >= 3:
        last3 = z[-3:]
        for side in (1, -1):
            if sum(1 for v in last3 if v * side > 2) >= 2 and last3[-1] * side > 2:
                hits.append("WE2: 2 of 3 beyond 2σ")
                break
    if len(z) >= 8 and (all(v > 0 for v in z[-8:]) or all(v < 0 for v in z[-8:])):
        hits.append("WE4: 8 consecutive one side")
    return hits


def _compute_limits(runs: list[dict], prev: dict) -> dict:
    """Shewhart individuals limits per series from the trailing WINDOW. Recompute only weekly."""
    if prev.get("computed") and prev.get("n", 0) >= MIN_RUNS:
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(prev["computed"])).days
            if age < RELIMIT_DAYS:
                return prev  # limits shouldn't chase the data — keep last week's
        except Exception:
            pass
    out = {"computed": _now(), "n": len(runs), "window": WINDOW, "series": {}}
    tail = runs[-WINDOW:]
    if len(tail) < MIN_RUNS:
        out["baseline"] = f"collecting baseline ({len(tail)}/{MIN_RUNS} runs)"
        return out
    for s in SPC_SERIES:
        vals = [r[s] for r in tail if isinstance(r.get(s), (int, float))]
        if len(vals) < MIN_RUNS:
            continue
        mrbar = sum(abs(vals[i] - vals[i - 1]) for i in range(1, len(vals))) / (len(vals) - 1)
        cl = sum(vals) / len(vals)
        sd = mrbar / 1.128  # sigma estimate from mean moving range (d2=1.128 for n=2)
        out["series"][s] = {"cl": round(cl, 3), "ucl": round(cl + 2.66 * mrbar, 3),
                            "lcl": round(cl - 2.66 * mrbar, 3), "sigma": round(sd, 3)}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"ts": os.getenv("MLB_RUN_TS") or _now(), "sha": _git_sha(),
           "ingest_sec": float(os.getenv("MLB_RUN_INGEST_SEC", 0)) or None,
           "dbt_test_sec": float(os.getenv("MLB_RUN_DBT_SEC", 0)) or None,
           **_canaries(), **_gates(), "dlq": _dlq_stats()}
    runs = _read_runs()
    runs.append(rec)
    runs = runs[-KEEP:]
    RUNS.write_text(json.dumps(runs))
    prev = json.loads(LIMITS.read_text()) if LIMITS.exists() else {}
    limits = _compute_limits(runs, prev)
    # mark the current run's Western Electric violations against the live limits
    viol = {}
    for s, lim in limits.get("series", {}).items():
        series = [r[s] for r in runs if isinstance(r.get(s), (int, float))]
        v = _we_violations(series, lim["cl"], lim["sigma"])
        if v:
            viol[s] = v
    limits["violations"] = viol
    LIMITS.write_text(json.dumps(limits))
    print(json.dumps({"stage": "ops", "event": "recorded", "runs": len(runs),
                      "limits": len(limits.get("series", {})), "violations": list(viol),
                      "dlq": rec["dlq"]}))


if __name__ == "__main__":
    main()
