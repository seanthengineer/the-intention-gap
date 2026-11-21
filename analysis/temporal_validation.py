"""Out-of-period validation of the frozen 2009 models on the 2015-16 baseline.

The evaluation protocol is fixed in docs/methodology.md, section 12, before
any later outcome is examined. In brief:

- Models A-D are rebuilt from the frozen M02 implementation (same cohort,
  household split, preprocessing and seeds) and checked against the stored
  parameter fingerprint in docs/frozen_model_parameters.json. Nothing is
  refitted or recalibrated on later data.
- Later baseline: the Round 17 interview (October 2015 to August 2016) and
  its YFER-4861 answer. Features are measured at that interview.
- Later outcome: a birth in months B+1 to B+59, using the primary rules of
  build_outcomes unchanged. Only Round 20 (2021) and Round 21 (2023)
  rosters can be collected after every Round 17 anniversary; the 2017 and
  2019 rosters all precede it and are not used. Uncertain outcomes stay
  unknown and are never scored.
- Setting A scores every eligible woman; setting B only women whose
  household contributed nobody to the M02 training partition.

The later variables are located by question name and survey year in the
NLS Investigator codebook of the temporal extract, so no reference number
is assumed. Without that extract the module reports the frozen models, the
baseline comparison that needs no later outcome, and the missing items, and
stops. Only aggregate results are printed.

Run from the project root:  python -m analysis.temporal_validation
"""

import json
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from analysis import analyze_calibration as ac
from analysis import build_outcomes as bo
from analysis import supplement_extract as se
from analysis.nlsy97 import (
    BIRTH_MONTH, BIRTH_YEAR, CHILD_BIRTH_MONTH, EXPECTATION, FEMALE, HOUSEHOLD_ID,
    INTERVIEW_MONTH, PROJECT_ROOT, RAW_DATA_PATH, RESPONDENT_ID, SEX, assess_roster,
    cmonth_from_date,
)

TEMPORAL_PATH = PROJECT_ROOT / "data" / "raw" / "intention_gap_nlsy97_temporal.csv"
TEMPORAL_CODEBOOK = TEMPORAL_PATH.with_suffix(".cdb")
PARAMETERS_PATH = PROJECT_ROOT / "docs" / "frozen_model_parameters.json"

LATER_BASELINE = 2015
LATER_FOLLOWUP = (2021, 2023)
BOOTSTRAP_SEED = 2015
N_BOOTSTRAP = 2000
PARAMETER_TOLERANCE = 1e-8

# (question name, survey year) located in the temporal extract's codebook.
LATER_ITEMS = {
    "expectation": ("YFER-4861", "2015"),
    "marital_status": ("CV_MARSTAT_COLLAPSED", "2015"),
    "weight": ("SAMPLING_WEIGHT_CC", "2015"),
    "interview_2021": ("CV_INTERVIEW_CMONTH", "2021"),
    "interview_2023": ("CV_INTERVIEW_CMONTH", "2023"),
    "vstrat": ("VSTRAT", "1997"),
    "vpsu": ("VPSU", "1997"),
}
ROSTER_NAME = "CV_CHILD_BIRTH_MONTH."
# Model D's grade feature is CV_HGC_0910, the highest secondary grade completed
# before the 2009/10 school year. Its 2015/16 counterpart has not been
# verified, so model D is scored only when one is named here.
LATER_GRADE_ITEM: tuple[str, str] | None = None
DESIGN_REFERENCES = {"vstrat": "R1489700", "vpsu": "R1489800"}

# Interpretation thresholds, fixed before the later outcomes are seen.
MATERIAL_AUC_CHANGE = 0.05
MATERIAL_MEAN_ERROR = 0.05


@dataclass
class FrozenModels:
    prevalence: float
    model_c: object
    model_d: object
    training_households: frozenset
    test_households: frozenset
    cohort_households: frozenset


