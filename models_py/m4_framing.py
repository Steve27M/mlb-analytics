"""M4 - catcher framing (Python side of the parity gate).

Logistic GLM of called-strike probability on pitch location. Called strikes above the
location-expected rate, summed per catcher and valued at ~0.125 runs/strike, are framing runs.
Reads ONLY the gold feed; writes a flat result file.
"""
from __future__ import annotations

import json
import os

import pandas as pd
import statsmodels.api as sm

RUN_PER_STRIKE = 0.125
MIN_PITCHES = 2000
FEATURES = ["plate_x", "plate_z", "plate_x_sq", "plate_z_sq"]


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/called_pitches.parquet")
    x = sm.add_constant(df[FEATURES].to_numpy())
    y = df["is_called_strike"].to_numpy()
    model = sm.GLM(y, x, family=sm.families.Binomial()).fit()  # IRLS, matches R glm

    df["pred"] = model.predict(x)
    df["framing"] = (df["is_called_strike"] - df["pred"]) * RUN_PER_STRIKE
    cs = df.groupby(["catcher_id", "season"]).agg(
        runs=("framing", "sum"), pitches=("framing", "size")
    ).reset_index()
    q = cs[cs["pitches"] >= MIN_PITCHES]

    names = ["intercept", *FEATURES]
    out = {
        "n": int(len(df)),
        "coef": {n: round(float(c), 8) for n, c in zip(names, model.params, strict=True)},
        "top_framer_runs": round(float(q["runs"].max()), 4),
        "bottom_framer_runs": round(float(q["runs"].min()), 4),
        "n_qualified": int(len(q)),
    }
    with open(f"{res}/m4_framing__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "m4_framing", **out}))


if __name__ == "__main__":
    main()
