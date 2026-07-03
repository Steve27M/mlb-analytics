"""Dashboard pre-render (Python): read the DuckDB warehouse + parity results, write one JSON the
static pages consume. Python owns all DuckDB I/O (the polyglot contract); the pages are plain
HTML/JS with no R dependency. Writes data/dashboard/site_data.json.

Sections: meta, dq (data quality), models (13 models + KAT status from metrics.json), teams
(per-team-season record + run environment), glossary (stat distributions).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "dashboard"
DB = os.getenv("MLB_DUCKDB_PATH", str(REPO / "data" / "warehouse.duckdb"))
RESULTS = REPO / "data" / "results"
RUN_RESULTS = REPO / "dbt" / "target" / "run_results.json"
PYTHAG_EXP = 1.83


def _dist_from_rows(con, sql, dec=3):
    """min/median/max + named leader/trailer from a SELECT of (label, value) rows."""
    import statistics
    rows = [(lab, v) for lab, v in con.execute(sql).fetchall() if v is not None]
    vals = sorted(v for _, v in rows)
    lo = min(rows, key=lambda x: x[1])
    hi = max(rows, key=lambda x: x[1])
    return {"min": round(vals[0], dec), "med": round(statistics.median(vals), dec),
            "max": round(vals[-1], dec),
            "lo": {"abbr": str(lo[0]), "val": round(lo[1], dec)},
            "hi": {"abbr": str(hi[0]), "val": round(hi[1], dec)}}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB, read_only=True)

    # --- meta ---
    n_pitch = con.execute("select count(*) from gold.fct_plate_appearance").fetchone()[0]
    n_games = con.execute("select count(*) from gold.fct_game").fetchone()[0]
    seasons = [r[0] for r in con.execute(
        "select distinct season from gold.fct_game order by 1").fetchall()]
    meta = {"seasons": seasons, "n_pa": n_pitch, "n_games": n_games,
            "n_pitches": con.execute("select count(*) from bronze.statcast").fetchone()[0]}

    # --- data quality: table row counts by layer + dbt test tally ---
    layers = con.execute("""
        select table_schema layer, table_name from information_schema.tables
        where table_schema in ('staging','silver','gold') order by table_schema, table_name
    """).fetchall()
    dq_tables = []
    for layer, tbl in layers:
        n = con.execute(f'select count(*) from "{layer}"."{tbl}"').fetchone()[0]
        dq_tables.append({"layer": layer, "table": tbl, "rows": n})
    tests = {"pass": 0, "warn": 0, "fail": 0}
    if RUN_RESULTS.exists():
        rr = json.loads(RUN_RESULTS.read_text())
        for res in rr.get("results", []):
            if res.get("unique_id", "").startswith("test."):
                st = res.get("status", "")
                tests["pass" if st == "pass" else "warn" if st == "warn" else "fail"] += 1
    dq = {"tables": dq_tables, "tests": tests}

    # --- teams: per-team-season record + run environment (+ Pythagorean win %) ---
    e = PYTHAG_EXP
    teams = con.execute(f"""
        select t.team_name, s.season, s.w, s.l, s.rs, s.ra,
               round(s.w::double/(s.w+s.l), 3) as win_pct,
               round(pow(s.rs,{e})/(pow(s.rs,{e})+pow(s.ra,{e})), 3) as pyth
        from gold.gold_team_season s join gold.dim_team t on t.team_id = s.team_id
        order by s.season, win_pct desc
    """).fetch_df().to_dict(orient="records")

    # --- models: parity + KAT status from metrics.json ---
    mfile = RESULTS / "metrics.json"
    metrics = json.loads(mfile.read_text()) if mfile.exists() else {}

    site = {"meta": meta, "dq": dq, "teams": teams, "metrics": metrics,
            "glossary": _glossary(con)}
    (OUT / "site_data.json").write_text(json.dumps(site, default=float))
    print(json.dumps({"stage": "dashboard", "event": "prepared",
                      "tables": len(dq_tables), "teams": len(teams), "models": len(metrics)}))
    con.close()


def _glossary(con) -> dict:
    """Stat distributions (named leader/trailer) from the warehouse, for the dictionary."""
    def bat(col):
        return _dist_from_rows(con, f"""
            select c.first_name || ' ' || c.last_name, b.{col}
            from gold.gold_batter_season b
            join staging.stg_chadwick__players c on c.player_id = b.batter_id
            where b.pa >= 300 and b.{col} is not null""")

    def team(expr):
        return _dist_from_rows(con, f"""
            select t.team_name, {expr}
            from gold.gold_team_season s join gold.dim_team t on t.team_id = s.team_id""")

    return {
        "k_pct": bat("k_pct"), "bb_pct": bat("bb_pct"), "babip": bat("babip"), "ops": bat("ops"),
        "win_pct": team("s.w::double / (s.w + s.l)"),
    }


if __name__ == "__main__":
    main()
