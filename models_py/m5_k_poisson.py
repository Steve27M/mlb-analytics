"""M5 - strikeouts per start (Python side of the parity gate).

Poisson regression of strikeout count on batters faced -> expected K totals per start
(prop-bet framing). Reads ONLY the gold feed; writes a flat result file.
"""
from __future__ import annotations

import json
import os

import pandas as pd
import statsmodels.api as sm


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/pitcher_start.parquet")
    x = sm.add_constant(df[["bf"]].to_numpy())
    model = sm.GLM(df["k"].to_numpy(), x, family=sm.families.Poisson()).fit()  # log link, IRLS

    out = {
        "n": int(len(df)),
        "coef": {
            "intercept": round(float(model.params[0]), 8),
            "bf": round(float(model.params[1]), 8),
        },
        "mean_k_per_start": round(float(df["k"].mean()), 4),
        "k_per_bf": round(float(df["k"].sum() / df["bf"].sum()), 6),
    }
    with open(f"{res}/m5_k_poisson__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "m5_k_poisson", **out}))


if __name__ == "__main__":
    main()