def frozen_models() -> FrozenModels:
    """Rebuild models A-D exactly as M02 fitted them on the 2009 training partition."""
    cohort = ac.load_cohort()
    ac.validate_cohort(cohort)
    train, test = ac.household_split(ac.labelled_sample(cohort))
    y = train["outcome"]
    return FrozenModels(
        prevalence=float(y.mean()),
        model_c=ac.stated_only_model().fit(train[[ac.STATED]], y),
        model_d=ac.covariate_model().fit(train[ac.MODEL_D_FEATURES], y),
        training_households=frozenset(train["household_id"]),
        test_households=frozenset(test["household_id"]),
        cohort_households=frozenset(cohort["household_id"]),
    )


def model_parameters(models: FrozenModels) -> dict:
    """Aggregate parameters that identify the fitted models; no respondent data."""
    scaler_c, logistic_c = models.model_c[0], models.model_c[-1]
    preprocess_d, logistic_d = models.model_d[0], models.model_d[-1]
    numeric = preprocess_d.named_transformers_["numeric"]
    categorical = preprocess_d.named_transformers_["categorical"]
    return {
        "A": {"prevalence": models.prevalence},
        "C": {"scaler_mean": scaler_c.mean_.tolist(), "scaler_scale": scaler_c.scale_.tolist(),
              "coef": logistic_c.coef_.ravel().tolist(),
              "intercept": logistic_c.intercept_.tolist()},
        "D": {"numeric_features": [ac.STATED, *ac.COVARIATES_NUMERIC],
              "imputer_medians": numeric[0].statistics_.tolist(),
              "scaler_mean": numeric[1].mean_.tolist(),
              "scaler_scale": numeric[1].scale_.tolist(),
              "marital_categories": categorical[1].categories_[0].tolist(),
              "coef": logistic_d.coef_.ravel().tolist(),
              "intercept": logistic_d.intercept_.tolist()},
    }


def parameter_differences(current: dict, stored: dict, tolerance=PARAMETER_TOLERANCE) -> list[str]:
    """Names of parameters that differ from the stored fingerprint."""
    differences = []
    for model, values in stored.items():
        for name, expected in values.items():
            actual = current.get(model, {}).get(name)
            if isinstance(expected, list) and expected and isinstance(expected[0], str):
                same = actual == expected
            else:
                same = (actual is not None and np.shape(actual) == np.shape(expected)
                        and np.allclose(actual, expected, rtol=0, atol=tolerance))
            if not same:
                differences.append(f"{model}.{name}")
    return differences


def verify_frozen(models: FrozenModels) -> None:
    if not PARAMETERS_PATH.exists():
        raise SystemExit(f"{PARAMETERS_PATH.name} not found; run with --freeze once.")
    stored = json.loads(PARAMETERS_PATH.read_text(encoding="utf-8"))
    differences = parameter_differences(model_parameters(models), stored)
    if differences:
        raise ValueError(f"Rebuilt models differ from the frozen fingerprint: {differences}")


def write_fingerprint(models: FrozenModels) -> None:
    if PARAMETERS_PATH.exists():
        raise SystemExit(f"{PARAMETERS_PATH.name} already exists; it is never overwritten.")
    PARAMETERS_PATH.write_text(json.dumps(model_parameters(models), indent=1) + "\n",
                               encoding="utf-8")


def predict(models: FrozenModels, frame: pd.DataFrame, include_d: bool) -> dict[str, np.ndarray]:
    """Frozen forecasts for later-baseline women; the models are only applied."""
    predictions = {
        "A": np.full(len(frame), models.prevalence),
        "B": frame[ac.STATED].to_numpy(dtype=float),
        "C": models.model_c.predict_proba(frame[[ac.STATED]])[:, 1],
    }
    if include_d:
        predictions["D"] = models.model_d.predict_proba(frame[ac.MODEL_D_FEATURES])[:, 1]
    return predictions


