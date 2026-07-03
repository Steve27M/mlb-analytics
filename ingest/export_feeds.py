"""Export gold model-input feeds to data/gold/*.parquet — the ONLY R<->Python interface.

Python owns all DuckDB/Parquet I/O (the polyglot contract): this writes the flat feeds that
both the R models (models_r/) and the Python parity fits (models_py/) read. Gold is
deterministic, so the feeds are byte-identical across rebuilds.
"""
from __future__ import annotations

import os

import duckdb

from _common import log

# feed name -> gold table
FEEDS = {
    "batter_season": "gold.gold_batter_season",
    "batted_balls": "gold.gold_batted_balls",
    "called_pitches": "gold.gold_called_pitches",
    "pitcher_start": "gold.gold_pitcher_start",
    "pitcher_arsenal": "gold.gold_pitcher_arsenal",
    "team_season": "gold.gold_team_season",
    "count_pitches": "gold.gold_count_pitches",
    "batter_games": "gold.gold_batter_games",
    "game_features": "gold.gold_game_features",
    "player_age": "gold.gold_player_age",
    "pa_transitions": "gold.gold_pa_transitions",
    "draft_production": "gold.gold_draft_production",
    "run_expectancy": "gold.gold_run_expectancy",
    "team_form": "gold.gold_team_form",
}


def main() -> None:
    db = os.getenv("MLB_DUCKDB_PATH", "data/warehouse.duckdb")
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    os.makedirs(gold, exist_ok=True)
    con = duckdb.connect(db, read_only=True)
    try:
        for name, tbl in FEEDS.items():
            out = f"{gold}/{name}.parquet".replace("\\", "/")
            con.execute(f"COPY (SELECT * FROM {tbl}) TO '{out}' (FORMAT parquet)")
            rows = con.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
            log("export", name, event="wrote", rows=rows, path=out)
    finally:
        con.close()


if __name__ == "__main__":
    main()
