"""M7 - BABIP shrinkage (Python side of the parity gate).

Linear mixed model with batter random intercepts: each batter's BABIP is shrunk toward the
league mean (regression to the mean). ICC = share of BABIP variance that is persistent between
batters (true talent) vs season-to-season noise. Reads ONLY the gold feed.
"""
from __future__ import annotations

import json
import os

import pandas as pd
import statsmodels.formula.api as smf

MIN_PA = 150


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/batter_season.parquet")
    df = df[(df["pa"] >= MIN_PA) & df["babip"].notna()].copy()
    df["batter_id"] = df["batter_id"].astype(str)
    # BABIP in points (x100): raw BABIP variance ~3e-4 makes MixedLM's optimizer hit a singular
    # Hessian. Points-scale is well-conditioned; ICC is scale-invariant so the result is identical.
    df["babip_pts"] = df["babip"] * 100.0

    # Nelder-Mead (gradient-free): the analytic-gradient optimizers (lbfgs/bfgs/cg) invert the
    # RE covariance in score_full and crash with a singular matrix when many one-observation groups
    # drive the group variance toward 0 mid-iteration. NM avoids that inversion.
    m = smf.mixedlm("babip_pts ~ 1", df, groups=df["batter_id"]).fit(
        reml=True, method="nm", maxiter=2000
    )
    group_var = float(m.cov_re.iloc[0, 0])   # random-intercept variance (absolute units)
    resid_var = float(m.scale)
    icc = group_var / (group_var + resid_var)
    blups = {b: round(float(v.iloc[0]), 6) for b, v in m.random_effects.items()}

    out = {
        "n_obs": int(len(df)),
        "n_batters": int(df["batter_id"].nunique()),
        "intercept": round(float(m.fe_params.iloc[0]), 6),
        "group_var": round(group_var, 8),
        "resid_var": round(resid_var, 8),
        "icc": round(icc, 6),
        "blups": blups,
    }
    with open(f"{res}/m7_babip_shrinkage__py.json", "w") as f:
        json.dump(out, f)
    print(json.dumps({"stage": "models_py", "model": "m7_babip_shrinkage",
                      **{k: out[k] for k in ("n_obs", "n_batters", "intercept",
                                             "group_var", "resid_var", "icc")}}))


if __name__ == "__main__":
    main()
