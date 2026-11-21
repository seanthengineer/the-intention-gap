"""M10 model, descriptive and covariate tests.

Synthetic panels with a known slope test the fixed-effects estimator, the CR1
cluster variance, the stacked contrast, the wild cluster bootstrap and the
failure conditions (rank deficiency, missing inputs, protocol drift). Integration
tests skip when the M10 data and results are absent.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from analysis import cdc_natality as cdc
from analysis import m10_covariates as cov
from analysis import m10_models as m

YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024]


def synthetic_panel(states: int = 30, slope: float = -0.6, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(states):
        effect = rng.normal(0, 5)
        for year in YEARS:
            x = 45 + 0.5 * s + 0.3 * (year - 2014) + rng.normal(0, 2)
            for age, shift in (("20-24", 0.0), ("25-29", 30.0)):
                rows.append({"state_fips": f"{s:02d}", "year": year, "age_group": age,
                             "burden30_pct": x, "outcome_rate": 80 + shift + effect
                             + 0.8 * (year - 2014) + slope * x + rng.normal(0, 1),
                             "female_population": 1000 + 10 * s})
    frame = pd.DataFrame(rows)
    frame["trend"] = frame["year"] - 2014
    return frame


class EstimatorTests(unittest.TestCase):
    def setUp(self):
        self.frame = synthetic_panel()
        self.single = m.age_frame(self.frame, "20-24")

    def test_recovers_known_slope(self):
        result = m.fit(self.single, "outcome_rate", ["burden30_pct"])
        self.assertAlmostEqual(result.coef[0], -0.6, delta=0.08)
        self.assertEqual(result.clusters, 30)
        row = result.row("burden30_pct")
        self.assertAlmostEqual(row["estimate_per10"], 10 * result.coef[0])
        self.assertLess(row["ci_low"], row["estimate_per10"])

    def test_matches_manual_within_transformation_and_cr1(self):
        data = self.single
        result = m.fit(data, "outcome_rate", ["burden30_pct"])
        x = m.two_way_demean(data, "burden30_pct").to_numpy()
        y = m.two_way_demean(data, "outcome_rate").to_numpy()
        beta = (x @ y) / (x @ x)
        self.assertAlmostEqual(result.coef[0], beta, places=10)
        u = y - beta * x
        groups = pd.factorize(data["state_fips"])[0]
        scores = np.bincount(groups, weights=x * u)
        n, k, g = len(data), 1 + 1 + 29 + 9, 30
        variance = g / (g - 1) * (n - 1) / (n - k) * (scores @ scores) / (x @ x) ** 2
        self.assertAlmostEqual(result.vcov[0, 0], variance, places=10)

    def test_rank_deficiency_raises(self):
        data = self.single.assign(state_mean=self.single.groupby("state_fips")[
            "burden30_pct"].transform("mean"))
        with self.assertRaises(ValueError):
            m.fit(data, "outcome_rate", ["state_mean"])

    def test_single_cluster_and_empty_raise(self):
        with self.assertRaises(ValueError):
            m.fit(self.single.iloc[:0], "outcome_rate", ["burden30_pct"])
        with self.assertRaises(ValueError):
            m.fit(self.single[self.single["state_fips"].eq("00")], "outcome_rate",
                  ["burden30_pct"], absorb=[])

    def test_stacked_contrast_equals_separate_fits(self):
        with mock.patch.object(m, "wild_cluster_p", return_value=0.5):
            contrast, fit = m.stacked_model(self.frame)
        b1 = m.fit(m.age_frame(self.frame, "20-24"), "outcome_rate", ["burden30_pct"]).coef[0]
        b2 = m.fit(m.age_frame(self.frame, "25-29"), "outcome_rate", ["burden30_pct"]).coef[0]
        self.assertAlmostEqual(contrast["estimate_per10"], 10 * (b1 - b2), places=8)
        self.assertEqual(fit.n, len(self.frame))
        self.assertEqual(fit.clusters, 30)

    def test_wild_bootstrap_detects_strong_effect_and_not_null(self):
        p_strong = m.wild_cluster_p(self.single, "outcome_rate", ["burden30_pct"],
                                    "burden30_pct", replicates=199)
        self.assertLess(p_strong, 0.05)
        null = synthetic_panel(slope=0.0, seed=3)
        p_null = m.wild_cluster_p(m.age_frame(null, "20-24"), "outcome_rate",
                                  ["burden30_pct"], "burden30_pct", replicates=199)
        self.assertGreater(p_null, 0.05)

    def test_population_weights_change_the_estimand(self):
        unweighted = m.fit(self.single, "outcome_rate", ["burden30_pct"]).coef[0]
        weighted = m.fit(self.single, "outcome_rate", ["burden30_pct"],
                         weight="female_population").coef[0]
        self.assertNotEqual(unweighted, weighted)

    def test_multiple_comparison_helpers(self):
        p = pd.Series([0.01, 0.04, 0.03])
        self.assertEqual(m.holm(p).round(4).tolist(), [0.03, 0.06, 0.06])
        self.assertEqual(m.benjamini_hochberg(p).round(4).tolist(), [0.03, 0.04, 0.04])


class ProtocolTests(unittest.TestCase):
    def test_protocol_drift_blocks_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            protocol, lock = Path(tmp) / "p.md", Path(tmp) / "lock.json"
            protocol.write_text("locked text", encoding="utf-8")
            lock.write_text(json.dumps({"sha256": "0" * 64}), encoding="utf-8")
            with mock.patch.object(m, "PROTOCOL_PATH", protocol), \
                    mock.patch.object(m, "LOCK_PATH", lock):
                with self.assertRaises(SystemExit):
                    m.verify_protocol()

    def test_missing_inputs_raise(self):
        with self.assertRaises(FileNotFoundError):
            m.load_analysis_frame(Path("missing.csv"), Path("missing2.csv"))


class SourceParsingTests(unittest.TestCase):
    def test_state_table_with_dot_leaders(self):
        text = ("Table 6. Birth rates, by age of mother: United States, each state and "
                "territory, 2024\n"
                "Alabama . . . . . . . 11.2  57.2  1,716.0  0.3  19.1  9.0  33.5  77.5  111.6  "
                "86.1  39.9  8.3  0.4\n"
                "Arkansas. . . . . . . 11.5  58.8  1,763.0  0.2  22.2  8.9  43.3  89.1  113.6  "
                "82.0  37.2  7.9  0.4\n"
                "Table 7. Birth rates for unmarried women\n")
        table = cdc.parse_nvsr_state_table(text).set_index("area")
        self.assertEqual(table.loc["Alabama", "rate_20_24"], 77.5)
        self.assertEqual(table.loc["Arkansas", "rate_25_29"], 113.6)

    def test_b25072_identity_failure_detected(self):
        header = ["NAME", *[f"B25072_{i:03d}{s}" for i in range(1, 30) for s in ("E", "M")],
                  "state"]
        values = {1: 100, 2: 40, 3: 10, 4: 10, 5: 5, 6: 5, 7: 5, 8: 5, 9: 60, 10: 20, 11: 10,
                  12: 10, 13: 10, 14: 5, 15: 5}
        row = ["Alabama", *[str(values.get(i, 0)) if s == "E" else "1" for i in range(1, 30)
                            for s in ("E", "M")], "01"]
        frame = pd.DataFrame([row], columns=header).assign(year=2024)
        good = cov.validate_table("B25072", [frame], {2024: {}})
        self.assertEqual(good["identity_failures"], 0)
        frame.loc[0, "B25072_007E"] = "9"
        bad = cov.validate_table("B25072", [frame], {2024: {}})
        self.assertGreater(bad["identity_failures"], 0)


HAS_RESULTS = (m.OUTPUT_DIR / "m10_primary.csv").exists() and m.PANEL_PATH.exists() and \
    m.COVARIATES_PATH.exists()


@unittest.skipUnless(HAS_RESULTS, "M10 data and results not present")
class M10IntegrationTests(unittest.TestCase):
    def test_protocol_lock_holds(self):
        lock = m.verify_protocol()
        self.assertEqual(len(lock["amendments"]), 1)

    def test_primary_reproduces_stored_result(self):
        frame = m.load_analysis_frame()
        self.assertEqual(len(frame), 1020)
        self.assertEqual(frame["outcome_rate"].isna().sum(), 0)
        stored = pd.read_csv(m.OUTPUT_DIR / "m10_primary.csv").set_index("test")
        for age in m.AGES:
            row = m.fit(m.age_frame(frame, age), "outcome_rate", ["burden30_pct"]).row(
                "burden30_pct")
            reference = stored.loc[f"beta {age} = 0 (model C)"]
            self.assertAlmostEqual(row["estimate_per10"], reference["estimate_per10"], places=7)
            self.assertAlmostEqual(row["se"], reference["se"], places=7)
            self.assertEqual(row["clusters"], 51)

    def test_coefficient_figure_matches_tables(self):
        models = pd.read_csv(m.OUTPUT_DIR / "m10_models.csv")
        robust = pd.read_csv(m.OUTPUT_DIR / "m10_robustness.csv")
        with tempfile.TemporaryDirectory() as tmp:
            plotted = m.figure_coefficients(models, robust, Path(tmp) / "f.png")
        self.assertEqual(len(plotted), 28)
        for row in plotted.itertuples():
            table, column = ((models, "model") if row.source == "models"
                             else (robust, "variant"))
            match = table[table["age_group"].eq(row.age_group) & table[column].eq(row.key)]
            self.assertEqual(len(match), 1)
            self.assertEqual(row.estimate_per10, match["estimate_per10"].iloc[0])
            self.assertEqual(row.ci_low, match["ci_low"].iloc[0])
            self.assertTrue(row.label.endswith("]"))
        severe = plotted[plotted["key"].str.contains("50%")]
        self.assertTrue(severe["label"].str.contains(r"\[50%\+ burden").all())

    def test_lag_model_uses_exact_years(self):
        frame = m.load_analysis_frame()
        lagged = frame.dropna(subset=["burden30_pct_lag1"])
        self.assertNotIn(2021, set(lagged["year"]))
        self.assertNotIn(2014, set(lagged["year"]))
        self.assertEqual(len(m.age_frame(lagged, "20-24")), 408)


if __name__ == "__main__":
    unittest.main()
