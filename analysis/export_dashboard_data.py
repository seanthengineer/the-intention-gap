"""Write the aggregate results used by the public dashboard.

Recomputes the calibration and baseline results and the robustness results
from the local research files, using the same functions and seeds, and
writes them to data/public/dashboard_summary.json. Requires the private raw
extract and processed cohort, so it runs only on the research machine.

Disclosure rules, enforced by check_public_payload:
1. No respondent rows, identifiers or fitted model objects.
2. A birth count or birth rate for a subgroup is published only if the
   subgroup has at least MIN_OUTCOME_CELL women. Reclassification counts by
   direction (unknown to birth, unknown to no birth) are not published.
3. A count of women in an answer value or category is published only if it
   is at least MIN_COUNT_CELL; smaller categories are combined, or reported
   only as a combined suppressed total.
4. No individual extreme values: the age range is rounded to whole years.
Whole-sample statistics under alternative outcome definitions are rounded
to three decimals. Differences between them can still indicate the net
reclassification of small, rule-defined groups; this residual is documented
in docs/methodology.md.
"""

import json
import math

import numpy as np
import pandas as pd

from analysis import analyze_calibration as ac
from analysis import build_outcomes as bo
from analysis import robustness_analysis as ra
from analysis.nlsy97 import PROJECT_ROOT

PUBLIC_DATA_PATH = PROJECT_ROOT / "data" / "public" / "dashboard_summary.json"

MIN_OUTCOME_CELL = 20
MIN_COUNT_CELL = 10
FORBIDDEN_KEYS = {"respondent_id", "household_id", "pubid", "R0000100", "R1193000"}
OTHER_UNKNOWN_REASON = "Other incomplete, conflicting or boundary-month birth histories"

# Scenarios shown on the dashboard. Fixed to the reviewed set so that new
# sensitivity analyses do not reach the public data before review.
PUBLISHED_SCENARIOS = [
    *(name for name in ra.RULE_SCENARIOS
      if name != "Strict date reconciliation of pre-baseline births"),
    *ra.OUTCOME_BOUNDS,
]
SENSITIVITY_FIELDS = [
    "scenario", "kind", "labels_changed", "1_to_0", "0_to_1", "n", "observed_rate",
    "mean_stated", "observed_at_0", "observed_at_50", "observed_at_100", "slope", "slope_ci",
    "brier_stated", "brier_recalibrated_cv", "auc_stated", "finding_holds",
]

UNKNOWN_REASON_LABELS = {
    bo.NO_FOLLOWUP_INTERVIEW: "No follow-up interview in 2015 or 2017",
    bo.INCOMPLETE_FOLLOWUP: "Follow-up birth history incomplete",
    bo.BASELINE_ROSTER_UNUSABLE: "2009 birth history unusable",
    bo.ROUNDS_DISAGREE: "2015 and 2017 histories disagree",
    bo.RECORD_CONFLICT: "Birth-record conflict",
    bo.BASELINE_MONTH_TIMING: "Birth in the interview month",
    bo.ANNIVERSARY_MONTH_TIMING: "Birth in the fifth-anniversary month",
}

MODEL_NAMES = {
    "A": "Constant probability baseline",
    "B": "Original stated probability",
    "C": "Logistic recalibration",
    "D": "Recalibration with baseline characteristics",
}


