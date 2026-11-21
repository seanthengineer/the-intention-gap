"""Expanded birth-history validation using the 2010, 2011, 2013 and 2019 rosters.

The primary cohort (2009 baseline, 2015 and 2017 follow-up rosters) is not
modified. This module:

- audits roster quality, implausible dates and child counts in every round;
- compares rosters across rounds by date, never by slot position;
- reclassifies the five-year outcome with the additional rosters under two
  pre-specified rule sets, and writes the result to a separate local
  sensitivity cohort;
- re-runs the calibration summary and the held-out comparison on the
  revised labels.

Rule sets (both use build_outcomes.evaluate_followup_roster for every roster
against the 2009 roster, unchanged):

    complete rosters  2015, 2017 and 2019 rosters that are usable and were
                      collected after the anniversary month. All must agree,
                      as in the primary rule; no round is preferred.
    interim rosters   usable 2010, 2011 and 2013 rosters. Every one of these
                      interviews precedes every anniversary month, so they
                      can show that a birth occurred but never that none did.

    conservative      A label is withdrawn (unknown) if an interim roster
                      conflicts with the 2009 roster, or if the window births
                      recorded up to an interim interview differ from those a
                      later roster places in the same period. A woman with no
                      complete roster is positive if an interim roster shows a
                      qualifying birth and no such discrepancy exists.
    lenient           As conservative, but window discrepancies are flagged
                      without withdrawing the label.

All records come from the same longitudinal survey, so agreement between
rounds is a consistency check, not independent verification. Only
aggregate results are printed.
"""

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from analysis import analyze_calibration as ac
from analysis import build_outcomes as bo
from analysis import pregnancy_status as ps
from analysis import robustness_analysis as rb
from analysis import supplement_extract as se
from analysis.nlsy97 import (
    BASELINE_ROUND, BIRTH_MONTH, BIRTH_YEAR, CHILD_BIRTH_MONTH, INTERVIEW_MONTH,
    NONRESPONSE_CODES, PROJECT_ROOT, RESPONDENT_ID, VALID_SKIP, assess_roster,
    cmonth_from_date,
)

OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "intention_gap_cohort_expanded.csv"

ALL_SLOTS = dict(sorted({**CHILD_BIRTH_MONTH, **se.SUPPLEMENT_CHILD_BIRTH_MONTH}.items()))
ALL_INTERVIEWS = dict(sorted({**INTERVIEW_MONTH, **se.SUPPLEMENT_INTERVIEW_MONTH}.items()))
ROUNDS = tuple(ALL_SLOTS)
INTERIM_ROUNDS = (2010, 2011, 2013)
COMPLETE_ROUNDS = (2015, 2017, 2019)
ADJACENT_PAIRS = list(zip(ROUNDS[:-1], ROUNDS[1:])) + [(2009, 2019), (2015, 2019)]

INTERIM_CONFLICT = "interim_roster_conflict"
WINDOW_DISCREPANCY = "window_births_differ_across_rounds"
EXPANDED_UNKNOWN_REASONS = [*bo.UNKNOWN_REASONS, INTERIM_CONFLICT, WINDOW_DISCREPANCY]

CONSERVATIVE = "conservative"
LENIENT = "lenient"
SHORT_SPACING_MONTHS = 6

IDENTICAL = "identical"
REDATED = "same count, dates revised"
DROPPED = "births missing from later roster"
ADDED = "earlier-dated births added later"


@dataclass
class ExpandedResult:
    outcome: int | None
    reason: str | None
    complete_used: tuple[int, ...] = ()
    interim_used: tuple[int, ...] = ()
    flags: dict[str, bool] = field(default_factory=dict)


def compare_rosters(earlier: list[int], earlier_interview: int, later: list[int]) -> dict:
    """Compare a later roster with an earlier one over the period both cover.

    Later births dated in the earlier interview month are matched to earlier
    births in that month first; any surplus may have been born after the
    earlier interview and is ignored.
    """
    before = [b for b in later if b < earlier_interview]
    surplus_month = sum(b == earlier_interview for b in later)
    matched_month = min(surplus_month, sum(b == earlier_interview for b in earlier))
    reported = sorted(before + [earlier_interview] * matched_month)
    recorded = sorted(earlier)
    difference = len(reported) - len(recorded)
    if difference < 0:
        category = DROPPED
    elif difference > 0:
        category = ADDED
    elif reported == recorded:
        category = IDENTICAL
    else:
        category = REDATED
    shift = max((abs(a - b) for a, b in zip(reported, recorded)), default=0) if difference == 0 else 0
    return {"category": category, "n_dropped": max(0, -difference),
            "n_added": max(0, difference), "max_shift": shift}


