"""Tests for the robustness analysis, using synthetic data.

Run with:  python -m unittest -v
"""

import unittest
from unittest import mock

import numpy as np
import pandas as pd

from analysis import build_outcomes as bo
from analysis import robustness_analysis as ra
from tests.test_analyze_calibration import synthetic_sample


class CrossValidationTests(unittest.TestCase):
    def test_repeated_cv_structure(self):
        train = synthetic_sample(n_households=200)
        with mock.patch.object(ra, "CV_SEEDS", (1, 2)):
            results = ra.repeated_grouped_cv(train)
        self.assertEqual(len(results), 2 * ra.CV_FOLDS * 4)
        self.assertTrue((results["n_fit"] + results["n_validation"] == len(train)).all())
        per_repeat = results[results["model"] == "A"].groupby("repeat")["n_validation"].sum()
        self.assertTrue((per_repeat == len(train)).all())

    def test_corrected_interval_is_wider_than_naive(self):
        rng = np.random.default_rng(0)
        differences = rng.normal(-0.01, 0.005, 50)
        mean, low, high = ra.corrected_resampled_interval(differences, n_fit=800, n_validation=200)
        naive_half_width = 2.01 * differences.std(ddof=1) / np.sqrt(50)
        self.assertAlmostEqual(mean, differences.mean())
        self.assertGreater((high - low) / 2, naive_half_width)


class SensitivityTests(unittest.TestCase):
    def setUp(self):
        self.primary = pd.DataFrame({
            "outcome": [1, 0, np.nan, np.nan, np.nan],
            "unknown_reason": [None, None, bo.RECORD_CONFLICT,
                               bo.NO_FOLLOWUP_INTERVIEW, bo.ANNIVERSARY_MONTH_TIMING],
        })

    def test_bound_changes_only_targeted_unknowns(self):
        bounded = ra.apply_bound(self.primary, ra.AMBIGUITY_REASONS, 1)
        self.assertEqual(bounded["outcome"].tolist()[:2], [1, 0])
        self.assertEqual(bounded["outcome"].iloc[2], 1)
        self.assertTrue(np.isnan(bounded["outcome"].iloc[3]))
        self.assertEqual(bounded["outcome"].iloc[4], 1)
        self.assertTrue(self.primary["outcome"].iloc[2:].isna().all())

    def test_label_change_counts(self):
        alternative = pd.Series([0, 0, 1, np.nan, 0])
        changes = ra.label_changes(self.primary["outcome"], alternative)
        self.assertEqual(changes["1_to_0"], 1)
        self.assertEqual(changes["unknown_to_1"], 1)
        self.assertEqual(changes["unknown_to_0"], 1)
        self.assertEqual(sum(changes.values()), 3)

    def test_linear_calibration_identity(self):
        p = np.linspace(0, 1, 101)
        intercept, slope = ra.linear_calibration(p, p)
        self.assertAlmostEqual(intercept, 0.0)
        self.assertAlmostEqual(slope, 1.0)

    def test_finding_checks(self):
        summary = {"slope_ci": (0.4, 0.5), "mean_stated": 0.42, "observed_rate": 0.36,
                   "brier_recalibrated_cv": 0.19, "brier_stated": 0.24}
        self.assertTrue(all(ra.finding_holds(summary).values()))
        summary["slope_ci"] = (0.9, 1.1)
        self.assertFalse(ra.finding_holds(summary)["too_extreme"])


class EarlyBirthTests(unittest.TestCase):
    def setUp(self):
        self.primary = pd.DataFrame(
            {"outcome": [1, 1, 1, 0, np.nan], "expectation_pct": [100, 100, 50, 0, 50]},
            index=pd.Index([10, 11, 12, 13, 14], name="respondent_id"))
        self.timing = pd.DataFrame({"first_birth_month": [3, 3, 20],
                                    "last_birth_month": [3, 30, 40]}, index=[10, 11, 12])

    def test_exclusion_removes_only_early_births(self):
        scenarios = ra.early_birth_scenarios(self.primary, self.timing)
        excluded = scenarios[f"Exclude first births within {ra.EARLY_BIRTH_MONTHS} months"]
        self.assertEqual(sorted(excluded.index), [12, 13])

    def test_redefined_outcome_counts_only_later_births(self):
        scenarios = ra.early_birth_scenarios(self.primary, self.timing)
        later = scenarios[f"Outcome: births in months {ra.EARLY_BIRTH_MONTHS + 1}-59 only"]
        self.assertEqual(later["outcome"].to_dict(), {10: 0, 11: 1, 12: 1, 13: 0})

    def test_unknown_outcomes_never_enter(self):
        for scenario in ra.early_birth_scenarios(self.primary, self.timing).values():
            self.assertNotIn(14, scenario.index)


class WeightingTests(unittest.TestCase):
    def test_equal_weights_match_unweighted(self):
        cohort = pd.DataFrame({"expectation_pct": [0, 50, 100, 20],
                               "sampling_weight_2009": [10.0] * 4})
        summary = ra.weighted_expectation_summary(cohort)
        np.testing.assert_allclose(summary["unweighted"], summary["round_13_weighted"])

    def test_non_positive_weight_rejected(self):
        cohort = pd.DataFrame({"expectation_pct": [0, 50], "sampling_weight_2009": [1.0, 0.0]})
        with self.assertRaises(ValueError):
            ra.weighted_expectation_summary(cohort)


if __name__ == "__main__":
    unittest.main()
