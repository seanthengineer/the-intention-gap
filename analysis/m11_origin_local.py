"""M11 post-review robustness analysis: origin-local strategy selection for cohort pseudo-backtests.

NOT pre-specified. Added after the independent review (2026-11-20) and
documented in docs/m11_decision_log.md and docs/m11_fertility_forecasts.md.

The locked pseudo-cohort backtest refits every model at each origin with data
up to that origin (origin-correct fitting), but always applies the strategy
chosen afterwards from the full 1952-2023 evaluation: no-change TFR x fixed age
shape x transformation T2. Its error and coverage figures are therefore
retrospective about the strategy.

Here, at each historical origin T, the strategy is chosen using only
information available at T:
- TFR method and age-shape method: the pseudo-real-time selection rule of
  protocol section 8.4 (conditions 1 and 3) on backtest errors whose target
  year is <= T, with at least 10 errors at each of h = 5, 10, 15;
- period-to-cohort transformation (T1 or T2): smaller mean absolute error on
  16-year validation windows that end by T, with at least 10 windows;
- interval spread: errors of this origin-local strategy with target <= T.
Origins without enough history are excluded and recorded, not defaulted.
The chosen strategy's forecasts (already fitted with data <= T) are evaluated
against later observed cohort fertility and compared with the fixed strategy
on the same origins.

    python -m analysis.m11_origin_local       # ~1 minute; needs python -m analysis.m11_forecast first
"""

import json
import sys

import numpy as np
import pandas as pd

from analysis import m11_backtest as bt
from analysis import m11_cohorts as coh
from analysis import m11_models as models
from analysis.m11_forecast import LOCAL, OUT, save
from analysis.m11_protocol import load_config, verify_lock

CONFIG = load_config()
SEL = CONFIG["selection"]
MIN_ERRORS = CONFIG["intervals"]["min_calibration_errors"]
LAST_ORIGIN = CONFIG["cohort"]["last_origin"]
FIXED_PIPELINE = "naive x S0_fixed"
HORIZON = 16
MIN_WINDOWS = 10


def choose_at_origin(records: pd.DataFrame, origin: int, col: str, methods: list, baseline: str) -> dict:
    """Pseudo-real-time selection (conditions 1 and 3) using only rows with target <= origin."""
    known = records[records["target"] <= origin]
    counts = {h: int(((known["method"] == baseline) & (known["h"] == h)).sum()) for h in bt.PRIMARY_H}
    if min(counts.values()) < MIN_ERRORS:
        return {"choice": None, "reason": f"insufficient history: {counts} errors at h 5/10/15 (need {MIN_ERRORS})",
                "errors_h15": counts[15]}
    if known["target"].max() > origin:
        raise AssertionError("selection used a target after the origin")
    candidates = [m for m in methods if m != baseline]
    boot = bt.bootstrap_ratio(known, candidates, baseline, col=col)
    scores = {}
    for m in candidates:
        r = float(np.mean([bt._abs_errors(known, m, h, col).mean() / bt._abs_errors(known, baseline, h, col).mean()
                           for h in bt.PRIMARY_H]))
        if r <= SEL["max_ratio"] and np.quantile(boot[m], SEL["bootstrap_upper"]) < 1:
            scores[m] = r
    if not scores:
        return {"choice": baseline, "reason": "no method qualified", "errors_h15": counts[15]}
    best = min(scores.values())
    near = sorted((m for m in scores if scores[m] <= best + SEL["simplicity_margin"]), key=methods.index)
    return {"choice": near[0], "reason": f"R={scores[near[0]]:.3f}", "errors_h15": counts[15]}


def choose_transform(validation: pd.DataFrame, origin: int) -> dict:
    usable = validation[validation["start"] + HORIZON <= origin]
    windows = usable["start"].nunique()
    if windows < MIN_WINDOWS:
        return {"choice": None, "reason": f"insufficient history: {windows} validation windows", "windows": windows}
    mae = usable.groupby("method")["error"].apply(lambda e: e.abs().mean())
    return {"choice": str(mae.idxmin()), "reason": f"MAE T1 {mae['T1']:.5f}, T2 {mae['T2']:.5f}", "windows": windows}


def summarise(records: pd.DataFrame, by) -> pd.DataFrame:
    return records.groupby(by, observed=True).agg(
        origins=("origin", "nunique"), mae=("error", lambda e: e.abs().mean()), bias=("error", "mean"),
        rmse=("error", lambda e: float(np.sqrt(np.mean(e ** 2))))).reset_index()


