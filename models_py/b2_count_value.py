"""B2 - count effects (Python side of the parity gate).

Run value by count (chaining RE24 to the count level) and swing rate by count. Reads ONLY the
gold feed; writes the count table for the gate to compare (exact tier).
"""
from __future__ import annotations

import json
import os

import pandas as pd


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/count_pitches.parquet")
    g = df.groupby(["balls", "strikes"]).agg(
        run_value=("pa_run_value", "mean"),
        swing_rate=("is_swing", "mean"),
        n=("is_swing", "size"),
    ).reset_index()

    counts = {
        f"{int(row.balls)}-{int(row.strikes)}": {
            "run_value": round(float(row.run_value), 6),
            "swing_rate": round(float(row.swing_rate), 6),
            "n": int(row.n),
        }
        for row in g.itertuples()
    }
    out = {"n": int(len(df)), "counts": counts}
    with open(f"{res}/b2_count_value__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "b2_count_value", "n": out["n"],
                      "rv_3_0": counts["3-0"]["run_value"], "rv_0_2": counts["0-2"]["run_value"]}))


if __name__ == "__main__":
    main()
