"""M6 - pitcher arsenal archetypes (Python side of the parity gate).

Standardize arsenal features -> PCA -> KMeans into pitch-mix / stuff archetypes. Parity is
LABEL-INVARIANT: PC scores match up to sign (compared by |corr|) and cluster labels are arbitrary
(compared by ARI). Writes per-row PC scores + cluster labels for the gate to compare.
"""
from __future__ import annotations

import json
import os

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

FEATURES = ["velo", "spin", "h_move", "v_move", "fastball_pct", "breaking_pct", "n_pitch_types"]
N_PC = 4
K = 6


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/pitcher_arsenal.parquet").sort_values(
        ["pitcher_id", "season"]
    ).reset_index(drop=True)
    x = StandardScaler().fit_transform(df[FEATURES].to_numpy())
    pca = PCA(n_components=N_PC, random_state=0).fit(x)
    pcs = pca.transform(x)
    labels = KMeans(n_clusters=K, n_init=25, random_state=0).fit(pcs).labels_

    out = {
        "n": int(len(df)),
        "features": FEATURES,
        "explained_var": [round(float(v), 6) for v in pca.explained_variance_ratio_],
        "rows": [
            {
                "pitcher_id": int(df.pitcher_id[i]),
                "season": int(df.season[i]),
                "pc": [round(float(pcs[i, j]), 6) for j in range(N_PC)],
                "cluster": int(labels[i]),
            }
            for i in range(len(df))
        ],
    }
    with open(f"{res}/m6_arsenal__py.json", "w") as f:
        json.dump(out, f)
    print(json.dumps({"stage": "models_py", "model": "m6_arsenal", "n": out["n"],
                      "explained_var": out["explained_var"]}))


if __name__ == "__main__":
    main()