def to_builtin(value):
    """Convert numpy and pandas scalars to JSON-safe Python values."""
    if isinstance(value, dict):
        return {str(k): to_builtin(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [to_builtin(v) for v in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if math.isnan(value) else round(float(value), 6)
    if value is pd.NA:
        return None
    return value


def sample_summary(cohort: pd.DataFrame, sample: pd.DataFrame, n_respondents: int) -> dict:
    counts = cohort["unknown_reason"].value_counts()
    reasons, other = [], 0
    for code, label in UNKNOWN_REASON_LABELS.items():
        n = int(counts.get(code, 0))
        if n >= MIN_COUNT_CELL:
            reasons.append({"reason": label, "n": n})
        else:
            other += n
    if other:
        reasons.append({"reason": OTHER_UNKNOWN_REASON, "n": other})
    age = cohort["age_at_baseline"]
    return {
        "respondents_in_extract": n_respondents,
        "eligible_women": len(cohort),
        "labelled": len(sample),
        "births": int(sample["outcome"].sum()),
        "no_births": int((sample["outcome"] == 0).sum()),
        "unknown": int(cohort["outcome"].isna().sum()),
        "labelled_households": sample["household_id"].nunique(),
        "unknown_reasons": reasons,
        "age_at_baseline": {
            "mean": round(age.mean(), 1), "min": int(round(age.min())), "max": int(round(age.max())),
        },
    }


def distribution_summary(sample: pd.DataFrame) -> dict:
    pct = sample["expectation_pct"]
    shares = ac.expectation_distribution(pct)["share_pct"]
    counts = pct.value_counts().sort_index()
    small = counts[counts < MIN_COUNT_CELL]
    return {
        "n": len(pct),
        "counts": [{"stated_pct": int(k), "n": int(v)}
                   for k, v in counts.items() if v >= MIN_COUNT_CELL],
        "suppressed": {"values": len(small), "n": int(small.sum())},
        "share_pct": {
            "exactly_0": shares["Exactly 0%"],
            "exactly_50": shares["Exactly 50%"],
            "exactly_100": shares["Exactly 100%"],
            "at_0_50_or_100": shares["0%, 50% or 100%"],
            "multiple_of_10": shares["Any multiple of 10%"],
            "multiple_of_5": shares["Any multiple of 5%"],
        },
    }


def stated_forecast_summary(sample: pd.DataFrame) -> dict:
    metrics = ac.forecast_metrics(sample["outcome"], sample[ac.STATED])
    intervals = ac.stated_forecast_intervals(sample)
    return {
        "n": metrics["n"],
        "mean_stated": metrics["mean_forecast"],
        "observed_rate": metrics["observed_rate"],
        "brier": metrics["brier"],
        "brier_ci": intervals["brier"],
        "auc": metrics["auc"],
        "auc_ci": intervals["auc"],
        "log_loss": {str(e): metrics[f"log_loss_clip_{e}"] for e in ac.LOG_LOSS_EPSILONS},
    }


def recalibration_curve(train: pd.DataFrame) -> list[dict]:
    """Model C's recalibrated probability for each possible stated percentage."""
    model = ac.stated_only_model().fit(train[[ac.STATED]], train["outcome"])
    grid = pd.DataFrame({ac.STATED: np.arange(101) / 100})
    fitted = model.predict_proba(grid)[:, 1]
    return [{"stated_pct": k, "recalibrated": p} for k, p in enumerate(fitted)]


def held_out_summary(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    results = ac.evaluate_baselines(test, ac.fit_and_predict(train, test))
    models = [
        {
            "id": key,
            "name": MODEL_NAMES[key],
            "mean_forecast": row["mean_forecast"],
            "brier": row["brier"],
            "brier_ci": row["brier_ci"],
            "brier_skill_vs_A": row["brier_skill_vs_A"],
            "auc": row["auc"],
            "auc_ci": row["auc_ci"],
        }
        for key, row in results.iterrows()
    ]
    comparisons = [("B", "A", ("brier",)), ("C", "A", ("brier",)),
                   ("C", "B", ("brier",)), ("D", "C", ("brier", "auc"))]
    differences = [
        {
            "comparison": f"{left} - {right}",
            "metric": metric,
            "mean": results.loc[left, f"{metric}_diff_vs_{right}"],
            "ci": results.loc[left, f"{metric}_diff_vs_{right}_ci"],
        }
        for left, right, metrics in comparisons
        for metric in metrics
    ]
    return {
        "n": len(test),
        "births": int(test["outcome"].sum()),
        "households": test["household_id"].nunique(),
        "training_n": len(train),
        "models": models,
        "differences": differences,
    }


def cross_validation_summary(train: pd.DataFrame) -> dict:
    results = ra.repeated_grouped_cv(train)
    _, comparisons = ra.summarise_cv(results)
    wide = results.pivot_table(index=["repeat", "fold"], columns="model", values=["brier", "auc"])
    by_model = results.groupby("model")[["brier", "auc"]].agg(["mean", "std"])
    return {
        "n": len(train),
        "households": train["household_id"].nunique(),
        "repeats": len(ra.CV_SEEDS),
        "folds": ra.CV_FOLDS,
        "models": [
            {
                "id": key,
                "name": MODEL_NAMES[key],
                "brier_mean": by_model.loc[key, ("brier", "mean")],
                "brier_sd": by_model.loc[key, ("brier", "std")],
                "auc_mean": by_model.loc[key, ("auc", "mean")],
                "auc_sd": by_model.loc[key, ("auc", "std")],
            }
            for key in MODEL_NAMES
        ],
        "differences": [
            {
                "comparison": row["comparison"],
                "metric": row["metric"],
                "mean": row["mean"],
                "ci": (row["corrected_ci_low"], row["corrected_ci_high"]),
                "folds_improved": int(row["folds_improved"].split("/")[0]),
                "folds_total": int(row["folds_improved"].split("/")[1]),
            }
            for _, row in comparisons.iterrows()
        ],
        "fold_differences_d_minus_c": {
            metric: (wide[(metric, "D")] - wide[(metric, "C")]).tolist()
            for metric in ("brier", "auc")
        },
    }


def round_floats(value, digits: int = 3):
    if isinstance(value, (list, tuple)):
        return [round_floats(v, digits) for v in value]
    if isinstance(value, (float, np.floating)) and not isinstance(value, bool):
        return round(float(value), digits)
    return value


def sensitivity_summary(eligible: pd.DataFrame) -> list[dict]:
    table = ra.sensitivity_table(eligible).set_index("scenario", drop=False)
    rows = table.loc[PUBLISHED_SCENARIOS, SENSITIVITY_FIELDS].to_dict(orient="records")
    return [{key: round_floats(value) for key, value in row.items()} for row in rows]


def check_public_payload(payload: dict) -> None:
    """Raise if the payload breaks any of the disclosure rules in the module docstring."""
    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_KEYS:
                    raise ValueError(f"Identifier key in public payload: {path}/{key}")
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for item in node:
                walk(item, path)

    walk(payload)
    problems = []
    problems += [f"calibration {row['range_pct']}: n={row['n']}"
                 for row in payload["calibration"] if row["n"] < MIN_OUTCOME_CELL]
    problems += [f"answer {row['stated_pct']}%: n={row['n']}"
                 for row in payload["distribution"]["counts"] if row["n"] < MIN_COUNT_CELL]
    suppressed = payload["distribution"]["suppressed"]["n"]
    if 0 < suppressed < MIN_COUNT_CELL:
        problems.append(f"suppressed answers total n={suppressed}")
    problems += [f"unknown reason {row['reason']}: n={row['n']}"
                 for row in payload["sample"]["unknown_reasons"] if row["n"] < MIN_COUNT_CELL]
    age = payload["sample"]["age_at_baseline"]
    if not (isinstance(age["min"], int) and isinstance(age["max"], int)):
        problems.append("age range not rounded to whole years")
    for row in payload["sensitivity"]:
        extra = set(row) - set(SENSITIVITY_FIELDS)
        if extra:
            problems.append(f"sensitivity {row['scenario']}: unpublished fields {sorted(extra)}")
    if problems:
        raise ValueError("Disclosure rules violated: " + "; ".join(problems))


def build_payload() -> dict:
    eligible, n_respondents = bo.load_eligible()
    cohort = ac.load_cohort()
    ac.validate_cohort(cohort)
    sample = ac.labelled_sample(cohort)
    train, test = ac.household_split(sample)

    calibration = ac.calibration_table(sample)
    payload = {
        "about": {
            "source": "NLSY97 public-use extract (U.S. Bureau of Labor Statistics)",
            "cohort_birth_years": [1980, 1984],
            "baseline": "Round 13 interview, 2009-10",
            "question": "In five years, what is the percent chance that you will have "
                        "(a/another) child?",
            "outcome": "At least one biological birth in the five years after the interview",
            "weighting": "unweighted",
        },
        "sample": sample_summary(cohort, sample, n_respondents),
        "distribution": distribution_summary(sample),
        "stated_forecast": stated_forecast_summary(sample),
        "calibration": calibration.to_dict(orient="records"),
        "recalibration_curve": recalibration_curve(train),
        "held_out": held_out_summary(train, test),
        "cross_validation": cross_validation_summary(train),
        "sensitivity": sensitivity_summary(eligible),
    }
    payload = to_builtin(payload)
    check_public_payload(payload)
    return payload


def main() -> None:
    payload = build_payload()
    PUBLIC_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_DATA_PATH.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote aggregate dashboard data to "
          f"{PUBLIC_DATA_PATH.relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
