"""Dashboard pre-render (Python): read the DuckDB warehouse + parity results, write one JSON the
static pages consume. Python owns all DuckDB I/O (the polyglot contract); the pages are plain
HTML/JS with no R dependency. Writes data/dashboard/site_data.json.

Everything here is a Python-only ROLLUP of the already-parity-gated warehouse + models (the same
precedent as the season simulator) — it introduces no new statistical estimation, so it is not
itself re-gated. See DECISIONS.md.

Sections: meta, provenance, dq, teams (record + run env + Pythagorean luck), metrics, glossary
(stat distributions), calibration (game-model reliability), stability (YoY skill vs. luck),
h2h (head-to-head season series), funfacts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "dashboard"
DB = os.getenv("MLB_DUCKDB_PATH", str(REPO / "data" / "warehouse.duckdb"))
GOLD = os.getenv("MLB_GOLD_DIR", str(REPO / "data" / "gold"))
RESULTS = REPO / "data" / "results"
# Prefer the FROZEN snapshot saved by the build stage (target/run_results.json gets overwritten by
# the live `dbt run`, which has no tests). Fall back to the live target for a standalone build.
_FROZEN_RR = REPO / "data" / "results" / "frozen_run_results.json"
RUN_RESULTS = _FROZEN_RR if _FROZEN_RR.exists() else REPO / "dbt" / "target" / "run_results.json"
SIM_SEED = 777  # season_sim.py fixed seed, surfaced in the provenance strip


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


def _pythag_exp(metrics: dict) -> float:
    """The Pythagorean exponent we FIT from our own data (B1). Used site-wide for consistency
    (was a hardcoded 1.83); B1 fits ~1.73 on 2023-2025, and using the fitted value is on-brand."""
    try:
        return float(metrics["b1_pythagoras"]["python"]["pythag_exponent"])
    except (KeyError, TypeError):
        return 1.83


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB, read_only=True)

    mfile = RESULTS / "metrics.json"
    metrics = json.loads(mfile.read_text()) if mfile.exists() else {}
    e = _pythag_exp(metrics)

    # --- meta + provenance (data-derived so docs/ rebuilds stay byte-identical) ---
    n_pa = con.execute("select count(*) from gold.fct_plate_appearance").fetchone()[0]
    n_games = con.execute("select count(*) from gold.fct_game").fetchone()[0]
    seasons = [r[0] for r in con.execute(
        "select distinct season from gold.fct_game order by 1").fetchall()]
    through = str(con.execute(
        "select max(game_date) from gold.fct_game where game_type='R'").fetchone()[0])
    # Scope the pitch count to the frozen analysis seasons (gold's seasons) — bronze.statcast also
    # holds the live current season, which must not inflate the retrospective totals.
    n_pitches = con.execute(
        "select count(*) from bronze.statcast where game_year in "
        "(select distinct season from gold.fct_game)").fetchone()[0]
    meta = {"seasons": seasons, "n_pa": n_pa, "n_games": n_games, "n_pitches": n_pitches}
    provenance = {"seasons": seasons, "through": through, "seed": SIM_SEED,
                  "pythag_exp": round(e, 3)}

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

    # --- teams: record + run environment + Pythagorean luck (W - pythW) ---
    teams = con.execute(f"""
        select t.team_id, t.team_name, s.season, s.games, s.w, s.l, s.rs, s.ra,
               round(s.w::double/(s.w+s.l), 3) as win_pct,
               round(pow(s.rs,{e})/(pow(s.rs,{e})+pow(s.ra,{e})), 3) as pyth,
               round(s.games * pow(s.rs,{e})/(pow(s.rs,{e})+pow(s.ra,{e})), 1) as pyth_w,
               round(s.w - s.games * pow(s.rs,{e})/(pow(s.rs,{e})+pow(s.ra,{e})), 1) as luck
        from gold.gold_team_season s join gold.dim_team t on t.team_id = s.team_id
        order by s.season, win_pct desc, t.team_id
    """).fetch_df().to_dict(orient="records")

    site = {"meta": meta, "provenance": provenance, "dq": dq, "teams": teams,
            "metrics": metrics, "glossary": _glossary(con),
            "calibration": _calibration(), "stability": _stability(con),
            "h2h": _h2h(con), "funfacts": _funfacts(con, e), "effects": _effects()}
    (OUT / "site_data.json").write_text(json.dumps(site, default=float))
    print(json.dumps({"stage": "dashboard", "event": "prepared", "tables": len(dq_tables),
                      "teams": len(teams), "models": len(metrics),
                      "calib_buckets": len(site["calibration"]["buckets"])}))
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


def _calibration() -> dict:
    """Game-model reliability: refit on 2023-24 (identical to the parity-gated model), predict the
    sealed 2025 season, and bucket by predicted probability. 5 EQUAL-COUNT (quantile) buckets, not
    equal-width — predictions cluster near .50 (a thin AUC~.55 edge), so equal-width buckets would
    be near-empty at the tails. n is shown per bucket. Python-only rollup (see module docstring)."""
    import pandas as pd
    import statsmodels.api as sm
    feat = ["off_rv_diff", "def_rv_diff", "win_pct_diff"]
    df = pd.read_parquet(f"{GOLD}/game_features.parquet")
    tr = df[df["season"].isin([2023, 2024])]
    te = df[df["season"] == 2025].copy()
    m = sm.GLM(tr["home_win"], sm.add_constant(tr[feat]), family=sm.families.Binomial()).fit()
    te["p"] = m.predict(sm.add_constant(te[feat]))
    te["bucket"] = pd.qcut(te["p"], 5, labels=False, duplicates="drop")
    buckets = []
    for _, g in te.groupby("bucket"):
        buckets.append({"p_mean": round(float(g["p"].mean()), 3),
                        "obs": round(float(g["home_win"].mean()), 3), "n": int(len(g))})
    acc = float(((te["p"] >= 0.5) == te["home_win"]).mean())
    return {"buckets": buckets, "accuracy": round(acc, 3),
            "base_home": round(float(te["home_win"].mean()), 3),
            "p_lo": round(float(te["p"].min()), 3), "p_hi": round(float(te["p"].max()), 3)}


def _effects() -> dict:
    """Effect-size numbers with uncertainty (Funder & Ozer 2019 framing): bootstrap CIs + concrete
    odds translations, so no finding is ever reported as bare r^2. Fixed seed -> reproducible."""
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    rng = np.random.default_rng(2026)
    # M8 draft: r + bootstrap CI + concordance (P a higher pick out-produces a lower pick)
    d = pd.read_parquet(f"{GOLD}/draft_production.parquet")
    pk, ops = d["pick"].to_numpy(), d["ops"].to_numpy()
    n8 = len(d)
    r8 = float(np.corrcoef(pk, ops)[0, 1])
    boot = [np.corrcoef(pk[i], ops[i])[0, 1]
            for i in (rng.integers(0, n8, n8) for _ in range(2000))]
    lo8, hi8 = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
    concord = float(0.5 + np.arcsin(-r8) / np.pi)   # earlier pick = lower number
    # game model: Brier improvement over home-field baseline + bootstrap CI
    feat = ["off_rv_diff", "def_rv_diff", "win_pct_diff"]
    g = pd.read_parquet(f"{GOLD}/game_features.parquet")
    tr = g[g["season"].isin([2023, 2024])]
    te = g[g["season"] == 2025].copy()
    m = sm.GLM(tr["home_win"], sm.add_constant(tr[feat]), family=sm.families.Binomial()).fit()
    p = m.predict(sm.add_constant(te[feat])).to_numpy()
    y = te["home_win"].to_numpy()
    base = float(tr["home_win"].mean())
    ng = len(y)
    deltas = []
    for _ in range(2000):
        idx = rng.integers(0, ng, ng)
        deltas.append(np.mean((base - y[idx]) ** 2) - np.mean((p[idx] - y[idx]) ** 2))
    dlo, dhi = (float(x) for x in np.percentile(deltas, [2.5, 97.5]))
    return {
        "m8": {"r": round(r8, 3), "ci": [round(lo8, 3), round(hi8, 3)], "n": n8,
               "concordance": round(concord * 100, 0)},
        "game": {"brier": round(float(np.mean((p - y) ** 2)), 4),
                 "brier_hfa": round(float(np.mean((base - y) ** 2)), 4),
                 "delta": round(float(np.mean((base - y) ** 2) - np.mean((p - y) ** 2)), 4),
                 "delta_ci": [round(dlo, 4), round(dhi, 4)],
                 "accuracy": round(float(((p >= 0.5) == y).mean()) * 100, 1),
                 "base_home": round(float(y.mean()) * 100, 1), "n_games": ng},
    }


def _stability(con) -> dict:
    """Year-over-year self-correlation per hitting stat (min 300 PA both years) — the evidence
    behind the glossary's 'stable skill' vs 'mostly luck' labels (M1/M7)."""
    out = {}
    for s in ("k_pct", "bb_pct", "babip", "ops"):
        r = con.execute(f"""
            with a as (select batter_id, season, {s} v from gold.gold_batter_season
                       where pa >= 300 and {s} is not null)
            select corr(a.v, b.v), count(*)
            from a join a b on b.batter_id = a.batter_id and b.season = a.season + 1
        """).fetchone()
        if r and r[0] is not None:
            out[s] = {"r": round(float(r[0]), 3), "n": int(r[1])}
    return out


