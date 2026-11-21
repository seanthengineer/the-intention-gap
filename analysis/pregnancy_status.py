"""Self-reported pregnancy at the Round 13 interview and the calibration finding.

Pregnancy status comes from the Round 13 self-administered items YSAQ2-314,
-314C, -315 and -316 in the supplementary extract. The routing is taken from
the supplement codebook:

    YSAQ2-314  ever pregnant; asked of women with no earlier valid answer
    YSAQ2-314C pregnant since the last interview, including a pregnancy
               current at that interview; asked of everyone else
    YSAQ2-315  pregnant now; asked only after a "yes" to 314 or 314C
    YSAQ2-316  weeks pregnant; asked only after a "yes" to 315

All four items require that the respondent is female, reports ever having
had sexual intercourse and is not interviewed in an insecure prison
setting. The intercourse and prison gates are not in either extract, so a
woman who skipped both 314 and 314C has unknown status, not "not pregnant".

Primary outcome labels and the original household split are reused
unchanged. Only aggregate results are printed.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from analysis import analyze_calibration as ac
from analysis import build_outcomes as bo
from analysis import robustness_analysis as rb
from analysis import supplement_extract as se
from analysis.nlsy97 import NON_INTERVIEW, NONRESPONSE_CODES, RESPONDENT_ID, VALID_SKIP

PREGNANT = "pregnant"
NOT_PREGNANT = "not_pregnant"
UNKNOWN = "unknown"
STATUSES = (PREGNANT, NOT_PREGNANT, UNKNOWN)

REPORTED_PREGNANT = "reported pregnant now (YSAQ2-315 = 1)"
REPORTED_NOT_PREGNANT = "reported not pregnant now (YSAQ2-315 = 0)"
NEVER_PREGNANT = "never pregnant (YSAQ2-314 = 0)"
NONE_SINCE_LAST = "no pregnancy since last interview (YSAQ2-314C = 0)"
ENTRY_NONRESPONSE = "refusal or don't know at YSAQ2-314/314C"
CURRENT_NONRESPONSE = "refusal or don't know at YSAQ2-315"
SKIPPED_BLOCK = "skipped pregnancy block (intercourse or prison gate)"
INCONSISTENT_ROUTING = "codes inconsistent with questionnaire routing"
NOT_INTERVIEWED = "non-interview code"

MAX_WEEKS = 40
DAYS_PER_MONTH = 30.4375
GESTATION_TOLERANCE = 2
TIMING_BANDS = [("1-3", 1, 3), ("4-6", 4, 6), ("7-8", 7, 8), ("9-12", 9, 12),
                ("13-59", 13, 59)]
POINTS = (0, 50, 100)
MIN_CLASS = 20


def classify_pregnancy(ever: int, since: int, now: int) -> tuple[str, str]:
    """Status and reason from the raw codes of YSAQ2-314, -314C and -315.

    A valid skip is read as "not pregnant" only when the questionnaire
    routing makes it so: an explicit "no" at 314 or 314C skips 315.
    """
    ever, since, now = int(ever), int(since), int(now)
    if NON_INTERVIEW in (ever, since, now):
        return UNKNOWN, NOT_INTERVIEWED
    if ever == VALID_SKIP and since == VALID_SKIP:
        return (UNKNOWN, SKIPPED_BLOCK) if now == VALID_SKIP else (UNKNOWN, INCONSISTENT_ROUTING)
    if ever != VALID_SKIP and since != VALID_SKIP:
        return UNKNOWN, INCONSISTENT_ROUTING

    entry = ever if since == VALID_SKIP else since
    if entry in NONRESPONSE_CODES:
        return (UNKNOWN, ENTRY_NONRESPONSE) if now == VALID_SKIP else (UNKNOWN, INCONSISTENT_ROUTING)
    if entry == 0:
        if now != VALID_SKIP:
            return UNKNOWN, INCONSISTENT_ROUTING
        return NOT_PREGNANT, NEVER_PREGNANT if since == VALID_SKIP else NONE_SINCE_LAST
    if entry != 1:
        return UNKNOWN, INCONSISTENT_ROUTING
    if now == 1:
        return PREGNANT, REPORTED_PREGNANT
    if now == 0:
        return NOT_PREGNANT, REPORTED_NOT_PREGNANT
    if now in NONRESPONSE_CODES:
        return UNKNOWN, CURRENT_NONRESPONSE
    return UNKNOWN, INCONSISTENT_ROUTING


def weeks_pregnant(status: str, weeks: int) -> float:
    """Reported weeks for a pregnant woman, or NaN when not reported or out of range."""
    weeks = int(weeks)
    return float(weeks) if status == PREGNANT and 1 <= weeks <= MAX_WEEKS else np.nan


def pregnancy_table(eligible: pd.DataFrame) -> pd.DataFrame:
    """Pregnancy status, reason and weeks for each eligible woman, by respondent_id."""
    rows = {}
    for _, row in eligible.iterrows():
        status, reason = classify_pregnancy(row[se.EVER_PREGNANT], row[se.PREGNANT_SINCE_LAST],
                                            row[se.PREGNANT_NOW])
        rows[row[RESPONDENT_ID]] = {
            "pregnancy_status": status,
            "pregnancy_reason": reason,
            "weeks_pregnant": weeks_pregnant(status, row[se.WEEKS_PREGNANT]),
            "weeks_code": int(row[se.WEEKS_PREGNANT]),
        }
    table = pd.DataFrame.from_dict(rows, orient="index")
    table.index.name = "respondent_id"
    return table


def rebuild_primary_cohort(eligible: pd.DataFrame) -> pd.DataFrame:
    """Rebuild the primary cohort from the joined data and confirm it matches the stored file."""
    rebuilt = bo.build_cohort(eligible)
    stored = ac.load_cohort()
    ac.validate_cohort(stored)
    left = rebuilt.set_index("respondent_id")["outcome"].sort_index()
    right = stored.set_index("respondent_id")["outcome"].astype("Int64").sort_index()
    if not left.index.equals(right.index) or not left.astype("Int64").equals(right):
        raise ValueError("Joined data do not reproduce the stored primary cohort")
    return stored


def status_counts(status: pd.DataFrame) -> pd.DataFrame:
    counts = status.groupby(["pregnancy_status", "pregnancy_reason"]).size().rename("women")
    table = counts.reset_index()
    table["share_pct"] = 100 * table["women"] / len(status)
    return table


def expectations_by_status(frame: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for name in STATUSES:
        pct = frame.loc[frame["pregnancy_status"] == name, "expectation_pct"]
        rows[name] = {
            "women": len(pct),
            "mean_stated_pct": pct.mean(),
            "median_stated_pct": pct.median(),
            "share_0_pct": 100 * (pct == 0).mean(),
            "share_50_pct": 100 * (pct == 50).mean(),
            "share_100_pct": 100 * (pct == 100).mean(),
        }
    return pd.DataFrame(rows).T


def outcomes_by_status(frame: pd.DataFrame, timing: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for name in STATUSES:
        group = frame[frame["pregnancy_status"] == name]
        labelled = group[group["outcome"].notna()]
        first = timing["first_birth_month"].reindex(labelled.index)
        births = int(labelled["outcome"].sum())
        early = int((first <= rb.EARLY_BIRTH_MONTHS).sum())
        rows[name] = {
            "women": len(group),
            "unknown_outcome": int(group["outcome"].isna().sum()),
            "labelled": len(labelled),
            "births": births,
            "birth_rate": births / len(labelled) if len(labelled) else np.nan,
            "first_birth_within_8_months": early,
            "early_share_of_births": early / births if births else np.nan,
            "births_after_month_8_only_rate": (
                int((labelled["outcome"] == 1).sum() - early) / len(labelled)
                if len(labelled) else np.nan),
        }
    return pd.DataFrame(rows).T


def first_birth_timing_by_status(frame: pd.DataFrame, timing: pd.DataFrame) -> pd.DataFrame:
    """Confirmed positives by months from interview to first qualifying birth."""
    positives = frame[frame["outcome"] == 1]
    first = timing["first_birth_month"].reindex(positives.index)
    table = {}
    for name in STATUSES:
        months = first[positives["pregnancy_status"] == name]
        table[name] = {label: int(months.between(low, high).sum())
                       for label, low, high in TIMING_BANDS}
    return pd.DataFrame(table)


def gestation_agreement(frame: pd.DataFrame, timing: pd.DataFrame) -> dict:
    """Compare reported weeks with the timing of the first qualifying birth.

    Expected months to delivery = (40 - weeks) * 7 / 30.44. The interview
    day is not known, so agreement within two months is treated as
    consistent.
    """
    pregnant = frame[frame["pregnancy_status"] == PREGNANT]
    with_weeks = pregnant[pregnant["weeks_pregnant"].notna()]
    labelled = with_weeks[with_weeks["outcome"].notna()]
    positives = labelled[labelled["outcome"] == 1]
    expected = (MAX_WEEKS - positives["weeks_pregnant"]) * 7 / DAYS_PER_MONTH
    observed = timing["first_birth_month"].reindex(positives.index)
    difference = observed - expected
    return {
        "pregnant_women": len(pregnant),
        "with_valid_weeks": len(with_weeks),
        "outcome_unknown": int(with_weeks["outcome"].isna().sum()),
        "labelled": len(labelled),
        "no_birth_in_window": int((labelled["outcome"] == 0).sum()),
        "birth_in_window": len(positives),
        "first_birth_within_tolerance": int((difference.abs() <= GESTATION_TOLERANCE).sum()),
        "first_birth_earlier_than_expected": int((difference < -GESTATION_TOLERANCE).sum()),
        "first_birth_later_than_expected": int((difference > GESTATION_TOLERANCE).sum()),
        "median_difference_months": float(difference.median()) if len(difference) else np.nan,
    }


def documented_versus_inferred(frame: pd.DataFrame, timing: pd.DataFrame) -> pd.DataFrame:
    """Labelled women: documented status against the early-birth proxy (first birth <= 8 months)."""
    labelled = frame[frame["outcome"].notna()]
    first = timing["first_birth_month"].reindex(labelled.index)
    proxy = np.where(first <= rb.EARLY_BIRTH_MONTHS, "early birth (proxy pregnant)",
                     "no early birth")
    return pd.crosstab(labelled["pregnancy_status"], proxy, margins=True)


def calibration_points(sample: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for point in POINTS:
        group = sample[sample["expectation_pct"] == point]
        n, births = len(group), int(group["outcome"].sum())
        low, high = ac.wilson_interval(births, n)
        rows[f"{point}%"] = {"women": n, "births": births,
                             "observed_pct": 100 * births / n if n else np.nan,
                             "ci_low_pct": 100 * low, "ci_high_pct": 100 * high}
    return pd.DataFrame(rows).T


def subgroup_summary(sample: pd.DataFrame) -> dict:
    """Stated-forecast performance for one labelled subgroup.

    Intervals, cross-fitting and the slope need both outcomes in reasonable
    numbers; below MIN_CLASS births or non-births only descriptive values are
    returned.
    """
    frame = sample.reset_index()
    y, p = frame["outcome"].to_numpy(), frame["expectation_prob"].to_numpy()
    if min(y.sum(), len(y) - y.sum()) < MIN_CLASS:
        return {"n": len(y), "births": int(y.sum()), "observed_rate": y.mean(),
                "mean_stated": p.mean(), "brier_stated": brier_score_loss(y, p),
                **{f"observed_at_{k}": y[frame["expectation_pct"] == k].mean() for k in POINTS}}
    summary = rb.calibration_summary(frame)
    intervals = ac.stated_forecast_intervals(frame)
    return {**summary, "brier_ci": intervals["brier"], "auc_ci": intervals["auc"],
            **rb.finding_holds(summary)}


SUBGROUPS = {
    "All labelled women (M02)": lambda f: f.index == f.index,
    "Confirmed not pregnant": lambda f: f["pregnancy_status"] == NOT_PREGNANT,
    "Excluding confirmed pregnant": lambda f: f["pregnancy_status"] != PREGNANT,
    "Pregnancy status unknown": lambda f: f["pregnancy_status"] == UNKNOWN,
    "Confirmed pregnant": lambda f: f["pregnancy_status"] == PREGNANT,
}


def subgroup_table(frame: pd.DataFrame) -> pd.DataFrame:
    labelled = frame[frame["outcome"].notna()].copy()
    labelled["outcome"] = labelled["outcome"].astype(int)
    rows = []
    for name, select in SUBGROUPS.items():
        group = labelled[np.asarray(select(labelled))]
        rows.append({"subgroup": name, **subgroup_summary(group)})
    return pd.DataFrame(rows)


def held_out_by_pregnancy(sample: pd.DataFrame, status: pd.Series) -> pd.DataFrame:
    """Held-out comparisons on the original household split.

    The split is drawn once on all labelled women exactly as in M02; women
    are then filtered within each side, so no woman changes side.
    """
    train, test = ac.household_split(sample)
    train_status = train["respondent_id"].map(status).to_numpy()
    test_status = test["respondent_id"].map(status).to_numpy()

    def keep(frame, mask):
        return frame[mask].reset_index(drop=True)

    scenarios = {
        "All labelled women (M02)": (train, test),
        "M02 models, confirmed not-pregnant test women":
            (train, keep(test, test_status == NOT_PREGNANT)),
        "Refit and test on confirmed not-pregnant women":
            (keep(train, train_status == NOT_PREGNANT), keep(test, test_status == NOT_PREGNANT)),
        "Refit and test excluding confirmed pregnant women":
            (keep(train, train_status != PREGNANT), keep(test, test_status != PREGNANT)),
    }
    rows = [{"scenario": name, "train_n": len(fit), **rb.held_out_comparison(fit, held)}
            for name, (fit, held) in scenarios.items()]
    return pd.DataFrame(rows)


def stated_brier_on(frame: pd.DataFrame) -> float:
    return brier_score_loss(frame["outcome"], frame["expectation_prob"])


def load_pregnancy_frame() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Primary cohort joined to pregnancy status, the joined eligible data and birth timing."""
    eligible = se.load_joined_eligible(bo.required_columns())
    cohort = rebuild_primary_cohort(eligible)
    status = pregnancy_table(eligible)
    frame = cohort.set_index("respondent_id").join(status, how="left")
    if frame["pregnancy_status"].isna().any():
        raise ValueError("Pregnancy status missing for an eligible woman")
    timing = rb.qualifying_birth_timing(eligible, cohort)
    return frame, eligible, timing


