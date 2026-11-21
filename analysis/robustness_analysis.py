"""Robustness checks for the calibration and predictive-baseline results.

- Repeated household-grouped cross-validation of approaches A-D inside the
  training partition of the held-out split; the test set is not used. This
  is exploratory: it was added after the held-out results were known.
- Outcome-definition sensitivity: alternative classification rules applied
  through build_outcomes.OutcomeRules, plus explicit bounds for unknown
  outcomes. The primary cohort file is never modified.
- Early-birth sensitivity: women whose first qualifying birth came soon
  after the interview may already have been pregnant when they answered.
- Round 13 cross-sectional weighted description of stated expectations.

All results are aggregate. Unless stated otherwise, estimates are unweighted.
"""

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

from analysis import analyze_calibration as ac
from analysis import build_outcomes as bo
from analysis.build_outcomes import NOT_QUALIFYING, QUALIFYING, OutcomeRules
from analysis.nlsy97 import (
    BASELINE_ROUND, CHILD_BIRTH_MONTH, INTERVIEW_MONTH, RESPONDENT_ID, assess_roster,
)

# Fixed before any cross-validation results were inspected.
CV_SEEDS = tuple(range(101, 111))
CV_FOLDS = 5
SENSITIVITY_CV_SEED = 211
SLOPE_BOOTSTRAP = 1000

RULE_SCENARIOS = {
    "Primary definition": bo.PRIMARY_RULES,
    "Unmatched baseline-month births qualify": OutcomeRules(baseline_month_birth=QUALIFYING),
    "Baseline-month births never qualify": OutcomeRules(baseline_month_birth=NOT_QUALIFYING),
    "Anniversary-month births qualify": OutcomeRules(anniversary_month_birth=QUALIFYING),
    "Anniversary-month births never qualify": OutcomeRules(anniversary_month_birth=NOT_QUALIFYING),
    "Both boundary months qualify": OutcomeRules(QUALIFYING, QUALIFYING),
    "Neither boundary month qualifies": OutcomeRules(NOT_QUALIFYING, NOT_QUALIFYING),
    "Follow-up dates accepted without 2009 reconciliation":
        OutcomeRules(reconcile_with_baseline_roster=False),
    "Disagreeing rounds resolved by 2015": OutcomeRules(preferred_round=2015),
    "Disagreeing rounds resolved by 2017": OutcomeRules(preferred_round=2017),
    "Strict date reconciliation of pre-baseline births":
        OutcomeRules(strict_date_reconciliation=True),
}

# A birth within this many months of the interview implies conception at or
# before the interview month. The proxy is defined by the outcome itself and
# is used only for sensitivity bounds; analysis.pregnancy_status uses the
# Round 13 self-report from the supplementary extract instead.
EARLY_BIRTH_MONTHS = 8
EARLY_BIRTH_THRESHOLDS = (7, 8, 9)

AMBIGUITY_REASONS = {
    bo.ROUNDS_DISAGREE, bo.RECORD_CONFLICT,
    bo.BASELINE_MONTH_TIMING, bo.ANNIVERSARY_MONTH_TIMING,
}
MISSING_REASONS = {
    bo.NO_FOLLOWUP_INTERVIEW, bo.INCOMPLETE_FOLLOWUP, bo.BASELINE_ROSTER_UNUSABLE,
}

# Bounds are not classifications: they show how far results could move if
# every respondent in a group of unknown outcomes had the same outcome.
OUTCOME_BOUNDS = {
    "Bound: ambiguous unknowns all births": (AMBIGUITY_REASONS, 1),
    "Bound: ambiguous unknowns all non-births": (AMBIGUITY_REASONS, 0),
    "Bound: missing-data unknowns all births": (MISSING_REASONS, 1),
    "Bound: missing-data unknowns all non-births": (MISSING_REASONS, 0),
}


