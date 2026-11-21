"""Synthetic validation of the design-based variance methods and weight adjustments.

Run with:  python -m unittest -v
"""

import unittest

import numpy as np
import pandas as pd

from analysis import survey_design as sd


def two_psu_sample(n_strata=40, per_psu=15, seed=0):
    """A stratified sample with two PSUs per stratum, cluster effects and unequal weights."""
    rng = np.random.default_rng(seed)
    strata = np.repeat(np.arange(n_strata), 2 * per_psu)
    psu = np.tile(np.repeat([1, 2], per_psu), n_strata)
    cluster = rng.normal(0, 1, (n_strata, 3))[strata, psu]
    y = 5 + cluster + rng.normal(0, 1, len(strata))
    weights = rng.uniform(1, 3, len(strata))
    return y, weights, strata, psu


class LinearizationTests(unittest.TestCase):
    def test_equal_weights_with_one_unit_per_psu_give_the_simple_standard_error(self):
        y = np.array([1.0, 4.0, 2.0, 8.0, 5.0, 3.0])
        strata, psu = np.zeros(6, dtype=int), np.arange(6)
        design = sd.design_table(strata, psu)
        mean, se = sd.linearized_mean(y, np.ones(6), strata, psu, design)
        self.assertAlmostEqual(mean, y.mean())
        self.assertAlmostEqual(se, y.std(ddof=1) / np.sqrt(6))

    def test_domain_estimate_uses_the_full_design(self):
        y, w, strata, psu = two_psu_sample()
        design = sd.design_table(strata, psu)
        domain = (strata % 3 != 0) & (y > 4)
        mean, se = sd.linearized_mean(y, w, strata, psu, design, domain)
        self.assertAlmostEqual(mean, np.average(y[domain], weights=w[domain]))
        kept = sd.linearized_mean(y[domain], w[domain], strata[domain], psu[domain], design)
        self.assertAlmostEqual(se, kept[1])

    def test_variance_matches_repeated_sampling(self):
        rng = np.random.default_rng(42)
        n_strata, clusters, size = 30, 20, 12
        effects = rng.normal(0, 1, (n_strata, clusters))
        estimates, variances = [], []
        for _ in range(300):
            picks = np.array([rng.choice(clusters, 2, replace=False) for _ in range(n_strata)])
            strata = np.repeat(np.arange(n_strata), 2 * size)
            psu = np.tile(np.repeat([0, 1], size), n_strata)
            chosen = picks[strata, psu]
            y = effects[strata, chosen] + rng.normal(0, 1, len(strata))
            w = np.full(len(y), clusters / 2)
            mean, se = sd.linearized_mean(y, w, strata, psu, sd.design_table(strata, psu))
            estimates.append(mean)
            variances.append(se ** 2)
        ratio = np.mean(variances) / np.var(estimates)
        self.assertGreater(ratio, 0.8)
        self.assertLess(ratio, 1.35)


class JackknifeTests(unittest.TestCase):
    def test_replicates_delete_one_psu_and_rescale_its_partner(self):
        strata, psu = np.array([0, 0, 0, 1, 1]), np.array([1, 1, 2, 1, 2])
        design = sd.design_table(strata, psu)
        factors = [f for _, _, f in sd.replicate_factors(strata, psu, design)]
        self.assertEqual(len(factors), 4)
        np.testing.assert_array_equal(factors[0], [0, 0, 2, 1, 1])
        np.testing.assert_array_equal(factors[3], [1, 1, 1, 2, 0])

    def test_jackknife_equals_linearization_for_a_total(self):
        y, w, strata, psu = two_psu_sample()
        design = sd.design_table(strata, psu)
        result = sd.jackknife(lambda v: {"total": np.sum(v * y)}, w, strata, psu, design)
        totals = pd.DataFrame({"s": strata, "p": psu, "t": w * y}).groupby(["s", "p"])["t"].sum()
        expected = np.sqrt((totals.groupby(level="s").diff().dropna() ** 2).sum())
        self.assertAlmostEqual(result.loc["total", "se"], expected, places=6)

    def test_jackknife_agrees_with_linearization_for_a_mean(self):
        y, w, strata, psu = two_psu_sample(n_strata=80)
        design = sd.design_table(strata, psu)
        result = sd.jackknife(lambda v: {"mean": np.average(y, weights=v)}, w, strata, psu,
                              design)
        _, se = sd.linearized_mean(y, w, strata, psu, design)
        self.assertAlmostEqual(result.loc["mean", "se"] / se, 1.0, delta=0.02)


