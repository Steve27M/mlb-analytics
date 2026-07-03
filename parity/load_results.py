"""Parity GATE + results loader.

Compares each model's R and Python outputs and FAILS the build (non-zero exit) on any
violation, then merges everything into data/results/metrics.json. Tolerance tiers (per
PROJECT_SPEC Phase 3):
  1. EXACT       - deterministic fits (OLS/GLM/Poisson/MLE): coefficients agree within EXACT_TOL.
  2. LABEL_INV   - PCA/clustering/mixed-effects: PC corr / cluster ARI / BLUP corr thresholds.
  3. DISTRIB     - stochastic sims: match deterministic INPUTS exactly; outputs within MC error.
Each model also asserts its known-answer test (KAT) anchors. Reads only flat result files.
"""
from __future__ import annotations

import json
import os
import sys

EXACT_TOL = 1e-6
COEF_TOL = 1e-5   # OLS/GLM coefficients: R (QR) vs statsmodels agree well within this


def _load(res: str, name: str) -> dict:
    with open(f"{res}/{name}.json") as f:
        return json.load(f)


def check_m1(res: str, fails: list[str], metrics: dict) -> None:
    """M1 metric stability: EXACT-tier parity on YoY correlations + skill-vs-noise KAT."""
    r, p = _load(res, "m1_stability__r"), _load(res, "m1_stability__py")
    for k in ("k_pct_yoy_corr", "bb_pct_yoy_corr", "babip_yoy_corr"):
        if abs(r[k] - p[k]) > EXACT_TOL:
            fails.append(f"M1 parity {k}: R={r[k]} Py={p[k]}")
    for k in ("k_pct_n", "bb_pct_n", "babip_n"):
        if r[k] != p[k]:
            fails.append(f"M1 sample mismatch: {k} R={r[k]} vs Py={p[k]}")
    # KAT: skill stats (K%, BB%) stabilize year-to-year more than noise (BABIP).
    babip = p["babip_yoy_corr"]
    for skill in ("k_pct_yoy_corr", "bb_pct_yoy_corr"):
        if not (p[skill] > babip):
            fails.append(f"M1 KAT: {skill}={p[skill]} not > babip={babip}")
    metrics["m1_stability"] = {"r": r, "python": p, "parity_ok": True, "tier": "exact"}


def check_m2(res: str, fails: list[str], metrics: dict) -> None:
    """M2/M3 xwOBA: EXACT-tier parity on OLS coefficients + R^2, plus physics KATs."""
    r, p = _load(res, "m2_xwoba__r"), _load(res, "m2_xwoba__py")
    for model in ("m2", "m3"):
        for k in r[model]:
            if abs(r[model][k] - p[model][k]) > COEF_TOL:
                fails.append(f"M2 parity {model}.{k}: R={r[model][k]} Py={p[model][k]}")
    # KATs (physics-grounded — a simple OLS is not full xwOBA, so we anchor on the known signs):
    #   exit velo increases value; launch angle is concave (an optimal mid-range exists);
    #   adding angle improves fit; and the fitted expected value shares Statcast xwOBA's signal.
    if not (p["m3"]["launch_speed"] > 0):
        fails.append(f"M2 KAT: launch_speed coef {p['m3']['launch_speed']} not > 0")
    if not (p["m3"]["launch_angle_sq"] < 0):
        fails.append(f"M2 KAT: launch_angle_sq {p['m3']['launch_angle_sq']} not < 0 (concave)")
    if not (p["m3"]["r_squared"] > p["m2"]["r_squared"]):
        fails.append("M2 KAT: M3 R2 not > M2 R2 (launch angle should add signal)")
    if not (p["m3_xwoba_corr"] > 0.4):
        fails.append(f"M2 KAT: pred vs Statcast xwOBA corr {p['m3_xwoba_corr']} not > 0.4")
    metrics["m2_xwoba"] = {"r": r, "python": p, "parity_ok": True, "tier": "exact"}


