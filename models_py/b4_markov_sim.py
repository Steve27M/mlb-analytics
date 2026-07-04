"""B4 - Markov half-inning simulation (Python side of the parity gate).

Build the base-out transition distribution from play-by-play, then simulate half-innings from a
given start state to estimate run expectancy. The simulated RE must reconcile with
gold_run_expectancy (RE24). Distributional tier: the transition summary is deterministic (matches
R exactly); the simulated means match within Monte-Carlo error. Reads ONLY gold feeds.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

N_SIM = 10000
ABSORB = 24  # "3 outs" absorbing state


def simulate(to_by_state: dict, runs_by_state: dict, start: int, rng, n: int) -> np.ndarray:
    totals = np.empty(n)
    for i in range(n):
        s, r = start, 0.0
        while s != ABSORB:
            tos, runs = to_by_state[s], runs_by_state[s]
            j = rng.integers(len(tos))
            r += runs[j]
            s = int(tos[j])
        totals[i] = r
    return totals


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/pa_transitions.parquet")
    # Stable transition order so the fixed-seed RNG maps to the same transitions every rebuild
    # (parquet/DuckDB row order isn't guaranteed) — makes the simulated RE byte-reproducible.
    df = df.sort_values(["from_state", "to_state", "runs"]).reset_index(drop=True)
    to_by = {int(s): g["to_state"].to_numpy() for s, g in df.groupby("from_state")}
    runs_by = {int(s): g["runs"].to_numpy() for s, g in df.groupby("from_state")}

    summ = df.groupby("from_state").agg(
        n=("runs", "size"), mean_runs=("runs", "mean")).reset_index()
    summary = {str(int(r.from_state)): {"n": int(r.n), "mean_runs": round(float(r.mean_runs), 6)}
               for r in summ.itertuples()}

    rng = np.random.default_rng(777)
    sim_empty0 = float(simulate(to_by, runs_by, 0, rng, N_SIM).mean())    # state 0 = empty, 0 outs
    sim_loaded0 = float(simulate(to_by, runs_by, 21, rng, N_SIM).mean())  # state 21 = loaded, 0 out

    re24 = pd.read_parquet(f"{gold}/run_expectancy.parquet")

    def pooled(bs: int, outs: int) -> float:
        sub = re24[(re24["base_state"] == bs) & (re24["outs_start"] == outs)]
        return float(np.average(sub["run_expectancy"], weights=sub["n_occurrences"]))

    out = {
        "n_transitions": int(len(df)),
        "transition_summary": summary,
        "sim_re_empty_0": round(sim_empty0, 4),
        "sim_re_loaded_0": round(sim_loaded0, 4),
        "re24_empty_0": round(pooled(0, 0), 4),
        "re24_loaded_0": round(pooled(7, 0), 4),
        "n_sim": N_SIM,
    }
    with open(f"{res}/b4_markov_sim__py.json", "w") as f:
        json.dump(out, f)
    print(json.dumps({"stage": "models_py", "model": "b4_markov_sim",
                      "sim_re_empty_0": out["sim_re_empty_0"], "re24_empty_0": out["re24_empty_0"],
                      "sim_re_loaded_0": out["sim_re_loaded_0"],
                      "re24_loaded_0": out["re24_loaded_0"]}))


if __name__ == "__main__":
    main()
