"""Build the five-year fertility outcome cohort for The Intention Gap.

Reads the raw NLSY97 extract (read only), selects women with a valid 2009
fertility expectation, classifies each woman's five-year outcome from the
2009, 2015 and 2017 biological-child rosters, and writes a local
respondent-level research file to data/processed/intention_gap_cohort.csv.

The outcome rules are documented in docs/methodology.md. Only aggregate
counts are printed.
"""

from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from analysis.nlsy97 import (
    BASELINE_ROUND,
    BIRTH_MONTH,
    BIRTH_YEAR,
    CHILD_BIRTH_MONTH,
    EXPECTATION,
    FAMILY_INCOME_2009,
    FEMALE,
    FOLLOWUP_ROUNDS,
    HIGHEST_GRADE_2009,
    HOUSEHOLD_ID,
    INTERVIEW_MONTH,
    MARITAL_STATUS_2009,
    PROJECT_ROOT,
    RACE_ETHNICITY,
    RAW_DATA_PATH,
    RESPONDENT_ID,
    SAMPLE_TYPE,
    SEX,
    WEIGHT_2009,
    assess_roster,
    cmonth_from_date,
)

OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "intention_gap_cohort.csv"
EXPECTED_ELIGIBLE = 3660
WINDOW_MONTHS = 60
EARLY_BIRTH_AGE = 13

# Evidence status of a single follow-up roster
POSITIVE = "positive"
NEGATIVE = "negative"
AMBIGUOUS = "ambiguous"
CONFLICT = "conflict"

# Treatments available for boundary-month births under OutcomeRules
QUALIFYING = "qualifying"
NOT_QUALIFYING = "not_qualifying"

# Reasons an outcome remains unknown, in order of precedence
NO_FOLLOWUP_INTERVIEW = "no_followup_interview"
INCOMPLETE_FOLLOWUP = "incomplete_followup_roster"
BASELINE_ROSTER_UNUSABLE = "baseline_roster_unusable"
ROUNDS_DISAGREE = "followup_rounds_disagree"
RECORD_CONFLICT = "birth_record_conflict"
BASELINE_MONTH_TIMING = "baseline_month_birth_timing"
ANNIVERSARY_MONTH_TIMING = "anniversary_month_birth_timing"
UNKNOWN_REASONS = [
    NO_FOLLOWUP_INTERVIEW,
    INCOMPLETE_FOLLOWUP,
    BASELINE_ROSTER_UNUSABLE,
    ROUNDS_DISAGREE,
    RECORD_CONFLICT,
    BASELINE_MONTH_TIMING,
    ANNIVERSARY_MONTH_TIMING,
]

FLAG_NAMES = [
    "flag_baseline_month_birth_pre_interview",
    "flag_baseline_month_birth_ambiguous",
    "flag_anniversary_month_birth",
    "flag_baseline_record_discrepancy",
    "flag_followup_window_records_differ",
    "flag_incomplete_roster_2015",
    "flag_incomplete_roster_2017",
    "flag_early_birth_under_13",
]


@dataclass(frozen=True)
class OutcomeRules:
    """Classification switches for sensitivity analysis.

    The defaults define the primary conservative outcome. Unmatched
    baseline-month births and anniversary-month births may each be treated
    as AMBIGUOUS, QUALIFYING or NOT_QUALIFYING. With
    reconcile_with_baseline_roster=False, follow-up birth dates are accepted
    as reported. preferred_round, if set, decides between usable follow-up
    rounds that disagree. With strict_date_reconciliation=True, pre-baseline
    births are matched to the 2009 roster by exact month, so a re-dated child
    counts as both a missing and an extra birth; the primary rule matches by
    count only.
    """

    baseline_month_birth: str = AMBIGUOUS
    anniversary_month_birth: str = AMBIGUOUS
    reconcile_with_baseline_roster: bool = True
    preferred_round: int | None = None
    strict_date_reconciliation: bool = False

    def __post_init__(self):
        treatments = {AMBIGUOUS, QUALIFYING, NOT_QUALIFYING}
        if {self.baseline_month_birth, self.anniversary_month_birth} - treatments:
            raise ValueError(f"Boundary-month treatment must be one of {sorted(treatments)}")
        if self.preferred_round not in (None, *FOLLOWUP_ROUNDS):
            raise ValueError(f"preferred_round must be None or one of {FOLLOWUP_ROUNDS}")