def locate_items(codebook: pd.DataFrame, grade_item=LATER_GRADE_ITEM) -> tuple[dict, list]:
    """Reference numbers for the later items, and the items that cannot be found."""
    items = dict(LATER_ITEMS)
    if grade_item is not None:
        items["grade"] = grade_item
    found, missing = {}, []
    for key, (name, year) in items.items():
        rows = codebook[(codebook["question_name"] == name) & (codebook["survey_year"] == year)]
        if len(rows) == 1:
            found[key] = rows["reference_number"].iloc[0]
        else:
            missing.append(f"{name} ({year})" + (" appears more than once" if len(rows) else ""))
    for key, reference in DESIGN_REFERENCES.items():
        if key in found and found[key] != reference:
            missing.append(f"{LATER_ITEMS[key][0]} is {found[key]}, expected {reference}")
    for year in LATER_FOLLOWUP:
        rows = codebook[codebook["question_name"].str.startswith(ROSTER_NAME)
                        & (codebook["survey_year"] == str(year))]
        if rows.empty:
            missing.append(f"{ROSTER_NAME}01 onward ({year})")
            continue
        slot = rows["question_name"].str[len(ROSTER_NAME):].astype(int)
        if sorted(slot) != list(range(1, len(slot) + 1)):
            missing.append(f"{ROSTER_NAME} slots for {year} are not consecutive from 01")
        found[f"roster_{year}"] = rows.assign(slot=slot).sort_values("slot")[
            "reference_number"].tolist()
    return found, missing


def later_eligibility(frame: pd.DataFrame, expectation: str) -> pd.Series:
    """Classify each woman's eligibility for the later baseline."""
    interviewed = frame[INTERVIEW_MONTH[LATER_BASELINE]] > 0
    answer = frame[expectation]
    status = pd.Series("eligible", index=frame.index)
    status[~answer.between(0, 100)] = "expectation item nonresponse"
    status[answer == -4] = "expectation valid skip"
    status[~interviewed] = "not interviewed in 2015"
    status[frame[SEX] != FEMALE] = "not female"
    return status


def later_cohort(frame: pd.DataFrame, items: dict) -> pd.DataFrame:
    """Baseline features and five-year outcomes for eligible later-baseline women."""
    eligible = frame[later_eligibility(frame, items["expectation"]) == "eligible"]
    rosters_by_year = {LATER_BASELINE: CHILD_BIRTH_MONTH[LATER_BASELINE],
                       **{year: items[f"roster_{year}"] for year in LATER_FOLLOWUP}}
    interviews = {LATER_BASELINE: INTERVIEW_MONTH[LATER_BASELINE],
                  **{year: items[f"interview_{year}"] for year in LATER_FOLLOWUP}}
    records = []
    for _, row in eligible.iterrows():
        baseline_month = int(row[interviews[LATER_BASELINE]])
        rosters = {year: [row[c] for c in slots] for year, slots in rosters_by_year.items()}
        months = {year: int(row[c]) for year, c in interviews.items()}
        result = bo.classify_outcome(baseline_month, rosters, months, bo.PRIMARY_RULES,
                                     LATER_BASELINE, LATER_FOLLOWUP)
        roster = assess_roster(rosters[LATER_BASELINE], months[LATER_BASELINE])
        records.append({"outcome": result.outcome, "unknown_reason": result.unknown_reason,
                        "parity_at_baseline": roster["n_births"] if roster["usable"] else None})
    results = pd.DataFrame(records, index=eligible.index)
    baseline = eligible[interviews[LATER_BASELINE]]
    own_birth = cmonth_from_date(eligible[BIRTH_YEAR], eligible[BIRTH_MONTH])
    grade = (bo.nonnegative_or_na(eligible[items["grade"]].where(eligible[items["grade"]] != 95))
             if "grade" in items else pd.Series(pd.NA, index=eligible.index, dtype="Int64"))
    # Model D's columns keep their 2009 names; here they hold the 2015 measurements.
    return pd.DataFrame({
        "respondent_id": eligible[RESPONDENT_ID],
        "household_id": eligible[HOUSEHOLD_ID],
        "outcome": results["outcome"].astype("Int64"),
        "unknown_reason": results["unknown_reason"],
        "expectation_pct": eligible[items["expectation"]],
        ac.STATED: eligible[items["expectation"]] / 100,
        "age_at_baseline": ((baseline - own_birth) / 12).round(2),
        "parity_at_baseline": results["parity_at_baseline"].astype("Int64"),
        "highest_grade_2009": grade,
        "marital_status_2009": bo.nonnegative_or_na(eligible[items["marital_status"]]),
        "sampling_weight_2015": eligible[items["weight"]] / 100,
    }).reset_index(drop=True)


