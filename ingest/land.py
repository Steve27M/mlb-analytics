"""Land bronze Parquet into DuckDB bronze.* tables (Python owns all DuckDB/Parquet I/O).

MLBAM ids are already BIGINT in the Parquet (cast at write); DuckDB preserves them on load.
One table per source; statcast asserts pitch_key uniqueness at load and fails loudly.
Config via env (MLB_DUCKDB_PATH, MLB_BRONZE_DIR) — Phase 6 lifts this to DuckDB-over-S3.
"""
from __future__ import annotations

import glob
import os

import duckdb

from _common import bronze_dir, log

# table name -> partition glob (relative to bronze dir)
TABLES = {
    "chadwick_register": "chadwick/*/data.parquet",
    "people": "people/*/data.parquet",
    "draft": "draft/*/data.parquet",
    "statcast": "statcast/*/data.parquet",
    "statsapi_schedule": "statsapi_schedule/*/data.parquet",
    "statsapi_boxscore": "statsapi_boxscore/*/data.parquet",
    "odds": "odds/*/data.parquet",  # empty until a free ODDS_API_KEY is set
}


def main() -> None:
    db = os.getenv("MLB_DUCKDB_PATH", "data/warehouse.duckdb")
    bd = bronze_dir().as_posix()
    con = duckdb.connect(db)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    for tbl, pat in TABLES.items():
        gpat = f"{bd}/{pat}"
        if not glob.glob(gpat):
            log("land", tbl, event="skip", reason="no partitions")
            continue
        con.execute(
            f"CREATE OR REPLACE TABLE bronze.{tbl} AS "
            f"SELECT * FROM read_parquet('{gpat}', union_by_name=true)"
        )
        n = con.execute(f"SELECT count(*) FROM bronze.{tbl}").fetchone()[0]
        log("land", tbl, event="loaded", rows=n)

    # Load-time invariant: pitch grain is unique.
    rows, keys = con.execute(
        "SELECT count(*), count(DISTINCT pitch_key) FROM bronze.statcast"
    ).fetchone()
    if rows != keys:
        raise AssertionError(f"pitch_key not unique in bronze.statcast: {rows} rows, {keys} keys")
    log("land", "statcast", event="key_check", rows=rows, unique=True)
    con.close()


if __name__ == "__main__":
    main()
