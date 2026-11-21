"""Tests for the calibration and baseline analysis, using synthetic data.

Run with:  python -m unittest -v
"""

import unittest

import numpy as np
import pandas as pd

from analysis import analyze_calibration as ac


def synthetic_sample(n_households: int = 300, seed: int = 0) -> pd.DataFrame:
    """Labelled respondents, one to three per household, with baseline columns."""
    rng = np.random.default_rng(seed)
    sizes = rng.integers(1, 4, n_households)
    household = np.repeat(np.arange(n_households), sizes)
    n = len(household)
    pct = rng.choice([0, 10, 25, 50, 75, 90, 100], n)
    outcome = (rng.random(n) < 0.15 + 0.6 * pct / 100).astype(int)
    grade = rng.integers(8, 17, n).astype(float)
    grade[rng.random(n) < 0.05] = np.nan
    marital = rng.integers(0, 4, n).astype(float)
    marital[rng.random(n) < 0.03] = np.nan
    return pd.DataFrame({
        "household_id": household,
        "outcome": outcome,
        "expectation_pct": pct,
        "expectation_prob": pct / 100,
        "age_at_baseline": rng.uniform(25, 30, n),
        "parity_at_baseline": rng.integers(0, 4, n),
        "highest_grade_2009": grade,
        "marital_status_2009": marital,
    })


class FeatureSafetyTests(unittest.TestCase):
    def test_features_are_baseline_columns_only(self):
        self.assertTrue(set(ac.MODEL_D_FEATURES) <= ac.BASELINE_COLUMNS)

    def test_no_identifier_or_post_baseline_columns_in_features(self):
        forbidden_prefixes = ("flag_", "interviewed_", "followup_", "outcome", "unknown_")
        forbidden = {"respondent_id", "household_id", "sampling_weight_2009"}
        for feature in ac.MODEL_D_FEATURES:
            self.assertNotIn(feature, forbidden)
            self.assertFalse(feature.startswith(forbidden_prefixes), feature)

    def test_unknown_outcomes_are_excluded(self):
        cohort = pd.DataFrame({"outcome": [1, 0, np.nan, 1], "household_id": [1, 2, 3, 4]})
        sample = ac.labelled_sample(cohort)
        self.assertEqual(len(sample), 3)
        self.assertTrue(sample["outcome"].isin([0, 1]).all())


class MetricTests(unittest.TestCase):
    def test_brier_uses_unclipped_probabilities(self):
        y = np.array([1, 0, 1, 0])
        p = np.array([1.0, 0.0, 0.0, 0.5])
        metrics = ac.forecast_metrics(y, p)
        self.assertAlmostEqual(metrics["brier"], np.mean((p - y) ** 2))

    def test_log_loss_is_finite_after_clipping(self):
        y = np.array([1, 0])
        p = np.array([0.0, 1.0])
        for epsilon in ac.LOG_LOSS_EPSILONS:
            value = ac.clipped_log_loss(y, p, epsilon)
            self.assertTrue(np.isfinite(value))
            self.assertAlmostEqual(value, -np.log(epsilon))

    def test_wilson_interval(self):
        low, high = ac.wilson_interval(0, 10)
        self.assertAlmostEqual(low, 0.0)
        self.assertGreater(high, 0.2)
        low, high = ac.wilson_interval(50, 100)
        self.assertAlmostEqual((low + high) / 2, 0.5)

    def test_calibration_ranges_cover_each_respondent_once(self):
        sample = pd.DataFrame({
            "expectation_pct": list(range(101)),
            "outcome": [i % 2 for i in range(101)],
        })
        table = ac.calibration_table(sample)
        self.assertEqual(int(table["n"].sum()), 101)
        heaps = table.set_index("range_pct").loc[["0", "50", "100"], "n"]
        self.assertTrue((heaps == 1).all())


class SplitAndModelTests(unittest.TestCase):
    def setUp(self):
        self.sample = synthetic_sample()
        self.train, self.test = ac.household_split(self.sample)

    def test_no_household_in_both_sets(self):
        shared = set(self.train["household_id"]) & set(self.test["household_id"])
        self.assertEqual(shared, set())
        self.assertEqual(len(self.train) + len(self.test), len(self.sample))

    def test_split_is_reproducible(self):
        train_again, _ = ac.household_split(self.sample)
        pd.testing.assert_frame_equal(self.train, train_again)

    def test_constant_baseline_is_training_prevalence(self):
        predictions = ac.fit_and_predict(self.train, self.test)
        self.assertTrue(np.allclose(predictions["A"], self.train["outcome"].mean()))

    def test_stated_baseline_is_unaltered(self):
        predictions = ac.fit_and_predict(self.train, self.test)
        np.testing.assert_array_equal(predictions["B"], self.test["expectation_prob"])

    def test_predictions_do_not_depend_on_test_outcomes(self):
        original = ac.fit_and_predict(self.train, self.test)
        shuffled_test = self.test.copy()
        shuffled_test["outcome"] = 1 - shuffled_test["outcome"]
        changed = ac.fit_and_predict(self.train, shuffled_test)
        for name in original:
            np.testing.assert_allclose(original[name], changed[name])

    def test_missing_covariates_are_handled(self):
        predictions = ac.fit_and_predict(self.train, self.test)
        self.assertFalse(np.isnan(predictions["D"]).any())
        self.assertTrue(((predictions["D"] > 0) & (predictions["D"] < 1)).all())


@unittest.skipUnless(ac.COHORT_PATH.exists(), "processed cohort not available")
class ProcessedCohortTests(unittest.TestCase):
    """Aggregate checks on the local processed cohort; no records are printed."""

    def test_cohort_passes_validation(self):
        ac.validate_cohort(ac.load_cohort())

    def test_labelled_sample_size(self):
        sample = ac.labelled_sample(ac.load_cohort())
        self.assertEqual(len(sample), 1234 + 2170)


if __name__ == "__main__":
    unittest.main()