def repeated_grouped_cv(train: pd.DataFrame) -> pd.DataFrame:
    """Per-fold Brier and AUC for approaches A-D.

    Folds keep households together and are stratified on the outcome. All
    preprocessing and fitting happen inside fit_and_predict on the fold's
    training part only.
    """
    records = []
    for repeat, seed in enumerate(CV_SEEDS):
        splitter = StratifiedGroupKFold(n_splits=CV_FOLDS, shuffle=True, random_state=seed)
        folds = splitter.split(train, train["outcome"], groups=train["household_id"])
        for fold, (fit_rows, validation_rows) in enumerate(folds):
            fit, validation = train.iloc[fit_rows], train.iloc[validation_rows]
            if set(fit["household_id"]) & set(validation["household_id"]):
                raise ValueError("Household split across cross-validation folds")
            y = validation["outcome"].to_numpy()
            for name, p in ac.fit_and_predict(fit, validation).items():
                records.append({
                    "repeat": repeat,
                    "fold": fold,
                    "model": name,
                    "n_fit": len(fit),
                    "n_validation": len(validation),
                    "brier": brier_score_loss(y, p),
                    "auc": roc_auc_score(y, p) if name != "A" else np.nan,
                })
    return pd.DataFrame(records)


def corrected_resampled_interval(differences, n_fit: float, n_validation: float,
                                 level: float = 0.95) -> tuple[float, float, float]:
    """Mean difference with a Nadeau-Bengio corrected resampled-t interval.

    Fold results share training data, so the naive standard error is too
    small; the correction inflates the variance by n_validation / n_fit. It
    is approximate: it was derived for random resampling of independent
    observations, not for household-grouped folds.
    """
    d = np.asarray(differences, dtype=float)
    k = len(d)
    standard_error = np.sqrt((1 / k + n_validation / n_fit) * d.var(ddof=1))
    t = stats.t.ppf(0.5 + level / 2, k - 1)
    return d.mean(), d.mean() - t * standard_error, d.mean() + t * standard_error


