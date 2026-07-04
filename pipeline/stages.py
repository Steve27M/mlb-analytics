"""Pipeline stage functions — the single implementation each stage.

`run.py` (Typer CLI) and the Dagster assets (Phase 2) are both thin wrappers over these functions,
so CLI behavior and scheduled behavior can never drift (FEEDBACK §10.1). Each function raises
`StageError` on failure; the caller decides how to surface it (CLI -> non-zero exit, Dagster ->
asset failure). Config is env-only (no absolute paths) for portability.

Stages: ingest -> land -> build -> export -> models -> parity -> dashboard, plus the determinism
GATE. `full_run` chains the seven build stages.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

R_MODELS = [
    "models_r/m1_stability.R", "models_r/m2_xwoba.R", "models_r/m4_framing.R",
    "models_r/m5_k_poisson.R", "models_r/m6_arsenal.R", "models_r/m7_babip_shrinkage.R",
    "models_r/m8_draft.R", "models_r/b1_pythagoras.R", "models_r/b2_count_value.R",
    "models_r/b3_aging.R", "models_r/b4_markov_sim.R", "models_r/b5_streaks.R",
    "models_r/game_model.R",
]
PY_MODELS = [f"models_py/{Path(m).stem}.py" for m in R_MODELS]
INGEST_SCRIPTS = [
    "ingest/pull_chadwick.py", "ingest/pull_statsapi.py", "ingest/pull_savant.py",
    "ingest/pull_people.py", "ingest/pull_draft.py", "ingest/pull_odds.py",
]


class StageError(RuntimeError):
    """A pipeline stage exited non-zero (or a required tool was missing)."""


def _log(msg: str) -> None:
    print(f"[pipeline] {msg}", flush=True)


def seasons() -> list[int]:
    raw = os.getenv("MLB_SEASONS", "2023,2024,2025")
    return [int(s) for s in raw.split(",") if s.strip()]


def find_rscript() -> str:
    exe = shutil.which("Rscript")
    if exe:
        return exe
    # Windows: R installs to C:\Program Files\R\R-x.y.z\bin\Rscript.exe (not always on PATH).
    cands = sorted(glob.glob(r"C:\Program Files\R\R-*\bin\Rscript.exe"), reverse=True)
    if cands:
        return cands[0]
    raise StageError("Rscript not found — install R or add it to PATH.")


def run_cmd(cmd: list[str], env: dict | None = None) -> None:
    """Run a subprocess from the repo root; raise StageError on non-zero exit."""
    _log("$ " + " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=REPO_ROOT, env={**os.environ, **(env or {})})
    if result.returncode != 0:
        joined = " ".join(map(str, cmd))
        raise StageError(f"stage command failed (exit {result.returncode}): {joined}")


def run_scripts(scripts: list[str], runner: list[str], env: dict | None = None) -> None:
    """Run each script that exists; loudly skip ones not present (phased-build tolerance)."""
    for s in scripts:
        if (REPO_ROOT / s).exists():
            run_cmd([*runner, s], env=env)
        else:
            _log(f"skip (not present): {s}")


def dbt(*args: str) -> list[str]:
    return ["uv", "run", "dbt", *args, "--project-dir", "dbt", "--profiles-dir", "dbt"]


# ---------------------------------------------------------------- stages
def ingest(season: str | None = None) -> None:
    """statsapi + Savant + Chadwick + people + draft + odds -> data/bronze/ (throttled, cached)."""
    env = {"MLB_SEASONS": season} if season else None
    run_scripts(INGEST_SCRIPTS, runner=["uv", "run", "python"], env=env)


def land() -> None:
    """Load bronze Parquet into DuckDB bronze.* (all MLBAM ids typed BIGINT)."""
    run_scripts(["ingest/land.py"], runner=["uv", "run", "python"])


def build() -> None:
    """dbt: staging -> SCD2 snapshots -> silver -> gold (+ tests)."""
    if not (REPO_ROOT / "dbt" / "dbt_project.yml").exists():
        _log("skip: dbt project not present")
        return
    run_cmd(dbt("deps"))
    run_cmd(dbt("run", "--select", "staging"))
    run_cmd(dbt("build"))
    # Snapshot the FROZEN dbt-test results so the dashboard's test tally survives a later live
    # `dbt run` (which overwrites target/run_results.json with the live, test-free results).
    import shutil
    rr = REPO_ROOT / "dbt" / "target" / "run_results.json"
    if rr.exists():
        dest = REPO_ROOT / "data" / "results"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(rr, dest / "frozen_run_results.json")


def export() -> None:
    """Export gold/silver model feeds to data/gold/*.parquet."""
    run_scripts(["ingest/export_feeds.py"], runner=["uv", "run", "python"])


def models() -> None:
    """Run the 13 models in R -> data/results/."""
    run_scripts(R_MODELS, runner=[find_rscript()])


def parity() -> None:
    """Python parity fits, then load_results with the three-tier parity GATE."""
    py = ["uv", "run", "python"]
    run_scripts(PY_MODELS, runner=py)
    run_scripts(["parity/load_results.py"], runner=py)  # parity GATE


def live_build() -> None:
    """Build the LIVE current-season warehouse (2026) into a SEPARATE DuckDB
    (MLB_LIVE_DUCKDB_PATH) — land all bronze, then dbt-run scoped to the live season via the
    analysis_seasons override. The frozen 2023-2025 warehouse is never touched."""
    live_db = os.getenv("MLB_LIVE_DUCKDB_PATH", "data/warehouse_live.duckdb")
    live_season = os.getenv("MLB_LIVE_SEASON", "2026")
    env = {"MLB_DUCKDB_PATH": live_db}
    run_scripts(["ingest/land.py"], runner=["uv", "run", "python"], env=env)
    run_cmd(dbt("run", "--vars", f"{{analysis_seasons: [{live_season}]}}"), env=env)


def dashboard() -> None:
    """Pre-render (DuckDB -> JSON) + season sim + live 2026 sim, then build the static site."""
    run_scripts(
        ["dashboard/prepare_dashboard_data.py", "dashboard/season_sim.py",
         "dashboard/live_sim.py", "dashboard/build_site.py"], runner=["uv", "run", "python"],
    )


def determinism() -> str:
    """Rebuild-determinism GATE: build gold_team_form twice, assert byte-identical. Returns the
    signature hash. Raises StageError on mismatch."""
    import duckdb

    db = os.getenv("MLB_DUCKDB_PATH", "data/warehouse.duckdb")
    sig_sql = (
        "SELECT md5(string_agg(rs, '' ORDER BY game_pk, team_id)) FROM ("
        "SELECT game_pk, team_id, md5(concat_ws('|', game_pk, team_id, game_seq, prior_games, "
        "roll_runs_for, roll_runs_against, roll_win_pct, roll_off_run_value, roll_def_run_value"
        ")) rs FROM gold.gold_team_form) t"
    )

    def signature() -> str:
        con = duckdb.connect(db, read_only=True)
        try:
            return con.execute(sig_sql).fetchone()[0]
        finally:
            con.close()

    run_cmd(dbt("run", "--select", "gold_team_form"))
    s1 = signature()
    run_cmd(dbt("run", "--select", "gold_team_form"))
    s2 = signature()
    if s1 != s2:
        raise StageError(f"determinism GATE failed — feed differs across rebuilds:\n  {s1}\n  {s2}")
    _log(f"determinism GATE passed - byte-identical ({s1[:12]}).")
    return s1


def full_run(season: str | None = None) -> None:
    """The seven build stages, in order."""
    ingest(season)
    land()
    build()
    export()
    models()
    parity()
    dashboard()
