"""Birth-history quality audit for the NLSY97 Intention Gap extract.

Reports aggregate availability and consistency of the 2009, 2015 and 2017
biological-child rosters for women with a valid 2009 fertility expectation.
The raw file is read only; no respondent-level values or identifiers are
printed.

Assumptions:
    - Continuous months start at January 1980 = 1.
    - CV_CHILD_BIRTH_MONTH rosters are cumulative (every biological child
      ever reported). The codebook does not state this; the cross-round
      comparison below provides empirical support.
    - Section D uses a preliminary inclusive window
      (baseline < birth <= baseline + 60). Final outcome rules are
      implemented in analysis.build_outcomes.
"""

import pandas as pd

from analysis.nlsy97 import (
    BASELINE_ROUND,
    BIRTH_MONTH,
    BIRTH_YEAR,
    CHILD_BIRTH_MONTH,
    EXPECTATION,
    FEMALE,
    INTERVIEW_MONTH,
    MISSING_CODES,
    RAW_DATA_PATH,
    SEX,
    assess_roster,
    cmonth_from_date,
    cmonth_to_text,
)

WINDOW_MONTHS = 60
RULE = "=" * 78


def show(label: str, count: int, total: int) -> None:
    percent = 100 * count / total if total else 0.0
    print(f"  {label:<62} {count:>6,}  ({percent:5.1f}%)")


def load_eligible_women() -> tuple[pd.DataFrame, int, int]:
    """Return eligible women plus the full-sample and female row counts."""
    required = [SEX, EXPECTATION, BIRTH_MONTH, BIRTH_YEAR, *INTERVIEW_MONTH.values()]
    for slots in CHILD_BIRTH_MONTH.values():
        required += slots

    available = pd.read_csv(RAW_DATA_PATH, nrows=0).columns
    missing_columns = [column for column in required if column not in available]
    if missing_columns:
        raise SystemExit(f"Missing required columns: {missing_columns}")

    data = pd.read_csv(RAW_DATA_PATH, usecols=required)
    blank_cells = int(data.isna().sum().sum())
    if blank_cells:
        raise SystemExit(f"Unexpected blank cells in required columns: {blank_cells}")

    women = data[data[SEX] == FEMALE]
    eligible = women[women[EXPECTATION].between(0, 100)].copy()
    return eligible, len(data), len(women)