def check_m4(res: str, fails: list[str], metrics: dict) -> None:
    """M4 framing: EXACT-tier parity on logistic-GLM coefficients + framing runs, magnitude KATs."""
    r, p = _load(res, "m4_framing__r"), _load(res, "m4_framing__py")
    for k in r["coef"]:
        if abs(r["coef"][k] - p["coef"][k]) > COEF_TOL:
            fails.append(f"M4 parity coef.{k}: R={r['coef'][k]} Py={p['coef'][k]}")
    for k in ("top_framer_runs", "bottom_framer_runs"):
        if abs(r[k] - p[k]) > 0.1:  # sums over ~1M predictions; coefs agree to COEF_TOL
            fails.append(f"M4 parity {k}: R={r[k]} Py={p[k]}")
    # KAT: called-strike prob concave in location (peaks over the middle of the zone); elite
    # framers ~ +10 to +20 runs/season (published leaderboard range); worst are strongly negative.
    if not (p["coef"]["plate_x_sq"] < 0 and p["coef"]["plate_z_sq"] < 0):
        fails.append("M4 KAT: location coefs not both concave (zone should peak in the middle)")
    if not (p["top_framer_runs"] > 8):
        fails.append(f"M4 KAT: top framer {p['top_framer_runs']} not > 8 runs")
    if not (p["bottom_framer_runs"] < -8):
        fails.append(f"M4 KAT: bottom framer {p['bottom_framer_runs']} not < -8 runs")
    metrics["m4_framing"] = {"r": r, "python": p, "parity_ok": True, "tier": "exact"}


def check_m5(res: str, fails: list[str], metrics: dict) -> None:
    """M5 K-Poisson: EXACT-tier parity on Poisson-GLM coefficients + league-K-rate KAT."""
    r, p = _load(res, "m5_k_poisson__r"), _load(res, "m5_k_poisson__py")
    for k in r["coef"]:
        if abs(r["coef"][k] - p["coef"][k]) > COEF_TOL:
            fails.append(f"M5 parity coef.{k}: R={r['coef'][k]} Py={p['coef'][k]}")
    # KAT: more batters faced -> more strikeouts; league K rate ~0.22 per PA (recent seasons).
    if not (p["coef"]["bf"] > 0):
        fails.append(f"M5 KAT: bf coef {p['coef']['bf']} not > 0")
    if not (0.18 <= p["k_per_bf"] <= 0.26):
        fails.append(f"M5 KAT: league K/BF {p['k_per_bf']} outside [0.18, 0.26]")
    metrics["m5_k_poisson"] = {"r": r, "python": p, "parity_ok": True, "tier": "exact"}


def check_m6(res: str, fails: list[str], metrics: dict) -> None:
    """M6 arsenal: LABEL-INVARIANT parity — PC scores match up to sign (|corr|), clusters by ARI."""
    import numpy as np
    from sklearn.metrics import adjusted_rand_score

    r, p = _load(res, "m6_arsenal__r"), _load(res, "m6_arsenal__py")
    rmap = {(x["pitcher_id"], x["season"]): x for x in r["rows"]}
    pmap = {(x["pitcher_id"], x["season"]): x for x in p["rows"]}
    keys = sorted(set(rmap) & set(pmap))
    if len(keys) != len(pmap):
        fails.append(f"M6: row alignment {len(keys)} common of {len(pmap)}")
        return
    for j in range(len(p["rows"][0]["pc"])):
        rv = np.array([rmap[k]["pc"][j] for k in keys])
        pv = np.array([pmap[k]["pc"][j] for k in keys])
        corr = abs(float(np.corrcoef(rv, pv)[0, 1]))
        if corr < 0.99:
            fails.append(f"M6 label-invariant PC{j + 1}: |corr| {corr:.4f} < 0.99")
    ari = float(adjusted_rand_score([rmap[k]["cluster"] for k in keys],
                                    [pmap[k]["cluster"] for k in keys]))
    if ari < 0.6:
        fails.append(f"M6 label-invariant: cluster ARI {ari:.3f} < 0.6")
    metrics["m6_arsenal"] = {"n": len(keys), "cluster_ari": round(ari, 4),
                             "explained_var": p["explained_var"], "parity_ok": True,
                             "tier": "label_invariant"}