PRIMARY_RULES = OutcomeRules()


@dataclass(frozen=True)
class RosterEvidence:
    """Outcome evidence from one usable follow-up roster."""

    status: str
    n_qualifying: int
    n_baseline_month_pre_interview: int
    n_baseline_month_ambiguous: int
    n_anniversary_month: int
    n_missing_baseline_births: int
    n_extra_pre_baseline_births: int
    baseline_dates_changed: bool

    @property
    def has_baseline_discrepancy(self) -> bool:
        return bool(
            self.n_missing_baseline_births
            or self.n_extra_pre_baseline_births
            or self.baseline_dates_changed
        )


@dataclass
class OutcomeResult:
    outcome: int | None
    unknown_reason: str | None
    rounds_used: tuple[int, ...] = ()
    flags: dict[str, bool] = field(default_factory=dict)


def evaluate_followup_roster(
    births: list[int],
    baseline_births: list[int],
    baseline_month: int,
    rules: OutcomeRules = PRIMARY_RULES,
) -> RosterEvidence:
    """Classify the five-year evidence in one follow-up roster.

    Window months, with B the baseline interview month:
        b < B          before baseline
        b == B         pre-interview if matched by a 2009 roster entry in
                       month B, otherwise ambiguous (day of month unknown)
        B < b < B+60   qualifying
        b == B+60      anniversary month, ambiguous
        b > B+60       after the window

    Births are reconciled with the 2009 roster by counting pre-baseline
    births, because slot numbers are not stable across rounds; changed dates
    with an unchanged count are flagged only. If the follow-up roster has
    fewer pre-baseline births than the 2009 roster, a child may have been
    re-dated into the window, so qualifying births count only if they
    outnumber the missing births. If it has more, a window birth may have
    been misdated, so a negative is not possible.

    Alternative rules change only how boundary-month births and
    reconciliation discrepancies affect the status; the recorded counts are
    the same under every rule set.
    """
    anniversary = baseline_month + WINDOW_MONTHS
    before = [b for b in births if b < baseline_month]
    n_at_baseline = sum(b == baseline_month for b in births)
    n_qualifying = sum(baseline_month < b < anniversary for b in births)
    n_anniversary = sum(b == anniversary for b in births)

    n_baseline_roster_at_baseline = sum(b == baseline_month for b in baseline_births)
    n_pre_interview = min(n_at_baseline, n_baseline_roster_at_baseline)
    n_ambiguous_at_baseline = n_at_baseline - n_pre_interview

    reported_pre_baseline = sorted(before + [baseline_month] * n_pre_interview)
    difference = len(reported_pre_baseline) - len(baseline_births)
    n_missing = max(0, -difference)
    n_extra = max(0, difference)
    dates_changed = difference == 0 and reported_pre_baseline != sorted(baseline_births)

    n_counted = n_qualifying
    if rules.baseline_month_birth == QUALIFYING:
        n_counted += n_ambiguous_at_baseline
    if rules.anniversary_month_birth == QUALIFYING:
        n_counted += n_anniversary
    has_ambiguous_birth = (
        (n_ambiguous_at_baseline and rules.baseline_month_birth == AMBIGUOUS)
        or (n_anniversary and rules.anniversary_month_birth == AMBIGUOUS)
    )
    if rules.strict_date_reconciliation:
        reported, recorded = Counter(reported_pre_baseline), Counter(baseline_births)
        missing_for_status = sum((recorded - reported).values())
        extra_for_status = sum((reported - recorded).values())
    else:
        missing_for_status, extra_for_status = n_missing, n_extra
    if not rules.reconcile_with_baseline_roster:
        missing_for_status = extra_for_status = 0

    if n_counted > missing_for_status:
        status = POSITIVE
    elif n_counted > 0 or extra_for_status > 0:
        status = CONFLICT
    elif has_ambiguous_birth:
        status = AMBIGUOUS
    else:
        status = NEGATIVE

    return RosterEvidence(
        status=status,
        n_qualifying=n_qualifying,
        n_baseline_month_pre_interview=n_pre_interview,
        n_baseline_month_ambiguous=n_ambiguous_at_baseline,
        n_anniversary_month=n_anniversary,
        n_missing_baseline_births=n_missing,
        n_extra_pre_baseline_births=n_extra,
        baseline_dates_changed=dates_changed,
    )