def assess_all_rosters(sample: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """Assess every round's roster; one row per respondent, indexed like sample."""
    assessments = {}
    for year, slots in CHILD_BIRTH_MONTH.items():
        interview_column = INTERVIEW_MONTH[year]
        records = [
            assess_roster([row[column] for column in slots], row[interview_column])
            for _, row in sample.iterrows()
        ]
        assessments[year] = pd.DataFrame(records, index=sample.index)
    return assessments


def report_round(sample: pd.DataFrame, year: int, facts: pd.DataFrame) -> None:
    n = len(sample)
    slots = CHILD_BIRTH_MONTH[year]
    interviewed = facts["interviewed"]
    usable = facts["usable"]

    print(f"\n{year} roster ({len(slots)} slots, {slots[0]}-{slots[-1]})")
    show("Interviewed", int(interviewed.sum()), n)
    show("Not interviewed (-5): history missing", int((~interviewed).sum()), n)
    show("Interviewed; roster contains -1/-2/-3: history incomplete",
         int((interviewed & facts["has_missing_code"]).sum()), n)
    show("Interviewed; -5 inside roster", int(facts["has_noninterview_code"].sum()), n)
    show("Interviewed; unexpected non-positive value",
         int((interviewed & facts["has_unexpected_value"]).sum()), n)
    show("Interviewed; gap between filled slots", int((interviewed & facts["has_gap"]).sum()), n)
    show("Interviewed; birth dated after interview month",
         int(facts["birth_after_interview"].sum()), n)
    show("Usable history", int(usable.sum()), n)
    show("  Usable, no children reported (slot 1 = -4)",
         int((usable & (facts["n_births"] == 0)).sum()), n)
    show("  Usable, one or more children", int((usable & (facts["n_births"] > 0)).sum()), n)
    show("Births listed out of chronological order", int(facts["out_of_order"].sum()), n)
    show("Every slot filled (possible truncation)", int(facts["all_slots_full"].sum()), n)

    values = sample[slots].stack()
    codes = values[values <= 0].value_counts().sort_index()
    labels = ", ".join(
        f"{MISSING_CODES.get(int(code), 'Unlabelled')} ({int(code)}): {count:,}"
        for code, count in codes.items()
    )
    print(f"  Special codes across all slots: {labels}")


def compare_rounds(
    sample: pd.DataFrame,
    rosters: dict[int, pd.DataFrame],
    earlier: int,
    later: int,
) -> pd.Series:
    """Compare pre-existing births between two rounds, matching by date.

    For women usable in both rounds, births in the later roster dated up to
    the earlier interview month should reproduce the earlier roster. A later
    roster that adds only a birth dated in the earlier interview month is a
    timing artefact (born after the interview day), not a conflict.

    Returns a boolean Series marking women with a genuine conflict.
    """
    both = rosters[earlier]["usable"] & rosters[later]["usable"]
    n_both = int(both.sum())
    cutoff_months = sample[INTERVIEW_MONTH[earlier]]
    conflicted = pd.Series(False, index=sample.index)
    same = timing_only = count_differs = dates_differ = 0

    for i in sample.index[both]:
        cutoff = cutoff_months[i]
        earlier_births = rosters[earlier].at[i, "births"]
        later_births = [b for b in rosters[later].at[i, "births"] if b <= cutoff]
        later_before_cutoff = [b for b in later_births if b < cutoff]
        if earlier_births == later_births:
            same += 1
        elif earlier_births == later_before_cutoff:
            timing_only += 1
        else:
            conflicted[i] = True
            if len(earlier_births) != len(later_births):
                count_differs += 1
            else:
                dates_differ += 1

    print(f"\n{earlier} vs {later} (usable in both: {n_both:,})")
    show("Pre-existing births match exactly", same, n_both)
    show("Differ only by a birth in the earlier interview month", timing_only, n_both)
    show("Conflict: different number of pre-existing births", count_differs, n_both)
    show("Conflict: same number, at least one birth month changed", dates_differ, n_both)
    return conflicted


def window_evidence(births, usable, baseline_month, start_offset, end_offset):
    """True/False if a usable roster shows a birth in the window, else None."""
    if not usable:
        return None
    start = baseline_month + start_offset
    end = baseline_month + end_offset
    return any(start < b <= end for b in births)


def evidence_pattern(sample, rosters, i, start_offset=0, end_offset=WINDOW_MONTHS):
    baseline_month = sample.at[i, INTERVIEW_MONTH[BASELINE_ROUND]]
    answers = {
        window_evidence(rosters[year].at[i, "births"], rosters[year].at[i, "usable"],
                        baseline_month, start_offset, end_offset)
        for year in (2015, 2017)
    }
    answers.discard(None)
    if not answers:
        return "No usable follow-up roster"
    if len(answers) == 2:
        return "2015 and 2017 disagree"
    return "Birth reported in window" if True in answers else "No birth in window"


def main() -> None:
    sample, n_total, n_women = load_eligible_women()
    n = len(sample)
    baseline = sample[INTERVIEW_MONTH[BASELINE_ROUND]]

    print("THE INTENTION GAP | BIRTH-HISTORY QUALITY AUDIT")
    print(RULE)
    print(f"Respondents: {n_total:,}   Women: {n_women:,}   "
          f"Eligible (valid 2009 expectation 0-100): {n:,}")
    print("\nInterview months among eligible women (continuous-month check):")
    for year, column in INTERVIEW_MONTH.items():
        months = sample.loc[sample[column] > 0, column]
        print(f"  {year}: {months.min()}-{months.max()} "
              f"= {cmonth_to_text(months.min())} to {cmonth_to_text(months.max())}")
    show("Eligible women with a valid baseline interview month", int((baseline > 0).sum()), n)

    rosters = assess_all_rosters(sample)

    print("\n" + RULE)
    print("A. BIRTH-HISTORY AVAILABILITY BY ROUND")
    for year, facts in rosters.items():
        report_round(sample, year, facts)

    print("\n" + RULE)
    print("B. FOLLOW-UP COVERAGE")
    use15, use17 = rosters[2015]["usable"], rosters[2017]["usable"]
    int15, int17 = rosters[2015]["interviewed"], rosters[2017]["interviewed"]
    show("Usable 2015 and usable 2017", int((use15 & use17).sum()), n)
    show("Usable 2015 only", int((use15 & ~use17).sum()), n)
    show("Usable 2017 only", int((~use15 & use17).sum()), n)
    show("Neither follow-up roster usable", int((~use15 & ~use17).sum()), n)
    show("  Not interviewed in either round", int((~int15 & ~int17).sum()), n)
    show("  Interviewed, but roster(s) incomplete",
         int((~use15 & ~use17 & (int15 | int17)).sum()), n)
    show("Interviewed 2015, not 2017", int((int15 & ~int17).sum()), n)
    show("Interviewed 2017, not 2015", int((~int15 & int17).sum()), n)
    show("Interviewed in 2015 or 2017", int((int15 | int17).sum()), n)

    followup_months = sample[[INTERVIEW_MONTH[2015], INTERVIEW_MONTH[2017]]]
    latest_window_end = int(baseline.max()) + WINDOW_MONTHS
    earliest_followup = int(followup_months.where(followup_months > 0).min().min())
    print(f"  Latest window end {latest_window_end} ({cmonth_to_text(latest_window_end)}); "
          f"earliest follow-up interview {earliest_followup} "
          f"({cmonth_to_text(earliest_followup)})")
    if earliest_followup > latest_window_end:
        print("  Every follow-up interview occurs after the 60-month window closes.")

    print("\n" + RULE)
    print("C. CONSISTENCY ACROSS ROUNDS (births matched by date, not slot number)")
    conflicts_09_15 = compare_rounds(sample, rosters, 2009, 2015)
    conflicts_15_17 = compare_rounds(sample, rosters, 2015, 2017)

    own_birth = cmonth_from_date(sample[BIRTH_YEAR], sample[BIRTH_MONTH])
    earliest_birth = pd.Series(
        [min(sum((rosters[year].at[i, "births"] for year in rosters), []), default=None)
         for i in sample.index],
        index=sample.index, dtype="float64",
    )
    age_at_first_birth = (earliest_birth - own_birth) / 12
    print("\nRespondent age at earliest recorded birth (any round)")
    show("Under 10 (biologically implausible)", int((age_at_first_birth < 10).sum()), n)
    show("10 to under 13 (requires verification)",
         int(age_at_first_birth.between(10, 13, inclusive="left").sum()), n)

    print("\n" + RULE)
    print("D. PRELIMINARY WINDOW EVIDENCE (baseline < birth <= baseline + 60; not labels)")
    patterns = pd.Series({i: evidence_pattern(sample, rosters, i) for i in sample.index})
    for name in ["Birth reported in window", "No birth in window",
                 "2015 and 2017 disagree", "No usable follow-up roster"]:
        show(name, int((patterns == name).sum()), n)

    followup_births = {
        i: rosters[2015].at[i, "births"] + rosters[2017].at[i, "births"] for i in sample.index
    }
    in_baseline_month = pd.Series(
        {i: baseline[i] in followup_births[i] for i in sample.index})
    in_2009_roster = pd.Series(
        {i: baseline[i] in rosters[2009].at[i, "births"] for i in sample.index})

    print("\nBirths dated in the baseline interview month")
    show("Follow-up roster lists a birth in the baseline month", int(in_baseline_month.sum()), n)
    show("  Also listed in 2009 roster (born before interview)",
         int((in_baseline_month & in_2009_roster).sum()), n)
    show("  Absent from 2009 roster (timing ambiguous)",
         int((in_baseline_month & ~in_2009_roster).sum()), n)

    print("\nRespondents changing category under alternative boundaries")
    alternatives = {
        "Include baseline-month births (baseline <= birth)": (-1, WINDOW_MONTHS),
        "Window ends at baseline + 59": (0, WINDOW_MONTHS - 1),
        "Window ends at baseline + 61": (0, WINDOW_MONTHS + 1),
    }
    for label, (start_offset, end_offset) in alternatives.items():
        alternative = pd.Series({
            i: evidence_pattern(sample, rosters, i, start_offset, end_offset)
            for i in sample.index
        })
        show(label, int((alternative != patterns).sum()), n)

    print("\n" + RULE)
    print("E. FLAGGED CASES (not mutually exclusive)")
    any_conflict = conflicts_09_15 | conflicts_15_17
    outcome_flags = {
        "No usable follow-up roster": patterns == "No usable follow-up roster",
        "2015 vs 2017 disagree on window birth": patterns == "2015 and 2017 disagree",
        "Baseline-month birth absent from 2009 roster": in_baseline_month & ~in_2009_roster,
        "Roster conflict and a window birth (possible re-dating)":
            any_conflict & (patterns == "Birth reported in window"),
    }
    other_flags = {
        "2009 roster unusable (baseline parity unknown)": ~rosters[2009]["usable"],
        "Any cross-round roster conflict": any_conflict,
        "Earliest birth before respondent age 13": age_at_first_birth < 13,
    }
    flags = pd.DataFrame({**outcome_flags, **other_flags})
    for name in flags.columns:
        show(name, int(flags[name].sum()), n)
    show("Any flag", int(flags.any(axis=1).sum()), n)
    show("Any outcome-relevant flag",
         int(flags[list(outcome_flags)].any(axis=1).sum()), n)

    print("\nAudit complete. Raw data were read only; no labels were saved.")


if __name__ == "__main__":
    main()
