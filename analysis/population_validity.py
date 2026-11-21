"""Selection, attrition and subgroup checks for the calibration findings.

- Reconciles the frozen primary cohort, the pregnancy classification and
  the conservative expanded cohort written by analysis.expanded_histories.
- Compares women with known and unknown outcomes on baseline information.
- Brackets the effect of unknown outcomes on the calibration findings with
  deterministic bounds (worst case) and with model-based estimates that
  hold only under stated assumptions (missing at random given baseline
  information, or a fixed departure from it).
- Describes results separately for women with and without children at
  baseline.

All estimates are unweighted and describe the sample. Only aggregate
results are printed.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from analysis import analyze_calibration as ac
from analysis import expanded_histories as eh
from analysis import pregnancy_status as ps
from analysis import robustness_analysis as rb

EXPECTED = {
    "pregnancy": {ps.PREGNANT: 187, ps.NOT_PREGNANT: 3418, ps.UNKNOWN: 55},
    "outcome": {"positive": 1234, "negative": 2170, "unknown": 256},
    "outcome_conservative": {"positive": 1249, "negative": 2202, "unknown": 209},
}
SELECTION_BOOTSTRAP = 1000
RESPONSE_CV_FOLDS = 5
RESPONSE_CV_SEEDS = tuple(range(101, 111))
IPW_BOOTSTRAP = 500
DELTAS = (-1.0, -0.5, 0.5, 1.0)
PARITY_GROUPS = {"No children at baseline": lambda f: f["parity_at_baseline"] == 0,
                 "One or more children": lambda f: f["parity_at_baseline"] >= 1}
MARITAL_LABELS = {0: "never married", 1: "married", 2: "separated", 3: "divorced",
                  4: "widowed"}
RACE_LABELS = {1: "Black", 2: "Hispanic", 3: "Mixed race (non-Hispanic)",
               4: "Non-Black, non-Hispanic"}
PROPENSITY_NUMERIC = ["expectation_prob", "age_at_baseline", "parity_at_baseline",
                      "highest_grade_2009"]
PROPENSITY_CATEGORICAL = ["marital_status_2009", "race_ethnicity", "cross_sectional_sample",
                          "pregnancy_status"]


def load_frame() -> pd.DataFrame:
    """Primary cohort with pregnancy status and expanded labels, by respondent_id."""
    if not eh.OUTPUT_PATH.exists():
        raise SystemExit("Run python -m analysis.expanded_histories first.")
    cohort = ac.load_cohort()
    ac.validate_cohort(cohort)
    expanded = pd.read_csv(eh.OUTPUT_PATH, index_col="respondent_id")
    frame = cohort.set_index("respondent_id")
    if not expanded["outcome_primary"].equals(frame["outcome"].reindex(expanded.index)):
        raise ValueError("Expanded file does not carry the frozen primary labels")
    columns = ["outcome_conservative", "reason_conservative", "revision_conservative",
               "pregnancy_status", "complete_rounds_used", "interim_rounds_used",
               "flag_interim_conflict", "flag_window_discrepancy"]
    return frame.join(expanded[columns], how="left")


def outcome_counts(series: pd.Series) -> dict:
    return {"positive": int((series == 1).sum()), "negative": int((series == 0).sum()),
            "unknown": int(series.isna().sum())}


def reconcile(frame: pd.DataFrame) -> dict:
    """Recount every headline total from the files; raise if any differs from M04.3."""
    found = {
        "pregnancy": frame["pregnancy_status"].value_counts().to_dict(),
        "outcome": outcome_counts(frame["outcome"]),
        "outcome_conservative": outcome_counts(frame["outcome_conservative"]),
    }
    for key, expected in EXPECTED.items():
        if found[key] != expected:
            raise ValueError(f"{key}: found {found[key]}, expected {expected}")
    primary_unknown = frame["outcome"].isna()
    revised_unknown = frame["outcome_conservative"].isna()
    found["unknown_breakdown"] = {
        "originally unknown, still unknown": int((primary_unknown & revised_unknown).sum()),
        "confirmed, now unknown": int((~primary_unknown & revised_unknown).sum()),
        "originally unknown, now resolved": int((primary_unknown & ~revised_unknown).sum()),
        "labels reversed": int((frame["outcome"].notna() & frame["outcome_conservative"].notna()
                                & (frame["outcome"] != frame["outcome_conservative"])).sum()),
    }
    return found


def agreement_denominators(eligible: pd.DataFrame) -> pd.DataFrame:
    """Cross-round agreement over all women and over women with children in the earlier roster."""
    rows = []
    for earlier, later in eh.ADJACENT_PAIRS:
        both = identical = with_children = identical_with_children = 0
        for _, row in eligible.iterrows():
            rosters, interviews = eh.row_rosters(row)
            e = eh.assess_roster(rosters[earlier], interviews[earlier])
            l = eh.assess_roster(rosters[later], interviews[later])
            if not (e["usable"] and l["usable"]):
                continue
            same = eh.compare_rosters(e["births"], interviews[earlier],
                                      l["births"])["category"] == eh.IDENTICAL
            both += 1
            identical += same
            if e["n_births"]:
                with_children += 1
                identical_with_children += same
        rows.append({"pair": f"{earlier}->{later}", "both_usable": both,
                     "identical_pct": 100 * identical / both,
                     "earlier_roster_has_children": with_children,
                     "identical_pct_among_those": 100 * identical_with_children / with_children})
    return pd.DataFrame(rows)


def interim_agreement(frame: pd.DataFrame) -> dict:
    """Denominator for the interim-roster window check."""
    interim = frame["interim_rounds_used"].fillna("")
    complete = frame["complete_rounds_used"].fillna("")
    checked = (interim != "") & ((complete != "") | interim.str.contains(r"\+"))
    discrepancy = frame["flag_window_discrepancy"].astype(bool)
    conflict = frame["flag_interim_conflict"].astype(bool)
    return {"women with an interim roster and a later roster": int(checked.sum()),
            "window discrepancy": int((checked & discrepancy).sum()),
            "interim conflict with 2009": int(((interim != "") & conflict).sum()),
            "either": int((checked & (discrepancy | conflict)).sum())}


def baseline_variables(frame: pd.DataFrame) -> pd.DataFrame:
    """Baseline characteristics as numeric columns or 0/1 indicators (NaN where missing)."""
    pct = frame["expectation_pct"]
    parity = frame["parity_at_baseline"].astype(float)
    marital = frame["marital_status_2009"]
    columns = {
        "Stated chance (%)": pct,
        "Stated 0%": (pct == 0).astype(float),
        "Stated 50%": (pct == 50).astype(float),
        "Stated 100%": (pct == 100).astype(float),
        "Age at baseline (years)": frame["age_at_baseline"],
        "Biological children at baseline": parity,
        "No children at baseline": (parity == 0).astype(float).where(parity.notna()),
        "Secondary-school grade (5-12)": frame["highest_grade_2009"].astype(float),
        **{f"Marital: {label}": (marital == code).astype(float).where(marital.notna())
           for code, label in MARITAL_LABELS.items() if code != 4},
        **{f"Race/ethnicity: {label}": (frame["race_ethnicity"] == code).astype(float)
           for code, label in RACE_LABELS.items()},
        "Cross-sectional sample": frame["cross_sectional_sample"].astype(float),
        "Reported pregnant": (frame["pregnancy_status"] == ps.PREGNANT).astype(float),
        "Pregnancy status unknown": (frame["pregnancy_status"] == ps.UNKNOWN).astype(float),
    }
    return pd.DataFrame(columns, index=frame.index)


def selection_table(frame: pd.DataFrame, outcome_column: str) -> pd.DataFrame:
    """Known vs unknown outcomes: means, difference with household-bootstrap CI, and SMD."""
    values = baseline_variables(frame).to_numpy(dtype=float)
    unknown = frame[outcome_column].isna().to_numpy()

    def means(rows):
        v, u = values[rows], unknown[rows]
        return np.nanmean(v[~u], axis=0), np.nanmean(v[u], axis=0)

    known_mean, unknown_mean = means(np.arange(len(frame)))
    differences = np.array([np.subtract(*means(rows)[::-1]) for rows in
                            ac.household_bootstrap_indices(frame["household_id"],
                                                           SELECTION_BOOTSTRAP,
                                                           ac.BOOTSTRAP_SEED)])
    pooled_sd = np.sqrt((np.nanvar(values[~unknown], axis=0, ddof=1)
                         + np.nanvar(values[unknown], axis=0, ddof=1)) / 2)
    table = pd.DataFrame({
        "known_n": (~np.isnan(values[~unknown])).sum(axis=0),
        "unknown_n": (~np.isnan(values[unknown])).sum(axis=0),
        "known": known_mean,
        "unknown": unknown_mean,
        "difference": unknown_mean - known_mean,
        # A replicate that draws no known or no unknown women has no difference.
        "ci_low": np.nanpercentile(differences, 2.5, axis=0),
        "ci_high": np.nanpercentile(differences, 97.5, axis=0),
        "smd": (unknown_mean - known_mean) / pooled_sd,
    }, index=baseline_variables(frame.iloc[:1]).columns)
    return table


def propensity_model():
    numeric = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler())
    categorical = make_pipeline(SimpleImputer(strategy="constant", fill_value=-1),
                                OneHotEncoder(handle_unknown="ignore"))
    return make_pipeline(
        ColumnTransformer([("numeric", numeric, PROPENSITY_NUMERIC),
                           ("categorical", categorical, PROPENSITY_CATEGORICAL)]),
        LogisticRegression(max_iter=1000))


def propensity_features(frame: pd.DataFrame) -> pd.DataFrame:
    features = frame[PROPENSITY_NUMERIC + PROPENSITY_CATEGORICAL].copy()
    for column in PROPENSITY_NUMERIC:
        features[column] = features[column].astype(float)
    features["pregnancy_status"] = features["pregnancy_status"].map(
        {s: k for k, s in enumerate(ps.STATUSES)})
    return features


def calibration_measures(y: np.ndarray, p: np.ndarray, weights=None) -> dict:
    """Calibration measures that accept fractional outcomes and analytic weights."""
    w = np.ones_like(p) if weights is None else np.asarray(weights, dtype=float)

    def rate(mask):
        return np.average(y[mask], weights=w[mask]) if mask.any() else np.nan

    slope, intercept = np.polyfit(p, y, 1, w=np.sqrt(w))
    observed, stated = np.average(y, weights=w), np.average(p, weights=w)
    return {"observed_rate": observed, "mean_stated": stated, "overestimate": stated - observed,
            "observed_at_0": rate(p == 0), "observed_at_50": rate(p == 0.5),
            "observed_at_100": rate(p == 1), "slope": slope,
            "brier": np.average(y * (1 - p) ** 2 + (1 - y) * p ** 2, weights=w)}


def inverse_probability_estimates(frame: pd.DataFrame, outcome_column: str) -> dict:
    """Calibration among labelled women reweighted by 1 / P(outcome known | baseline).

    Valid only if outcomes are missing at random given the propensity
    variables. The household bootstrap refits the propensity model in each
    replicate.
    """
    features = propensity_features(frame)
    known = frame[outcome_column].notna().to_numpy()
    y_all = frame[outcome_column].to_numpy(dtype=float)
    p_all = frame["expectation_prob"].to_numpy()

    def estimate(rows):
        model = propensity_model().fit(features.iloc[rows], known[rows])
        probability = model.predict_proba(features.iloc[rows])[:, 1]
        keep = known[rows]
        return calibration_measures(y_all[rows][keep], p_all[rows][keep],
                                    1 / probability[keep]), probability

    point, probability = estimate(np.arange(len(frame)))
    replicates = pd.DataFrame([estimate(rows)[0] for rows in ac.household_bootstrap_indices(
        frame["household_id"], IPW_BOOTSTRAP, ac.BOOTSTRAP_SEED)])
    return {
        "point": point,
        "ci": {k: tuple(np.percentile(replicates[k].dropna(), [2.5, 97.5])) for k in point},
        "propensity_auc": roc_auc_score(known, probability),
        "max_weight": float((1 / probability[known]).max()),
        "min_probability": float(probability.min()),
    }


def cross_validated_response_auc(frame: pd.DataFrame, outcome_column: str,
                                 seeds=RESPONSE_CV_SEEDS, n_splits=RESPONSE_CV_FOLDS) -> dict:
    """Out-of-fold AUC of the response model, with households kept within one fold.

    The in-sample AUC reported by inverse_probability_estimates scores the
    model on the women it was fitted to; this is the corresponding
    held-out estimate, repeated over several fold assignments.
    """
    features = propensity_features(frame)
    known = frame[outcome_column].notna().to_numpy()
    groups = frame["household_id"].to_numpy()
    aucs = []
    for seed in seeds:
        folds = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        out_of_fold = np.empty(len(frame))
        for train, test in folds.split(features, known, groups):
            model = propensity_model().fit(features.iloc[train], known[train])
            out_of_fold[test] = model.predict_proba(features.iloc[test])[:, 1]
        aucs.append(roc_auc_score(known, out_of_fold))
    return {"mean": float(np.mean(aucs)), "min": float(np.min(aucs)),
            "max": float(np.max(aucs)), "repeats": len(aucs)}


def missing_outcome_scenarios(frame: pd.DataFrame, outcome_column: str) -> pd.DataFrame:
    """Calibration measures when unknown outcomes are filled under stated assumptions."""
    y = frame[outcome_column].to_numpy(dtype=float)
    p = frame["expectation_prob"].to_numpy()
    unknown = np.isnan(y)
    labelled = frame[~unknown].assign(outcome=y[~unknown].astype(int))
    model = ac.covariate_model().fit(labelled[ac.MODEL_D_FEATURES], labelled["outcome"])
    predicted = model.predict_proba(frame[ac.MODEL_D_FEATURES])[:, 1]
    logit = np.log(predicted / (1 - predicted))
    above_mean = (p > p.mean()).astype(float)

    fills = {
        "Complete cases (unknowns excluded)": None,
        "Worst case: every unknown had a birth": np.ones(len(y)),
        "Worst case: no unknown had a birth": np.zeros(len(y)),
        "Extreme: births only where stated chance above mean": above_mean,
        "Extreme: births only where stated chance at or below mean": 1 - above_mean,
        "Model: missing at random given baseline (model D)": predicted,
        **{f"Model: odds of a birth x{np.exp(d):.2f} among unknowns": 1 / (1 + np.exp(-(logit + d)))
           for d in DELTAS},
    }
    rows = []
    for name, fill in fills.items():
        if fill is None:
            measures = calibration_measures(y[~unknown], p[~unknown])
            n = int((~unknown).sum())
        else:
            measures = calibration_measures(np.where(unknown, fill, y), p)
            n = len(y)
        rows.append({"scenario": name, "kind": name.split(":")[0], "n": n, **measures,
                     "too_extreme": measures["slope"] < 1,
                     "overestimates_on_average": measures["overestimate"] > 0})
    return pd.DataFrame(rows)


def eligible_population_shares(frame: pd.DataFrame) -> pd.DataFrame:
    """Race/ethnicity and sample-type shares: sample, Round 13 weighted, labelled."""
    weights = frame["sampling_weight_2009"]
    labelled = frame["outcome"].notna()
    rows = {}
    for code, label in RACE_LABELS.items():
        x = (frame["race_ethnicity"] == code).astype(float)
        rows[label] = (x.mean(), np.average(x, weights=weights), x[labelled].mean())
    x = frame["cross_sectional_sample"].astype(float)
    rows["Cross-sectional sample"] = (x.mean(), np.average(x, weights=weights), x[labelled].mean())
    return 100 * pd.DataFrame(rows, index=["eligible_unweighted", "eligible_round13_weighted",
                                           "labelled_unweighted"]).T


def weighted_illustration(frame: pd.DataFrame) -> pd.DataFrame:
    """Calibration of labelled women under illustrative weights; point estimates only.

    The Round 13 weight describes Round 13 participants, not the labelled
    sample, and no design-based variance is possible without VSTRAT and
    VPSU. Multiplying it by an inverse response propensity shows only
    whether composition could move the estimates; it is not a population
    estimate.
    """
    labelled = frame["outcome"].notna().to_numpy()
    model = propensity_model().fit(propensity_features(frame), labelled)
    response = model.predict_proba(propensity_features(frame))[:, 1]
    y = frame["outcome"].to_numpy(dtype=float)[labelled]
    p = frame["expectation_prob"].to_numpy()[labelled]
    round13 = frame["sampling_weight_2009"].to_numpy()[labelled]
    parity = frame["parity_at_baseline"].to_numpy(dtype=float)[labelled]
    rows = {
        "Unweighted": calibration_measures(y, p),
        "Round 13 weight": calibration_measures(y, p, round13),
        "Round 13 weight / response propensity": calibration_measures(
            y, p, round13 / response[labelled]),
    }
    for name, mask in (("No children, Round 13 weight", parity == 0),
                       ("One or more children, Round 13 weight", parity >= 1)):
        rows[name] = calibration_measures(y[mask], p[mask], round13[mask])
    return pd.DataFrame(rows).T


def parenthood_description(frame: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for name, select in PARITY_GROUPS.items():
        group = frame[select(frame).fillna(False).to_numpy(dtype=bool)]
        pct = group["expectation_pct"]
        rows[name] = {
            "women": len(group), "mean_stated_pct": pct.mean(),
            "share_0_pct": 100 * (pct == 0).mean(), "share_50_pct": 100 * (pct == 50).mean(),
            "share_100_pct": 100 * (pct == 100).mean(),
            "pregnant_pct": 100 * (group["pregnancy_status"] == ps.PREGNANT).mean(),
            "pregnancy_unknown_pct": 100 * (group["pregnancy_status"] == ps.UNKNOWN).mean(),
            "outcome_unknown_pct": 100 * group["outcome"].isna().mean(),
            "labelled": int(group["outcome"].notna().sum()),
            "births": int((group["outcome"] == 1).sum()),
        }
    rows["Baseline roster unusable"] = {"women": int(frame["parity_at_baseline"].isna().sum())}
    return pd.DataFrame(rows).T


def parenthood_performance(frame: pd.DataFrame) -> pd.DataFrame:
    labelled = frame[frame["outcome"].notna()].copy()
    labelled["outcome"] = labelled["outcome"].astype(int)
    rows = []
    for name, select in PARITY_GROUPS.items():
        group = labelled[select(labelled).to_numpy(dtype=bool)]
        for restriction, subset in (("all labelled", group),
                                    ("confirmed not pregnant",
                                     group[group["pregnancy_status"] == ps.NOT_PREGNANT])):
            rows.append({"group": name, "restriction": restriction,
                         **ps.subgroup_summary(subset)})
    return pd.DataFrame(rows)


def parenthood_held_out(sample: pd.DataFrame) -> pd.DataFrame:
    """M02 models (fitted on the whole M02 training partition) scored on each subgroup's test women."""
    train, test = ac.household_split(sample)
    rows = [{"group": "All test women", **rb.held_out_comparison(train, test)}]
    for name, select in PARITY_GROUPS.items():
        subset = test[select(test).to_numpy(dtype=bool)].reset_index(drop=True)
        rows.append({"group": name, **rb.held_out_comparison(train, subset)})
    return pd.DataFrame(rows)