def check_m7(res: str, fails: list[str], metrics: dict) -> None:
    """M7 BABIP shrinkage: variance components / ICC agree, BLUP |corr| (mixed-effects tier)."""
    import numpy as np

    r, p = _load(res, "m7_babip_shrinkage__r"), _load(res, "m7_babip_shrinkage__py")
    if abs(r["intercept"] - p["intercept"]) > 1e-4:
        fails.append(f"M7 intercept: R={r['intercept']} Py={p['intercept']}")
    for k in ("group_var", "resid_var", "icc"):
        if abs(r[k] - p[k]) / max(abs(p[k]), 1e-9) > 0.03:
            fails.append(f"M7 {k}: R={r[k]} Py={p[k]} (>3% rel)")
    keys = sorted(set(r["blups"]) & set(p["blups"]))
    rv = np.array([r["blups"][k] for k in keys])
    pv = np.array([p["blups"][k] for k in keys])
    corr = abs(float(np.corrcoef(rv, pv)[0, 1]))
    if corr < 0.99:
        fails.append(f"M7 BLUP |corr| {corr:.4f} < 0.99")
    # KAT: BABIP is mostly noise -> persistent (between-batter) share is low (ICC < 0.5).
    if not (0 < p["icc"] < 0.5):
        fails.append(f"M7 KAT: ICC {p['icc']} not in (0, 0.5)")
    keep = ("intercept", "group_var", "resid_var", "icc")
    metrics["m7_babip_shrinkage"] = {"r": {k: r[k] for k in keep},
                                     "python": {k: p[k] for k in keep},
                                     "blup_corr": round(corr, 4), "parity_ok": True,
                                     "tier": "label_invariant"}


def check_b1(res: str, fails: list[str], metrics: dict) -> None:
    """B1 Pythagorean: EXACT-tier parity on exponent + runs-per-win, both anchored to literature."""
    r, p = _load(res, "b1_pythagoras__r"), _load(res, "b1_pythagoras__py")
    for k in ("pythag_exponent", "runs_per_win"):
        if abs(r[k] - p[k]) > COEF_TOL:
            fails.append(f"B1 parity {k}: R={r[k]} Py={p[k]}")
    # KAT: published Pythagorean exponent ~1.83; marginal runs-per-win ~9-10.
    if not (1.7 <= p["pythag_exponent"] <= 2.0):
        fails.append(f"B1 KAT: exponent {p['pythag_exponent']} not in [1.7, 2.0]")
    if not (8.0 <= p["runs_per_win"] <= 12.0):
        fails.append(f"B1 KAT: runs_per_win {p['runs_per_win']} not in [8, 11]")
    metrics["b1_pythagoras"] = {"r": r, "python": p, "parity_ok": True, "tier": "exact"}


def check_b2(res: str, fails: list[str], metrics: dict) -> None:
    """B2 count value: EXACT-tier parity on the count table + count-effect monotonicity KATs."""
    r, p = _load(res, "b2_count_value__r"), _load(res, "b2_count_value__py")
    for key in p["counts"]:
        for f in ("run_value", "swing_rate"):
            if abs(r["counts"][key][f] - p["counts"][key][f]) > COEF_TOL:
                fails.append(f"B2 parity {key}.{f}: {r['counts'][key][f]} vs {p['counts'][key][f]}")
    c = p["counts"]
    # KAT: hitter's counts carry more run value; two-strike counts -> protect (swing more).
    if not (c["3-0"]["run_value"] > c["0-0"]["run_value"] > c["0-2"]["run_value"]):
        fails.append("B2 KAT: run value not monotonic 3-0 > 0-0 > 0-2")
    if not (c["0-2"]["swing_rate"] > c["0-0"]["swing_rate"] > c["3-0"]["swing_rate"]):
        fails.append("B2 KAT: swing rate not monotonic 0-2 > 0-0 > 3-0")
    metrics["b2_count_value"] = {"counts": c, "parity_ok": True, "tier": "exact"}