def summarise_cv(results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scores = (
        results.groupby("model")[["brier", "auc"]]
        .agg(["mean", "std", "min", "max"])
        .rename(index={k: v for k, v in ac.MODEL_LABELS.items()})
    )
    wide = results.pivot_table(index=["repeat", "fold"], columns="model",
                               values=["brier", "auc"])
    n_fit = results["n_fit"].mean()
    n_validation = results["n_validation"].mean()

    # AUC is undefined for A, and C is a monotone transform of B, so their
    # AUCs are identical by construction; only meaningful metrics are compared.
    comparisons = [
        ("D - C", "D", "C", ("brier", "auc")),
        ("C - B", "C", "B", ("brier",)),
        ("C - A", "C", "A", ("brier",)),
        ("B - A", "B", "A", ("brier",)),
    ]
    rows = []
    for label, left, right, metrics in comparisons:
        for metric in metrics:
            diff = wide[(metric, left)] - wide[(metric, right)]
            improved = diff < 0 if metric == "brier" else diff > 0
            by_repeat = diff.groupby(level="repeat").mean()
            mean, low, high = corrected_resampled_interval(diff, n_fit, n_validation)
            rows.append({
                "comparison": label,
                "metric": metric,
                "mean": mean,
                "corrected_ci_low": low,
                "corrected_ci_high": high,
                "fold_min": diff.min(),
                "fold_max": diff.max(),
                "folds_improved": f"{int(improved.sum())}/{len(diff)}",
                "repeat_mean_min": by_repeat.min(),
                "repeat_mean_max": by_repeat.max(),
            })
    return scores, pd.DataFrame(rows)


def build_scenario_outcomes(eligible: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Outcome columns under each rule scenario, indexed by respondent_id."""
    columns = ["respondent_id", "household_id", "outcome", "unknown_reason",
               "expectation_pct", "expectation_prob"]
    return {
        name: bo.build_cohort(eligible, rules)[columns].set_index("respondent_id")
        for name, rules in RULE_SCENARIOS.items()
    }


def apply_bound(primary: pd.DataFrame, reasons: set[str], value: int) -> pd.DataFrame:
    bounded = primary.copy()
    bounded.loc[bounded["unknown_reason"].isin(reasons), "outcome"] = value
    return bounded


def label_changes(primary: pd.Series, alternative: pd.Series) -> dict[str, int]:
    p = primary.astype("Int64")
    a = alternative.astype("Int64")
    return {
        "unknown_to_1": int((p.isna() & (a == 1)).sum()),
        "unknown_to_0": int((p.isna() & (a == 0)).sum()),
        "1_to_unknown": int(((p == 1) & a.isna()).sum()),
        "0_to_unknown": int(((p == 0) & a.isna()).sum()),
        "1_to_0": int(((p == 1) & (a == 0)).sum()),
        "0_to_1": int(((p == 0) & (a == 1)).sum()),
    }


def linear_calibration(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    """Intercept and slope of observed outcome regressed on stated probability.

    Perfect calibration gives intercept 0 and slope 1; a slope below 1 means
    the stated probabilities are more extreme than the outcomes support.
    """
    slope, intercept = np.polyfit(p, y, 1)
    return intercept, slope


def cross_fitted_recalibration_brier(sample: pd.DataFrame) -> tuple[float, float]:
    """Brier of the constant and of logistic recalibration, both cross-fitted."""
    splitter = StratifiedGroupKFold(n_splits=CV_FOLDS, shuffle=True,
                                    random_state=SENSITIVITY_CV_SEED)
    constant = np.empty(len(sample))
    recalibrated = np.empty(len(sample))
    for fit_rows, held_rows in splitter.split(sample, sample["outcome"],
                                             groups=sample["household_id"]):
        fit, held = sample.iloc[fit_rows], sample.iloc[held_rows]
        model = ac.stated_only_model().fit(fit[[ac.STATED]], fit["outcome"])
        constant[held_rows] = fit["outcome"].mean()
        recalibrated[held_rows] = model.predict_proba(held[[ac.STATED]])[:, 1]
    y = sample["outcome"].to_numpy()
    return brier_score_loss(y, constant), brier_score_loss(y, recalibrated)


def calibration_summary(scenario: pd.DataFrame) -> dict:
    sample = scenario[scenario["outcome"].notna()].reset_index()
    sample["outcome"] = sample["outcome"].astype(int)
    y = sample["outcome"].to_numpy()
    p = sample["expectation_prob"].to_numpy()

    intercept, slope = linear_calibration(y, p)
    slopes = [
        linear_calibration(y[rows], p[rows])[1]
        for rows in ac.household_bootstrap_indices(
            sample["household_id"], SLOPE_BOOTSTRAP, ac.BOOTSTRAP_SEED)
    ]
    constant_brier, recalibrated_brier = cross_fitted_recalibration_brier(sample)
    pct = sample["expectation_pct"]
    return {
        "n": len(sample),
        "births": int(y.sum()),
        "observed_rate": y.mean(),
        "mean_stated": p.mean(),
        "observed_at_0": y[pct == 0].mean(),
        "observed_at_50": y[pct == 50].mean(),
        "observed_at_100": y[pct == 100].mean(),
        "intercept": intercept,
        "slope": slope,
        "slope_ci": tuple(np.percentile(slopes, [2.5, 97.5])),
        "brier_stated": brier_score_loss(y, p),
        "brier_constant_cv": constant_brier,
        "brier_recalibrated_cv": recalibrated_brier,
        "auc_stated": roc_auc_score(y, p),
    }


def finding_holds(summary: dict) -> dict[str, bool]:
    """Pre-specified checks of the calibration finding."""
    return {
        "too_extreme": summary["slope_ci"][1] < 1,
        "overestimates_on_average": summary["mean_stated"] > summary["observed_rate"],
        "recalibration_improves": summary["brier_recalibrated_cv"] < summary["brier_stated"],
    }


def sensitivity_table(eligible: pd.DataFrame) -> pd.DataFrame:
    scenarios = build_scenario_outcomes(eligible)
    primary = scenarios["Primary definition"]
    for name, (reasons, value) in OUTCOME_BOUNDS.items():
        scenarios[name] = apply_bound(primary, reasons, value)

    rows = []
    for name, scenario in scenarios.items():
        changes = label_changes(primary["outcome"], scenario["outcome"])
        summary = calibration_summary(scenario)
        checks = finding_holds(summary)
        rows.append({
            "scenario": name,
            "kind": "bound" if name.startswith("Bound") else "rule",
            "labels_changed": sum(changes.values()),
            **changes,
            **summary,
            **checks,
            "finding_holds": all(checks.values()),
        })
    return pd.DataFrame(rows)


def weighted_expectation_summary(cohort: pd.DataFrame) -> pd.DataFrame:
    """Round 13 cross-sectional description of stated expectations.

    SAMPLING_WEIGHT_CC applies to Round 13 participants, so it supports
    cross-sectional description of the 2009-10 expectation among eligible
    women. It does not adjust for later attrition or for item nonresponse to
    the expectation question, and no design-based standard errors are
    possible without VSTRAT and VPSU.
    """
    pct = cohort["expectation_pct"]
    weights = cohort["sampling_weight_2009"]
    if (weights <= 0).any():
        raise ValueError("Non-positive Round 13 weight among eligible women")
    measures = {
        "Mean stated probability (%)": pct,
        "Share stating 0%": 100 * (pct == 0),
        "Share stating 50%": 100 * (pct == 50),
        "Share stating 100%": 100 * (pct == 100),
    }
    return pd.DataFrame({
        "unweighted": {k: v.mean() for k, v in measures.items()},
        "round_13_weighted": {k: np.average(v, weights=weights) for k, v in measures.items()},
    })


def held_out_reference(sample: pd.DataFrame) -> pd.Series:
    train, test = ac.household_split(sample)
    predictions = ac.fit_and_predict(train, test)
    y = test["outcome"].to_numpy()
    return pd.Series({name: brier_score_loss(y, p) for name, p in predictions.items()})


def qualifying_birth_timing(eligible: pd.DataFrame, cohort: pd.DataFrame) -> pd.DataFrame:
    """Months from the baseline interview to the first and last qualifying birth.

    Covers confirmed positives only, using the follow-up rounds that
    supported each label. Indexed by respondent_id.
    """
    rounds_used = cohort[cohort["outcome"] == 1].set_index("respondent_id")["followup_rounds_used"]
    records = {}
    for _, row in eligible[eligible[RESPONDENT_ID].isin(rounds_used.index)].iterrows():
        baseline = int(row[INTERVIEW_MONTH[BASELINE_ROUND]])
        offsets = []
        for year in map(int, rounds_used[row[RESPONDENT_ID]].split("+")):
            roster = assess_roster([row[c] for c in CHILD_BIRTH_MONTH[year]],
                                   row[INTERVIEW_MONTH[year]])
            offsets += [b - baseline for b in roster["births"]
                        if baseline < b < baseline + bo.WINDOW_MONTHS]
        records[row[RESPONDENT_ID]] = (min(offsets), max(offsets))
    return pd.DataFrame.from_dict(records, orient="index",
                                  columns=["first_birth_month", "last_birth_month"])


def early_birth_mask(index: pd.Index, timing: pd.DataFrame, months: int) -> pd.Series:
    first = timing["first_birth_month"].reindex(index)
    return (first <= months).fillna(False).astype(bool)


def later_birth_outcome(index: pd.Index, timing: pd.DataFrame) -> pd.Series:
    last = timing["last_birth_month"].reindex(index)
    return (last > EARLY_BIRTH_MONTHS).fillna(False).astype(int)


def early_birth_scenarios(primary: pd.DataFrame, timing: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Labelled sample with early births excluded, or with the outcome redefined.

    Both alternatives are biased sensitivity bounds, not estimates of the
    effect of a known pregnancy. Exclusion removes only women whose
    pregnancy ended in an observed live birth; women pregnant at interview
    whose pregnancy did not produce a live birth in the window stay in. The
    redefined outcome counts only births after the early months, so women
    whose only qualifying birth was early become non-events.
    """
    labelled = primary[primary["outcome"].notna()]
    scenarios = {"All labelled women (primary)": labelled}
    for months in EARLY_BIRTH_THRESHOLDS:
        early = early_birth_mask(labelled.index, timing, months)
        scenarios[f"Exclude first births within {months} months"] = labelled[~early]
    later = labelled.copy()
    later["outcome"] = later_birth_outcome(later.index, timing)
    scenarios[f"Outcome: births in months {EARLY_BIRTH_MONTHS + 1}-59 only"] = later
    return scenarios


def early_birth_by_answer(primary: pd.DataFrame, timing: pd.DataFrame) -> pd.DataFrame:
    labelled = primary[primary["outcome"].notna()]
    early = early_birth_mask(labelled.index, timing, EARLY_BIRTH_MONTHS)
    pct = labelled["expectation_pct"]
    groups = {"0%": pct == 0, "1-49%": pct.between(1, 49), "50%": pct == 50,
              "51-99%": pct.between(51, 99), "100%": pct == 100}
    rows = {}
    for name, mask in groups.items():
        births, n_early, women = int(labelled.loc[mask, "outcome"].sum()), int(early[mask].sum()), int(mask.sum())
        rows[name] = {
            "women": women,
            "births": births,
            "early_births": n_early,
            "early_share_of_births": n_early / births,
            "birth_rate": births / women,
            "birth_rate_excluding_early": (births - n_early) / (women - n_early),
        }
    return pd.DataFrame(rows).T


def early_birth_table(primary: pd.DataFrame, timing: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, scenario in early_birth_scenarios(primary, timing).items():
        summary = calibration_summary(scenario)
        checks = finding_holds(summary)
        rows.append({"scenario": name, **summary, **checks, "finding_holds": all(checks.values())})
    return pd.DataFrame(rows)


def held_out_comparison(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """Held-out scores and paired differences, re-fitting the existing models A-D."""
    results = ac.evaluate_baselines(test, ac.fit_and_predict(train, test))
    return {
        "test_n": len(test),
        "test_births": int(test["outcome"].sum()),
        **{f"brier_{k}": results.loc[k, "brier"] for k in "ABCD"},
        **{f"auc_{k}": results.loc[k, "auc"] for k in "BCD"},
        "c_minus_b_brier": results.loc["C", "brier_diff_vs_B"],
        "c_minus_b_brier_ci": results.loc["C", "brier_diff_vs_B_ci"],
        "d_minus_c_brier": results.loc["D", "brier_diff_vs_C"],
        "d_minus_c_brier_ci": results.loc["D", "brier_diff_vs_C_ci"],
        "d_minus_c_auc": results.loc["D", "auc_diff_vs_C"],
        "d_minus_c_auc_ci": results.loc["D", "auc_diff_vs_C_ci"],
    }


def held_out_sensitivity(sample: pd.DataFrame, timing: pd.DataFrame,
                         strict_outcome: pd.Series) -> pd.DataFrame:
    """Held-out comparison on the original household split under alternative labels.

    Women keep their original train or test assignment; excluded women are
    dropped from whichever side they were on.
    """
    train, test = ac.household_split(sample)
    rows = [{"scenario": "All labelled women (primary)", **held_out_comparison(train, test)}]

    def keep(frame, mask):
        return frame[mask.to_numpy()].reset_index(drop=True)

    rows.append({"scenario": f"Exclude first births within {EARLY_BIRTH_MONTHS} months",
                 **held_out_comparison(
                     *(keep(f, ~early_birth_mask(pd.Index(f["respondent_id"]), timing,
                                                 EARLY_BIRTH_MONTHS)) for f in (train, test)))})
    later = [f.assign(outcome=later_birth_outcome(pd.Index(f["respondent_id"]), timing).to_numpy())
             for f in (train, test)]
    rows.append({"scenario": f"Outcome: births in months {EARLY_BIRTH_MONTHS + 1}-59 only",
                 **held_out_comparison(*later)})
    strict = []
    for frame in (train, test):
        relabelled = frame.assign(outcome=frame["respondent_id"].map(strict_outcome))
        relabelled = keep(relabelled, relabelled["outcome"].notna())
        strict.append(relabelled.assign(outcome=relabelled["outcome"].astype(int)))
    rows.append({"scenario": "Strict date reconciliation of pre-baseline births",
                 **held_out_comparison(*strict)})
    return pd.DataFrame(rows)


def main() -> None:
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 30)
    cohort = ac.load_cohort()
    ac.validate_cohort(cohort)
    sample = ac.labelled_sample(cohort)
    train, _ = ac.household_split(sample)

    print("THE INTENTION GAP | ROBUSTNESS CHECKS")
    print("=" * 72)

    print(f"\nRepeated household-grouped CV inside the held-out split training partition "
          f"({len(train):,} women, {train['household_id'].nunique():,} households; "
          f"{len(CV_SEEDS)} repeats x {CV_FOLDS} folds)")
    cv_results = repeated_grouped_cv(train)
    scores, comparisons = summarise_cv(cv_results)
    print(scores.round(4).to_string())
    print("\nPaired differences across folds (row - reference; Brier < 0 and AUC > 0 favour row)")
    print(comparisons.round(4).to_string(index=False))
    print("\nHeld-out Brier for reference: "
          + ", ".join(f"{k} {v:.4f}" for k, v in held_out_reference(sample).items()))

    print("\nOutcome-definition sensitivity (descriptive, all labelled women per scenario)")
    eligible, _ = bo.load_eligible()
    table = sensitivity_table(eligible)
    change_columns = ["scenario", "kind", "labels_changed", "unknown_to_1", "unknown_to_0",
                      "1_to_unknown", "0_to_unknown", "1_to_0", "0_to_1", "n", "births"]
    print(table[change_columns].to_string(index=False))
    metric_columns = ["scenario", "observed_rate", "mean_stated", "observed_at_0",
                      "observed_at_50", "observed_at_100", "slope", "slope_ci",
                      "brier_stated", "brier_constant_cv", "brier_recalibrated_cv",
                      "auc_stated", "finding_holds"]
    formatted = table[metric_columns].copy()
    formatted["slope_ci"] = formatted["slope_ci"].map(lambda ci: f"[{ci[0]:.3f}, {ci[1]:.3f}]")
    print()
    print(formatted.round(3).to_string(index=False))

    print(f"\nEarly-birth sensitivity: first qualifying birth within {EARLY_BIRTH_MONTHS} months "
          "of the interview (proxy for possible pregnancy at interview; biased bounds)")
    primary = cohort.set_index("respondent_id")
    timing = qualifying_birth_timing(eligible, cohort)
    for months in EARLY_BIRTH_THRESHOLDS:
        print(f"  Within {months} months: "
              f"{int((timing['first_birth_month'] <= months).sum())} of {len(timing):,} confirmed births")
    print(early_birth_by_answer(primary, timing).round(3).to_string())
    early = early_birth_table(primary, timing)
    early["slope_ci"] = early["slope_ci"].map(lambda ci: f"[{ci[0]:.3f}, {ci[1]:.3f}]")
    print()
    print(early[["scenario"] + metric_columns[1:]].round(3).to_string(index=False))

    strict_rules = RULE_SCENARIOS["Strict date reconciliation of pre-baseline births"]
    strict_outcome = bo.build_cohort(eligible, strict_rules).set_index("respondent_id")["outcome"]
    held = held_out_sensitivity(sample, timing, strict_outcome)
    for column in ("c_minus_b_brier_ci", "d_minus_c_brier_ci", "d_minus_c_auc_ci"):
        held[column] = held[column].map(lambda ci: f"[{ci[0]:+.4f}, {ci[1]:+.4f}]")
    print("\nHeld-out comparison on the original household split, by label scenario")
    print(held.round(4).T.to_string(header=False))

    print("\nRound 13 cross-sectional description, all eligible women "
          f"(n = {len(cohort):,}; point estimates only)")
    print(weighted_expectation_summary(cohort).round(1).to_string())


if __name__ == "__main__":
    main()
