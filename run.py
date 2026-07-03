#!/usr/bin/env python
"""Polyglot MLB pipeline orchestrator.

Sequences the whole build as SUBPROCESS stages; a non-zero exit aborts the run (clean
failure handling). R and Python share state ONLY through flat files + the DuckDB warehouse,
never in-memory — kill any stage and the pipeline fails cleanly.

    ingest (Python)    statsapi + Savant + Chadwick + odds -> data/bronze/ (throttled, cached)
    land   (Python)    bronze Parquet -> DuckDB bronze.* (typed on load, BIGINT ids)
    build  (dbt)       staging -> snapshots(SCD2, date-by-date) -> silver -> gold (+ tests)
    export (Python)    gold/silver -> data/gold/*.parquet (model feeds)
    models (R)         M1-M8 + B1-B5 + game win-prob model -> data/results/
    parity (Python)    Python parity fits + market eval + load_results (parity GATE)
    dashboard (Python) DuckDB pre-render + season sim -> static DIAMONDIQ site in docs/

    uv run python run.py                       # full pipeline
    uv run python run.py build                 # one stage
    uv run python run.py backfill --season 2022

Phase 6 portability: stages read config from env vars only; no absolute local paths.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console

REPO_ROOT = Path(__file__).resolve().parent
console = Console()
app = typer.Typer(add_completion=False, help=__doc__)


def _seasons() -> list[int]:
    raw = os.getenv("MLB_SEASONS", "2023,2024,2025")
    return [int(s) for s in raw.split(",") if s.strip()]


def _find_rscript() -> str:
    exe = shutil.which("Rscript")
    if exe:
        return exe
    # Windows: R installs to C:\Program Files\R\R-x.y.z\bin\Rscript.exe (not always on PATH).
    cands = sorted(glob.glob(r"C:\Program Files\R\R-*\bin\Rscript.exe"), reverse=True)
    if cands:
        return cands[0]
    console.print("[red]Rscript not found — install R or add it to PATH.[/red]")
    raise typer.Exit(1)


def _find_quarto() -> str:
    exe = shutil.which("quarto")
    if exe:
        return exe
    cands = (glob.glob(r"C:\Program Files\Quarto\bin\quarto.cmd")
             + glob.glob(r"C:\Program Files\Quarto\bin\quarto.exe"))
    if cands:
        return cands[0]
    console.print("[red]quarto not found — install Quarto or add it to PATH.[/red]")
    raise typer.Exit(1)


def _run(cmd: list[str], env: dict | None = None) -> None:
    console.rule(f"[bold cyan]{' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=REPO_ROOT, env={**os.environ, **(env or {})})
    if result.returncode != 0:
        console.print(f"[red]Stage failed (exit {result.returncode}). Aborting pipeline.[/red]")
        raise typer.Exit(result.returncode)


def _run_scripts(scripts: list[str], runner: list[str]) -> None:
    """Run each script that exists; loudly skip ones not yet implemented (phased build)."""
    for s in scripts:
        if (REPO_ROOT / s).exists():
            _run([*runner, s])
        else:
            console.print(f"[yellow]skip (not yet implemented): {s}[/yellow]")


def _dbt(*args: str) -> list[str]:
    return ["uv", "run", "dbt", *args, "--project-dir", "dbt", "--profiles-dir", "dbt"]


@app.command()
def ingest(season: str = typer.Option(None, help="Override MLB_SEASONS, e.g. '2024'.")) -> None:
    """statsapi + Savant + Chadwick + odds -> data/bronze/ (throttled, cached, idempotent)."""
    env = {"MLB_SEASONS": season} if season else {}
    py = ["uv", "run", "python"]
    # Chadwick crosswalk first — it seeds dim_player_xref and prevents silent join loss later.
    scripts = [
        "ingest/pull_chadwick.py",
        "ingest/pull_statsapi.py",
        "ingest/pull_savant.py",
        "ingest/pull_odds.py",
    ]
    for s in scripts:
        if (REPO_ROOT / s).exists():
            _run([*py, s], env=env)
        else:
            console.print(f"[yellow]skip (not yet implemented): {s}[/yellow]")


@app.command()
def land() -> None:
    """Load bronze Parquet into DuckDB bronze.* (all MLBAM ids typed BIGINT)."""
    _run_scripts(["ingest/land.py"], runner=["uv", "run", "python"])


@app.command()
def build() -> None:
    """dbt: staging -> SCD2 snapshots (date-by-date) -> silver -> gold (+ tests, freshness)."""
    if not (REPO_ROOT / "dbt" / "dbt_project.yml").exists():
        console.print("[yellow]skip: dbt project not yet created (Phase 2).[/yellow]")
        return
    _run(_dbt("deps"))
    _run(_dbt("run", "--select", "staging"))
    # dim_player SCD2: replay the snapshot date-by-date so trade-deadline moves land as
    # correctly-bounded validity ranges (season-by-season would collapse midseason trades).
    # Snapshot-date driver is implemented in Phase 2; wired here for the full-run path.
    _run(_dbt("build"))


@app.command()
def export() -> None:
    """Export gold/silver model feeds to data/gold/*.parquet (byte-identical across rebuilds)."""
    _run_scripts(["ingest/export_feeds.py"], runner=["uv", "run", "python"])


@app.command()
def models() -> None:
    """Run the book's models (M1-M8, B1-B5, game win-prob) in R -> data/results/."""
    scripts = [
        "models_r/m1_stability.R",       # M1 skill-vs-noise stability
        "models_r/m2_xwoba.R",           # M2/M3 xwOBA-over-expected (lm)
        "models_r/m4_framing.R",         # M4 called-strike prob / framing (glm binomial)
        "models_r/m5_k_poisson.R",       # M5 strikeout counts (Poisson)
        "models_r/m6_arsenal.R",         # M6 pitcher-arsenal archetypes (PCA + cluster)
        "models_r/m7_babip_shrinkage.R", # M7 BABIP multilevel shrinkage (lme4)
        "models_r/m8_draft.R",           # M8 draft position vs production (ethical scrape)
        "models_r/b1_pythagoras.R",      # B1 Pythagorean expectation
        "models_r/b2_count_value.R",     # B2 run value by count
        "models_r/b3_aging.R",           # B3 aging curves
        "models_r/b4_markov_sim.R",      # B4 Markov half-inning + Bradley-Terry sim
        "models_r/b5_streaks.R",         # B5 streak/permutation tests
        "models_r/game_model.R",         # win-prob model (sealed 2025 holdout)
    ]
    _run_scripts(scripts, runner=[_find_rscript()])


@app.command()
def parity() -> None:
    """Python parity fits + market eval, then load_results with the three-tier parity GATE."""
    py = ["uv", "run", "python"]
    _run_scripts([
        "models_py/m1_stability.py", "models_py/m2_xwoba.py", "models_py/m4_framing.py",
        "models_py/m5_k_poisson.py", "models_py/m6_arsenal.py", "models_py/m7_babip_shrinkage.py",
        "models_py/m8_draft.py", "models_py/b1_pythagoras.py", "models_py/b2_count_value.py",
        "models_py/b3_aging.py", "models_py/b4_markov_sim.py", "models_py/b5_streaks.py",
        "models_py/game_model.py",
    ], runner=py)
    _run_scripts(["parity/load_results.py"], runner=py)  # parity GATE


@app.command()
def dashboard() -> None:
    """Python pre-render (DuckDB -> site_data.json), build the static DIAMONDIQ site into docs/."""
    py = ["uv", "run", "python"]
    _run_scripts(
        ["dashboard/prepare_dashboard_data.py", "dashboard/season_sim.py",
         "dashboard/build_site.py"], runner=py
    )


@app.command()
def backfill(season: int = typer.Option(..., help="Prior season to pull, e.g. 2022.")) -> None:
    """Bounded historical bronze pull for a single prior season."""
    ingest(season=str(season))


@app.command()
def determinism() -> None:
    """Rebuild-determinism GATE: build the rolling-form feed twice, assert byte-identical content.

    Guards against a non-total window order or float non-determinism silently changing features.
    """
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

    _run(_dbt("run", "--select", "gold_team_form"))
    s1 = signature()
    _run(_dbt("run", "--select", "gold_team_form"))
    s2 = signature()
    if s1 != s2:
        console.print("[red]Determinism GATE FAILED - feed differs across rebuilds:[/red]")
        console.print(f"[red]  {s1}\n  {s2}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Determinism GATE passed - byte-identical ({s1[:12]}).[/green]")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context,
         season: str = typer.Option(None, help="Season(s) for a full run, e.g. '2024'.")) -> None:
    """With no subcommand, run the whole pipeline end-to-end."""
    if ctx.invoked_subcommand is not None:
        return
    ingest(season=season)
    land()
    build()
    export()
    models()
    parity()
    dashboard()
    console.print("[bold green]Pipeline complete.[/bold green]")


if __name__ == "__main__":
    app()