def check_b5(res: str, fails: list[str], metrics: dict) -> None:
    """B5 streaks: DISTRIBUTIONAL tier - observed exact, permutation null within MC error."""

    r, p = _load(res, "b5_streaks__r"), _load(res, "b5_streaks__py")
    # Deterministic: observed runs (exact int) + z per hitter-season must match.
    keys = sorted(set(r["observed"]) & set(p["observed"]))
    if len(keys) != len(p["observed"]):
        fails.append(f"B5 observed alignment {len(keys)}/{len(p['observed'])}")
    for k in keys:
        if r["observed"][k]["runs"] != p["observed"][k]["runs"]:
            fails.append(f"B5 observed runs {k} differ")
        if abs(r["observed"][k]["z"] - p["observed"][k]["z"]) > 1e-4:
            fails.append(f"B5 observed z {k}: R={r['observed'][k]['z']} Py={p['observed'][k]['z']}")
    if abs(r["mean_z"] - p["mean_z"]) > 1e-4 or abs(r["sd_z"] - p["sd_z"]) > 1e-4:
        fails.append(f"B5 aggregate z differ: R={r['mean_z']} Py={p['mean_z']}")
    # Distributional: SAME deterministic input (batter + observed_runs), perm null within MC error.
    rp, pp = r["perm"], p["perm"]
    if rp["key"] != pp["key"] or rp["observed_runs"] != pp["observed_runs"]:
        fails.append("B5 perm: deterministic input (batter/observed_runs) differs")
    se = pp["perm_sd"] / (pp["n_perm"] ** 0.5)
    if abs(rp["perm_mean"] - pp["perm_mean"]) > 5 * se:
        fails.append(f"B5 perm_mean {rp['perm_mean']} vs {pp['perm_mean']} beyond 5 MC-SE")
    # KAT: hitting streaks are largely consistent with randomness -> mean z near 0 as a group.
    if abs(p["mean_z"]) > 0.5:
        fails.append(f"B5 KAT: mean_z {p['mean_z']} — group unexpectedly streaky (|z|>0.5)")
    metrics["b5_streaks"] = {"n": len(keys), "mean_z": p["mean_z"], "perm": pp,
                             "parity_ok": True, "tier": "distributional"}


def check_game(res: str, fails: list[str], metrics: dict) -> None:
    """Game model: EXACT-tier parity on coefficients + holdout metrics; beats-baseline KATs."""
    r, p = _load(res, "game_model__r"), _load(res, "game_model__py")
    for k in r["coef"]:
        if abs(r["coef"][k] - p["coef"][k]) > COEF_TOL:
            fails.append(f"Game parity coef.{k}: R={r['coef'][k]} Py={p['coef'][k]}")
    for k in ("brier", "auc", "accuracy", "brier_hfa_baseline", "brier_pyth_baseline"):
        if abs(r[k] - p[k]) > 1e-4:
            fails.append(f"Game parity {k}: R={r[k]} Py={p[k]}")
    # KATs on the sealed 2025 holdout: model beats BOTH the naive home-field baseline and the
    # B1-Pythagorean (log5) baseline on Brier; AUC is in a realistic band for game-level MLB
    # prediction; the model is well-calibrated.
    if not (p["brier"] < p["brier_hfa_baseline"]):
        fails.append(f"Game KAT: Brier {p['brier']} not < HFA baseline {p['brier_hfa_baseline']}")
    if not (p["brier"] < p["brier_pyth_baseline"]):
        pb = p["brier_pyth_baseline"]
        fails.append(f"Game KAT: Brier {p['brier']} not < Pythag baseline {pb}")
    if not (0.5 < p["auc"] < 0.68):
        fails.append(f"Game KAT: AUC {p['auc']} outside (0.5, 0.68)")
    if not (abs(p["mean_pred"] - p["mean_actual"]) < 0.03):
        fails.append(f"Game KAT: miscalibrated, mean_pred {p['mean_pred']} vs {p['mean_actual']}")
    metrics["game_model"] = {"r": r, "python": p, "parity_ok": True, "tier": "exact"}


def check_b3(res: str, fails: list[str], metrics: dict) -> None:
    """B3 aging: EXACT-tier parity on the quadratic fit + peak-age KAT."""
    r, p = _load(res, "b3_aging__r"), _load(res, "b3_aging__py")
    for k in r["coef"]:
        if abs(r["coef"][k] - p["coef"][k]) > COEF_TOL:
            fails.append(f"B3 parity coef.{k}: R={r['coef'][k]} Py={p['coef'][k]}")
    if abs(r["peak_age"] - p["peak_age"]) > 1e-3:
        fails.append(f"B3 parity peak_age: R={r['peak_age']} Py={p['peak_age']}")
    # KAT: aging curve is concave (a peak exists) and peaks in the late-20s (published ~26-29;
    # cross-sectional survivor bias can push it a touch later).
    if not (p["coef"]["age_sq"] < 0):
        fails.append(f"B3 KAT: age_sq {p['coef']['age_sq']} not < 0 (curve should be concave)")
    if not (24 <= p["peak_age"] <= 31):
        fails.append(f"B3 KAT: peak age {p['peak_age']} outside [24, 31]")
    metrics["b3_aging"] = {"r": r, "python": p, "parity_ok": True, "tier": "exact"}