class AdjustmentTests(unittest.TestCase):
    def test_labelled_women_carry_their_cell_weight(self):
        w = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        known = np.array([True, False, True, True, True])
        cells = np.array(["a", "a", "a", "b", "b"])
        adjusted = sd.adjusted_weights(w, known, cells)
        self.assertEqual(adjusted[1], 0.0)
        self.assertAlmostEqual(adjusted[cells == "a"].sum(), 6.0)
        np.testing.assert_allclose(adjusted[3:], [4.0, 5.0])

    def test_sparse_cells_collapse_to_a_coarser_level(self):
        n = 60
        frame = pd.DataFrame({
            "expectation_pct": [0] * n + [100] * n,
            "parity": [0] * (n // 2) + [1] * (n // 2) + [0] * n,
            "race": ["Black"] * 5 + ["Other"] * (n - 5) + ["Other"] * n,
            "outcome": [0.0] * (2 * n),
        })
        cells = sd.adjustment_cells(frame, min_cell=20)
        self.assertEqual(cells[0], "0|none")
        self.assertEqual(cells[10], "0|none|Other")
        self.assertEqual(cells[n], "100|none|Other")


class OutcomeStatisticTests(unittest.TestCase):
    def test_equal_weights_give_simple_summaries_and_zero_weights_are_ignored(self):
        y = np.array([0.0, 1.0, 1.0, 0.0, 1.0])
        p = np.array([0.0, 1.0, 0.5, 0.5, 1.0])
        c = np.full(5, 0.4)
        parity = np.array([0, 0, 1, 1, 2])
        w = np.array([1.0, 1.0, 1.0, 1.0, 0.0])
        stats = sd.outcome_statistics(y, p, c, parity, np.ones(5, bool), w)
        self.assertAlmostEqual(stats["overestimate"], p[:4].mean() - y[:4].mean())
        self.assertAlmostEqual(stats["overestimate, mothers"], 0.5 - 0.5)
        self.assertAlmostEqual(stats["birth rate after 100%"], 1.0)
        self.assertAlmostEqual(stats["C - B"], np.mean((c - y)[:4] ** 2) - np.mean((p - y)[:4] ** 2))


class BoundTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        n = 40
        self.p = rng.choice([0.0, 0.1, 0.5, 0.9, 1.0], n)
        self.c = 0.2 + 0.5 * self.p
        self.parity = rng.integers(0, 3, n)
        self.w = rng.uniform(1, 4, n)
        self.y = (rng.random(n) < 0.4).astype(float)
        self.unknown = np.zeros(n, dtype=bool)
        self.unknown[rng.choice(n, 8, replace=False)] = True

    def statistic(self, y):
        return sd.outcome_statistics(y, self.p, self.c, self.parity, np.ones(len(y), bool), self.w)

    def test_bounds_equal_exhaustive_enumeration(self):
        bounds = sd.respondent_bounds(self.statistic, self.y, self.unknown)
        index = np.flatnonzero(self.unknown)
        values = []
        for code in range(2 ** len(index)):
            y = self.y.copy()
            y[index] = [(code >> k) & 1 for k in range(len(index))]
            values.append(self.statistic(y))
        values = pd.DataFrame(values)
        for name in ("C - B", "linear slope", "mothers minus no children", "overestimate"):
            self.assertAlmostEqual(bounds.loc[name, "lower"], values[name].min())
            self.assertAlmostEqual(bounds.loc[name, "upper"], values[name].max())

    def test_uniform_assignments_can_fall_inside_the_bounds(self):
        bounds = sd.respondent_bounds(self.statistic, self.y, self.unknown)
        uniform = [self.statistic(np.where(self.unknown, v, self.y))["C - B"] for v in (0.0, 1.0)]
        self.assertLess(bounds.loc["C - B", "lower"], min(uniform))
        self.assertGreater(bounds.loc["C - B", "upper"], max(uniform))

    def test_non_additive_statistic_is_rejected(self):
        with self.assertRaises(ValueError):
            sd.respondent_bounds(lambda y: {"square": y.mean() ** 2}, self.y, self.unknown)

    def test_recalibration_bounds_are_blank_when_the_evaluation_set_excludes_unknowns(self):
        frame = pd.DataFrame({"outcome": np.where(self.unknown, np.nan, self.y),
                              "expectation_prob": self.p, "forecast_c": self.c,
                              "parity": self.parity.astype(float), "weight": self.w,
                              "evaluate": ~self.unknown})
        table = sd.outcome_bounds(frame)
        self.assertTrue(table.loc[sd.RECALIBRATION_ROWS].isna().all().all())
        self.assertFalse(table.loc["linear slope"].isna().any())


if __name__ == "__main__":
    unittest.main()
