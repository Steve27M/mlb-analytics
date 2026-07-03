"""B3 - aging curves (Python side of the parity gate).

Quadratic fit of OPS on age -> peak-age estimate. Cross-sectional over 2023-2025 (survivor bias
noted). Reads ONLY the gold feed.
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

    df = pd.read_parquet(f"{gold}/player_age.parquet")
    df["age_sq"] = df["age"] ** 2
    m = sm.OLS(df["ops"].to_numpy(), sm.add_constant(df[["age", "age_sq"]].to_numpy())).fit()
    b0, b1, b2 = (float(c) for c in m.params)

    out = {
        "n": int(len(df)),
        "coef": {"intercept": round(b0, 8), "age": round(b1, 8), "age_sq": round(b2, 8)},
        "peak_age": round(-b1 / (2 * b2), 4),
        "r_squared": round(float(m.rsquared), 6),
    }
    with open(f"{res}/b3_aging__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "b3_aging", **out}))


if __name__ == "__main__":
    main()