def overlap_with_2009(later: pd.DataFrame, models: FrozenModels) -> pd.Series:
    """Where each later woman's household sat in the 2009 analysis."""
    households = later["household_id"]
    return pd.Series(np.select(
        [households.isin(models.training_households), households.isin(models.test_households),
         households.isin(models.cohort_households)],
        ["2009 training household", "2009 test household", "2009 cohort, unlabelled household"],
        "not in the 2009 cohort"), index=later.index)


def settings(later: pd.DataFrame, models: FrozenModels) -> dict[str, pd.DataFrame]:
    labelled = later[later["outcome"].notna()].assign(outcome=lambda f: f["outcome"].astype(int))
    return {
        "A. Same cohort, all eligible women": labelled,
        "B. Households absent from the 2009 training partition":
            labelled[~labelled["household_id"].isin(models.training_households)],
    }


PARENTHOOD_2015 = {"No children at the 2015 interview": lambda f: f["parity_at_baseline"] == 0,
                   "One or more children": lambda f: f["parity_at_baseline"] >= 1}
ANSWER_CATEGORIES = ([-1, 0, 49, 50, 99, 100], ["0", "1-49", "50", "51-99", "100"])


def answer_category(pct: pd.Series) -> pd.Series:
    return pd.cut(pct, ANSWER_CATEGORIES[0], labels=ANSWER_CATEGORIES[1])


def unknown_outcome_sensitivity(later: pd.DataFrame, models: FrozenModels) -> pd.DataFrame:
    """Brier scores of B and C over all eligible women, filling unknown outcomes by assumption.

    For each woman, d1 and d0 are the C - B differences in squared error if
    she had a birth or not. Deterministic bounds choose the outcome per
    woman; the estimates assume outcomes are missing at random within cells
    of answer category and 2015 parenthood, optionally shifted by a fixed
    odds ratio. Nothing is refitted; the forecasts are the frozen ones.
    """
    p_b = later[ac.STATED].to_numpy(dtype=float)
    p_c = models.model_c.predict_proba(later[[ac.STATED]])[:, 1]
    unknown = later["outcome"].isna().to_numpy()
    y = later["outcome"].fillna(0).to_numpy(dtype=float)
    cells = pd.DataFrame({"answer": answer_category(later["expectation_pct"]),
                          "mother": later["parity_at_baseline"].fillna(-1).ge(1)})
    rate = (pd.Series(y[~unknown]).groupby([cells["answer"][~unknown].to_numpy(),
                                            cells["mother"][~unknown].to_numpy()]).mean())
    mar = np.array([rate.get((a, m), np.nan) for a, m in zip(cells["answer"], cells["mother"])])
    if np.isnan(mar[unknown]).any():
        raise ValueError("An unknown outcome falls in a cell with no known outcomes")

    def shifted(odds_ratio):
        odds = mar / (1 - mar) * odds_ratio
        return odds / (1 + odds)

    def score(name, kind, fill=None):
        rows = ~unknown if fill is None else np.ones(len(y), dtype=bool)
        filled = np.where(unknown, fill if fill is not None else 0.0, y)[rows]
        b, c = p_b[rows], p_c[rows]
        brier_b = np.mean(filled * (1 - b) ** 2 + (1 - filled) * b ** 2)
        brier_c = np.mean(filled * (1 - c) ** 2 + (1 - filled) * c ** 2)
        return {"scenario": name, "kind": kind, "n": int(rows.sum()),
                "observed_rate": filled.mean(), "brier_b": brier_b, "brier_c": brier_c,
                "c_minus_b": brier_c - brier_b}

    d1, d0 = (1 - p_c) ** 2 - (1 - p_b) ** 2, p_c ** 2 - p_b ** 2
    rows = [
        score("Complete cases (unknowns excluded)", "observed"),
        score("Every unknown had a birth", "bound", 1.0),
        score("No unknown had a birth", "bound", 0.0),
        score("Least favourable to C (each unknown chosen)", "bound", (d1 > d0).astype(float)),
        score("Most favourable to C (each unknown chosen)", "bound", (d1 < d0).astype(float)),
        score("Missing at random within answer x parenthood cells", "estimate", mar),
        score("As above, odds of a birth x0.5 among unknowns", "estimate", shifted(0.5)),
        score("As above, odds of a birth x2 among unknowns", "estimate", shifted(2.0)),
    ]
    return pd.DataFrame(rows)


