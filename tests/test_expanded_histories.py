"""Tests for expanded birth-history reconciliation, using synthetic rosters.

Run with:  python -m unittest -v
"""

import unittest

import pandas as pd

from analysis import analyze_calibration as ac
from analysis import build_outcomes as bo
from analysis import expanded_histories as eh

BASELINE = 360
INTERVIEWS = {2009: 360, 2010: 372, 2011: 384, 2013: 408, 2015: 430, 2017: 455, 2019: 480}


def rosters_for(births: dict[int, list[int]]):
    """Slot values and interview months; rounds absent from births were not interviewed."""
    rosters, interviews = {}, {}
    for year, slots in eh.ALL_SLOTS.items():
        if year in births:
            values = sorted(births[year])
            rosters[year] = values + [-4] * (len(slots) - len(values))
            interviews[year] = INTERVIEWS[year]
        else:
            rosters[year] = [-5] * len(slots)
            interviews[year] = -5
    return rosters, interviews


def classify(births, mode=eh.CONSERVATIVE):
    return eh.classify_expanded(BASELINE, *rosters_for(births), mode=mode)


class CompareRostersTests(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(eh.compare_rosters([300], 372, [300, 380])["category"], eh.IDENTICAL)
        redated = eh.compare_rosters([300], 372, [302])
        self.assertEqual((redated["category"], redated["max_shift"]), (eh.REDATED, 2))
        self.assertEqual(eh.compare_rosters([300, 310], 372, [300])["category"], eh.DROPPED)
        self.assertEqual(eh.compare_rosters([300], 372, [290, 300])["category"], eh.ADDED)

    def test_birth_in_earlier_interview_month_may_postdate_interview(self):
        self.assertEqual(eh.compare_rosters([300], 372, [300, 372])["category"], eh.IDENTICAL)

    def test_window_consistency_with_tolerance(self):
        self.assertTrue(eh.window_births_consistent([380], 384, [380, 384], BASELINE))
        self.assertFalse(eh.window_births_consistent([], 384, [383], BASELINE))
        self.assertTrue(eh.window_births_consistent([], 384, [383], BASELINE, tolerance=2))
        self.assertFalse(eh.window_births_consistent([380], 384, [], BASELINE))


class ClassifyExpandedTests(unittest.TestCase):
    def test_interim_birth_resolves_missing_followup(self):
        result = classify({2009: [300], 2010: [300], 2011: [300, 380], 2013: [300, 380]})
        self.assertEqual((result.outcome, result.complete_used), (1, ()))

    def test_interim_rosters_never_establish_a_negative(self):
        result = classify({2009: [300], 2010: [300], 2011: [300], 2013: [300]})
        self.assertIsNone(result.outcome)
        self.assertEqual(result.reason, bo.NO_FOLLOWUP_INTERVIEW)

    def test_2019_roster_can_establish_an_outcome(self):
        self.assertEqual(classify({2009: [300], 2011: [300], 2019: [300, 450]}).outcome, 0)
        self.assertEqual(classify({2009: [300], 2011: [300], 2019: [300, 400]}).outcome, 1)

    def test_newer_roster_does_not_override_older_one(self):
        result = classify({2009: [300], 2015: [300], 2019: [300, 400]})
        self.assertEqual((result.outcome, result.reason), (None, bo.ROUNDS_DISAGREE))

    def test_interim_birth_absent_later(self):
        births = {2009: [300], 2011: [300, 380], 2015: [300], 2017: [300], 2019: [300]}
        self.assertEqual(classify(births).reason, eh.WINDOW_DISCREPANCY)
        lenient = classify(births, eh.LENIENT)
        self.assertEqual(lenient.outcome, 0)
        self.assertTrue(lenient.flags["window_discrepancy"])

    def test_later_roster_adds_birth_before_interim_interview(self):
        births = {2009: [300], 2010: [300], 2015: [300, 365], 2017: [300, 365]}
        self.assertEqual(classify(births).reason, eh.WINDOW_DISCREPANCY)
        self.assertEqual(classify(births, eh.LENIENT).outcome, 1)

    def test_interim_conflict_with_baseline_withdraws_label_in_both_modes(self):
        births = {2009: [300], 2010: [290, 300], 2015: [300, 400], 2017: [300, 400]}
        for mode in (eh.CONSERVATIVE, eh.LENIENT):
            self.assertEqual(classify(births, mode).reason, eh.INTERIM_CONFLICT)

    def test_matches_primary_rule_without_new_rounds(self):
        cases = [
            {2009: [300], 2015: [300, 400], 2017: [300, 400]},
            {2009: [300], 2015: [300], 2017: [300]},
            {2009: [300], 2015: [300, 400], 2017: [300]},
            {2009: [300], 2015: [300, 420]},
            {2009: [], 2015: [360], 2017: [360]},
            {2009: [300, 310], 2015: [300, 380]},
        ]
        for births in cases:
            rosters, interviews = rosters_for(births)
            primary = bo.classify_outcome(BASELINE, rosters, interviews)
            expanded = eh.classify_expanded(BASELINE, rosters, interviews)
            self.assertEqual((expanded.outcome, expanded.reason),
                             (primary.outcome, primary.unknown_reason), births)

    def test_interim_interview_after_anniversary_is_rejected(self):
        rosters, interviews = rosters_for({2009: [300], 2013: [300]})
        interviews[2013] = BASELINE + bo.WINDOW_MONTHS
        with self.assertRaises(ValueError):
            eh.classify_expanded(BASELINE, rosters, interviews)


class RevisionTests(unittest.TestCase):
    def test_revision_categories(self):
        primary = pd.Series([1, 0, None, None, 1, 0], dtype="Float64")
        revised = pd.Series([1, None, 0, None, 0, 0], dtype="Int64")
        self.assertEqual(list(eh.revision_categories(primary, revised)), [
            "retained", "challenged: now unknown", "newly resolved", "remains unknown",
            "challenged: label reversed", "retained"])

    def test_original_households_keep_their_side(self):
        sample = pd.DataFrame({"respondent_id": range(80),
                               "household_id": [k // 2 for k in range(80)],
                               "outcome": [k % 2 for k in range(80)]})
        new = pd.DataFrame({"respondent_id": range(80, 92),
                            "household_id": [100 + k // 3 for k in range(12)],
                            "outcome": [k % 2 for k in range(12)]})
        labelled = pd.concat([sample, new], ignore_index=True)
        side = eh.assign_expanded_split(labelled, sample)
        train, test = ac.household_split(sample)
        self.assertTrue((side[labelled["respondent_id"].isin(train["respondent_id"])] == "train").all())
        self.assertTrue((side[labelled["respondent_id"].isin(test["respondent_id"])] == "test").all())
        self.assertEqual(side.notna().sum(), len(labelled))
        sides_per_household = side.groupby(labelled["household_id"]).nunique()
        self.assertTrue((sides_per_household == 1).all())


if __name__ == "__main__":
    unittest.main()
