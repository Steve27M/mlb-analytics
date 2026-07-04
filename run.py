#!/usr/bin/env python
"""Polyglot MLB pipeline orchestrator (Typer CLI).

Thin wrapper over `pipeline.stages` — the CLI and the Dagster assets (Phase 2) call the SAME stage
functions, so behavior can never drift (FEEDBACK §10.1). Each stage runs as subprocesses and aborts
the run on a non-zero exit. R and Python share state ONLY through flat files + the DuckDB warehouse.

    ingest (Python)    statsapi + Savant + Chadwick + people + draft + odds -> data/bronze/
    land   (Python)    bronze Parquet -> DuckDB bronze.* (BIGINT ids)
    build  (dbt)       staging -> SCD2 snapshots -> silver -> gold (+ tests)
    export (Python)    gold/silver -> data/gold/*.parquet (model feeds)
    models (R)         M1-M8 + B1-B5 + game win-prob -> data/results/
    parity (Python)    Python parity fits + load_results (parity GATE)
    dashboard (Python) DuckDB pre-render + season sim -> static DIAMONDIQ site in docs/

    uv run python run.py                       # full pipeline
    uv run python run.py build                 # one stage
    uv run python run.py backfill --season 2022

Config via env vars only; no absolute local paths.
"""
from __future__ import annotations

import typer
from rich.console import Console

from pipeline import stages

console = Console()
app = typer.Typer(add_completion=False, help=__doc__)


def _stage(fn, *args, **kwargs):
    """Run a stage function, converting a StageError into a clean non-zero CLI exit."""
    try:
        return fn(*args, **kwargs)
    except stages.StageError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def ingest(season: str = typer.Option(None, help="Override MLB_SEASONS, e.g. '2024'.")) -> None:
    """statsapi + Savant + Chadwick + people + draft + odds -> data/bronze/ (cached, idempotent)."""
    _stage(stages.ingest, season)


@app.command()
def land() -> None:
    """Load bronze Parquet into DuckDB bronze.* (all MLBAM ids typed BIGINT)."""
    _stage(stages.land)


@app.command()
def build() -> None:
    """dbt: staging -> SCD2 snapshots -> silver -> gold (+ tests, freshness)."""
    _stage(stages.build)


@app.command()
def export() -> None:
    """Export gold/silver model feeds to data/gold/*.parquet (byte-identical across rebuilds)."""
    _stage(stages.export)


@app.command()
def models() -> None:
    """Run the book's models (M1-M8, B1-B5, game win-prob) in R -> data/results/."""
    _stage(stages.models)


@app.command()
def parity() -> None:
    """Python parity fits, then load_results with the three-tier parity GATE."""
    _stage(stages.parity)


@app.command()
def live() -> None:
    """Build the LIVE current-season (2026) warehouse into a separate DuckDB (frozen untouched)."""
    _stage(stages.live_build)


@app.command()
def dashboard() -> None:
    """Python pre-render (DuckDB -> site_data.json), build the static DIAMONDIQ site into docs/."""
    _stage(stages.dashboard)


@app.command()
def backfill(season: int = typer.Option(..., help="Prior season to pull, e.g. 2022.")) -> None:
    """Bounded historical bronze pull for a single prior season."""
    _stage(stages.ingest, str(season))


@app.command()
def determinism() -> None:
    """Rebuild-determinism GATE: build the rolling-form feed twice; assert byte-identical."""
    _stage(stages.determinism)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context,
         season: str = typer.Option(None, help="Season(s) for a full run, e.g. '2024'.")) -> None:
    """With no subcommand, run the whole pipeline end-to-end."""
    if ctx.invoked_subcommand is not None:
        return
    _stage(stages.full_run, season)
    console.print("[bold green]Pipeline complete.[/bold green]")


if __name__ == "__main__":
    app()