def forecast_summary(y: np.ndarray, p: np.ndarray) -> dict:
    varies = np.ptp(p) > 0
    return {"brier": brier_score_loss(y, p),
            "auc": roc_auc_score(y, p) if varies else np.nan,
            "mean_forecast": p.mean(), "observed": y.mean(),
            "mean_error": p.mean() - y.mean(),
            "linear_slope": np.polyfit(p, y, 1)[0] if varies else np.nan}


def evaluate(sample: pd.DataFrame, predictions: dict[str, np.ndarray],
             n_bootstrap=N_BOOTSTRAP, seed=BOOTSTRAP_SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Metrics per model and paired Brier differences, with household-bootstrap intervals."""
    y = sample["outcome"].to_numpy()
    point = {m: forecast_summary(y, p) for m, p in predictions.items()}
    pairs = [(a, b) for a, b in (("C", "A"), ("C", "B"), ("B", "A"), ("D", "C"))
             if a in predictions and b in predictions]
    replicates, differences = {m: [] for m in predictions}, {pair: [] for pair in pairs}
    for rows in ac.household_bootstrap_indices(sample["household_id"].reset_index(drop=True),
                                               n_bootstrap, seed):
        if y[rows].min() == y[rows].max():
            continue
        scores = {m: forecast_summary(y[rows], p[rows]) for m, p in predictions.items()}
        for m in predictions:
            replicates[m].append(scores[m])
        for a, b in pairs:
            differences[(a, b)].append(scores[a]["brier"] - scores[b]["brier"])
    metrics = []
    for m, values in point.items():
        table = pd.DataFrame(replicates[m])
        row = {"model": m, **values}
        for name in ("brier", "auc", "mean_error", "linear_slope"):
            column = table[name].dropna()
            row[f"{name}_ci"] = tuple(np.percentile(column, [2.5, 97.5])) if len(column) else None
        metrics.append(row)
    contrasts = pd.DataFrame([
        {"comparison": f"{a} - {b}", "brier_difference": point[a]["brier"] - point[b]["brier"],
         "ci": tuple(np.percentile(differences[(a, b)], [2.5, 97.5]))}
        for a, b in pairs])
    return pd.DataFrame(metrics), contrasts


def interpret(metrics: pd.DataFrame, contrasts: pd.DataFrame, reference_auc: float) -> dict:
    """Apply the pre-specified interpretation rules to model C in one setting."""
    c = metrics.set_index("model").loc["C"]
    ci = contrasts.set_index("comparison")["ci"]
    return {
        "discrimination retained (AUC lower bound > 0.5)": c["auc_ci"][0] > 0.5,
        f"material AUC change (|change| >= {MATERIAL_AUC_CHANGE})":
            abs(c["auc"] - reference_auc) >= MATERIAL_AUC_CHANGE,
        f"calibration-in-the-large drift (|mean error| >= {MATERIAL_MEAN_ERROR})":
            abs(c["mean_error"]) >= MATERIAL_MEAN_ERROR,
        "frozen recalibration beats stated (C - B upper bound < 0)": ci["C - B"][1] < 0,
        "frozen recalibration beats constant (C - A upper bound < 0)": ci["C - A"][1] < 0,
    }


def reference_held_out() -> dict:
    """M02 held-out results from the published summary, for comparison only."""
    summary = json.loads((PROJECT_ROOT / "data" / "public" / "dashboard_summary.json")
                         .read_text(encoding="utf-8"))
    return {m["id"]: m for m in summary["held_out"]["models"]}


def baseline_shift(frame: pd.DataFrame) -> pd.DataFrame:
    """Age and parenthood at the 2009 and 2015 interviews (no later outcome used).

    The 2015 column covers all women interviewed in 2015 with a usable 2015
    roster, because the 2015 expectation answer is not yet in the extract.
    """
    cohort = ac.load_cohort()
    women = frame[(frame[SEX] == FEMALE) & (frame[INTERVIEW_MONTH[LATER_BASELINE]] > 0)]
    month = women[INTERVIEW_MONTH[LATER_BASELINE]]
    slots = women[CHILD_BIRTH_MONTH[LATER_BASELINE]].to_numpy()
    assessed = [assess_roster(row, m) for row, m in zip(slots, month)]
    usable = np.array([a["usable"] for a in assessed])
    parity = pd.Series([a["n_births"] for a in assessed], index=women.index)[usable]
    age = ((month - cmonth_from_date(women[BIRTH_YEAR], women[BIRTH_MONTH])) / 12)[usable]
    in_2009 = women[usable][EXPECTATION].between(0, 100)

    def describe(ages, parities):
        return {"women": len(ages), "mean age": ages.mean(),
                "age range": f"{ages.min():.1f}-{ages.max():.1f}",
                "no children (%)": 100 * (parities == 0).mean(),
                "mean children": parities.mean(),
                "three or more (%)": 100 * (parities >= 3).mean()}

    base_parity = cohort["parity_at_baseline"].dropna().astype(float)
    return pd.DataFrame({
        "2009 eligible cohort": describe(cohort["age_at_baseline"][cohort["parity_at_baseline"]
                                                                   .notna()], base_parity),
        "2015, all women with usable roster": describe(age, parity),
        "2015, of whom in 2009 cohort": describe(age[in_2009.to_numpy()],
                                                 parity[in_2009.to_numpy()]),
    })


def load_temporal() -> tuple[pd.DataFrame | None, dict, list]:
    """Original, supplement and temporal extracts joined in memory, if present."""
    original = pd.read_csv(RAW_DATA_PATH)
    joined = se.join_extracts(original, pd.read_csv(se.SUPPLEMENT_PATH))
    if not TEMPORAL_PATH.exists() or not TEMPORAL_CODEBOOK.exists():
        return joined, {}, ["temporal extract and codebook (data/raw/"
                            f"{TEMPORAL_PATH.name}, {TEMPORAL_CODEBOOK.name})"]
    temporal = pd.read_csv(TEMPORAL_PATH)
    items, missing = locate_items(se.codebook_index(TEMPORAL_CODEBOOK))
    return se.join_extracts(joined, temporal), items, missing


def format_ci(ci) -> str:
    return "" if ci is None else f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def report_setting(name: str, sample: pd.DataFrame, models: FrozenModels, include_d: bool):
    metrics, contrasts = evaluate(sample, predict(models, sample, include_d))
    print(f"\n{name}: n {len(sample):,}, births {int(sample['outcome'].sum()):,}, "
          f"households {sample['household_id'].nunique():,}")
    shown = metrics.copy()
    for column in ("brier_ci", "auc_ci", "mean_error_ci", "linear_slope_ci"):
        shown[column] = shown[column].map(format_ci)
    print(shown.round(4).to_string(index=False))
    print(contrasts.assign(ci=contrasts["ci"].map(
        lambda ci: f"[{ci[0]:+.4f}, {ci[1]:+.4f}]")).round(4).to_string(index=False))
    return metrics, contrasts


def main() -> None:
    pd.set_option("display.width", 200)
    models = frozen_models()
    if "--freeze" in sys.argv:
        write_fingerprint(models)
        print(f"Wrote {PARAMETERS_PATH.relative_to(PROJECT_ROOT).as_posix()}")
        return
    verify_frozen(models)
    print("THE INTENTION GAP | OUT-OF-PERIOD VALIDATION (2015-16 BASELINE)")
    print("=" * 72)
    print(f"Frozen models rebuilt and matched to {PARAMETERS_PATH.name}; "
          f"training prevalence {models.prevalence:.4f}, "
          f"{len(models.training_households):,} training households.")

    frame, items, missing = load_temporal()
    print("\nBaseline composition, 2009 versus 2015 (no later outcome used)")
    print(baseline_shift(frame).round(2).to_string())
    if missing:
        print("\nValidation not run. Missing from the temporal extract:")
        for item in missing:
            print(f"  - {item}")
        print("See docs/temporal_extract_manifest.csv.")
        return

    print("\nLater-baseline eligibility (all respondents)")
    print(later_eligibility(frame, items["expectation"]).value_counts().to_string())
    later = later_cohort(frame, items)
    include_d = "grade" in items
    print("\nLater outcomes: " + ", ".join(
        f"{k} {v:,}" for k, v in {"births": int((later["outcome"] == 1).sum()),
                                  "no births": int((later["outcome"] == 0).sum()),
                                  "unknown": int(later["outcome"].isna().sum())}.items()))
    print(later["unknown_reason"].value_counts().to_string())
    births, n = int((later["outcome"] == 1).sum()), len(later)
    print(f"Observed birth rate, worst-case bounds over unknowns: {births / n:.3f} "
          f"(none had a birth) to {(births + int(later['outcome'].isna().sum())) / n:.3f} (all did)")
    print("\nOverlap with the 2009 analysis (labelled later women)")
    labelled = later[later["outcome"].notna()]
    print(overlap_with_2009(labelled, models).value_counts().to_string())

    reference = reference_held_out()
    groups = settings(later, models)
    for name, sample in groups.items():
        metrics, contrasts = report_setting(name, sample, models, include_d)
        print(f"  M02 held-out reference for C: AUC {reference['C']['auc']:.3f}, "
              f"Brier {reference['C']['brier']:.3f}; AUC change "
              f"{metrics.set_index('model').loc['C', 'auc'] - reference['C']['auc']:+.3f}")
        for rule, value in interpret(metrics, contrasts, reference["C"]["auc"]).items():
            print(f"  {rule}: {'yes' if value else 'no'}")

    print("\nBy parenthood at the 2015 interview (frozen models; descriptive, not pre-specified)")
    for setting, sample in groups.items():
        for name, select in PARENTHOOD_2015.items():
            report_setting(f"{setting[:2]} {name}", sample[select(sample).to_numpy(dtype=bool)],
                           models, include_d)

    print("\nC - B Brier difference over all eligible women, unknown outcomes filled "
          "by assumption (setting A)")
    print(unknown_outcome_sensitivity(later, models).round(4).to_string(index=False))
    if not include_d:
        print("\nModel D not scored: no verified 2015/16 counterpart of CV_HGC_0910.")


if __name__ == "__main__":
    main()
