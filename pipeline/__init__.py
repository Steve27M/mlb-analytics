"""Pipeline package: the single implementation of each build stage.

`run.py` (Typer CLI) and the Dagster assets are both thin wrappers over `pipeline.stages` — there is
exactly one implementation per stage, so the CLI and the scheduled pipeline can never drift.
"""