def classify_outcome(
    baseline_month: int,
    rosters: dict[int, list[int]],
    interview_months: dict[int, int],
    rules: OutcomeRules = PRIMARY_RULES,
    baseline_round: int = BASELINE_ROUND,
    followup_rounds: tuple[int, ...] = FOLLOWUP_ROUNDS,
) -> OutcomeResult:
    """Assign a five-year outcome (1, 0 or None) from raw roster slot values.

    rosters maps each round (by default 2009, 2015, 2017) to its raw
    CV_CHILD_BIRTH_MONTH slot values; interview_months maps each round to
    CV_INTERVIEW_CMONTH. A follow-up roster is used only if it is usable and
    the interview took place after the anniversary month. Under the primary
    rules, all used follow-up rosters must agree and no round is preferred.
    Other baseline and follow-up rounds apply the same rules unchanged.
    """
    anniversary = baseline_month + WINDOW_MONTHS
    assessments = {
        year: assess_roster(rosters[year], interview_months[year])
        for year in (baseline_round, *followup_rounds)
    }
    flags = dict.fromkeys(FLAG_NAMES, False)
    for year in followup_rounds:
        flags[f"flag_incomplete_roster_{year}"] = (
            assessments[year]["interviewed"] and not assessments[year]["usable"]
        )

    rounds_used = tuple(
        year for year in followup_rounds
        if assessments[year]["usable"] and interview_months[year] > anniversary
    )
    if not rounds_used:
        interviewed = any(assessments[year]["interviewed"] for year in followup_rounds)
        reason = INCOMPLETE_FOLLOWUP if interviewed else NO_FOLLOWUP_INTERVIEW
        return OutcomeResult(None, reason, rounds_used, flags)

    baseline = assessments[baseline_round]
    if not baseline["usable"]:
        return OutcomeResult(None, BASELINE_ROSTER_UNUSABLE, rounds_used, flags)

    evidence = {
        year: evaluate_followup_roster(
            assessments[year]["births"], baseline["births"], baseline_month, rules
        )
        for year in rounds_used
    }
    flags["flag_baseline_month_birth_pre_interview"] = any(
        e.n_baseline_month_pre_interview for e in evidence.values())
    flags["flag_baseline_month_birth_ambiguous"] = any(
        e.n_baseline_month_ambiguous for e in evidence.values())
    flags["flag_anniversary_month_birth"] = any(
        e.n_anniversary_month for e in evidence.values())
    flags["flag_baseline_record_discrepancy"] = any(
        e.has_baseline_discrepancy for e in evidence.values())
    if len(rounds_used) > 1:
        window_births = [
            [b for b in assessments[year]["births"] if baseline_month <= b <= anniversary]
            for year in rounds_used
        ]
        flags["flag_followup_window_records_differ"] = any(
            births != window_births[0] for births in window_births[1:])

    statuses = {e.status for e in evidence.values()}
    if len(statuses) > 1 and rules.preferred_round in evidence:
        statuses = {evidence[rules.preferred_round].status}
    if statuses == {POSITIVE}:
        return OutcomeResult(1, None, rounds_used, flags)
    if statuses == {NEGATIVE}:
        return OutcomeResult(0, None, rounds_used, flags)

    if {POSITIVE, NEGATIVE} <= statuses:
        reason = ROUNDS_DISAGREE
    elif CONFLICT in statuses:
        reason = RECORD_CONFLICT
    elif len(statuses) > 1:
        reason = ROUNDS_DISAGREE
    elif (flags["flag_baseline_month_birth_ambiguous"]
          and rules.baseline_month_birth == AMBIGUOUS):
        reason = BASELINE_MONTH_TIMING
    else:
        reason = ANNIVERSARY_MONTH_TIMING
    return OutcomeResult(None, reason, rounds_used, flags)


def required_columns() -> list[str]:
    columns = [
        RESPONDENT_ID, HOUSEHOLD_ID, SEX, BIRTH_MONTH, BIRTH_YEAR, SAMPLE_TYPE,
        RACE_ETHNICITY, HIGHEST_GRADE_2009, FAMILY_INCOME_2009,
        MARITAL_STATUS_2009, WEIGHT_2009, EXPECTATION, *INTERVIEW_MONTH.values(),
    ]
    for slots in CHILD_BIRTH_MONTH.values():
        columns += slots
    return columns


