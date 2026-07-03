"""B5 - streaky performances (Python side of the parity gate).

Wald-Wolfowitz runs test on each hitter's game-by-game hit/no-hit sequence, plus a permutation
test on the busiest hitter-season. Distributional-tier parity: the observed statistics are
deterministic (match R exactly); the permutation null is stochastic (matches within MC error, not
by seed). Reads ONLY the gold feed.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

MIN_GAMES = 100
N_PERM = 10000


def runs_count(seq: np.ndarray) -> int:
    return int(1 + np.sum(seq[1:] != seq[:-1])) if len(seq) else 0


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/batter_games.parquet").sort_values(
        ["batter_id", "season", "game_date", "game_pk"]
    )
    observed: dict = {}
    seqs: dict = {}
    for (b, s), g in df.groupby(["batter_id", "season"]):
        seq = g["got_hit"].to_numpy()
        n, n1 = len(seq), int(g["got_hit"].sum())
        n0 = n - n1
        if n < MIN_GAMES or n1 == 0 or n0 == 0:
            continue
        runs = runs_count(seq)
        exp = 2 * n1 * n0 / n + 1
        var = 2 * n1 * n0 * (2 * n1 * n0 - n) / (n**2 * (n - 1))
        key = f"{int(b)}-{int(s)}"
        observed[key] = {"n": n, "runs": runs, "z": round((runs - exp) / np.sqrt(var), 6)}
        seqs[key] = seq

    zs = np.array([v["z"] for v in observed.values()])
    # Deterministic pick: busiest hitter-season (tie-break by key) -> permutation test.
    top_key = max(observed, key=lambda k: (observed[k]["n"], k))
    seq = seqs[top_key]
    rng = np.random.default_rng(12345)
    perm = np.array([runs_count(rng.permutation(seq)) for _ in range(N_PERM)])

    out = {
        "n_batter_seasons": len(observed),
        "mean_z": round(float(zs.mean()), 6),
        "sd_z": round(float(zs.std(ddof=1)), 6),
        "observed": observed,
        "perm": {
            "key": top_key,
            "observed_runs": observed[top_key]["runs"],
            "perm_mean": round(float(perm.mean()), 4),
            "perm_sd": round(float(perm.std(ddof=1)), 4),
            "perm_p": round(float(np.mean(perm <= observed[top_key]["runs"])), 4),
            "n_perm": N_PERM,
        },
    }
    with open(f"{res}/b5_streaks__py.json", "w") as f:
        json.dump(out, f)
    print(json.dumps({"stage": "models_py", "model": "b5_streaks",
                      "n_batter_seasons": out["n_batter_seasons"], "mean_z": out["mean_z"],
                      "perm_mean": out["perm"]["perm_mean"]}))


if __name__ == "__main__":
    main()
