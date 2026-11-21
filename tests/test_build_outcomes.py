"""Unit tests for the five-year outcome rules, using synthetic respondents.

Run with:  python -m unittest -v
"""

import unittest

from analysis import build_outcomes as bo
from analysis.nlsy97 import RAW_DATA_PATH, assess_roster, cmonth_from_date, cmonth_to_text

BASELINE = 358    # October 2009
INTERVIEW_2015 = 431
INTERVIEW_2017 = 456
NOT_INTERVIEWED = -5
SLOTS = {2009: 9, 2015: 12, 2017: 12}


def roster(year: int, *births: int) -> list[int]:
    """Slot values for an interviewed respondent: births, then valid skips."""
    return list(births) + [-4] * (SLOTS[year] - len(births))


def absent(year: int) -> list[int]:
    return [NOT_INTERVIEWED] * SLOTS[year]


def classify(r2009, r2015, r2017, interviewed_2015=True, interviewed_2017=True):
    return bo.classify_outcome(
        BASELINE,
        {2009: r2009, 2015: r2015, 2017: r2017},
        {
            2009: BASELINE,
            2015: INTERVIEW_2015 if interviewed_2015 else NOT_INTERVIEWED,
            2017: INTERVIEW_2017 if interviewed_2017 else NOT_INTERVIEWED,
        },
    )


def same_followup(*births, baseline_births=()):
    """Respondent whose 2015 and 2017 rosters both list the given births."""
    return classify(
        roster(2009, *baseline_births),
        roster(2015, *births),
        roster(2017, *births),
    )


class ContinuousMonthTests(unittest.TestCase):
    def test_january_1980_is_month_one(self):
        self.assertEqual(cmonth_from_date(1980, 1), 1)
        self.assertEqual(cmonth_to_text(1), "1980-01")

    def test_baseline_fieldwork_months(self):
        self.assertEqual(cmonth_to_text(357), "2009-09")
        self.assertEqual(cmonth_to_text(364), "2010-04")


class RosterAssessmentTests(unittest.TestCase):
    def test_valid_skip_only_is_usable_with_no_children(self):
        result = assess_roster(roster(2015), INTERVIEW_2015)
        self.assertTrue(result["usable"])
        self.assertEqual(result["n_births"], 0)

    def test_non_interview_is_not_usable(self):
        result = assess_roster(absent(2015), NOT_INTERVIEWED)
        self.assertFalse(result["interviewed"])
        self.assertFalse(result["usable"])

    def test_missing_codes_make_roster_unusable(self):
        for code in (-1, -2, -3):
            with self.subTest(code=code):
                slots = [300, code] + [-4] * 10
                self.assertFalse(assess_roster(slots, INTERVIEW_2015)["usable"])

    def test_gap_between_births_is_unusable(self):
        slots = [300, -4, 320] + [-4] * 9
        result = assess_roster(slots, INTERVIEW_2015)
        self.assertTrue(result["has_gap"])
        self.assertFalse(result["usable"])

    def test_birth_after_interview_is_unusable(self):
        slots = roster(2015, INTERVIEW_2015 + 1)
        self.assertFalse(assess_roster(slots, INTERVIEW_2015)["usable"])


class WindowBoundaryTests(unittest.TestCase):
    def test_birth_inside_window_is_positive(self):
        result = same_followup(BASELINE + 24)
        self.assertEqual(result.outcome, 1)
        self.assertIsNone(result.unknown_reason)

    def test_birth_before_baseline_is_negative(self):
        result = same_followup(BASELINE - 30, baseline_births=[BASELINE - 30])
        self.assertEqual(result.outcome, 0)

    def test_birth_after_window_is_negative(self):
        result = same_followup(BASELINE + 70)
        self.assertEqual(result.outcome, 0)

    def test_first_and_last_full_months_qualify(self):
        self.assertEqual(same_followup(BASELINE + 1).outcome, 1)
        self.assertEqual(same_followup(BASELINE + 59).outcome, 1)

    def test_anniversary_month_birth_is_unknown(self):
        result = same_followup(BASELINE + 60)
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.ANNIVERSARY_MONTH_TIMING)
        self.assertTrue(result.flags["flag_anniversary_month_birth"])

    def test_anniversary_birth_does_not_override_qualifying_birth(self):
        result = same_followup(BASELINE + 20, BASELINE + 60)
        self.assertEqual(result.outcome, 1)
        self.assertTrue(result.flags["flag_anniversary_month_birth"])


class BaselineMonthTests(unittest.TestCase):
    def test_baseline_month_birth_in_2009_roster_is_pre_interview(self):
        result = same_followup(BASELINE, baseline_births=[BASELINE])
        self.assertEqual(result.outcome, 0)
        self.assertTrue(result.flags["flag_baseline_month_birth_pre_interview"])

    def test_baseline_month_birth_absent_from_2009_roster_is_unknown(self):
        result = same_followup(BASELINE)
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.BASELINE_MONTH_TIMING)

    def test_ambiguous_baseline_month_birth_with_qualifying_birth_is_positive(self):
        result = same_followup(BASELINE, BASELINE + 30)
        self.assertEqual(result.outcome, 1)
        self.assertTrue(result.flags["flag_baseline_month_birth_ambiguous"])

    def test_second_baseline_month_birth_not_in_2009_roster_is_ambiguous(self):
        result = same_followup(BASELINE, BASELINE, baseline_births=[BASELINE])
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.BASELINE_MONTH_TIMING)