def load_eligible(path=RAW_DATA_PATH) -> tuple[pd.DataFrame, int]:
    """Return eligible women (female, expectation 0-100) and the full row count."""
    columns = required_columns()
    available = pd.read_csv(path, nrows=0).columns
    missing_columns = [column for column in columns if column not in available]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    data = pd.read_csv(path, usecols=columns)
    if data.isna().any().any():
        raise ValueError("Unexpected blank cells in required columns")

    eligible = data[(data[SEX] == FEMALE) & data[EXPECTATION].between(0, 100)].copy()
    return eligible, len(data)


def nonnegative_or_na(series: pd.Series) -> pd.Series:
    """Replace NLSY97 negative missing-value codes with NA."""
    return series.where(series >= 0).astype("Int64")


def build_cohort(eligible: pd.DataFrame, rules: OutcomeRules = PRIMARY_RULES) -> pd.DataFrame:
    """Classify outcomes and assemble the respondent-level cohort table."""
    baseline_months = eligible[INTERVIEW_MONTH[BASELINE_ROUND]]
    own_birth = cmonth_from_date(eligible[BIRTH_YEAR], eligible[BIRTH_MONTH])

    records = []
    for i, row in eligible.iterrows():
        rosters = {year: [row[c] for c in slots] for year, slots in CHILD_BIRTH_MONTH.items()}
        interview_months = {year: int(row[c]) for year, c in INTERVIEW_MONTH.items()}
        result = classify_outcome(int(baseline_months[i]), rosters, interview_months, rules)

        baseline_roster = assess_roster(rosters[BASELINE_ROUND], interview_months[BASELINE_ROUND])
        all_births = [value for slots in rosters.values() for value in slots if value > 0]
        flags = dict(result.flags)
        flags["flag_early_birth_under_13"] = bool(all_births) and (
            min(all_births) - own_birth[i] < EARLY_BIRTH_AGE * 12
        )

        records.append({
            "outcome": result.outcome,
            "outcome_status": "unknown" if result.outcome is None else "confirmed",
            "unknown_reason": result.unknown_reason,
            "followup_rounds_used": "+".join(str(y) for y in result.rounds_used),
            "interviewed_2015": interview_months[2015] > 0,
            "interviewed_2017": interview_months[2017] > 0,
            "parity_at_baseline": (
                baseline_roster["n_births"] if baseline_roster["usable"] else None
            ),
            **flags,
        })
    results = pd.DataFrame(records, index=eligible.index)

    highest_grade = eligible[HIGHEST_GRADE_2009]
    cohort = pd.DataFrame({
        # Identifiers: for linkage and grouped splitting only, never features.
        "respondent_id": eligible[RESPONDENT_ID],
        "household_id": eligible[HOUSEHOLD_ID],
        # Target and label provenance (post-baseline information).
        "outcome": results["outcome"].astype("Int64"),
        "outcome_status": results["outcome_status"],
        "unknown_reason": results["unknown_reason"],
        "followup_rounds_used": results["followup_rounds_used"],
        "interviewed_2015": results["interviewed_2015"],
        "interviewed_2017": results["interviewed_2017"],
        **{name: results[name] for name in FLAG_NAMES},
        # Baseline (2009 or earlier) information.
        "expectation_pct": eligible[EXPECTATION],
        "expectation_prob": eligible[EXPECTATION] / 100,
        "baseline_interview_cmonth": baseline_months,
        "age_at_baseline": ((baseline_months - own_birth) / 12).round(2),
        "parity_at_baseline": results["parity_at_baseline"].astype("Int64"),
        "race_ethnicity": eligible[RACE_ETHNICITY],
        "cross_sectional_sample": eligible[SAMPLE_TYPE],
        "highest_grade_2009": nonnegative_or_na(highest_grade.where(highest_grade != 95)),
        "family_income_2009": nonnegative_or_na(eligible[FAMILY_INCOME_2009]),
        "marital_status_2009": nonnegative_or_na(eligible[MARITAL_STATUS_2009]),
        "sampling_weight_2009": eligible[WEIGHT_2009] / 100,
    })
    return cohort.reset_index(drop=True)