def format_ci(ci) -> str:
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]" if isinstance(ci, tuple) else ""


def main() -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    frame = load_frame()
    print("THE INTENTION GAP | POPULATION VALIDITY AND SELECTION")
    print("=" * 72)

    print("\nReconciliation (all totals recomputed from the files)")
    for key, value in reconcile(frame).items():
        print(f"  {key}: {value}")
    _, eligible, _ = ps.load_pregnancy_frame()
    print("\nCross-round agreement: denominators")
    print(agreement_denominators(eligible).round(2).to_string(index=False))
    print(f"  Interim-roster window check: {interim_agreement(frame)}")

    for column, title in (("outcome", "primary"), ("outcome_conservative", "conservative expanded")):
        print(f"\nKnown vs unknown outcomes, {title} cohort (unknown minus known; "
              "household bootstrap 95% CI)")
        print(selection_table(frame, column).round(3).to_string())

    print("\nComposition: eligible women (unweighted, Round 13 weighted) and labelled women (%)")
    print(eligible_population_shares(frame).round(1).to_string())

    for column, title in (("outcome", "primary"), ("outcome_conservative", "conservative expanded")):
        print(f"\nMissing-outcome scenarios, {title} cohort")
        print(missing_outcome_scenarios(frame, column).round(3).to_string(index=False))
        ipw = inverse_probability_estimates(frame, column)
        cv = cross_validated_response_auc(frame, column)
        print(f"  Inverse-probability weighting (missing at random given baseline): "
              f"response-model AUC {ipw['propensity_auc']:.3f} in-sample, "
              f"{cv['mean']:.3f} cross-validated ({RESPONSE_CV_FOLDS}-fold by household, "
              f"{cv['repeats']} repeats, range {cv['min']:.3f}-{cv['max']:.3f}), "
              f"largest weight {ipw['max_weight']:.2f}")
        for key, value in ipw["point"].items():
            print(f"    {key:<16} {value:.3f} {format_ci(ipw['ci'][key])}")

    print("\nIllustrative weighted calibration of labelled women (point estimates only; "
          "not population estimates)")
    print(weighted_illustration(frame).round(3).to_string())

    print("\nBaseline parenthood: description of all eligible women")
    print(parenthood_description(frame).round(1).to_string())
    print("\nBaseline parenthood: stated-forecast performance")
    table = parenthood_performance(frame)
    for column in ("slope_ci", "brier_ci", "auc_ci"):
        table[column] = table[column].map(format_ci)
    columns = ["group", "restriction", "n", "births", "observed_rate", "mean_stated",
               "observed_at_0", "observed_at_50", "observed_at_100", "slope", "slope_ci",
               "brier_stated", "brier_ci", "brier_constant_cv", "brier_recalibrated_cv",
               "auc_stated", "auc_ci", "too_extreme", "overestimates_on_average",
               "recalibration_improves"]
    print(table[columns].round(3).T.to_string(header=False))
    labelled = frame[frame["outcome"].notna()].assign(
        outcome=lambda f: f["outcome"].astype(int))
    for name, select in PARITY_GROUPS.items():
        print(f"\nCalibration at 0, 50 and 100%: {name} (Wilson 95% intervals)")
        print(ps.calibration_points(labelled[select(labelled).to_numpy(dtype=bool)])
              .round(1).to_string())
    print("\nBaseline parenthood: held-out comparison (M02 split and M02 models)")
    held = parenthood_held_out(ac.labelled_sample(ac.load_cohort()))
    for column in ("c_minus_b_brier_ci", "d_minus_c_brier_ci", "d_minus_c_auc_ci"):
        held[column] = held[column].map(lambda ci: f"[{ci[0]:+.4f}, {ci[1]:+.4f}]")
    print(held.round(4).T.to_string(header=False))


if __name__ == "__main__":
    main()
