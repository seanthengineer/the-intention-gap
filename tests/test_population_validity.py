"""Tests for selection and missing-outcome checks, using synthetic data.

Run with:  python -m unittest -v
"""

import unittest

import numpy as np
import pandas as pd

from analysis import population_validity as pv
from analysis import pregnancy_status as ps


def synthetic_frame(n: int = 200, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pct = rng.choice([0, 10, 50, 90, 100], size=n)
    outcome = (rng.random(n) < 0.2 + 0.5 * pct / 100).astype(float)
    outcome[: n // 10] = np.nan
    return pd.DataFrame({
        "household_id": np.arange(n) // 2,
        "outcome": outcome,
        "expectation_pct": pct,
        "expectation_prob": pct / 100,
        "age_at_baseline": np.where(np.isnan(outcome), 29.0, 27.0),
        "parity_at_baseline": rng.integers(0, 3, n).astype(float),
        "highest_grade_2009": rng.integers(9, 13, n).astype(float),
        "marital_status_2009": rng.integers(0, 4, n).astype(float),
        "race_ethnicity": rng.integers(1, 5, n),
        "cross_sectional_sample": rng.integers(0, 2, n),
        "pregnancy_status": rng.choice(list(ps.STATUSES), size=n),
    })


class CalibrationMeasureTests(unittest.TestCase):
    def test_fractional_outcomes_equal_to_forecasts_are_calibrated(self):
        p = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        measures = pv.calibration_measures(p.copy(), p)
        self.assertAlmostEqual(measures["slope"], 1.0)
        self.assertAlmostEqual(measures["overestimate"], 0.0)

    def test_weights_change_the_average(self):
        y, p = np.array([0.0, 1.0]), np.array([0.5, 0.5])
        self.assertAlmostEqual(pv.calibration_measures(y, p, [3, 1])["observed_rate"], 0.25)


class MissingOutcomeTests(unittest.TestCase):
    def test_worst_case_bounds_fill_every_unknown(self):
        frame = synthetic_frame()
        table = pv.missing_outcome_scenarios(frame, "outcome").set_index("scenario")
        known = frame["outcome"].dropna()
        n = len(frame)
        self.assertEqual(table.loc["Complete cases (unknowns excluded)", "n"], len(known))
        self.assertAlmostEqual(table.loc["Worst case: every unknown had a birth", "observed_rate"],
                               (known.sum() + n - len(known)) / n)
        self.assertAlmostEqual(table.loc["Worst case: no unknown had a birth", "observed_rate"],
                               known.sum() / n)

    def test_selection_table_reports_unknown_minus_known(self):
        table = pv.selection_table(synthetic_frame(), "outcome")
        self.assertAlmostEqual(table.loc["Age at baseline (years)", "difference"], 2.0)
        self.assertGreater(table.loc["Age at baseline (years)", "ci_low"], 0)


class ReconcileTests(unittest.TestCase):
    def test_mismatched_totals_raise(self):
        frame = pd.DataFrame({"pregnancy_status": [ps.PREGNANT], "outcome": [1.0],
                              "outcome_conservative": [1.0]})
        with self.assertRaises(ValueError):
            pv.reconcile(frame)


if __name__ == "__main__":
    unittest.main()
