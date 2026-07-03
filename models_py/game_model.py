"""Game win-probability model (Python side of the parity gate).

Logistic model of home win from home-minus-away pre-game rolling form (leakage-safe). Trained on
2023-2024; evaluated ONCE on the sealed 2025 holdout. Benchmarked against a home-field-advantage
baseline. Reports Brier / AUC / accuracy / calibration. Reads ONLY the gold feed.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import brier_score_loss, roc_auc_score

FEATURES = ["off_rv_diff", "def_rv_diff", "win_pct_diff"]


def _pythag_baseline(train: pd.DataFrame, test: pd.DataFrame, gold: str) -> np.ndarray:
    """B1-Pythagorean baseline via log5. The exponent is fit on TRAIN team-seasons only (same
    origin log-log fit as b1_pythagoras), so the sealed holdout is never touched. Each team's
    strength = its rolling Pythagorean win expectation from leakage-safe rolling RS/RA; log5
    combines the two, then a fixed train-derived home-field log-odds bump is applied."""
    ts = pd.read_parquet(f"{gold}/team_season.parquet")
    ts = ts[(ts["season"].isin([2023, 2024])) & (ts["w"] > 0) & (ts["l"] > 0)]
    e = float(sm.OLS(np.log(ts["w"] / ts["l"]), np.log(ts["rs"] / ts["ra"])).fit().params.iloc[0])

    def pyth(rs: pd.Series, ra: pd.Series) -> np.ndarray:
        return (rs**e) / (rs**e + ra**e)

    ph = pyth(test["home_rs"], test["home_ra"]).to_numpy()
    pa = pyth(test["away_rs"], test["away_ra"]).to_numpy()
    p0 = (ph * (1 - pa)) / (ph * (1 - pa) + pa * (1 - ph))   # log5: home beats away, strength only
    b = float(train["home_win"].mean())
    hfa = float(np.log(b / (1 - b)))   # fixed train-derived home-field advantage in log-odds
    return 1.0 / (1.0 + np.exp(-(np.log(p0 / (1 - p0)) + hfa)))


def main() -> None:
    gold = os.getenv("MLB_GOLD_DIR", "data/gold")
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    os.makedirs(res, exist_ok=True)

    df = pd.read_parquet(f"{gold}/game_features.parquet")
    train = df[df["season"].isin([2023, 2024])]
    test = df[df["season"] == 2025]   # sealed holdout — evaluated once, never tuned on

    x_tr = sm.add_constant(train[FEATURES].to_numpy())
    y_tr = train["home_win"].to_numpy()
    if np.linalg.matrix_rank(x_tr) != x_tr.shape[1]:
        raise ValueError("design matrix is rank-deficient (collinear features)")
    m = sm.GLM(y_tr, x_tr, family=sm.families.Binomial()).fit()

    x_te = sm.add_constant(test[FEATURES].to_numpy())
    y_te = test["home_win"].to_numpy()
    pred = m.predict(x_te)
    base = float(y_tr.mean())   # HFA baseline: predict the train home-win rate for every game
    pyth = _pythag_baseline(train, test, gold)   # B1-Pythagorean log5 baseline (train-fit exponent)

    names = ["intercept", *FEATURES]
    out = {
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "coef": {n: round(float(c), 8) for n, c in zip(names, m.params, strict=True)},
        "brier": round(float(brier_score_loss(y_te, pred)), 6),
        "auc": round(float(roc_auc_score(y_te, pred)), 6),
        "accuracy": round(float(np.mean((pred >= 0.5) == y_te)), 6),
        "brier_hfa_baseline": round(float(brier_score_loss(y_te, np.full(len(y_te), base))), 6),
        "brier_pyth_baseline": round(float(brier_score_loss(y_te, pyth)), 6),
        "mean_pred": round(float(pred.mean()), 6),
        "mean_actual": round(float(y_te.mean()), 6),
    }
    with open(f"{res}/game_model__py.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"stage": "models_py", "model": "game_model", **out}))


if __name__ == "__main__":
    main()