def _h2h(con) -> dict:
    """Head-to-head regular-season series per team pair, nested {season: {'a-b': {aw, bw}}} where
    a < b by team_id. Only pairs that actually met appear (interleague pairs often don't)."""
    rows = con.execute("""
        select season,
               least(home_team_id, away_team_id)    as a,
               greatest(home_team_id, away_team_id) as b,
               sum(case when winner_team_id = least(home_team_id, away_team_id)
                        then 1 else 0 end) as aw,
               sum(case when winner_team_id = greatest(home_team_id, away_team_id)
                        then 1 else 0 end) as bw
        from gold.fct_game
        where game_type = 'R' and winner_team_id is not null
        group by 1, 2, 3
        order by 1, 2, 3
    """).fetchall()
    d: dict = {}
    for season, a, b, aw, bw in rows:
        d.setdefault(str(season), {})[f"{int(a)}-{int(b)}"] = {"aw": int(aw), "bw": int(bw)}
    return d


def _funfacts(con, e: float) -> list:
    """3-4 plain-English one-liners mined from the data, each with the number that makes it true."""
    facts = []
    hi_babip = con.execute("""
        select c.first_name||' '||c.last_name, b.babip, b.season from gold.gold_batter_season b
        join staging.stg_chadwick__players c on c.player_id = b.batter_id
        where b.pa >= 300 order by b.babip desc limit 1""").fetchone()
    facts.append(f"{hi_babip[0]} ran a {hi_babip[1]:.3f} BABIP in {hi_babip[2]} — the flukiest "
                 "batted-ball luck in the dataset. It almost never repeats.")
    luck = con.execute(f"""
        select t.team_name, s.season,
               round(s.w - s.games*pow(s.rs,{e})/(pow(s.rs,{e})+pow(s.ra,{e})), 1) lk
        from gold.gold_team_season s join gold.dim_team t on t.team_id = s.team_id
        order by lk desc limit 1""").fetchone()
    facts.append(f"The {luck[1]} {luck[0]} won {luck[2]:.0f} more games than their runs scored and "
                 "allowed say they should have — the biggest overachievement in the dataset.")
    snake = con.execute(f"""
        select t.team_name, s.season,
               round(s.w - s.games*pow(s.rs,{e})/(pow(s.rs,{e})+pow(s.ra,{e})), 1) lk
        from gold.gold_team_season s join gold.dim_team t on t.team_id = s.team_id
        order by lk asc limit 1""").fetchone()
    facts.append(f"The {snake[1]} {snake[0]} won {abs(snake[2]):.0f} FEWER games than their run "
                 "totals earned — the most snakebitten season here.")
    hi_ops = con.execute("""
        select c.first_name||' '||c.last_name, b.ops, b.season from gold.gold_batter_season b
        join staging.stg_chadwick__players c on c.player_id = b.batter_id
        where b.pa >= 300 order by b.ops desc limit 1""").fetchone()
    facts.append(f"{hi_ops[0]}'s {hi_ops[1]:.3f} OPS in {hi_ops[2]} is the best full-season "
                 "hitting line in the dataset.")
    return facts


if __name__ == "__main__":
    main()
