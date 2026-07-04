"""Live 2026 season simulator (playoff odds) — the live counterpart to season_sim.py.

season_sim.py simulates a COMPLETE season (all games have leakage-safe features) for the sealed
2025 evaluation. This one is for the IN-PROGRESS 2026 season: take the CURRENT standings, predict
each REMAINING scheduled game with the FROZEN game model (trained on 2023-24, never retrained) using
each team's current rolling form, and Monte-Carlo the rest of the season into playoff odds.

Frozen/live split: the model coefficients are refit from the FROZEN feed (data/gold/game_features
= 2023-2025); the live 2026 standings / current form / remaining schedule come from the separate
LIVE warehouse (MLB_LIVE_DUCKDB_PATH). The frozen analysis is never touched.

Writes data/dashboard/live_sim.json. Fixed seed -> reproducible. Descriptive playoff projection
(aggregate season odds), not game-level picks.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "dashboard"
GOLD = os.getenv("MLB_GOLD_DIR", str(REPO / "data" / "gold"))          # frozen feeds (model refit)
LIVE_DB = os.getenv("MLB_LIVE_DUCKDB_PATH", str(REPO / "data" / "warehouse_live.duckdb"))
REF = REPO / "reference" / "team_divisions.csv"
FEATURES = ["off_rv_diff", "def_rv_diff", "win_pct_diff"]
N_SIM = 10000
SEED = 777
LIVE_SEASON = 2026


def _frozen_coefs() -> np.ndarray:
    """Refit the frozen game model on 2023-24 (identical to the parity-gated model)."""
    df = pd.read_parquet(f"{GOLD}/game_features.parquet")
    tr = df[df["season"].isin([2023, 2024])]
    m = sm.GLM(tr["home_win"].to_numpy(), sm.add_constant(tr[FEATURES].to_numpy()),
               family=sm.families.Binomial()).fit()
    return np.asarray(m.params)  # [const, off, def, win]


def main() -> None:
    if not Path(LIVE_DB).exists():
        print(json.dumps({"stage": "live_sim", "event": "skip",
                          "reason": f"no live warehouse at {LIVE_DB} (run `run.py live` first)"}))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    ref = pd.read_csv(REF)
    teams = ref["team_id"].to_numpy()
    pos = {int(t): i for i, t in enumerate(teams)}
    n_teams = len(teams)
    coefs = _frozen_coefs()

    con = duckdb.connect(LIVE_DB, read_only=True)
    # current standings (wins so far)
    stand = con.execute(f"""
        select team_id, w, l, games from gold.gold_team_season where season = {LIVE_SEASON}
    """).fetch_df()
    cur_w = np.zeros(n_teams)
    played = {}
    for r in stand.itertuples():
        cur_w[pos[int(r.team_id)]] = r.w
        played[int(r.team_id)] = (int(r.w), int(r.l))
    # each team's CURRENT rolling form (most recent game)
    form = con.execute("""
        select team_id, roll_off_run_value, roll_def_run_value, roll_win_pct from (
          select team_id, roll_off_run_value, roll_def_run_value, roll_win_pct,
                 row_number() over (partition by team_id
                     order by game_date desc, game_number desc, game_pk desc) rn
          from gold.gold_team_form)
        where rn = 1
    """).fetch_df().set_index("team_id")
    # remaining schedule: scheduled games with no result yet
    rem = con.execute("""
        select s.home_id, s.away_id
        from staging.stg_statsapi__schedule s
        where s.game_type = 'R'
          and s.game_pk not in (select game_pk from gold.fct_game where winner_team_id is not null)
        order by s.game_pk
    """).fetch_df()
    con.close()

    # predict each remaining game with the frozen model on current form
    def form_of(tid):
        f = form.loc[tid]
        return f["roll_off_run_value"], f["roll_def_run_value"], f["roll_win_pct"]

    hi, ai, p = [], [], []
    for r in rem.itertuples():
        h, a = int(r.home_id), int(r.away_id)
        if h not in pos or a not in pos or h not in form.index or a not in form.index:
            continue
        ho, hd, hw = form_of(h)
        ao, ad, aw = form_of(a)
        x = np.array([1.0, ho - ao, hd - ad, hw - aw])
        p_home = 1.0 / (1.0 + np.exp(-float(coefs @ x)))
        hi.append(pos[h])
        ai.append(pos[a])
        p.append(p_home)
    hi, ai, p = np.array(hi), np.array(ai), np.array(p)
    n_rem = len(p)

    # Monte-Carlo the remaining schedule on top of current wins
    rng = np.random.default_rng(SEED)
    home_win = rng.random((N_SIM, n_rem)) < p
    wins = np.tile(cur_w, (N_SIM, 1)).astype(float)
    np.add.at(wins.T, hi, home_win.T)
    np.add.at(wins.T, ai, (~home_win).T)

    playoff, divwin = _playoff_odds(ref, pos, wins, n_teams, N_SIM)

    proj = wins.mean(axis=0)
    p10 = np.percentile(wins, 10, axis=0)
    p90 = np.percentile(wins, 90, axis=0)
    rows = []
    for t in teams:
        i, tid = pos[int(t)], int(t)
        rr = ref[ref.team_id == tid].iloc[0]
        w, losses = played.get(tid, (0, 0))
        rows.append({
            "team_id": tid, "abbr": rr["team_abbr"], "league": rr["league"],
            "division": rr["division"],
            "cur_w": w, "cur_l": losses, "proj_wins": round(float(proj[i]), 1),
            "p10": round(float(p10[i]), 1), "p90": round(float(p90[i]), 1),
            "playoff_odds": round(float(playoff[i] / N_SIM), 3),
            "div_odds": round(float(divwin[i] / N_SIM), 3),
        })
    rows.sort(key=lambda x: -x["playoff_odds"])
    payload = {"n_sim": N_SIM, "seed": SEED, "season": LIVE_SEASON, "n_remaining": int(n_rem),
               "games_played": int(cur_w.sum()), "teams": rows}
    (OUT / "live_sim.json").write_text(json.dumps(payload))
    print(json.dumps({"stage": "live_sim", "event": "simulated", "season": LIVE_SEASON,
                      "n_remaining": int(n_rem), "leaders": [r["abbr"] for r in rows[:4]]}))


def _playoff_odds(ref, pos, wins, n_teams, n_sim):
    """3 division winners + 3 wildcards per league (ties -> lower team_id), same as season_sim."""
    eff = wins - 1e-6 * np.arange(n_teams)
    playoff = np.zeros(n_teams)
    divwin = np.zeros(n_teams)
    for lg in ("AL", "NL"):
        lg_cols = np.array([pos[int(t)] for t in ref[ref.league == lg]["team_id"]])
        is_winner = np.zeros((n_sim, n_teams), dtype=bool)
        for dv in ("East", "Central", "West"):
            dcols = np.array([pos[int(t)] for t in
                              ref[(ref.league == lg) & (ref.division == dv)]["team_id"]])
            w = dcols[np.argmax(eff[:, dcols], axis=1)]
            is_winner[np.arange(n_sim), w] = True
        lg_eff = eff[:, lg_cols].copy()
        lg_eff[is_winner[:, lg_cols]] = -np.inf
        wc = lg_cols[np.argpartition(-lg_eff, 3, axis=1)[:, :3]]
        made = is_winner.copy()
        made[np.arange(n_sim)[:, None], wc] = True
        playoff += made.sum(axis=0)
        divwin += is_winner.sum(axis=0)
    return playoff, divwin


if __name__ == "__main__":
    main()