def window_births_consistent(earlier: list[int], earlier_interview: int, later: list[int],
                             baseline_month: int, tolerance: int = 0) -> bool:
    """Do two rosters agree on births from the baseline month to the earlier interview?

    A later birth dated in the earlier interview month may have occurred
    after that interview, so it is allowed either way. A positive tolerance
    also allows later births dated that many months either side of the
    earlier interview.
    """
    recorded = sum(baseline_month <= b <= earlier_interview for b in earlier)
    strictly_before = sum(baseline_month <= b < earlier_interview - tolerance for b in later)
    through = sum(baseline_month <= b <= earlier_interview + tolerance for b in later)
    return strictly_before <= recorded <= through


def classify_expanded(baseline_month: int, rosters: dict[int, list[int]],
                      interview_months: dict[int, int], mode: str = CONSERVATIVE) -> ExpandedResult:
    """Five-year outcome using every available roster (see module docstring)."""
    if mode not in (CONSERVATIVE, LENIENT):
        raise ValueError(f"mode must be {CONSERVATIVE!r} or {LENIENT!r}")
    anniversary = baseline_month + bo.WINDOW_MONTHS
    assessments = {year: assess_roster(rosters[year], interview_months[year]) for year in ROUNDS}
    for year in INTERIM_ROUNDS:
        if assessments[year]["interviewed"] and interview_months[year] >= anniversary:
            raise ValueError(f"{year} interview on or after the anniversary month")
    flags = {"interim_conflict": False, "window_discrepancy": False}

    complete = tuple(year for year in COMPLETE_ROUNDS
                     if assessments[year]["usable"] and interview_months[year] > anniversary)
    interim = tuple(year for year in INTERIM_ROUNDS
                    if assessments[year]["usable"] and interview_months[year] > baseline_month)
    interviewed_complete = any(assessments[year]["interviewed"] for year in COMPLETE_ROUNDS)
    baseline = assessments[BASELINE_ROUND]
    if not baseline["usable"]:
        return ExpandedResult(None, bo.BASELINE_ROSTER_UNUSABLE, complete, interim, flags)

    def evidence(year):
        return bo.evaluate_followup_roster(assessments[year]["births"], baseline["births"],
                                           baseline_month)

    interim_status = {year: evidence(year).status for year in interim}
    flags["interim_conflict"] = bo.CONFLICT in interim_status.values()
    for earlier in interim:
        for later in (*interim, *complete):
            if later == earlier or interview_months[later] <= interview_months[earlier]:
                continue
            if not window_births_consistent(assessments[earlier]["births"],
                                            interview_months[earlier],
                                            assessments[later]["births"], baseline_month):
                flags["window_discrepancy"] = True

    def withdrawn() -> str | None:
        if flags["interim_conflict"]:
            return INTERIM_CONFLICT
        if flags["window_discrepancy"] and mode == CONSERVATIVE:
            return WINDOW_DISCREPANCY
        return None

    if not complete:
        if bo.POSITIVE in interim_status.values() and withdrawn() is None:
            return ExpandedResult(1, None, complete, interim, flags)
        reason = bo.INCOMPLETE_FOLLOWUP if interviewed_complete else bo.NO_FOLLOWUP_INTERVIEW
        return ExpandedResult(None, withdrawn() or reason, complete, interim, flags)

    statuses = {evidence(year).status for year in complete}
    if statuses == {bo.POSITIVE} or statuses == {bo.NEGATIVE}:
        reason = withdrawn()
        if reason:
            return ExpandedResult(None, reason, complete, interim, flags)
        return ExpandedResult(int(statuses == {bo.POSITIVE}), None, complete, interim, flags)
    if {bo.POSITIVE, bo.NEGATIVE} <= statuses:
        reason = bo.ROUNDS_DISAGREE
    elif bo.CONFLICT in statuses:
        reason = bo.RECORD_CONFLICT
    elif len(statuses) > 1:
        reason = bo.ROUNDS_DISAGREE
    elif any(evidence(year).n_baseline_month_ambiguous for year in complete):
        reason = bo.BASELINE_MONTH_TIMING
    else:
        reason = bo.ANNIVERSARY_MONTH_TIMING
    return ExpandedResult(None, reason, complete, interim, flags)