def run() -> dict:
    verify_lock()
    rates = bt.hfd_rates()
    vv = coh.vv_matrix()
    tfr_records = pd.read_csv(OUT / "m11_fc_tfr_backtest_records.csv")
    shape_records = pd.read_csv(LOCAL / "m11_fc_shape_backtest.csv")
    fixed = pd.read_csv(LOCAL / "m11_fc_cohort_backtest.csv")
    fixed = fixed[fixed["pipeline"] == FIXED_PIPELINE]
    validation = coh.validate_transformation(rates, vv)
    tfr_methods, shape_methods = list(models.TFR_METHODS), list(models.SHAPE_METHODS)

    choices, ol_rows = [], []
    for origin in range(CONFIG["backtest"]["first_origin"], LAST_ORIGIN + 1):
        tfr_pick = choose_at_origin(tfr_records, origin, "error", tfr_methods, "naive")
        shape_pick = choose_at_origin(shape_records, origin, "shape_l1", shape_methods, "S0_fixed")
        transform_pick = choose_transform(validation, origin)
        reasons = [f"{name}: {p['reason']}" for name, p in (("TFR", tfr_pick), ("shape", shape_pick),
                                                           ("transform", transform_pick)) if p["choice"] is None]
        eligible = not reasons
        choices.append({"origin": origin, "eligible": eligible, "exclusion_reason": "; ".join(reasons),
                        "tfr_choice": tfr_pick["choice"], "tfr_reason": tfr_pick["reason"],
                        "shape_choice": shape_pick["choice"], "shape_reason": shape_pick["reason"],
                        "transform_choice": transform_pick["choice"], "transform_reason": transform_pick["reason"],
                        "tfr_errors_h15_available": tfr_pick["errors_h15"],
                        "transform_windows_available": transform_pick["windows"]})
        if not eligible:
            continue
        path = tfr_records[(tfr_records["method"] == tfr_pick["choice"]) & (tfr_records["origin"] == origin)] \
            .sort_values("h")
        if list(path["h"]) != list(range(1, HORIZON + 1)) or (path["train_last"] != origin).any():
            raise AssertionError(f"TFR path at {origin} is incomplete or not origin-correct")
        window = rates[rates.index <= origin].iloc[-CONFIG["shape"]["window"]:].to_numpy()
        shape = models.forecast_shape(shape_pick["choice"], window, HORIZON)["shape"]
        coherent = models.coherent_rates(shape, path["forecast"].to_numpy())
        ol_rows.append(coh.pseudo_cohort_backtest(rates, vv, {origin: coherent}, "origin_local",
                                                  transform_pick["choice"], [origin]))
    choices = pd.DataFrame(choices)
    origin_local = pd.concat(ol_rows, ignore_index=True)
    LOCAL.mkdir(parents=True, exist_ok=True)
    origin_local.to_csv(LOCAL / "m11_pr_origin_local_cohort_backtest.csv", index=False, float_format="%.10g")
    eligible = choices.loc[choices["eligible"], "origin"].tolist()

    fixed_same = fixed[fixed["origin"].isin(eligible)].assign(pipeline="fixed (naive x S0_fixed x T2)")
    both = pd.concat([fixed_same, origin_local.assign(pipeline="origin-local selection")], ignore_index=True)
    both["a0_group"] = pd.cut(both["age_at_origin"], [11, 17, 23, 29], labels=["12-17", "18-23", "24-29"])
    keep = both[both["h"].isin([5, 10, 15, 16])]
    comparison = pd.concat([summarise(keep, ["pipeline", "a0_group", "h"]),
                            summarise(keep, ["pipeline", "h"]).assign(a0_group="all")], ignore_index=True)
    wide = comparison.pivot_table(index=["a0_group", "h"], columns="pipeline", values="mae").reset_index()
    wide["ratio_origin_local_to_fixed"] = wide["origin-local selection"] / wide["fixed (naive x S0_fixed x T2)"]

    coverage = []
    for name, recs in [("origin-local selection", origin_local), ("fixed (naive x S0_fixed x T2), same origins",
                                                                  fixed_same)]:
        cov = coh.cohort_real_time_coverage(recs)
        if cov.empty:
            continue
        summary = cov.groupby("h")[["covered80", "covered95"]].mean().reset_index()
        summary["evaluations"] = cov.groupby("h").size().to_numpy()
        summary["evaluated_origins"] = cov.groupby("h")["origin"].nunique().to_numpy()
        coverage.append(summary.assign(strategy=name))
    coverage = pd.concat(coverage, ignore_index=True)

    tfr_cmp = []
    for origin in eligible:
        pick = choices.set_index("origin").loc[origin, "tfr_choice"]
        for h in bt.PRIMARY_H:
            sub = tfr_records[(tfr_records["origin"] == origin) & (tfr_records["h"] == h)].set_index("method")
            if len(sub):
                tfr_cmp.append({"origin": origin, "h": h, "chosen": pick, "abs_error_chosen": abs(sub.loc[pick, "error"]),
                                "abs_error_naive": abs(sub.loc["naive", "error"])})
    tfr_cmp = pd.DataFrame(tfr_cmp).groupby("h").agg(origins=("origin", "nunique"), mae_chosen=("abs_error_chosen", "mean"),
                                                      mae_naive=("abs_error_naive", "mean")).reset_index()
    tfr_cmp["ratio"] = tfr_cmp["mae_chosen"] / tfr_cmp["mae_naive"]

    save(choices, "m11_pr_origin_local_choices")
    save(comparison, "m11_pr_origin_local_cohort_errors")
    save(wide, "m11_pr_origin_local_cohort_comparison")
    save(coverage, "m11_pr_origin_local_interval_coverage")
    save(tfr_cmp, "m11_pr_origin_local_tfr_comparison")
    summary = {"status": "post-review robustness analysis; not pre-specified",
               "eligible_origins": [min(eligible), max(eligible), len(eligible)],
               "excluded_origins": choices.loc[~choices["eligible"], "origin"].tolist(),
               "tfr_choices": choices["tfr_choice"].value_counts().to_dict(),
               "shape_choices": choices["shape_choice"].value_counts().to_dict(),
               "transform_choices": choices["transform_choice"].value_counts().to_dict(),
               "mae_ratio_all_ages": wide[wide["a0_group"] == "all"].set_index("h")["ratio_origin_local_to_fixed"].to_dict()}
    (OUT / "m11_pr_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary


def main() -> int:
    print(json.dumps(run(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
