"""M8 - draft position vs production (Python side of the parity gate).

Regress current (2023-2025) OPS on draft pick for drafted position players who reached MLB. The
honest result: among players who make the majors, draft position barely predicts production
(the draft is a crapshoot). Reads ONLY the gold feed (draft data via the ethical Wikipedia pull).
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

    df = pd.read_parquet(f"{gold}/draft_production.parquet")
    m = sm.OLS(df["ops"].to_numpy(), sm.add_constant(df[["pick"]].to_numpy())).fit()

    out = {
        "n": int(len(df)),
        "coef": {
            "intercept": round(float(m.params[0]), 8),
            "pick": round(float(m.params[1]), 8),
        },
        "corr_pick_ops": round(float(np.corrcoef(df["pick"], df["ops"])[0, 1]), 6),
        "r_squared": round(float(m.rsquared), 6),
    }
    with open(f"{res}/m8_draft__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "m8_draft", **out}))


if __name__ == "__main__":
    main()