def format_ci(ci) -> str:
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def main() -> None:
    pd.set_option("display.width", 180)
    pd.set_option("display.max_columns", 40)
    frame, _, timing = load_pregnancy_frame()

    print("THE INTENTION GAP | PREGNANCY AT THE ROUND 13 INTERVIEW")
    print("=" * 72)
    print(f"\nPregnancy status, {len(frame):,} eligible women")
    print(status_counts(frame).round(1).to_string(index=False))
    totals = frame["pregnancy_status"].value_counts()
    for name in STATUSES:
        print(f"  {name:<14} {totals.get(name, 0):>6,}  ({100 * totals.get(name, 0) / len(frame):.1f}%)")
    pregnant = frame[frame["pregnancy_status"] == PREGNANT]
    print(f"  Pregnant women with valid weeks: {int(pregnant['weeks_pregnant'].notna().sum())}; "
          f"median weeks {pregnant['weeks_pregnant'].median():.0f}; "
          f"weeks code counts outside 1-40: "
          f"{pregnant.loc[pregnant['weeks_pregnant'].isna(), 'weeks_code'].value_counts().to_dict()}")

    print("\nStated expectations by pregnancy status")
    print(expectations_by_status(frame).round(1).to_string())
    print("\nOutcomes by pregnancy status (primary labels)")
    print(outcomes_by_status(frame, timing).round(3).to_string())
    print("\nConfirmed positives: months from interview to first qualifying birth")
    print(first_birth_timing_by_status(frame, timing).to_string())
    print("\nReported weeks against observed first-birth timing (pregnant women)")
    for key, value in gestation_agreement(frame, timing).items():
        print(f"  {key:<36} {value:.2f}" if isinstance(value, float) else f"  {key:<36} {value}")
    print("\nDocumented status against the early-birth proxy (labelled women)")
    print(documented_versus_inferred(frame, timing).to_string())

    print("\nStated-forecast performance by subgroup (all labelled women in each group)")
    table = subgroup_table(frame)
    for column in ("slope_ci", "brier_ci", "auc_ci"):
        table[column] = table[column].map(lambda ci: format_ci(ci) if isinstance(ci, tuple) else "")
    columns = ["subgroup", "n", "births", "observed_rate", "mean_stated", "observed_at_0",
               "observed_at_50", "observed_at_100", "slope", "slope_ci", "brier_stated",
               "brier_ci", "brier_constant_cv", "brier_recalibrated_cv", "auc_stated", "auc_ci",
               "too_extreme", "overestimates_on_average", "recalibration_improves"]
    print(table[columns].round(3).T.to_string(header=False))

    labelled = frame[frame["outcome"].notna()].copy()
    labelled["outcome"] = labelled["outcome"].astype(int)
    for name in (NOT_PREGNANT, PREGNANT):
        print(f"\nCalibration at 0, 50 and 100%: {name.replace('_', ' ')} (Wilson 95% intervals)")
        print(calibration_points(labelled[labelled["pregnancy_status"] == name]).round(1).to_string())

    print("\nHeld-out comparison on the original household split (seed "
          f"{ac.SPLIT_SEED}; household bootstrap seed {ac.BOOTSTRAP_SEED})")
    sample = ac.labelled_sample(ac.load_cohort())
    held = held_out_by_pregnancy(sample, frame["pregnancy_status"])
    for column in ("c_minus_b_brier_ci", "d_minus_c_brier_ci", "d_minus_c_auc_ci"):
        held[column] = held[column].map(lambda ci: f"[{ci[0]:+.4f}, {ci[1]:+.4f}]")
    print(held.round(4).T.to_string(header=False))


if __name__ == "__main__":
    main()
