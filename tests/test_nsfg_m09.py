"""M09 tests: constructs, survey estimation, reliability, leakage safety and models.

Unit tests use synthetic files with valid NSFG coding and a 20-stratum,
80-cluster design, so they run without the NSFG data. Integration tests
skip when the public-use files are absent; none passes without them.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import nsfg
from analysis import nsfg_descriptive as nd
from analysis import nsfg_models as nm
from analysis import survey_design as sd
from analysis.nlsy97 import PROJECT_ROOT

HAS_DATA = nsfg.data_available()


def synthetic_file(sex: str, n: int = 900, seed: int = 0) -> pd.DataFrame:
    """Raw-coded respondent file whose intention items follow the CDC routing."""
    rng = np.random.default_rng(seed)
    pick = rng.choice
    cells = np.arange(80)
    cell = np.concatenate([cells, pick(cells, n - 80)])
    frame = pd.DataFrame({
        nsfg.STRATUM: cell // 4 + 1, nsfg.CLUSTER: cell % 4 + 1,
        nsfg.WEIGHT: rng.uniform(2000, 40000, n),
        "AGER": pick(np.arange(18, 30), n), "YEAR": pick([1, 2], n),
        "RMARIT": pick([0, 1, 2], n, p=[0.6, 0.25, 0.15]),
        "RSTRSTAT": pick([0, 1], n, p=[0.92, 0.08]),
        "RWANT": pick([1, 5, 9], n, p=[0.7, 0.25, 0.05]).astype(float),
    })
    frame["CMINTVW"] = np.where(frame["YEAR"].eq(1), 1470, 1480)
    married = frame["RMARIT"].isin(nsfg.MARRIED_OR_COHABITING)
    frame["PSTRSTAT"] = np.where(married, pick([0, 1], n, p=[0.92, 0.08]), np.nan)
    fertile = frame["RSTRSTAT"].eq(0) & ~(married & frame["PSTRSTAT"].eq(1))
    frame["JINTEND"] = np.where(married & fertile, pick([1, 5], n, p=[0.8, 0.2]), np.nan)
    yes, no = nsfg.INTEND_YES[sex], nsfg.INTEND_NO[sex]
    asked = ~married & frame["RSTRSTAT"].eq(0) & frame["RWANT"].isin([1, 9])
    frame["INTEND"] = np.where(asked, pick(list(yes) + list(no), n), np.nan)
    frame["INTENT"] = nsfg.reconstruct_intent(frame, sex)
    frame["INTENDN"] = np.where(frame["INTEND"].isin(yes), pick([1, 2, 3, 99], n), np.nan)
    frame["JINTENDN"] = np.where(frame["JINTEND"].eq(1), pick([1, 2, 98], n), np.nan)
    frame["ADDEXP"] = np.where(frame["INTENT"].eq(1), 20, 0)
    for column, codes in {"MARSTAT": [1, 2, 3], "EVRMARRY": [0, 1], "ADDEXP_I": [0],
                          "PROBWANT": [1, 2], "CURRPREG": [1, 5], "HIEDUC": range(1, 12),
                          "HISPRACE2": [1, 2, 3, 4], "LABORFOR": range(1, 8),
                          "METRO": [1, 2, 3], "RELIGION": [1, 2, 3, 4], "CURR_INS": [1, 2, 3, 4],
                          "NUMKDHH": [0, 1, 2]}.items():
        frame[column] = pick(list(codes), n)
    frame["POVERTY"] = pick(np.arange(50, 701), n)
    if sex == "female":
        frame["PARITY"] = pick([0, 0, 1, 2, 3], n)
        frame["FECUND"], frame["STRLOPER"], frame["CONSTAT1"] = 5, np.nan, pick([6, 42], n)
    else:
        frame["HADSEX"] = pick([1, 2], n, p=[0.8, 0.2])
        frame["EVBIOKID"] = np.where(frame["HADSEX"].eq(1), pick([1, 5, 8], n,
                                                                 p=[0.4, 0.55, 0.05]), np.nan)
        frame["NUMBIOKID"] = np.where(frame["EVBIOKID"].eq(1), pick([1, 2, 98], n), np.nan)
    return frame


def write_synthetic(directory: Path, seed: int = 0) -> dict[str, Path]:
    paths = {}
    for offset, sex in enumerate(nsfg.SEXES):
        paths[sex] = directory / f"{sex}.csv"
        synthetic_file(sex, seed=seed + offset).to_csv(paths[sex], index=False)
    return paths


class SyntheticSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = write_synthetic(Path(cls.tmp.name))
        cls.sample = nsfg.analysis_sample(cls.paths)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class ConstructTests(SyntheticSample):
    def test_men_children_coding(self):
        men = self.sample[self.sample["sex"].eq("male")]
        self.assertTrue(men.loc[men["HADSEX"].eq(2), "children"].eq(0).all())
        self.assertTrue(men.loc[men["EVBIOKID"].eq(5), "children"].eq(0).all())
        self.assertTrue(men.loc[men["EVBIOKID"].eq(8), "children"].isna().all())
        self.assertTrue(men.loc[men["NUMBIOKID"].eq(98), "children"].isna().all())

    def test_intended_number_only_for_intenders(self):
        known = self.sample["intended_number"].notna()
        self.assertTrue(self.sample.loc[known, "INTENT"].eq(nsfg.INTENDS).all())
        self.assertFalse(self.sample["intended_number"].isin(nsfg.NUMBER_NOT_GIVEN).any())

    def test_target_categories_are_exclusive(self):
        explicit, sterility = self.sample["explicit"], self.sample["sterility"]
        self.assertFalse((explicit & sterility).any())
        self.assertTrue(self.sample.loc[sterility, "JINTEND"].isna().all())

    def test_bands_cover_all_codes(self):
        for column in ("education", "race_ethnicity", "poverty_group", "labor_force"):
            self.assertFalse(self.sample[column].isna().any(), column)

    def test_invalid_code_raises(self):
        frame = synthetic_file("female", n=100)
        frame.loc[0, "HIEDUC"] = 15
        with self.assertRaises(ValueError):
            nsfg.derive_constructs(frame, "female")

    def test_missing_column_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "female.csv"
            synthetic_file("female", n=100).drop(columns="PARITY").to_csv(path, index=False)
            with self.assertRaises(KeyError):
                nsfg.load_analysis_frame("female", path)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            nsfg.load_analysis_frame("male", Path("does/not/exist.csv"))

    def test_incompatible_designs_raise(self):
        female = synthetic_file("female", n=200)
        male = synthetic_file("male", n=200, seed=3)
        male[nsfg.CLUSTER] = male[nsfg.CLUSTER] + 4
        with self.assertRaises(ValueError):
            nsfg.pooled_respondents(female, male)


class SurveyMathTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.n = 600
        self.strata = np.repeat(np.arange(10), 60)
        self.psu = np.tile(np.repeat([1, 2, 3], 20), 10)
        self.weights = rng.uniform(1, 5, self.n)
        self.y = rng.binomial(1, 0.3, self.n).astype(float)
        self.design = sd.design_table(self.strata, self.psu)
        self.domains = [self.strata < 5, self.strata >= 5, self.psu == 1]

    def test_covariance_matches_existing_functions(self):
        means, cov = sd.linearized_domain_covariance(self.y, self.weights, self.strata,
                                                     self.psu, self.design, self.domains)
        for i, domain in enumerate(self.domains):
            mean, se = sd.linearized_mean(self.y, self.weights, self.strata, self.psu,
                                          self.design, domain)
            self.assertAlmostEqual(means[i], mean, places=12)
            self.assertAlmostEqual(np.sqrt(cov[i, i]), se, places=12)
        difference, se = sd.linearized_domain_difference(
            self.y, self.weights, self.strata, self.psu, self.design, *self.domains[:2])
        self.assertAlmostEqual(np.sqrt(cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]), se, places=12)
        self.assertAlmostEqual(means[0] - means[1], difference, places=12)

    def test_wald_equal_means_gives_p_one(self):
        statistic, df1, df2, p = sd.adjusted_wald_test(np.array([0.3, 0.3, 0.3]),
                                                       np.eye(3) * 1e-3, 60)
        self.assertEqual((df1, df2), (2, 59))
        self.assertAlmostEqual(statistic, 0.0)
        self.assertAlmostEqual(p, 1.0)

    def test_wald_rejects_single_domain_or_small_df(self):
        with self.assertRaises(ValueError):
            sd.adjusted_wald_test(np.array([0.3]), np.eye(1), 60)
        with self.assertRaises(ValueError):
            sd.adjusted_wald_test(np.zeros(5), np.eye(5), 2)

    def test_korn_graubard_matches_clopper_pearson_for_srs(self):
        lower, upper, effective = nd.korn_graubard_interval(0.5, np.sqrt(0.25 / 100), 100, 10**6)
        self.assertAlmostEqual(lower, 0.3983, places=3)
        self.assertAlmostEqual(upper, 0.6017, places=3)
        self.assertAlmostEqual(effective, 100, delta=0.5)

    def test_nchs_reliability_rules(self):
        self.assertTrue(nd.proportion_reliability(0.1, 0.05, 0.2, 25, 60).startswith("suppress"))
        self.assertTrue(nd.proportion_reliability(0.5, 0.3, 0.65, 100, 60).startswith(
            "suppress: CI width"))
        self.assertTrue(nd.proportion_reliability(0.03, 0.005, 0.08, 200, 60).startswith(
            "suppress: relative"))
        self.assertEqual(nd.proportion_reliability(0.3, 0.25, 0.35, 300, 60), "reliable")
        self.assertTrue(nd.proportion_reliability(0.3, 0.25, 0.35, 300, 5).startswith("flag"))

    def test_holm(self):
        adjusted = nd.holm(pd.Series([0.01, 0.04, 0.03], index=list("abc")))
        self.assertEqual(adjusted.round(4).to_dict(), {"a": 0.03, "b": 0.06, "c": 0.06})


class DescriptiveTests(SyntheticSample):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tables = nd.build_tables(cls.sample)

    def test_empty_domain_is_suppressed(self):
        survey = nd.Survey(nd.prepare(self.sample).reset_index(drop=True))
        result = survey.share("wants", np.zeros(len(survey.sample), dtype=bool))
        self.assertEqual(result["n"], 0)
        self.assertTrue(result["reliability"].startswith("suppress"))
        with self.assertRaises(ValueError):
            survey.difference("wants", np.zeros(len(survey.sample), dtype=bool),
                              np.ones(len(survey.sample), dtype=bool))

    def test_empty_sample_raises(self):
        with self.assertRaises(ValueError):
            nd.Survey(self.sample.iloc[:0])

    def test_decomposition_sums_to_one(self):
        data = self.tables["response_distributions"]
        data = data[data["item"].eq("intention category among wanters")]
        totals = data.groupby(["cohort", "population"])["estimate"].sum()
        np.testing.assert_allclose(totals.to_numpy(), 1.0, atol=1e-9)

    def test_denominators_are_reported(self):
        for name in ("estimates", "subgroups"):
            self.assertTrue(self.tables[name]["n"].ge(0).all())
            self.assertIn("reliability", self.tables[name])

    def test_sparse_groups_are_flagged(self):
        subgroups = self.tables["subgroups"]
        small = subgroups[subgroups["n"].lt(30)]
        self.assertTrue(small["reliability"].str.startswith("suppress").all())

    def test_planned_comparisons_are_holm_adjusted(self):
        tests = self.tables["subgroup_tests"]
        planned = tests[tests["role"].eq("planned comparison")]
        self.assertEqual(len(planned), len(nd.PLANNED_TESTS))
        self.assertTrue((planned["holm_p_planned_family"] >= planned["p_value"]).all())

    def test_public_tables_blank_suppressed_rows(self):
        public = nd.public_tables(self.tables)
        suppressed_rows = 0
        for name, table in public.items():
            hide = nd.is_suppressed(table)
            suppressed_rows += int(hide.sum())
            for column in nd.SUPPRESSED_COLUMNS:
                if column in table:
                    self.assertTrue(table.loc[hide, column].isna().all(), (name, column))
            full = self.tables[name]
            keep = ~hide
            for column in [c for c in ("estimate", "se", "n") if c in table]:
                pd.testing.assert_series_equal(table.loc[keep, column].astype(float),
                                               full.loc[keep, column].astype(float))
        self.assertGreater(suppressed_rows, 0)  # the synthetic sample has sparse cells

    def test_written_outputs_honor_suppression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nd.write_outputs(self.tables, root / "public", root / "figures", root / "internal")
            for path in (root / "public").glob("*.csv"):
                table = pd.read_csv(path)
                hide = nd.is_suppressed(table)
                for column in nd.SUPPRESSED_COLUMNS:
                    if column in table:
                        self.assertTrue(table.loc[hide, column].isna().all(), path.name)
            internal = pd.read_csv(root / "internal" / "subgroups.csv")
            hidden = nd.is_suppressed(internal)
            self.assertTrue(internal.loc[hidden, "estimate"].notna().all())
            self.assertEqual(len(list((root / "figures").glob("*.png"))), len(nd.FIGURES))

    def test_figures_draw_no_suppressed_points(self):
        public = nd.public_tables(self.tables)["subgroups"]
        drawn = nd.plottable(public)
        self.assertFalse(nd.is_suppressed(drawn).any())
        self.assertTrue(drawn["estimate"].notna().all())
        flagged = public.assign(reliability="suppress: test")
        self.assertTrue(nd.plottable(flagged).empty)

    def test_expected_total_is_women_only(self):
        estimates = self.tables["estimates"]
        rows = estimates[estimates["measure"].eq("expected_total")]
        self.assertNotIn("male", set(rows["population"]))

    def test_main_without_data_exits(self):
        original = nsfg.DATA_PATHS
        try:
            nsfg.DATA_PATHS = {sex: Path("missing") / f"{sex}.csv" for sex in nsfg.SEXES}
            with self.assertRaises(SystemExit):
                nd.main()
            with self.assertRaises(SystemExit):
                nm.main()
        finally:
            nsfg.DATA_PATHS = original


class LeakageTests(unittest.TestCase):
    def test_primary_features_pass(self):
        nm.assert_no_leakage(nm.FEATURE_SETS["primary"])

    def test_target_and_derived_variables_rejected(self):
        for feature in ("INTENT", "JINTEND", "INTEND", "ADDEXP", "RSTRSTAT", "PWANT",
                        "expected_additional", "category", nsfg.WEIGHT, "cluster"):
            with self.assertRaises(ValueError, msg=feature):
                nm.assert_no_leakage(["AGER", feature])

    def test_routing_features_need_explicit_permission(self):
        with self.assertRaises(ValueError):
            nm.assert_no_leakage(["AGER", "partnership"])
        nm.assert_no_leakage(["AGER", "partnership"], allow_routing=True)

    def test_dictionary_covers_every_feature(self):
        listed = {row[0] for row in nm.FEATURE_DICTIONARY}
        for features in nm.FEATURE_SETS.values():
            self.assertLessEqual(set(features), listed)


class ModelTests(SyntheticSample):
    def setUp(self):
        self.frame = nm.eligible(self.sample)

    def test_eligibility_excludes_non_direct_labels(self):
        self.assertTrue(self.frame["category"].isin([nsfg.POSITIVE,
                                                     nsfg.EXPLICIT_NEGATIVE]).all())
        self.assertTrue(self.frame["wants"].all())
        self.assertEqual(self.frame["label"].sum(), self.frame["explicit"].sum())

    def test_unknown_eligibility_raises(self):
        with self.assertRaises(ValueError):
            nm.eligible(self.sample, eligibility="anything")

    def test_holdout_keeps_clusters_apart(self):
        train, test = nm.holdout_split(self.frame, 4, 0, 7)
        self.assertFalse(set(self.frame["cluster"].iloc[train])
                         & set(self.frame["cluster"].iloc[test]))

    def test_threshold_and_calibration_helpers(self):
        rng = np.random.default_rng(0)
        p = rng.uniform(0.01, 0.6, 5000)
        y = rng.binomial(1, p)
        slope, intercept, in_large = nm.calibration_fit(y, p)
        self.assertAlmostEqual(slope, 1.0, delta=0.15)
        self.assertAlmostEqual(in_large, 0.0, delta=0.15)
        threshold = nm.best_threshold(y, p)
        self.assertTrue(0 < threshold < 1)
        constant = nm.ranking_metrics(y, np.full(len(y), y.mean()), y.mean())
        self.assertAlmostEqual(constant["roc_auc"], 0.5)
        self.assertTrue(constant["constant_prediction"])

    def test_small_experiment_runs_and_isolates_holdout(self):
        config = deepcopy(nm.CONFIG)
        config.update({"bootstrap_replicates": 30, "permutation_repeats": 2,
                       "selection": {"folds": 3, "repeats": 1, "metric": "pr_auc"},
                       "grids": {"logistic": {"C": [0.1], "class_weight": [None]},
                                 "boosting": {"max_iter": [20], "min_samples_leaf": [20],
                                              "class_weight": [None]}}})
        result = nm.run_experiment(self.sample, config)
        partitions = result["partition_counts"].set_index("partition")
        self.assertEqual(partitions["respondents"].sum(), len(self.frame))
        self.assertEqual(set(result["holdout"]["model"]), {"dummy", "logistic", "boosting"})
        dummy = result["holdout"].set_index("model").loc["dummy"]
        self.assertAlmostEqual(dummy["roc_auc"], 0.5)
        again = nm.run_experiment(self.sample, config)
        pd.testing.assert_frame_equal(result["holdout"], again["holdout"])


@unittest.skipUnless(HAS_DATA, "NSFG 2022-2023 public-use files not present")
class M09DataIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = nsfg.analysis_sample()

    def test_stage3_values_reproduce_through_m09_pipeline(self):
        tables = nd.build_tables(self.sample)
        estimates = tables["estimates"].set_index(["cohort", "population", "measure"])
        row = estimates.loc[("conservative", "all", "divergence_among_wanters")]
        self.assertEqual(row["n"], 1703)
        self.assertAlmostEqual(100 * row["estimate"], 11.24, delta=0.005)
        self.assertAlmostEqual(100 * row["se"], 0.98, delta=0.005)
        explicit = estimates.loc[("conservative", "all", "explicit_among_wanters")]
        self.assertAlmostEqual(100 * explicit["estimate"], 6.56, delta=0.005)

    def test_model_class_counts(self):
        frame = nm.eligible(self.sample)
        self.assertEqual(len(frame), 1607)
        self.assertEqual(int(frame["label"].sum()), 116)

    def test_stored_outputs_match_a_fresh_run(self):
        path = nd.OUTPUT_DIR / "estimates.csv"
        if not path.exists():
            self.skipTest("Run python -m analysis.nsfg_descriptive first")
        fresh = nd.public_tables(nd.build_tables(self.sample))
        for name in ("estimates", "subgroups", "expected_by_category", "sensitivity"):
            stored = pd.read_csv(nd.OUTPUT_DIR / f"{name}.csv")
            np.testing.assert_allclose(stored["estimate"], fresh[name]["estimate"], rtol=1e-5,
                                       equal_nan=True, err_msg=name)

    def test_stored_public_outputs_honor_suppression(self):
        paths = sorted(nd.OUTPUT_DIR.glob("*.csv"))
        if not paths:
            self.skipTest("Run python -m analysis.nsfg_descriptive first")
        suppressed = 0
        for path in paths:
            table = pd.read_csv(path)
            hide = nd.is_suppressed(table)
            suppressed += int(hide.sum())
            for column in nd.SUPPRESSED_COLUMNS:
                if column in table:
                    self.assertTrue(table.loc[hide, column].isna().all(), path.name)
        self.assertGreater(suppressed, 0)

    def test_stored_model_results_reproduce(self):
        if not nm.RESULTS_PATH.exists():
            self.skipTest("Run python -m analysis.nsfg_models first")
        stored = json.loads(nm.RESULTS_PATH.read_text(encoding="utf-8"))
        result = nm.run_experiment(self.sample, stored["config"])
        fresh = result["holdout"].set_index("model")
        for row in stored["holdout"]:
            for key in ("roc_auc", "pr_auc", "brier", "f1"):
                self.assertAlmostEqual(fresh.loc[row["model"], key], row[key], places=8)


class VerifierWithoutDataTests(unittest.TestCase):
    def test_verifier_requires_data(self):
        script = PROJECT_ROOT / "audit" / "verify_nsfg_m09.py"
        code = ("import sys, runpy; from pathlib import Path; from analysis import nsfg; "
                "nsfg.DATA_PATHS = {s: Path('missing') / s for s in nsfg.SEXES}; "
                f"sys.argv = ['verify', '--require-data']; runpy.run_path(r'{script}', "
                "run_name='__main__')")
        completed = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT,
                                   capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2, completed.stderr)


if __name__ == "__main__":
    unittest.main()
