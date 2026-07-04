"""Season Monte-Carlo simulator (playoff odds) for the dashboard.

This is NOT a new statistical model and is intentionally Python-only: it is a Monte-Carlo ROLLUP of
the already-parity-gated game model. The statistical estimation (the logistic fit) lives in
models_r/game_model.R and models_py/game_model.py and is checked by the parity gate. Here we simply
(1) refit that same 3-feature logistic model on 2023-2024, (2) score every 2025 game with its
LEAKAGE-SAFE pre-game rolling-form probability (a genuine forecast, never the 2025 outcome), and
(3) simulate the real 2025 schedule N times to get each team's projected-win distribution and
playoff odds. Cross-language RNG parity is explicitly out of scope per the project rules ("Never
attempt cross-language RNG seed matching"), so the simulation lives on one side only.

MLB playoff rule applied per league: 3 division winners (most wins in each division) + 3 wildcards
(next 3 by wins). Ties broken deterministically by team_id (a documented simplification; real MLB
uses head-to-head and other tiebreakers). Reads the game-model feed + a static division reference;
writes data/dashboard/season_sim.json. Fixed seed -> reproducible page.
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
DB = os.getenv("MLB_DUCKDB_PATH", str(REPO / "data" / "warehouse.duckdb"))
GOLD = os.getenv("MLB_GOLD_DIR", str(REPO / "data" / "gold"))
REF = REPO / "reference" / "team_divisions.csv"
FEATURES = ["off_rv_diff", "def_rv_diff", "win_pct_diff"]   # identical to the game model
N_SIM = 10000
SEED = 777


def _game_probs(gold: str) -> pd.DataFrame:
    """Refit the game model on 2023-2024 and return each 2025 game's leakage-safe P(home win)."""
    df = pd.read_parquet(f"{gold}/game_features.parquet")
    train = df[df["season"].isin([2023, 2024])]
    # Sort by game_pk so the fixed-seed RNG maps to games in a stable order regardless of the
    # parquet/DuckDB row order — makes the simulation byte-reproducible across environments.
    test = df[df["season"] == 2025].sort_values("game_pk").copy()
    x_tr = sm.add_constant(train[FEATURES].to_numpy())
    m = sm.GLM(train["home_win"].to_numpy(), x_tr, family=sm.families.Binomial()).fit()
    test["p_home"] = m.predict(sm.add_constant(test[FEATURES].to_numpy()))
    return test[["home_team_id", "away_team_id", "p_home"]].reset_index(drop=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ref = pd.read_csv(REF)
    teams = ref["team_id"].to_numpy()
    pos = {int(t): i for i, t in enumerate(teams)}   # column index per team_id
    n_teams = len(teams)

    games = _game_probs(GOLD)
    hi = games["home_team_id"].map(pos).to_numpy()
    ai = games["away_team_id"].map(pos).to_numpy()
    p = games["p_home"].to_numpy()
    n_games = len(games)

    # --- Monte Carlo: N seasons x n_games home-win draws -> per-team win totals (N x n_teams) ---
    rng = np.random.default_rng(SEED)
    home_win = rng.random((N_SIM, n_games)) < p            # (N, games) bool
    wins = np.zeros((N_SIM, n_teams))
    np.add.at(wins.T, hi, home_win.T)                      # home team gets a win when home_win
    np.add.at(wins.T, ai, (~home_win).T)                   # away team gets a win otherwise

    # deterministic tiebreak: lower team_id wins ties (subtract a tiny position-based epsilon)
    eff = wins - 1e-6 * np.arange(n_teams)

    playoff = np.zeros(n_teams)
    divwin = np.zeros(n_teams)
    for lg in ("AL", "NL"):
        lg_cols = np.array([pos[int(t)] for t in ref[ref.league == lg]["team_id"]])
        is_winner = np.zeros((N_SIM, n_teams), dtype=bool)
        for dv in ("East", "Central", "West"):
            dcols = np.array([pos[int(t)] for t in
                              ref[(ref.league == lg) & (ref.division == dv)]["team_id"]])
            w = dcols[np.argmax(eff[:, dcols], axis=1)]    # division winner column per sim
            is_winner[np.arange(N_SIM), w] = True
        # wildcards: among non-winners in the league, top 3 by wins
        lg_eff = eff[:, lg_cols].copy()
        winner_mask = is_winner[:, lg_cols]
        lg_eff[winner_mask] = -np.inf
        wc_local = np.argpartition(-lg_eff, 3, axis=1)[:, :3]    # 3 wildcard local indices per sim
        wc_cols = lg_cols[wc_local]
        made = is_winner.copy()
        made[np.arange(N_SIM)[:, None], wc_cols] = True
        playoff += made.sum(axis=0)
        divwin += is_winner.sum(axis=0)

    # --- actual 2025 records + names, for the side-by-side ---
    con = duckdb.connect(DB, read_only=True)
    act = con.execute("""
        select t.team_id, t.team_name, s.w, s.l, s.rs, s.ra
        from gold.gold_team_season s join gold.dim_team t on t.team_id = s.team_id
        where s.season = 2025
    """).fetch_df().set_index("team_id")
    con.close()

    proj_mean = wins.mean(axis=0)
    proj_p10 = np.percentile(wins, 10, axis=0)
    proj_p90 = np.percentile(wins, 90, axis=0)

    rows = []
    for t in teams:
        i, tid = pos[int(t)], int(t)
        r = ref[ref.team_id == tid].iloc[0]
        a = act.loc[tid]
        rows.append({
            "team_id": tid, "abbr": r["team_abbr"], "name": str(a["team_name"]),
            "league": r["league"], "division": r["division"],
            "actual_w": int(a["w"]), "actual_l": int(a["l"]),
            "proj_wins": round(float(proj_mean[i]), 1),
            "p10": round(float(proj_p10[i]), 1), "p90": round(float(proj_p90[i]), 1),
            "playoff_odds": round(float(playoff[i] / N_SIM), 3),
            "div_odds": round(float(divwin[i] / N_SIM), 3),
        })
    rows.sort(key=lambda x: -x["playoff_odds"])

    # actual 2025 playoff field (top-6 per league by wins, same rule) for the validation note
    actual_playoff = _actual_playoff(ref, act)
    for row in rows:
        row["made_playoffs_actual"] = row["team_id"] in actual_playoff
    corr = float(np.corrcoef(
        [r["proj_wins"] for r in rows], [r["actual_w"] for r in rows])[0, 1])
    hit = sum(1 for r in sorted(rows, key=lambda x: -x["playoff_odds"])[:12]
              if r["made_playoffs_actual"])

    payload = {
        "n_sim": N_SIM, "seed": SEED, "n_games": n_games,
        "corr_proj_actual": round(corr, 3),
        "top12_playoff_hits": hit,   # of the 12 highest-odds teams, how many actually made it
        "teams": rows,
    }
    (OUT / "season_sim.json").write_text(json.dumps(payload))
    print(json.dumps({"stage": "season_sim", "event": "simulated", "n_sim": N_SIM,
                      "corr_proj_actual": payload["corr_proj_actual"],
                      "top12_playoff_hits": hit}))


def _actual_playoff(ref: pd.DataFrame, act: pd.DataFrame) -> set:
    """Actual 2025 playoff field, same rule: 3 division winners + 3 wildcards per league."""
    field = set()
    for lg in ("AL", "NL"):
        winners, lg_teams = set(), []
        for dv in ("East", "Central", "West"):
            ids = ref[(ref.league == lg) & (ref.division == dv)]["team_id"].tolist()
            w = max(ids, key=lambda t: (int(act.loc[t, "w"]), -t))
            winners.add(w)
        for t in ref[ref.league == lg]["team_id"]:
            lg_teams.append(int(t))
        rest = [t for t in lg_teams if t not in winners]
        rest.sort(key=lambda t: (-int(act.loc[t, "w"]), t))
        field |= winners | set(rest[:3])
    return field


if __name__ == "__main__":
    main()
