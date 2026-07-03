"""M2/M3 - xwOBA-over-expected (Python side of the parity gate).

M2 (simple) and M3 (multiple) OLS of batted-ball outcome value (woba_value) on launch speed and
angle. The fitted value is expected batted-ball value (xwOBA-on-contact); residuals aggregate to
hitter over/under-performance. Reads ONLY the gold feed; writes a flat result file.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm


def _fit(x: np.ndarray, y: np.ndarray):
    return sm.OLS(y, sm.add_constant(x)).fit()


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/batted_balls.parquet").dropna(
        subset=["launch_speed", "launch_angle", "woba_value"]
    )
    df["launch_angle_sq"] = df["launch_angle"] ** 2
    y = df["woba_value"].to_numpy()

    m2 = _fit(df[["launch_speed"]].to_numpy(), y)
    x3 = df[["launch_speed", "launch_angle", "launch_angle_sq"]].to_numpy()
    m3 = _fit(x3, y)

    pred3 = m3.predict(sm.add_constant(x3))
    ok = df["statcast_xwoba"].notna().to_numpy()
    xwoba_corr = float(np.corrcoef(pred3[ok], df["statcast_xwoba"].to_numpy()[ok])[0, 1])

    out = {
        "n": int(len(df)),
        "m2": {
            "intercept": round(float(m2.params[0]), 8),
            "launch_speed": round(float(m2.params[1]), 8),
            "r_squared": round(float(m2.rsquared), 8),
        },
        "m3": {
            "intercept": round(float(m3.params[0]), 8),
            "launch_speed": round(float(m3.params[1]), 8),
            "launch_angle": round(float(m3.params[2]), 8),
            "launch_angle_sq": round(float(m3.params[3]), 8),
            "r_squared": round(float(m3.rsquared), 8),
        },
        "m3_xwoba_corr": round(xwoba_corr, 6),
    }
    with open(f"{res}/m2_xwoba__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "m2_xwoba", **out}))


if __name__ == "__main__":
    main()