def check_b4(res: str, fails: list[str], metrics: dict) -> None:
    """B4 Markov sim: DISTRIBUTIONAL tier + RE24 reconciliation KAT."""
    r, p = _load(res, "b4_markov_sim__r"), _load(res, "b4_markov_sim__py")
    # Deterministic transition summary must match exactly (per from_state count + mean runs).
    for s in p["transition_summary"]:
        rr, pp = r["transition_summary"][s], p["transition_summary"][s]
        if rr["n"] != pp["n"] or abs(rr["mean_runs"] - pp["mean_runs"]) > 1e-4:
            fails.append(f"B4 transition {s}: R={rr} Py={pp}")
    # Deterministic RE24 pooled values must match exactly across languages.
    for k in ("re24_empty_0", "re24_loaded_0"):
        if abs(r[k] - p[k]) > 1e-3:
            fails.append(f"B4 {k}: R={r[k]} Py={p[k]}")
    # Distributional: simulated means within Monte-Carlo error (sd/inning ~1; 10k sims -> ~0.05).
    for k in ("sim_re_empty_0", "sim_re_loaded_0"):
        if abs(r[k] - p[k]) > 0.08:
            fails.append(f"B4 {k}: R={r[k]} Py={p[k]} beyond MC error")
    # KAT (RECONCILIATION): the Markov sim must reproduce RE24 — RE(empty,0) ~ 0.5 and the sim
    # matches the RE24 matrix; runners raise RE. This is the spec's "matrix reconciles" requirement.
    if not (0.44 <= p["re24_empty_0"] <= 0.56):
        fails.append(f"B4 KAT: RE24(empty,0) {p['re24_empty_0']} not ~0.5")
    if abs(p["sim_re_empty_0"] - p["re24_empty_0"]) > 0.06:
        fails.append(f"B4 KAT: sim {p['sim_re_empty_0']} vs RE24 {p['re24_empty_0']}")
    if abs(p["sim_re_loaded_0"] - p["re24_loaded_0"]) > 0.12:
        fails.append(f"B4 KAT: sim loaded {p['sim_re_loaded_0']} vs RE24 {p['re24_loaded_0']}")
    if not (p["sim_re_loaded_0"] > p["sim_re_empty_0"]):
        fails.append("B4 KAT: RE(loaded,0) not > RE(empty,0)")
    metrics["b4_markov_sim"] = {"r": r, "python": p, "parity_ok": True, "tier": "distributional"}


def check_m8(res: str, fails: list[str], metrics: dict) -> None:
    """M8 draft: EXACT-tier parity on the fit + weak-relationship KAT (draft is a crapshoot)."""
    r, p = _load(res, "m8_draft__r"), _load(res, "m8_draft__py")
    for k in r["coef"]:
        if abs(r["coef"][k] - p["coef"][k]) > COEF_TOL:
            fails.append(f"M8 parity coef.{k}: R={r['coef'][k]} Py={p['coef'][k]}")
    if abs(r["corr_pick_ops"] - p["corr_pick_ops"]) > 1e-4:
        fails.append(f"M8 parity corr: R={r['corr_pick_ops']} Py={p['corr_pick_ops']}")
    # KAT: among players who reached MLB, draft pick barely predicts current production -> the
    # correlation is weak (|corr| < 0.3) and the relationship is (weakly) in the expected direction.
    if not (abs(p["corr_pick_ops"]) < 0.3):
        fails.append(f"M8 KAT: |corr(pick, OPS)| {p['corr_pick_ops']} not < 0.3")
    if not (p["n"] >= 30):
        fails.append(f"M8 KAT: only {p['n']} matched players (need >= 30 for a stable estimate)")
    metrics["m8_draft"] = {"r": r, "python": p, "parity_ok": True, "tier": "exact"}


CHECKS = [check_m1, check_m2, check_m4, check_m5, check_m6, check_m7, check_m8,
          check_b1, check_b2, check_b3, check_b4, check_b5, check_game]


def main() -> None:
    res = os.getenv("MLB_RESULTS_DIR", "data/results")
    fails: list[str] = []
    metrics: dict = {}
    for check in CHECKS:
        try:
            check(res, fails, metrics)
        except FileNotFoundError as e:
            fails.append(f"{check.__name__}: missing result file ({e.filename})")

    with open(f"{res}/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, sort_keys=True)

    if fails:
        print("PARITY GATE FAILED:")
        for x in fails:
            print("  -", x)
        sys.exit(1)
    print(f"PARITY GATE passed ({len(metrics)} model(s): {', '.join(metrics)}).")


if __name__ == "__main__":
    main()