def validate_cohort(cohort: pd.DataFrame) -> None:
    """Raise if outcome counts do not reconcile with the eligible sample."""
    n = len(cohort)
    if n != EXPECTED_ELIGIBLE:
        raise ValueError(f"Expected {EXPECTED_ELIGIBLE} eligible women, found {n}")
    labelled = cohort["outcome"].notna()
    counted = int(labelled.sum()) + int(cohort["unknown_reason"].notna().sum())
    if counted != n:
        raise ValueError("Outcome and unknown-reason counts do not sum to the sample")
    if (labelled & cohort["unknown_reason"].notna()).any():
        raise ValueError("A labelled respondent also has an unknown reason")
    if not cohort.loc[labelled, "outcome"].isin([0, 1]).all():
        raise ValueError("Outcome contains values other than 0 and 1")
    if not cohort["unknown_reason"].dropna().isin(UNKNOWN_REASONS).all():
        raise ValueError("Unrecognised unknown reason")
    if cohort["respondent_id"].duplicated().any():
        raise ValueError("Duplicate respondent identifiers")


def show(label: str, count: int, total: int) -> None:
    print(f"  {label:<52} {count:>6,}  ({100 * count / total:5.1f}%)")


def attrition_table(cohort: pd.DataFrame) -> pd.DataFrame:
    """Unweighted baseline characteristics of labelled vs unlabelled women."""
    groups = {
        "Labelled": cohort["outcome"].notna(),
        "Unknown (all)": cohort["outcome"].isna(),
        "No follow-up interview": cohort["unknown_reason"] == NO_FOLLOWUP_INTERVIEW,
    }
    rows = {}
    for name, mask in groups.items():
        group = cohort[mask]
        rows[name] = {
            "N": len(group),
            "Mean expectation (0-100)": group["expectation_pct"].mean(),
            "Expectation = 0 (%)": 100 * (group["expectation_pct"] == 0).mean(),
            "Expectation = 100 (%)": 100 * (group["expectation_pct"] == 100).mean(),
            "Mean age at baseline": group["age_at_baseline"].mean(),
            "Mean parity at baseline": group["parity_at_baseline"].mean(),
            "Childless at baseline (%)": 100 * (group["parity_at_baseline"] == 0).mean(),
            "Married at baseline (%)": 100 * (group["marital_status_2009"] == 1).mean(),
            "Black (%)": 100 * (group["race_ethnicity"] == 1).mean(),
            "Hispanic (%)": 100 * (group["race_ethnicity"] == 2).mean(),
            "Mean secondary-school grade 2009": group["highest_grade_2009"].mean(),
            "Median family income 2009": group["family_income_2009"].median(),
            "Cross-sectional sample (%)": 100 * group["cross_sectional_sample"].mean(),
        }
    return pd.DataFrame(rows).round(1)


def report(cohort: pd.DataFrame, n_total: int) -> None:
    n = len(cohort)
    print("THE INTENTION GAP | FIVE-YEAR OUTCOME COHORT")
    print("=" * 72)
    print(f"Respondents in extract: {n_total:,}   Eligible women: {n:,}")

    print("\nOutcomes")
    show("Confirmed positive (1)", int((cohort["outcome"] == 1).sum()), n)
    show("Confirmed negative (0)", int((cohort["outcome"] == 0).sum()), n)
    show("Unknown", int(cohort["outcome"].isna().sum()), n)

    print("\nUnknown reasons (one primary reason per respondent)")
    for reason in UNKNOWN_REASONS:
        show(reason, int((cohort["unknown_reason"] == reason).sum()), n)

    print("\nFollow-up rounds used for labelled respondents")
    labelled = cohort[cohort["outcome"].notna()]
    for rounds, count in labelled["followup_rounds_used"].value_counts().items():
        show(rounds, int(count), n)

    print("\nQuality and boundary flags (not mutually exclusive)")
    for name in FLAG_NAMES:
        flagged = cohort[name]
        show(name, int(flagged.sum()), n)
        by_status = cohort.loc[flagged, "outcome"].value_counts(dropna=False)
        detail = ", ".join(
            f"{'unknown' if pd.isna(k) else int(k)}: {v}" for k, v in by_status.items()
        )
        if detail:
            print(f"  {'':<52} [{detail}]")

    print("\nPreliminary attrition comparison (unweighted, baseline variables only)")
    print(attrition_table(cohort).to_string())


def main() -> None:
    eligible, n_total = load_eligible()
    cohort = build_cohort(eligible)
    validate_cohort(cohort)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cohort.to_csv(OUTPUT_PATH, index=False)

    report(cohort, n_total)
    print(f"\nWrote {len(cohort):,} rows x {cohort.shape[1]} columns to "
          f"{OUTPUT_PATH.relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
