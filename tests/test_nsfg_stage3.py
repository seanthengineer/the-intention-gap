"""Tests for the NSFG Stage 3 definitions, estimators and audit runner.

Unit tests use synthetic respondents only. Tests that need the NSFG
public-use files are in NsfgDataIntegrationTests and are skipped when the
files are absent. Written with unittest (the project convention); pytest
collects them unchanged.

Run with:  python -m unittest tests.test_nsfg_stage3 -v
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import nsfg
from analysis import survey_design as sd
from audit import nsfg_stage3_checks as audit

NAN = np.nan


def respondents(rows: list[dict]) -> pd.DataFrame:
    """Synthetic respondents with every intention and status field present."""
    defaults = {"RWANT": 1, "JINTEND": NAN, "INTEND": NAN, "INTENT": 1, "RMARIT": 0,
                "RSTRSTAT": 0, "PSTRSTAT": NAN, "AGER": 22, "YEAR": 2}
    return pd.DataFrame([{**defaults, **row} for row in rows])


class InterviewYearTests(unittest.TestCase):
    def test_codes_decode_to_calendar_years(self):
        years = nsfg.interview_year(pd.Series([1, 2, 2, 1]))
        self.assertEqual(years.tolist(), [2022, 2023, 2023, 2022])

    def test_unknown_codes_are_rejected(self):
        for bad in ([3], [0], [NAN]):
            with self.assertRaises(ValueError):
                nsfg.interview_year(pd.Series(bad))


class CohortBoundaryTests(unittest.TestCase):
    def frame(self):
        ages = [17, 18, 26, 27, 28, 29]
        return pd.DataFrame({"AGER": ages * 2, "YEAR": [1] * 6 + [2] * 6})

    def test_conservative_bounds_depend_on_interview_year(self):
        members = nsfg.in_cohort(self.frame(), "conservative")
        self.assertEqual(members.tolist(),
                         [False, True, True, False, False, False,
                          False, True, True, True, False, False])

    def test_inclusive_bounds_add_one_year_of_age(self):
        members = nsfg.in_cohort(self.frame(), "inclusive")
        self.assertEqual(members.tolist(),
                         [False, True, True, True, False, False,
                          False, True, True, True, True, False])

    def test_inclusive_contains_conservative(self):
        frame = self.frame()
        self.assertFalse((nsfg.in_cohort(frame, "conservative")
                          & ~nsfg.in_cohort(frame, "inclusive")).any())


class RecodeRoutingTests(unittest.TestCase):
    """INTENT rebuilt from the CDC specification for each questionnaire path."""

    def rebuilt(self, rows, sex="female"):
        return nsfg.reconstruct_intent(respondents(rows), sex).tolist()

    def test_joint_question_for_married_or_cohabiting_fertile_couples(self):
        rows = [{"RMARIT": 1, "PSTRSTAT": 0, "JINTEND": 1},
                {"RMARIT": 2, "PSTRSTAT": 0, "JINTEND": 5},
                {"RMARIT": 1, "PSTRSTAT": 0, "JINTEND": 9},
                {"RMARIT": 1, "PSTRSTAT": 0, "JINTEND": 8},
                {"RMARIT": 1, "PSTRSTAT": 0, "JINTEND": NAN}]
        self.assertEqual(self.rebuilt(rows), [1, 2, 3, 4, 4])

    def test_sterility_gives_intent_2_without_the_question(self):
        rows = [{"RSTRSTAT": 1}, {"RSTRSTAT": 2},
                {"RMARIT": 1, "PSTRSTAT": 1}, {"RMARIT": 2, "PSTRSTAT": 2}]
        self.assertEqual(self.rebuilt(rows), [2, 2, 2, 2])

    def test_individual_question_for_other_respondents(self):
        rows = [{"INTEND": 1}, {"INTEND": 5}, {"INTEND": 9}, {"INTEND": 8},
                {"INTEND": NAN, "RWANT": 5}, {"INTEND": NAN, "RWANT": 8}]
        self.assertEqual(self.rebuilt(rows), [1, 2, 3, 4, 2, 2])

    def test_male_individual_codes(self):
        rows = [{"INTEND": code} for code in (1, 2, 3, 4)]
        self.assertEqual(self.rebuilt(rows, "male"), [1, 1, 2, 2])

    def test_male_unmarried_sterility_needs_a_missing_item(self):
        rows = [{"RSTRSTAT": 2, "INTEND": NAN}]
        self.assertEqual(self.rebuilt(rows, "male"), [2])


class ClassificationTests(unittest.TestCase):
    def frame(self):
        return respondents([
            {"INTENT": 1, "INTEND": 1},
            {"INTENT": 2, "INTEND": 5},
            {"INTENT": 2, "RMARIT": 1, "PSTRSTAT": 0, "JINTEND": 5},
            {"INTENT": 2, "RSTRSTAT": 2},
            {"INTENT": 2, "RMARIT": 2, "PSTRSTAT": 1},
            {"INTENT": 2, "INTEND": NAN},
            {"INTENT": 3, "INTEND": 9},
            {"INTENT": 4, "INTEND": 8},
            {"INTENT": NAN},
        ])

    def test_each_respondent_has_exactly_one_category(self):
        categories = nsfg.classify_intention(self.frame(), "female")
        self.assertTrue(categories.isin(nsfg.CATEGORIES).all())
        self.assertEqual(categories.tolist(), [
            nsfg.POSITIVE, nsfg.EXPLICIT_NEGATIVE, nsfg.EXPLICIT_NEGATIVE,
            nsfg.STERILITY_LINKED, nsfg.STERILITY_LINKED, nsfg.UNEXPLAINED, nsfg.UNKNOWN,
            nsfg.NOT_PROVIDED_OR_OTHER, nsfg.NOT_PROVIDED_OR_OTHER])

    def test_sterility_link_without_a_blank_item_is_not_sterility_linked(self):
        frame = respondents([{"INTENT": 2, "RSTRSTAT": 1, "INTEND": 5}])
        self.assertEqual(nsfg.classify_intention(frame, "female").tolist(),
                         [nsfg.EXPLICIT_NEGATIVE])

    def test_male_negative_codes_are_explicit(self):
        frame = respondents([{"INTENT": 2, "INTEND": 3}, {"INTENT": 2, "INTEND": 4}])
        self.assertEqual(nsfg.classify_intention(frame, "male").tolist(),
                         [nsfg.EXPLICIT_NEGATIVE] * 2)
        self.assertEqual(nsfg.classify_intention(frame, "female").tolist(),
                         [nsfg.UNEXPLAINED] * 2)

    def test_sex_can_vary_by_row(self):
        frame = respondents([{"INTENT": 2, "INTEND": 3}, {"INTENT": 2, "INTEND": 5}])
        sexes = pd.Series(["male", "female"])
        self.assertEqual(nsfg.classify_intention(frame, sexes).tolist(),
                         [nsfg.EXPLICIT_NEGATIVE] * 2)


def design_frame(n_strata=10, per_cluster=12, seed=0):
    """Synthetic two-sex sample: n_strata strata x 4 clusters, unequal weights."""
    rng = np.random.default_rng(seed)
    strata = np.repeat(np.arange(1, n_strata + 1), 4 * per_cluster)
    clusters = np.tile(np.repeat([1, 2, 3, 4], per_cluster), n_strata)
    effect = rng.normal(0, 0.15, (n_strata + 1, 5))[strata, clusters]
    return pd.DataFrame({
        nsfg.STRATUM: strata, nsfg.CLUSTER: clusters,
        nsfg.WEIGHT: rng.uniform(500, 3000, len(strata)),
        "sex": rng.choice(["female", "male"], len(strata)),
        "y": (rng.random(len(strata)) < 0.2 + effect).astype(float),
        "domain": rng.random(len(strata)) < 0.7,
    })


class WeightedShareTests(unittest.TestCase):
    def test_equal_weights_give_the_simple_proportion(self):
        frame = design_frame().assign(**{nsfg.WEIGHT: 1.0})
        estimate = nsfg.weighted_share(frame, frame["y"].astype(bool), frame["domain"])
        self.assertAlmostEqual(estimate.estimate, frame.loc[frame["domain"], "y"].mean())
        self.assertEqual(estimate.n, int(frame["domain"].sum()))

    def test_weighted_share_is_the_weighted_domain_mean(self):
        frame = design_frame()
        estimate = nsfg.weighted_share(frame, frame["y"].astype(bool), frame["domain"])
        inside = frame[frame["domain"]]
        self.assertAlmostEqual(estimate.estimate,
                               np.average(inside["y"], weights=inside[nsfg.WEIGHT]))
        self.assertEqual(estimate.df, 10 * 4 - 10)


class SurveyVarianceTests(unittest.TestCase):
    def test_difference_of_domains_in_separate_strata_adds_variances(self):
        frame = design_frame(seed=4)
        y, w = frame["y"].to_numpy(), frame[nsfg.WEIGHT].to_numpy()
        strata, psu = frame[nsfg.STRATUM].to_numpy(), frame[nsfg.CLUSTER].to_numpy()
        design = sd.design_table(strata, psu)
        a, b = strata <= 5, strata > 5
        _, se_a = sd.linearized_mean(y, w, strata, psu, design, a)
        _, se_b = sd.linearized_mean(y, w, strata, psu, design, b)
        difference, se = sd.linearized_domain_difference(y, w, strata, psu, design, a, b)
        self.assertAlmostEqual(se, np.hypot(se_a, se_b))
        self.assertAlmostEqual(difference, np.average(y[a], weights=w[a])
                               - np.average(y[b], weights=w[b]))

    def test_contrast_interval_and_p_value_use_the_design_df(self):
        frame = design_frame(seed=5)
        result = nsfg.sex_contrast(frame, frame["y"].astype(bool), frame["domain"])
        quantile = nsfg.stats.t.ppf(0.975, result.df)
        self.assertEqual(result.df, 30)
        self.assertAlmostEqual(result.ci[1] - result.difference, quantile * result.se)
        self.assertAlmostEqual(result.p_value,
                               2 * nsfg.stats.t.sf(abs(result.difference / result.se), 30))
        self.assertAlmostEqual(result.difference,
                               result.female.estimate - result.male.estimate)

    def test_design_degrees_of_freedom(self):
        design = sd.design_table(np.array([1, 1, 1, 2, 2]), np.array([1, 2, 3, 1, 2]))
        self.assertEqual(sd.design_degrees_of_freedom(design), 3)

    @unittest.skipUnless(importlib.util.find_spec("svy"), "svy is not installed")
    def test_linearization_matches_svy_on_synthetic_data(self):
        import polars as pl
        import svy

        frame = design_frame(seed=6)
        ours = nsfg.weighted_share(frame, frame["y"].astype(bool), frame["domain"])
        sample = svy.Sample(pl.from_pandas(frame), svy.Design(
            stratum=nsfg.STRATUM, psu=nsfg.CLUSTER, wgt=nsfg.WEIGHT))
        row = sample.estimation.mean("y", where=pl.col("domain")).to_dicts()[0]
        self.assertAlmostEqual(row["est"], ours.estimate, places=12)
        self.assertAlmostEqual(row["se"], ours.se, places=12)


class MissingDataTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())

    def test_missing_file_and_missing_column_raise(self):
        with self.assertRaises(FileNotFoundError):
            nsfg.load_respondents("female", path=self.directory / "absent.csv")
        path = self.directory / "partial.csv"
        pd.DataFrame({"AGER": [20], "YEAR": [1]}).to_csv(path, index=False)
        with self.assertRaises(KeyError):
            nsfg.load_respondents("female", path=path)

    def test_missing_datasets_skip_every_check(self):
        data = audit.AuditData({sex: self.directory / f"{sex}.csv" for sex in nsfg.SEXES})
        results = audit.run(sorted(audit.CHECKS), data)
        self.assertEqual(len(results), 19)
        self.assertEqual({r.status for r in results}, {audit.SKIP})

    def test_require_data_is_an_error(self):
        original = nsfg.DATA_PATHS
        nsfg.DATA_PATHS = {sex: self.directory / f"{sex}.csv" for sex in nsfg.SEXES}
        try:
            self.assertEqual(audit.main(["--require-data", "--check", "1"]), 2)
        finally:
            nsfg.DATA_PATHS = original


class RegistryTests(unittest.TestCase):
    def test_nineteen_checks_are_registered_in_order(self):
        self.assertEqual(list(audit.CHECKS), [f"{k:02d}" for k in range(1, 20)])

    def test_expectations_fail_on_mismatch(self):
        expect = audit.Expectations()
        expect.near("value", 11.244, 11.24, 2)
        self.assertEqual(expect.status(), audit.PASS)
        expect.near("value", 11.256, 11.24, 2)
        self.assertEqual(expect.status(), audit.FAIL)


@unittest.skipUnless(nsfg.data_available(), "NSFG public-use files not available")
class NsfgDataIntegrationTests(unittest.TestCase):
    """Full-data checks against the recorded Stage 3 values."""

    @classmethod
    def setUpClass(cls):
        cls.data = audit.AuditData()
        cls.results = {r.check_id: r for r in audit.run(sorted(audit.CHECKS), cls.data)}

    def test_no_check_fails(self):
        failed = {k: r.notes for k, r in self.results.items() if r.status == audit.FAIL}
        self.assertEqual(failed, {})

    def test_expected_warnings(self):
        # M09 cleanup: Check 19's shared design is established from the CDC sample-design
        # documentation (docs/nsfg_stage3_validation.md); Check 03 keeps its WARN.
        warned = sorted(k for k, r in self.results.items() if r.status == audit.WARN)
        self.assertEqual(warned, ["03"])

    def test_routing_exceptions_traced(self):
        trace = self.results["03"].results
        self.assertEqual(
            trace["male exception trace"]["partnered, partner sterility missing, routed to "
                                          "INTEND"], 3)
        self.assertEqual(trace["female exception trace"]["intention section blank (RWANT "
                                                         "missing)"], 1)
        self.assertEqual(trace["male exception trace"]["joint item blank after RWANT answered "
                                                       "(unexplained)"], 1)

    def test_cdc_benchmark_passes(self):
        self.assertEqual(self.results["17"].status, audit.PASS)
        self.assertIn("18.9586%", self.results["17"].results["ages 20-24"])

    def test_primary_decomposition(self):
        pooled = self.data.pooled
        domain = audit.cohort_domain(pooled, "conservative")
        counts = pooled.loc[domain, "category"].value_counts().to_dict()
        self.assertEqual(counts.get(nsfg.EXPLICIT_NEGATIVE), 116)
        self.assertEqual(counts.get(nsfg.STERILITY_LINKED), 77)
        self.assertNotIn(nsfg.UNEXPLAINED, counts)

    def test_primary_sex_contrast(self):
        pooled = self.data.pooled
        result = nsfg.sex_contrast(pooled, pooled["divergence"],
                                   audit.cohort_domain(pooled, "conservative"))
        self.assertAlmostEqual(100 * result.difference, 1.90, delta=0.005)
        self.assertAlmostEqual(100 * result.se, 2.09, delta=0.005)
        self.assertAlmostEqual(result.p_value, 0.3676, delta=0.00005)


if __name__ == "__main__":
    unittest.main()
