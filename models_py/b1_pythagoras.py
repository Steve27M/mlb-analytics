"""B1 - Pythagorean expectation (Python side of the parity gate).

Fit the Pythagorean exponent from team-season run ratios, and estimate marginal runs-per-win.
Both are famous sabermetric constants (exponent ~1.83, ~9-10 runs/win) used as KAT anchors and as
a baseline for the game model. Reads ONLY the gold feed.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/team_season.parquet")
    df = df[(df["w"] > 0) & (df["l"] > 0)]

    # Pythagorean exponent: log(W/L) = k * log(RS/RA), fit through the origin.
    k = float(sm.OLS(np.log(df["w"] / df["l"]), np.log(df["rs"] / df["ra"])).fit().params.iloc[0])
    # Runs per win: (W - G/2) = (RS - RA) / runs_per_win, fit through the origin.
    slope = float(sm.OLS(df["w"] - df["games"] / 2, df["rs"] - df["ra"]).fit().params.iloc[0])

    out = {
        "n_team_seasons": int(len(df)),
        "pythag_exponent": round(k, 6),
        "runs_per_win": round(1.0 / slope, 4),
    }
    with open(f"{res}/b1_pythagoras__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "b1_pythagoras", **out}))


if __name__ == "__main__":
    main()