def row_rosters(row: pd.Series) -> tuple[dict[int, list[int]], dict[int, int]]:
    rosters = {year: [int(row[c]) for c in slots] for year, slots in ALL_SLOTS.items()}
    interviews = {year: int(row[c]) for year, c in ALL_INTERVIEWS.items()}
    return rosters, interviews


def expanded_outcomes(eligible: pd.DataFrame) -> pd.DataFrame:
    """Expanded outcomes under both rule sets, indexed by respondent_id."""
    records = {}
    baseline_column = INTERVIEW_MONTH[BASELINE_ROUND]
    for _, row in eligible.iterrows():
        rosters, interviews = row_rosters(row)
        record = {}
        for mode in (CONSERVATIVE, LENIENT):
            result = classify_expanded(int(row[baseline_column]), rosters, interviews, mode)
            record[f"outcome_{mode}"] = result.outcome
            record[f"reason_{mode}"] = result.reason
            if mode == CONSERVATIVE:
                record["complete_rounds_used"] = "+".join(map(str, result.complete_used))
                record["interim_rounds_used"] = "+".join(map(str, result.interim_used))
                record.update({f"flag_{k}": v for k, v in result.flags.items()})
        records[row[RESPONDENT_ID]] = record
    table = pd.DataFrame.from_dict(records, orient="index")
    for mode in (CONSERVATIVE, LENIENT):
        table[f"outcome_{mode}"] = table[f"outcome_{mode}"].astype("Int64")
    table.index.name = "respondent_id"
    return table