class FollowUpCoverageTests(unittest.TestCase):
    def test_no_children_with_complete_follow_up_is_negative(self):
        result = same_followup()
        self.assertEqual(result.outcome, 0)
        self.assertEqual(result.rounds_used, (2015, 2017))

    def test_no_follow_up_interview_is_unknown(self):
        result = classify(roster(2009), absent(2015), absent(2017), False, False)
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.NO_FOLLOWUP_INTERVIEW)

    def test_2015_roster_used_when_2017_missing(self):
        result = classify(roster(2009), roster(2015, BASELINE + 12), absent(2017),
                          interviewed_2017=False)
        self.assertEqual(result.outcome, 1)
        self.assertEqual(result.rounds_used, (2015,))

    def test_2017_roster_used_when_2015_missing(self):
        result = classify(roster(2009), absent(2015), roster(2017), interviewed_2015=False)
        self.assertEqual(result.outcome, 0)
        self.assertEqual(result.rounds_used, (2017,))

    def test_invalid_skip_in_only_follow_up_is_unknown(self):
        incomplete = [BASELINE + 12, -3] + [-4] * 10
        result = classify(roster(2009), incomplete, absent(2017), interviewed_2017=False)
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.INCOMPLETE_FOLLOWUP)
        self.assertTrue(result.flags["flag_incomplete_roster_2015"])

    def test_incomplete_roster_falls_back_to_other_usable_round(self):
        incomplete = [-3] + [-4] * 11
        result = classify(roster(2009), roster(2015), incomplete)
        self.assertEqual(result.outcome, 0)
        self.assertEqual(result.rounds_used, (2015,))
        self.assertTrue(result.flags["flag_incomplete_roster_2017"])

    def test_unusable_baseline_roster_is_unknown(self):
        baseline = [300, -3] + [-4] * 7
        result = classify(baseline, roster(2015, 300, BASELINE + 12),
                          roster(2017, 300, BASELINE + 12))
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.BASELINE_ROSTER_UNUSABLE)


class ConflictTests(unittest.TestCase):
    def test_follow_up_rounds_disagreeing_is_unknown(self):
        result = classify(roster(2009), roster(2015), roster(2017, BASELINE + 20))
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.ROUNDS_DISAGREE)
        self.assertTrue(result.flags["flag_followup_window_records_differ"])

    def test_newest_round_is_not_preferred(self):
        result = classify(roster(2009), roster(2015, BASELINE + 20), roster(2017))
        self.assertEqual(result.unknown_reason, bo.ROUNDS_DISAGREE)

    def test_baseline_child_redated_into_window_is_unknown(self):
        result = same_followup(BASELINE + 10, baseline_births=[BASELINE - 30])
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.RECORD_CONFLICT)
        self.assertTrue(result.flags["flag_baseline_record_discrepancy"])

    def test_new_birth_alongside_baseline_child_is_positive(self):
        result = same_followup(BASELINE - 30, BASELINE + 10, baseline_births=[BASELINE - 30])
        self.assertEqual(result.outcome, 1)
        self.assertFalse(result.flags["flag_baseline_record_discrepancy"])

    def test_extra_qualifying_birth_survives_missing_baseline_child(self):
        result = same_followup(BASELINE + 10, BASELINE + 40, baseline_births=[BASELINE - 30])
        self.assertEqual(result.outcome, 1)
        self.assertTrue(result.flags["flag_baseline_record_discrepancy"])

    def test_unrecorded_pre_baseline_birth_blocks_negative(self):
        result = same_followup(BASELINE - 30)
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.RECORD_CONFLICT)

    def test_dropped_baseline_child_without_window_birth_stays_negative(self):
        result = same_followup(baseline_births=[BASELINE - 30])
        self.assertEqual(result.outcome, 0)
        self.assertTrue(result.flags["flag_baseline_record_discrepancy"])

    def test_corrected_pre_baseline_date_stays_negative(self):
        result = same_followup(BASELINE - 31, baseline_births=[BASELINE - 30])
        self.assertEqual(result.outcome, 0)
        self.assertTrue(result.flags["flag_baseline_record_discrepancy"])


def classify_with(rules, *births, baseline_births=()):
    return bo.classify_outcome(
        BASELINE,
        {2009: roster(2009, *baseline_births), 2015: roster(2015, *births),
         2017: roster(2017, *births)},
        {2009: BASELINE, 2015: INTERVIEW_2015, 2017: INTERVIEW_2017},
        rules,
    )


