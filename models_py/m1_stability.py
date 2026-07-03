"""M1 - metric stability (Python side of the parity gate).

Year-over-year correlation of batter rate stats separates skill from noise: K% and BB%
stabilize fast (high YoY correlation), BABIP is mostly noise (low). Reads ONLY the gold feed;
writes results to data/results/ as a flat file for the parity gate. No DuckDB here.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

MIN_PA = 300
STATS = ["k_pct", "bb_pct", "babip"]


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/batter_season.parquet")
    q = df[df["pa"] >= MIN_PA][["batter_id", "season", *STATS]]
    # Pair each qualified batter-season t with the same batter's season t+1.
    nxt = q.assign(season=q["season"] - 1)
    pairs = q.merge(nxt, on=["batter_id", "season"], suffixes=("_t", "_t1"))

    out: dict = {"n_pairs": int(len(pairs))}
    for s in STATS:
        sub = pairs[[f"{s}_t", f"{s}_t1"]].dropna()
        out[f"{s}_yoy_corr"] = round(float(np.corrcoef(sub[f"{s}_t"], sub[f"{s}_t1"])[0, 1]), 6)
        out[f"{s}_n"] = int(len(sub))

    with open(f"{res}/m1_stability__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "m1_stability", **out}))


if __name__ == "__main__":
    main()