def roster_quality(eligible: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for year in ROUNDS:
        facts = [assess_roster(r[0][year], r[1][year])
                 for r in (row_rosters(row) for _, row in eligible.iterrows())]
        facts = pd.DataFrame(facts)
        interviewed = facts["interviewed"]
        rows[year] = {
            "interviewed": int(interviewed.sum()),
            "usable": int(facts["usable"].sum()),
            "missing_code": int((interviewed & facts["has_missing_code"]).sum()),
            "gap_or_unexpected": int((interviewed & (facts["has_gap"]
                                                     | facts["has_unexpected_value"])).sum()),
            "birth_after_interview": int(facts["birth_after_interview"].sum()),
            "all_slots_full": int((interviewed & facts["all_slots_full"]).sum()),
            "women_with_births": int((facts["n_births"] > 0).sum()),
            "slots": len(ALL_SLOTS[year]),
        }
    return pd.DataFrame(rows).T


def implausible_dates(eligible: pd.DataFrame) -> pd.DataFrame:
    """Women whose roster has a birth before age 13 or two births 1-6 months apart."""
    own_birth = cmonth_from_date(eligible[BIRTH_YEAR], eligible[BIRTH_MONTH])
    rows = {}
    for year in ROUNDS:
        young = spacing_one = spacing_short = 0
        for i, row in eligible.iterrows():
            births = sorted(b for b in (int(row[c]) for c in ALL_SLOTS[year]) if b > 0)
            if not births:
                continue
            young += births[0] - own_birth[i] < bo.EARLY_BIRTH_AGE * 12
            gaps = np.diff(births)
            spacing_one += bool((gaps == 1).any())
            spacing_short += bool(((gaps >= 2) & (gaps <= SHORT_SPACING_MONTHS)).any())
        rows[year] = {"birth_before_age_13": young, "births_1_month_apart": spacing_one,
                      f"births_2_to_{SHORT_SPACING_MONTHS}_months_apart": spacing_short}
    return pd.DataFrame(rows).T


def cross_round_comparison(eligible: pd.DataFrame) -> pd.DataFrame:
    """Whole-history agreement between pairs of usable rosters."""
    rows = []
    for earlier, later in ADJACENT_PAIRS:
        counts = {IDENTICAL: 0, REDATED: 0, DROPPED: 0, ADDED: 0}
        shifts = {"shift_1": 0, "shift_2_12": 0, "shift_over_12": 0}
        both = 0
        for _, row in eligible.iterrows():
            rosters, interviews = row_rosters(row)
            e = assess_roster(rosters[earlier], interviews[earlier])
            l = assess_roster(rosters[later], interviews[later])
            if not (e["usable"] and l["usable"]):
                continue
            both += 1
            result = compare_rosters(e["births"], interviews[earlier], l["births"])
            counts[result["category"]] += 1
            if result["category"] == REDATED:
                shift = result["max_shift"]
                shifts["shift_1" if shift == 1 else "shift_2_12" if shift <= 12
                       else "shift_over_12"] += 1
        rows.append({"pair": f"{earlier}->{later}", "both_usable": both, **counts, **shifts})
    return pd.DataFrame(rows)


def child_count_check(eligible: pd.DataFrame) -> pd.DataFrame:
    """Roster length against CV_BIO_CHILD_HH + CV_BIO_CHILD_NR in the same round."""
    rows = {}
    for year, (resident, nonresident) in se.BIO_CHILD_COUNTS.items():
        tally = dict.fromkeys(["usable_roster", "count_missing_code", "agree",
                               "roster_exceeds_count", "roster_below_count",
                               "skip_code_but_roster_births"], 0)
        for _, row in eligible.iterrows():
            rosters, interviews = row_rosters(row)
            roster = assess_roster(rosters[year], interviews[year])
            if not roster["usable"]:
                continue
            tally["usable_roster"] += 1
            hh, nr = int(row[resident]), int(row[nonresident])
            if hh in NONRESPONSE_CODES or nr in NONRESPONSE_CODES:
                tally["count_missing_code"] += 1
            elif hh == VALID_SKIP and nr == VALID_SKIP:
                key = "agree" if roster["n_births"] == 0 else "skip_code_but_roster_births"
                tally[key] += 1
            elif roster["n_births"] == hh + nr:
                tally["agree"] += 1
            elif roster["n_births"] > hh + nr:
                tally["roster_exceeds_count"] += 1
            else:
                tally["roster_below_count"] += 1
        rows[year] = tally
    return pd.DataFrame(rows).T


def total_children_check(eligible: pd.DataFrame) -> pd.DataFrame:
    """CVC_TTL_BIO_CHILD against the most recent usable roster in this data."""
    rows = {}
    for _, row in eligible.iterrows():
        rosters, interviews = row_rosters(row)
        usable = [year for year in ROUNDS
                  if assess_roster(rosters[year], interviews[year])["usable"]]
        latest = usable[-1] if usable else None
        n = assess_roster(rosters[latest], interviews[latest])["n_births"] if latest else None
        total = int(row[se.TOTAL_BIO_CHILD])
        if latest is None:
            category = "no usable roster"
        elif total == VALID_SKIP:
            category = "skip code; roster empty" if n == 0 else "skip code; roster has births"
        elif total < 0:
            category = "missing code"
        elif total == n:
            category = "equal"
        elif total > n:
            category = "total exceeds roster"
        else:
            category = "total below roster"
        key = (2019 if latest == 2019 else "earlier round", category)
        rows[key] = rows.get(key, 0) + 1
    table = pd.Series(rows).rename("women").rename_axis(["latest_usable_roster", "category"])
    return table.reset_index()


def discrepancy_detail(eligible: pd.DataFrame, frame: pd.DataFrame) -> pd.Series:
    """Women with a window discrepancy, by direction and whether it is near-boundary timing.

    "Near the interim interview" means the rosters agree once later births
    dated within two months of the interim interview are allowed either way;
    such differences cannot move a birth across the five-year window.
    """
    flagged = set(frame.index[frame["flag_window_discrepancy"].astype(bool)])
    tally = {}
    for _, row in eligible[eligible[RESPONDENT_ID].isin(flagged)].iterrows():
        rosters, interviews = row_rosters(row)
        baseline = int(row[INTERVIEW_MONTH[BASELINE_ROUND]])
        anniversary = baseline + bo.WINDOW_MONTHS
        usable = {y: assess_roster(rosters[y], interviews[y]) for y in ROUNDS}
        kinds = set()
        for earlier, later in combinations(ROUNDS, 2):
            if earlier not in INTERIM_ROUNDS or not (usable[earlier]["usable"]
                                                     and usable[later]["usable"]):
                continue
            if later in COMPLETE_ROUNDS and interviews[later] <= anniversary:
                continue
            e, l = usable[earlier]["births"], usable[later]["births"]
            if window_births_consistent(e, interviews[earlier], l, baseline):
                continue
            recorded = sum(baseline <= b <= interviews[earlier] for b in e)
            direction = ("later roster adds a birth before the interim interview"
                         if recorded < sum(baseline <= b < interviews[earlier] for b in l)
                         else "interim birth absent or re-dated in later roster")
            near = window_births_consistent(e, interviews[earlier], l, baseline, tolerance=2)
            kinds.add(f"{direction}; {'within 2 months of interim interview' if near else 'further'}")
        for kind in kinds:
            tally[kind] = tally.get(kind, 0) + 1
    return pd.Series(tally, name="women").sort_index()


def problem_overlap(eligible: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Primary-label status of women affected by each data problem (any round)."""
    own_birth = cmonth_from_date(eligible[BIRTH_YEAR], eligible[BIRTH_MONTH])
    problems = {name: set() for name in ("birth before age 13", "births 1-6 months apart",
                                         "roster below living-child count",
                                         "CVC total below 2019 roster")}
    for i, row in eligible.iterrows():
        rosters, interviews = row_rosters(row)
        pid = row[RESPONDENT_ID]
        for year in ROUNDS:
            roster = assess_roster(rosters[year], interviews[year])
            births = roster["births"]
            if births and births[0] - own_birth[i] < bo.EARLY_BIRTH_AGE * 12:
                problems["birth before age 13"].add(pid)
            gaps = np.diff(births)
            if ((gaps >= 1) & (gaps <= SHORT_SPACING_MONTHS)).any():
                problems["births 1-6 months apart"].add(pid)
            if roster["usable"] and year in se.BIO_CHILD_COUNTS:
                hh, nr = (int(row[c]) for c in se.BIO_CHILD_COUNTS[year])
                if hh >= 0 and nr >= 0 and roster["n_births"] < hh + nr:
                    problems["roster below living-child count"].add(pid)
            if year == 2019 and roster["usable"] and \
                    0 <= int(row[se.TOTAL_BIO_CHILD]) < roster["n_births"]:
                problems["CVC total below 2019 roster"].add(pid)
    status = frame["outcome"].map({1.0: "positive", 0.0: "negative"}).fillna("unknown")
    rows = {name: status[status.index.isin(ids)].value_counts().reindex(
                ["positive", "negative", "unknown"], fill_value=0)
            for name, ids in problems.items()}
    return pd.DataFrame(rows).T


def unresolved_coverage(frame: pd.DataFrame, eligible: pd.DataFrame) -> pd.Series:
    """For women still lacking follow-up, the last round in which they were interviewed."""
    remaining = frame.index[frame["reason_conservative"].isin(
        [bo.NO_FOLLOWUP_INTERVIEW, bo.INCOMPLETE_FOLLOWUP])]
    subset = eligible[eligible[RESPONDENT_ID].isin(remaining)]
    last = []
    for _, row in subset.iterrows():
        rounds = [y for y, c in ALL_INTERVIEWS.items() if int(row[c]) > 0]
        last.append(f"last interviewed {max(rounds)}")
    return pd.Series(last).value_counts().sort_index()


def revision_categories(primary: pd.Series, revised: pd.Series) -> pd.Series:
    p, r = primary.astype("Int64"), revised.astype("Int64")
    categories = pd.Series("", index=p.index)
    categories[p.notna() & (p == r)] = "retained"
    categories[p.notna() & r.notna() & (p != r)] = "challenged: label reversed"
    categories[p.notna() & r.isna()] = "challenged: now unknown"
    categories[p.isna() & r.notna()] = "newly resolved"
    categories[p.isna() & r.isna()] = "remains unknown"
    return categories


def recovery_table(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    original = frame["unknown_reason"].fillna(
        frame["outcome"].map({1.0: "confirmed positive", 0.0: "confirmed negative"}))
    revised = frame[f"reason_{mode}"].fillna(
        frame[f"outcome_{mode}"].astype("Float64").map({1.0: "positive", 0.0: "negative"}))
    return pd.crosstab(original, revised, margins=True)


def resolution_source(frame: pd.DataFrame, mode: str) -> pd.Series:
    resolved = frame[frame["outcome"].isna() & frame[f"outcome_{mode}"].notna()]
    source = np.where(resolved["complete_rounds_used"] == "", "interim roster only",
                      "complete roster " + resolved["complete_rounds_used"])
    return pd.crosstab(source, resolved[f"outcome_{mode}"].astype(int))


def assign_expanded_split(labelled: pd.DataFrame, sample: pd.DataFrame) -> pd.Series:
    """Train/test side for each labelled woman in the revised cohort.

    Households in the original split keep their side. Households new to the
    labelled sample are split once with the original seed and test share.
    """
    train, test = ac.household_split(sample)
    side = pd.Series(index=labelled.index, dtype=object)
    side[labelled["household_id"].isin(train["household_id"]).to_numpy()] = "train"
    side[labelled["household_id"].isin(test["household_id"]).to_numpy()] = "test"
    new = labelled[side.isna().to_numpy()]
    if len(new):
        splitter = GroupShuffleSplit(n_splits=1, test_size=ac.TEST_SIZE,
                                     random_state=ac.SPLIT_SEED)
        new_train, new_test = next(splitter.split(new, groups=new["household_id"]))
        side[new.index[new_train]] = "train"
        side[new.index[new_test]] = "test"
    return side


def modelling_frame(frame: pd.DataFrame, outcome_column: str) -> pd.DataFrame:
    labelled = frame[frame[outcome_column].notna()].copy()
    labelled["outcome"] = labelled[outcome_column].astype(int)
    return labelled


def held_out_expanded(frame: pd.DataFrame, sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    in_original = frame.index.isin(sample["respondent_id"])
    scenarios = {
        "Primary labels (M02)": ("outcome", np.ones(len(frame), bool)),
        "Conservative labels, original sample only": ("outcome_conservative", in_original),
        "Conservative labels, including newly resolved": ("outcome_conservative",
                                                          np.ones(len(frame), bool)),
        "Lenient labels, including newly resolved": ("outcome_lenient",
                                                     np.ones(len(frame), bool)),
        "Conservative labels, confirmed not pregnant": (
            "outcome_conservative", (frame["pregnancy_status"] == ps.NOT_PREGNANT).to_numpy()),
    }
    for name, (column, keep) in scenarios.items():
        labelled = modelling_frame(frame[keep], column).reset_index()
        side = assign_expanded_split(labelled, sample)
        train = labelled[(side == "train").to_numpy()].reset_index(drop=True)
        test = labelled[(side == "test").to_numpy()].reset_index(drop=True)
        rows.append({"scenario": name, "train_n": len(train),
                     **rb.held_out_comparison(train, test)})
    return pd.DataFrame(rows)


def calibration_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, column in (("Primary labels (M02)", "outcome"),
                         ("Conservative expanded labels", "outcome_conservative"),
                         ("Lenient expanded labels", "outcome_lenient")):
        scenario = frame[["household_id", "expectation_pct", "expectation_prob"]].assign(
            outcome=frame[column].astype("Float64"))
        summary = rb.calibration_summary(scenario)
        rows.append({"labels": name, **summary, **rb.finding_holds(summary)})
    return pd.DataFrame(rows)


def build_expanded_frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    frame, eligible, _ = ps.load_pregnancy_frame()
    expanded = expanded_outcomes(eligible)
    frame = frame.join(expanded, how="left")
    for mode in (CONSERVATIVE, LENIENT):
        frame[f"revision_{mode}"] = revision_categories(frame["outcome"], frame[f"outcome_{mode}"])
        if not frame[f"reason_{mode}"].dropna().isin(EXPANDED_UNKNOWN_REASONS).all():
            raise ValueError("Unrecognised expanded unknown reason")
        if not (frame[f"outcome_{mode}"].isna() == frame[f"reason_{mode}"].notna()).all():
            raise ValueError("Expanded outcomes and reasons are inconsistent")
    return frame, eligible


def write_sensitivity_cohort(frame: pd.DataFrame) -> None:
    columns = ["household_id", "outcome", "unknown_reason", "outcome_conservative",
               "reason_conservative", "revision_conservative", "outcome_lenient",
               "reason_lenient", "revision_lenient", "complete_rounds_used",
               "interim_rounds_used", "flag_interim_conflict", "flag_window_discrepancy",
               "pregnancy_status", "pregnancy_reason", "weeks_pregnant",
               "expectation_pct", "expectation_prob", *ac.COVARIATES_NUMERIC,
               *ac.COVARIATES_CATEGORICAL]
    frame[columns].rename(columns={"outcome": "outcome_primary",
                                   "unknown_reason": "reason_primary"}).to_csv(OUTPUT_PATH)


def main() -> None:
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 40)
    frame, eligible = build_expanded_frame()

    print("THE INTENTION GAP | EXPANDED BIRTH-HISTORY VALIDATION")
    print("=" * 72)
    print(f"\nRoster quality by round ({len(eligible):,} eligible women)")
    print(roster_quality(eligible).to_string())
    print("\nImplausible dates (women)")
    print(implausible_dates(eligible).to_string())
    print("\nWhole-history agreement between usable rosters (women)")
    print(cross_round_comparison(eligible).to_string(index=False))
    print("\nRoster length against CV_BIO_CHILD_HH + CV_BIO_CHILD_NR (women)")
    print(child_count_check(eligible).to_string())
    print("\nCVC_TTL_BIO_CHILD (Z9085400) against the latest usable roster (women)")
    print(total_children_check(eligible).to_string(index=False))

    for mode in (CONSERVATIVE, LENIENT):
        print(f"\nOutcome revision, {mode} rules")
        print(frame[f"revision_{mode}"].value_counts().to_string())
        print(recovery_table(frame, mode).to_string())
        print("Newly resolved, by source of evidence")
        print(resolution_source(frame, mode).to_string())
    print("\nFlags among all eligible women: "
          f"interim conflict {int(frame['flag_interim_conflict'].sum())}, "
          f"window discrepancy {int(frame['flag_window_discrepancy'].sum())}")
    print("Window discrepancies by kind (a woman may have more than one)")
    print(discrepancy_detail(eligible, frame).to_string())
    print("\nWomen still without a complete roster, by last interview")
    print(unresolved_coverage(frame, eligible).to_string())
    print("\nPrimary labels of women affected by data problems in any round")
    print(problem_overlap(eligible, frame).to_string())

    print("\nCalibration of stated expectations by label set")
    table = calibration_comparison(frame)
    table["slope_ci"] = table["slope_ci"].map(ps.format_ci)
    columns = ["labels", "n", "births", "observed_rate", "mean_stated", "observed_at_0",
               "observed_at_50", "observed_at_100", "slope", "slope_ci", "brier_stated",
               "brier_constant_cv", "brier_recalibrated_cv", "auc_stated", "too_extreme",
               "overestimates_on_average", "recalibration_improves"]
    print(table[columns].round(3).T.to_string(header=False))

    print("\nHeld-out comparison (original households keep their side)")
    sample = ac.labelled_sample(ac.load_cohort())
    held = held_out_expanded(frame, sample)
    for column in ("c_minus_b_brier_ci", "d_minus_c_brier_ci", "d_minus_c_auc_ci"):
        held[column] = held[column].map(lambda ci: f"[{ci[0]:+.4f}, {ci[1]:+.4f}]")
    print(held.round(4).T.to_string(header=False))

    write_sensitivity_cohort(frame)
    print(f"\nSensitivity cohort written to {OUTPUT_PATH.relative_to(PROJECT_ROOT).as_posix()} "
          "(local only; the primary cohort file is unchanged)")


if __name__ == "__main__":
    main()