class OutcomeRulesTests(unittest.TestCase):
    def test_default_rules_are_primary(self):
        self.assertEqual(bo.OutcomeRules(), bo.PRIMARY_RULES)

    def test_redated_pre_baseline_birth_is_tolerated_by_primary_rule(self):
        result = classify_with(bo.PRIMARY_RULES, 301, baseline_births=[300])
        self.assertEqual(result.outcome, 0)
        result = classify_with(bo.PRIMARY_RULES, 301, BASELINE + 12, baseline_births=[300])
        self.assertEqual(result.outcome, 1)

    def test_strict_date_reconciliation_treats_redating_as_conflict(self):
        strict = bo.OutcomeRules(strict_date_reconciliation=True)
        result = classify_with(strict, 301, baseline_births=[300])
        self.assertEqual((result.outcome, result.unknown_reason), (None, bo.RECORD_CONFLICT))
        result = classify_with(strict, 301, BASELINE + 12, baseline_births=[300])
        self.assertEqual((result.outcome, result.unknown_reason), (None, bo.RECORD_CONFLICT))
        self.assertEqual(classify_with(strict, 300, BASELINE + 12, baseline_births=[300]).outcome, 1)

    def test_invalid_rule_values_rejected(self):
        with self.assertRaises(ValueError):
            bo.OutcomeRules(baseline_month_birth="sometimes")
        with self.assertRaises(ValueError):
            bo.OutcomeRules(preferred_round=2009)

    def test_unmatched_baseline_month_birth_can_qualify(self):
        rules = bo.OutcomeRules(baseline_month_birth=bo.QUALIFYING)
        self.assertEqual(classify_with(rules, BASELINE).outcome, 1)

    def test_matched_baseline_month_birth_never_qualifies(self):
        rules = bo.OutcomeRules(baseline_month_birth=bo.QUALIFYING)
        result = classify_with(rules, BASELINE, baseline_births=[BASELINE])
        self.assertEqual(result.outcome, 0)

    def test_baseline_month_birth_can_be_excluded(self):
        rules = bo.OutcomeRules(baseline_month_birth=bo.NOT_QUALIFYING)
        self.assertEqual(classify_with(rules, BASELINE).outcome, 0)

    def test_anniversary_month_treatments(self):
        qualifying = bo.OutcomeRules(anniversary_month_birth=bo.QUALIFYING)
        excluded = bo.OutcomeRules(anniversary_month_birth=bo.NOT_QUALIFYING)
        self.assertEqual(classify_with(qualifying, BASELINE + 60).outcome, 1)
        self.assertEqual(classify_with(excluded, BASELINE + 60).outcome, 0)

    def test_remaining_ambiguity_reports_correct_reason(self):
        rules = bo.OutcomeRules(baseline_month_birth=bo.NOT_QUALIFYING)
        result = classify_with(rules, BASELINE, BASELINE + 60)
        self.assertEqual(result.unknown_reason, bo.ANNIVERSARY_MONTH_TIMING)

    def test_without_reconciliation_follow_up_dates_are_accepted(self):
        rules = bo.OutcomeRules(reconcile_with_baseline_roster=False)
        redated = classify_with(rules, BASELINE + 10, baseline_births=[BASELINE - 30])
        unrecorded = classify_with(rules, BASELINE - 30)
        self.assertEqual(redated.outcome, 1)
        self.assertEqual(unrecorded.outcome, 0)

    def test_preferred_round_resolves_disagreement(self):
        rosters = {2009: roster(2009), 2015: roster(2015), 2017: roster(2017, BASELINE + 20)}
        months = {2009: BASELINE, 2015: INTERVIEW_2015, 2017: INTERVIEW_2017}
        prefer_2015 = bo.classify_outcome(BASELINE, rosters, months,
                                          bo.OutcomeRules(preferred_round=2015))
        prefer_2017 = bo.classify_outcome(BASELINE, rosters, months,
                                          bo.OutcomeRules(preferred_round=2017))
        self.assertEqual(prefer_2015.outcome, 0)
        self.assertEqual(prefer_2017.outcome, 1)


@unittest.skipUnless(RAW_DATA_PATH.exists(), "local NLSY97 extract not available")
class CohortReconciliationTests(unittest.TestCase):
    """Aggregate checks against the local extract; no records are printed."""

    @classmethod
    def setUpClass(cls):
        eligible, cls.n_total = bo.load_eligible()
        cls.cohort = bo.build_cohort(eligible)

    def test_sample_sizes(self):
        self.assertEqual(self.n_total, 8984)
        self.assertEqual(len(self.cohort), bo.EXPECTED_ELIGIBLE)

    def test_outcome_counts_reconcile_to_eligible_women(self):
        bo.validate_cohort(self.cohort)
        positives = int((self.cohort["outcome"] == 1).sum())
        negatives = int((self.cohort["outcome"] == 0).sum())
        unknown = int(self.cohort["outcome"].isna().sum())
        self.assertEqual(positives + negatives + unknown, bo.EXPECTED_ELIGIBLE)
        reasons = self.cohort["unknown_reason"].value_counts()
        self.assertEqual(int(reasons.sum()), unknown)

    def test_expectation_probability_scale(self):
        probability = self.cohort["expectation_prob"]
        self.assertTrue(probability.between(0, 1).all())
        self.assertTrue((probability * 100).round(6).eq(self.cohort["expectation_pct"]).all())


if __name__ == "__main__":
    unittest.main()
