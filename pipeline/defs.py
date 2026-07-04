"""Dagster definitions — the medallion pipeline as software-defined assets (FEEDBACK §10).

Each asset is a thin wrapper over one `pipeline.stages` function (the SAME code the Typer CLI runs —
no parallel orchestration path). Assets are side-effecting (they write bronze/warehouse/feeds/docs)
and ordered by `deps`, not by passing data through IO managers. The parity gate and the dbt data
tests are exposed as BLOCKING asset checks: a red check stops the run before `site` is rebuilt, so a
bad pull can never publish a partially-updated dashboard.

Run locally:  uv run dagster asset materialize --select 'landed+' -m pipeline.defs
Scheduled:    the nightly GitHub Actions workflow materializes 'bronze+' (Phase 2).
"""
from __future__ import annotations

import json
from pathlib import Path

import dagster as dg

from pipeline import stages

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "data" / "results"
RUN_RESULTS = REPO / "dbt" / "target" / "run_results.json"
GROUP = "medallion"


@dg.asset(group_name=GROUP, description="Pull statsapi + Savant + Chadwick + people + draft + odds "
          "to date-partitioned bronze Parquet (idempotent, cached).")
def bronze() -> dg.MaterializeResult:
    stages.ingest()
    return dg.MaterializeResult(metadata={"seasons": ", ".join(map(str, stages.seasons()))})


@dg.asset(group_name=GROUP, deps=[bronze], description="Load bronze Parquet into DuckDB bronze.*.")
def landed() -> dg.MaterializeResult:
    stages.land()
    return dg.MaterializeResult()


@dg.asset(group_name=GROUP, deps=[landed],
          description="dbt: staging -> SCD2 -> silver -> gold, with the data tests.")
def warehouse() -> dg.MaterializeResult:
    stages.build()
    tests = {"pass": 0, "warn": 0, "fail": 0}
    if RUN_RESULTS.exists():
        for r in json.loads(RUN_RESULTS.read_text()).get("results", []):
            if r.get("unique_id", "").startswith("test."):
                st = r.get("status", "")
                tests["pass" if st == "pass" else "warn" if st == "warn" else "fail"] += 1
    return dg.MaterializeResult(metadata={f"tests_{k}": v for k, v in tests.items()})


@dg.asset(group_name=GROUP, deps=[warehouse],
          description="Export gold/silver feeds to data/gold/*.parquet (the R<->Python interface).")
def feeds() -> dg.MaterializeResult:
    stages.export()
    return dg.MaterializeResult()


@dg.asset(group_name=GROUP, deps=[feeds], description="Fit the 13 models in R -> data/results/.")
def r_models() -> dg.MaterializeResult:
    stages.models()
    return dg.MaterializeResult()


@dg.asset(group_name=GROUP, deps=[r_models],
          description="Fit the 13 models in Python and run the three-tier parity GATE.")
def parity() -> dg.MaterializeResult:
    stages.parity()
    mfile = RESULTS / "metrics.json"
    n = len(json.loads(mfile.read_text())) if mfile.exists() else 0
    return dg.MaterializeResult(metadata={"models": n})


@dg.asset(group_name=GROUP, deps=[parity],
          description="Pre-render + season sim + build the static DIAMONDIQ site into docs/.")
def site() -> dg.MaterializeResult:
    stages.dashboard()
    return dg.MaterializeResult()


# ---------------------------------------------------------------- gates as blocking asset checks
@dg.asset_check(asset=warehouse, blocking=True, description="All dbt data tests pass (0 failing).")
def dbt_tests_pass() -> dg.AssetCheckResult:
    if not RUN_RESULTS.exists():
        return dg.AssetCheckResult(passed=False, metadata={"reason": "no run_results.json"})
    results = json.loads(RUN_RESULTS.read_text()).get("results", [])
    failing = [r["unique_id"] for r in results
               if r.get("unique_id", "").startswith("test.") and r.get("status") != "pass"]
    return dg.AssetCheckResult(passed=not failing,
                               metadata={"failing": len(failing), "examples": failing[:5]})


@dg.asset_check(asset=parity, blocking=True,
                description="All 13 models agree R<->Python across every parity tier.")
def parity_all_green() -> dg.AssetCheckResult:
    mfile = RESULTS / "metrics.json"
    if not mfile.exists():
        return dg.AssetCheckResult(passed=False, metadata={"reason": "no metrics.json"})
    metrics = json.loads(mfile.read_text())
    failing = [k for k, v in metrics.items() if not v.get("parity_ok")]
    return dg.AssetCheckResult(passed=not failing,
                               metadata={"models": len(metrics), "failing": failing})


defs = dg.Definitions(
    assets=[bronze, landed, warehouse, feeds, r_models, parity, site],
    asset_checks=[dbt_tests_pass, parity_all_green],
)
