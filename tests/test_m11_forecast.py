"""M11 forecasting tests on synthetic data: methods, guards, leakage, coherence and cohorts.

Integration tests at the end check the saved M11 forecast outputs and skip when
they have not been built.
"""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import m11_models as models


def simulate_ar1(n=1500, phi=0.6, mean=0.4, seed=1):
    rng = np.random.default_rng(seed)
    y = np.empty(n)
    y[0] = mean
    for t in range(1, n):
        y[t] = mean + phi * (y[t - 1] - mean) + rng.normal(0, 0.02)
    return y


class ExponentialSmoothingTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(7)
        self.y = np.log(2.0) + np.cumsum(rng.normal(-0.005, 0.02, 60))

    def test_vectorised_damped_errors_match_scalar_recursion(self):
        alpha, beta, phi = 0.4, 0.1, 0.9
        level, trend = self.y[0], self.y[1] - self.y[0]
        expected = []
        for t in range(1, len(self.y)):
            e = self.y[t] - (level + phi * trend)
            if t >= 2:
                expected.append(e)
            level = level + phi * trend + alpha * e
            trend = phi * trend + beta * e
        grid = models.damped_errors(np.vstack([self.y, self.y]), np.array([[alpha, 0.2]]),
                                    np.array([[beta, 0.05]]), np.array([[phi, 0.85]]))
        self.assertTrue(np.allclose(grid[:, 0, 0], expected))
        self.assertTrue(np.allclose(grid[:, 1, 0], expected))
        self.assertTrue(np.allclose(models.damped_errors(self.y, alpha, beta, phi), expected))

    def test_damped_fit_is_no_worse_than_any_grid_point_and_respects_bounds(self):
        fit = models.fit_damped(self.y)
        ga, gb, gp = models._damped_grid()
        grid_sse = np.sum(models.damped_errors(self.y, ga, ga * gb, gp) ** 2, axis=0)
        self.assertLessEqual(fit["sse"], grid_sse.min() + 1e-12)
        self.assertTrue(0.80 <= fit["phi"] <= 0.98 and 0 < fit["beta"] <= fit["alpha"] < 1)

    def test_ses_with_alpha_one_is_the_naive_forecast(self):
        self.assertAlmostEqual(models.ses_state(self.y, 1.0), self.y[-1])

    def test_damped_variance_factor_starts_at_one(self):
        fit = models.fit_damped(self.y)
        factors = models.damped_variance_factors(fit, 5)
        self.assertEqual(factors[0], 1.0)
        self.assertTrue(np.all(np.diff(factors) > 0))


class AutoregressionTests(unittest.TestCase):
    def test_ar_level_recovers_coefficient_and_mean(self):
        fit = models.fit_ar_level(simulate_ar1())
        self.assertEqual(fit["order"], 1)
        self.assertAlmostEqual(fit["phi"][0], 0.6, delta=0.05)
        self.assertAlmostEqual(fit["intercept"] / (1 - fit["phi"][0]), 0.4, delta=0.01)

    def test_psi_weights_of_ar1_are_powers(self):
        self.assertTrue(np.allclose(models.psi_weights([0.5], 5), 0.5 ** np.arange(5)))

    def test_ari_order_zero_is_a_random_walk(self):
        rng = np.random.default_rng(3)
        y = np.cumsum(rng.normal(0, 0.02, 400))
        out = models.forecast_tfr("ari", y, 4)
        if out["params"]["order"] == 0:
            self.assertTrue(np.allclose(out["log_mean"], y[-1]))
        self.assertTrue(np.all(np.diff(out["log_sd_model"]) > 0))


class TfrMethodGuardTests(unittest.TestCase):
    def setUp(self):
        self.y = np.log(np.linspace(2.2, 1.6, 30))

    def test_every_protocol_method_returns_finite_positive_forecasts(self):
        for method in models.TFR_METHODS:
            out = models.forecast_tfr(method, self.y, 16)
            self.assertEqual(len(out["log_mean"]), 16, method)
            self.assertTrue(np.all(np.isfinite(np.exp(out["log_mean"]))), method)
            self.assertEqual(out["log_sd_model"] is not None, method in models.STOCHASTIC, method)

    def test_baseline_definitions(self):
        self.assertTrue(np.allclose(models.forecast_tfr("naive", self.y, 3)["log_mean"], self.y[-1]))
        self.assertAlmostEqual(models.forecast_tfr("mean10", self.y, 1)["log_mean"][0], self.y[-10:].mean())
        drift = (self.y[-1] - self.y[-11]) / 10
        self.assertAlmostEqual(models.forecast_tfr("drift10", self.y, 2)["log_mean"][1], self.y[-1] + 2 * drift)
        converge = models.forecast_tfr("converge30", self.y, 25)["log_mean"]
        self.assertAlmostEqual(converge[19], self.y[-30:].mean())        # reached at h = 20
        self.assertAlmostEqual(converge[24], self.y[-30:].mean())

    def test_unsupported_settings_are_rejected(self):
        with self.assertRaises(ValueError):
            models.forecast_tfr("prophet", self.y, 5)
        with self.assertRaises(ValueError):
            models.forecast_tfr("naive", self.y, 0)
        with self.assertRaises(ValueError):
            models.forecast_shape("S9_neural", np.ones((25, 44)), 5)

    def test_data_gaps_are_rejected(self):
        gap = self.y.copy()
        gap[10] = np.nan
        with self.assertRaises(ValueError):
            models.forecast_tfr("holt_damped", gap, 5)
        with self.assertRaises(ValueError):
            models.forecast_tfr("naive", self.y[:5], 5)


class AgeProfileTests(unittest.TestCase):
    def setUp(self):
        ages = np.arange(12, 56)
        years = 30
        mean_age = np.linspace(26, 30, years)[:, None]
        self.rates = 0.12 * np.exp(-0.5 * ((ages[None, :] - mean_age) / 5.5) ** 2)

    def test_every_shape_method_is_non_negative_and_sums_to_one(self):
        for method in models.SHAPE_METHODS:
            out = models.forecast_shape(method, self.rates, 16)
            self.assertEqual(out["shape"].shape, (16, 44), method)
            self.assertTrue(np.all(out["shape"] > 0), method)
            self.assertTrue(np.allclose(out["shape"].sum(axis=1), 1.0), method)

    def test_fixed_shape_repeats_the_jump_off_year(self):
        out = models.forecast_shape("S0_fixed", self.rates, 3)
        self.assertTrue(np.allclose(out["shape"], models.shape_of(self.rates[-1:])))

    def test_shape_trend_continues_postponement(self):
        ages = np.arange(12, 56) + 0.5
        mean_age = (models.forecast_shape("S1_shape_drift", self.rates, 10)["shape"] * ages).sum(axis=1)
        observed = (models.shape_of(self.rates[-1:]) * ages).sum()
        self.assertGreater(mean_age[-1], observed)

    def test_coherent_rates_sum_to_tfr(self):
        shape = models.forecast_shape("S2_shape_damped", self.rates, 5)["shape"]
        tfr = np.array([1.6, 1.58, 1.57, 1.55, 1.54])
        self.assertTrue(np.allclose(models.coherent_rates(shape, tfr).sum(axis=1), tfr, atol=1e-12))

    def test_incoherent_shape_and_negative_rates_are_rejected(self):
        with self.assertRaises(ValueError):
            models.coherent_rates(np.full((2, 44), 0.03), np.array([1.6, 1.6]))
        bad = self.rates.copy()
        bad[3, 10] = -0.001
        with self.assertRaises(ValueError):
            models.forecast_shape("S0_fixed", bad, 2)
        with self.assertRaises(ValueError):
            models.reconcile(bad, np.full(len(bad), 1.6))

    def test_reconciliation_restores_the_total(self):
        own = models.forecast_shape("S4_lee_carter", self.rates, 4)["rates"]
        target = np.full(4, 1.5)
        self.assertTrue(np.allclose(models.reconcile(own, target).sum(axis=1), target))


def synthetic_tfr(first=1933, last=2024, seed=11):
    rng = np.random.default_rng(seed)
    years = np.arange(first, last + 1)
    return pd.Series(np.exp(np.log(2.0) + np.cumsum(rng.normal(0, 0.03, len(years)))), index=years, name="tfr")


class BacktestEngineTests(unittest.TestCase):
    def setUp(self):
        from analysis import m11_backtest as bt
        self.bt = bt
        self.tfr = synthetic_tfr()

    def test_poisoned_future_does_not_change_any_forecast(self):
        origin = 1990
        clean = self.bt.tfr_backtest(self.tfr, [origin], max_h=16)
        poisoned_series = self.tfr.copy()
        poisoned_series[poisoned_series.index > origin] = 9.9
        poisoned = self.bt.tfr_backtest(poisoned_series, [origin], max_h=16)
        self.assertTrue(np.allclose(clean["log_forecast"], poisoned["log_forecast"]))
        self.assertTrue((clean["train_last"] == origin).all() and (clean["target"] > origin).all())

    def test_minimum_training_length_and_last_target(self):
        records = self.bt.tfr_backtest(self.tfr, range(1945, 1955), methods=["naive"], max_h=16)
        self.assertEqual(records["origin"].min(), 1952)                 # 1933-1952 = 20 years
        late = self.bt.tfr_backtest(self.tfr, [2020], methods=["naive"], max_h=16)
        self.assertEqual(late["target"].max(), 2024)

    def test_rate_matrix_rejects_gaps_invalid_ages_and_negative_rates(self):
        rows = [{"Year": y, "Age": a, "ASFR": 0.01} for y in (2000, 2001, 2003) for a in range(12, 56)]
        with self.assertRaises(ValueError):
            self.bt.rate_matrix(pd.DataFrame(rows))                       # 2002 missing
        rows = [{"Year": y, "Age": a, "ASFR": 0.01} for y in (2000, 2001) for a in range(12, 57)]
        with self.assertRaises(ValueError):
            self.bt.rate_matrix(pd.DataFrame(rows))                       # age 56
        rows = [{"Year": y, "Age": a, "ASFR": -0.01 if a == 30 else 0.01} for y in (2000, 2001) for a in range(12, 56)]
        with self.assertRaises(ValueError):
            self.bt.rate_matrix(pd.DataFrame(rows))
        rows = [{"Year": y, "Age": a, "ASFR": 0.01} for y in (2000, 2001) for a in range(12, 55)]
        with self.assertRaises(ValueError):
            self.bt.rate_matrix(pd.DataFrame(rows))                       # age 55 missing

    def test_block_bootstrap_indices_are_circular_blocks(self):
        idx = self.bt.block_indices(10, 4, 50, np.random.default_rng(0))
        self.assertEqual(idx.shape, (50, 10))
        steps = np.diff(idx[:, :4], axis=1) % 10
        self.assertTrue(np.all(steps == 1))

    def test_selection_rule_and_simplicity_margin(self):
        table = pd.DataFrame({"method": ["naive", "ses", "holt_damped"], "R": [1.0, 0.85, 0.84],
                              "qualifies": [False, True, True], "complexity": [0, 1, 3]})
        self.assertEqual(self.bt.choose(table, "naive", ["naive", "ses", "holt_damped"]), "ses")
        table.loc[1, "R"] = 0.88
        self.assertEqual(self.bt.choose(table, "naive", ["naive", "ses", "holt_damped"]), "holt_damped")
        self.assertEqual(self.bt.choose(table.assign(qualifies=False), "naive", []), "naive")

    def test_lognormal_crps_matches_numerical_integral(self):
        from scipy import stats
        mu, sigma, y = np.log(1.7), 0.12, 1.55
        grid = np.linspace(0.5, 4.0, 200001)
        cdf = stats.lognorm.cdf(grid, s=sigma, scale=np.exp(mu))
        numeric = np.trapezoid((cdf - (grid >= y)) ** 2, grid)
        self.assertAlmostEqual(float(self.bt.lognormal_crps(mu, sigma, y)), numeric, places=5)

    def test_real_time_sigma_uses_only_observable_errors(self):
        records = self.bt.tfr_backtest(self.tfr, range(1952, 2024), methods=["naive"], max_h=5)
        timed = self.bt.real_time_sigma(records)
        row = timed[(timed["h"] == 5) & (timed["origin"] == 1970)].iloc[0]
        usable = records[(records["h"] == 5) & (records["target"] <= 1970)]
        self.assertEqual(row["n_cal"], len(usable))
        self.assertAlmostEqual(row["sigma_rt"], np.sqrt(np.mean(usable["log_error"] ** 2)))
        early = timed[(timed["h"] == 5) & (timed["origin"] == 1960)].iloc[0]
        self.assertTrue(np.isnan(early["sigma_rt"]))                      # fewer than 10 errors


class CohortTransformationTests(unittest.TestCase):
    def setUp(self):
        from analysis import m11_cohorts as coh
        self.coh = coh

    def test_t1_averages_adjacent_squares_of_the_same_cohort(self):
        rr = np.zeros((1, 44))
        rr[0, 18] = 0.10        # age 30 (completed years)
        vv = self.coh.t1(rr)
        self.assertAlmostEqual(vv[0, 18], 0.05)   # age reached 30: lower triangle of age 30
        self.assertAlmostEqual(vv[0, 19], 0.05)   # age reached 31: upper triangle of age 30
        self.assertAlmostEqual(vv.sum(), rr.sum())

    def test_projection_accumulates_contributions_along_cohort_diagonals(self):
        observed = pd.DataFrame({"cohort": [2000], "year": [2024], "ardy": [24], "contribution": [0.3],
                                 "cumulative": [0.3], "segment": ["observed"]})
        future = np.zeros((3, 44))
        future[0, 25 - 12] = 0.1     # 2025, age reached 25 -> cohort 2000
        future[1, 26 - 12] = 0.2     # 2026, age reached 26 -> cohort 2000
        future[1, 25 - 12] = 9.0     # 2026, age reached 25 -> cohort 2001, not 2000
        out = self.coh.project_cohorts(future, 2025, observed, [2000])
        self.assertTrue(np.allclose(out["cumulative"], [0.4, 0.6, 0.6]))
        self.assertEqual(out["ardy"].tolist(), [25, 26, 27])

    def test_unknown_transformation_and_missing_ratios_are_rejected(self):
        with self.assertRaises(ValueError):
            self.coh.to_vv(np.ones((1, 44)), "T9")
        with self.assertRaises(ValueError):
            self.coh.to_vv(np.ones((1, 44)), "T2")

    def test_completion_labels(self):
        self.assertEqual(self.coh.completion_label(0.97, 0.99), "nearly complete by historical standards")
        self.assertEqual(self.coh.completion_label(0.80, 0.85), "substantial but incomplete")
        self.assertEqual(self.coh.completion_label(0.55, 0.60), "partial")


class ScenarioTests(unittest.TestCase):
    def test_cohort_rebasing_follows_birth_year(self):
        from analysis import m11_scenarios as scen
        projection = pd.DataFrame([[100.0, 100.0, 100.0], [100.0, 100.0, 100.0]], index=[2025, 2026], columns=[0, 1, 2])
        reference = pd.Series([110.0, 120.0, 130.0], index=[0, 1, 2])
        rebased = scen.rebase(projection, reference, 2025, [2026], "cohort")
        self.assertTrue(np.allclose(rebased.loc[2026], [110.0, 110.0, 120.0]))   # age 1 in 2026 was age 0 in 2025
        by_age = scen.rebase(projection, reference, 2025, [2026], "age")
        self.assertTrue(np.allclose(by_age.loc[2026], [110.0, 120.0, 130.0]))
        with self.assertRaises(ValueError):
            scen.rebase(projection, reference, 2025, [2026], "magic")

    def test_births_refuse_missing_exposure_or_invalid_rates(self):
        from analysis import m11_scenarios as scen
        asfr = pd.DataFrame(0.05, index=[2030], columns=list(range(12, 56)))
        asfr.iloc[0, 3] = np.nan
        with self.assertRaises(ValueError):
            scen.scenario_births(asfr, "none")
        asfr.iloc[0, 3] = -0.01
        with self.assertRaises(ValueError):
            scen.scenario_births(asfr, "none")


OUT_BUILT = (Path(__file__).resolve().parents[1] / "data" / "public" / "m11" / "forecast" / "m11_fc_summary.json").exists()


@unittest.skipUnless(OUT_BUILT, "M11 forecast outputs not built")
class SavedForecastTests(unittest.TestCase):
    @staticmethod
    def table(name):
        from analysis.m11_forecast import OUT
        return pd.read_csv(OUT / f"{name}.csv")

    def test_protocol_locked_before_the_run_and_unchanged(self):
        import json
        from analysis.m11_forecast import OUT
        from analysis.m11_protocol import verify_lock
        lock = verify_lock()
        record = json.loads((OUT / "m11_run_record.json").read_text(encoding="utf-8"))
        self.assertLess(lock["locked_utc"], record["started_utc"])
        self.assertEqual(record["protocol_sha256"], lock["sha256"])

    def test_selected_methods_follow_the_locked_rules(self):
        tfr = self.table("m11_fc_tfr_selection")
        qualified = tfr[tfr["qualifies"]]
        selected = tfr.loc[tfr["selected"], "method"].item()
        if qualified.empty:
            self.assertEqual(selected, "naive")
        else:
            self.assertIn(selected, set(qualified["method"]))
        shape = self.table("m11_fc_shape_selection")
        if not shape["qualifies"].any():
            self.assertEqual(shape.loc[shape["selected"], "method"].item(), "S0_fixed")

    def test_forecast_years_intervals_and_coherence(self):
        fc = self.table("m11_fc_tfr_forecast")
        self.assertEqual(fc["year"].tolist(), list(range(2025, 2041)))
        self.assertTrue(((fc["lower95"] <= fc["lower80"]) & (fc["lower80"] <= fc["forecast"])
                         & (fc["forecast"] <= fc["upper80"]) & (fc["upper80"] <= fc["upper95"])).all())
        asfr = self.table("m11_fc_asfr_forecast")
        sums = asfr.groupby("year")["asfr"].sum().to_numpy()
        self.assertTrue(np.allclose(sums, fc["forecast"], atol=1e-9))
        self.assertTrue((asfr["asfr"] >= 0).all())

    def test_backtest_records_never_train_past_the_origin(self):
        rec = self.table("m11_fc_tfr_backtest_records")
        self.assertTrue((rec["train_last"] == rec["origin"]).all())
        self.assertTrue((rec["target"] > rec["origin"]).all() and (rec["target"] <= 2024).all())

    def test_gen_z_projection_is_complete_and_monotone(self):
        ends = self.table("m11_fc_genz_endpoints_2040")
        self.assertEqual(ends["cohort"].tolist(), list(range(1995, 2013)))
        self.assertTrue((ends["projected_2040"] >= ends["observed_2024"]).all())
        self.assertTrue(((ends["lower80"] <= ends["projected_2040"]) & (ends["projected_2040"] <= ends["upper80"])).all())
        self.assertTrue((ends["lower80"] >= ends["observed_2024"]).all())
        traj = self.table("m11_fc_genz_trajectories")
        steps = traj.sort_values(["cohort", "year"]).groupby("cohort")["cumulative"].diff().dropna()
        self.assertTrue((steps >= 0).all())

    def test_birth_counts_published_only_after_the_alignment_and_rebasing_tests(self):
        from analysis.m11_forecast import OUT
        alignment = self.table("m11_fc_census_alignment")
        test = self.table("m11_fc_census_rebasing_test")
        valid = test[test["method"] != "none"].groupby("method")["beats_unrebased"].all().any()
        published = (OUT / "m11_fc_census_births.csv").exists()
        self.assertEqual(published, bool(alignment["within_tolerance"].all() and valid))

    def test_public_forecast_tables_hold_aggregates_only(self):
        from analysis.m11_forecast import OUT
        for path in OUT.glob("m11_fc_*.csv"):
            columns = set(pd.read_csv(path, nrows=1).columns)
            self.assertFalse({"restatus", "lbo_rec", "age_imputed", "PUBID", "pubid"} & columns, path.name)




# --------------------------------------------------------------- post-review regression tests

REQUIRED_SENTENCE = "No alternative model satisfied the prespecified criteria for replacing the no-change baseline."


class IntervalLabelFunctionTests(unittest.TestCase):
    def test_labels_never_claim_validated_calibration(self):
        from analysis import m11_forecast as fc
        self.assertIn("failed the prespecified calibration criterion", fc.tfr_interval_label(False))
        self.assertIn("not a validated probability interval", fc.tfr_interval_label(False))
        coverage = pd.DataFrame({"h": [5, 16], "covered80": [0.78, 0.964809]})
        label = fc.cohort_interval_label(coverage)
        self.assertIn("0.96", label)
        self.assertIn("not a validated probability interval", label)
        self.assertNotIn("calibrated prediction interval", label)

    def test_band_label_is_descriptive(self):
        from analysis import m11_forecast as fc
        self.assertIn("not a confidence or prediction interval", fc.BAND_LABEL)
        types = set(fc.data_dictionary()["interval_type"])
        self.assertTrue({"descriptive band", "scenario range", "model-dependent uncertainty range"} <= types)

    def test_figure_wording(self):
        code = (Path(__file__).resolve().parents[1] / "analysis" / "m11_figures.py").read_text(encoding="utf-8")
        self.assertIn(REQUIRED_SENTENCE, code)
        self.assertNotIn("no method beat it", code)
        self.assertNotIn("Bands are calibrated", code)


class OriginLocalSelectionTests(unittest.TestCase):
    @staticmethod
    def records(poison_after=None):
        rows = []
        for origin in range(1952, 2010):
            for h in (5, 10, 15):
                for method, error in (("naive", 0.2), ("ses", 0.1)):
                    target = origin + h
                    value = 50.0 if poison_after is not None and target > poison_after and method == "ses" else error
                    rows.append({"method": method, "origin": origin, "h": h, "target": target,
                                 "error": value * (1 + 0.1 * np.sin(origin))})
        return pd.DataFrame(rows)

    def test_choice_ignores_rows_after_the_origin(self):
        from analysis import m11_origin_local as ol
        clean = ol.choose_at_origin(self.records(), 1990, "error", ["naive", "ses"], "naive")
        poisoned = ol.choose_at_origin(self.records(poison_after=1990), 1990, "error", ["naive", "ses"], "naive")
        self.assertEqual(clean, poisoned)
        self.assertEqual(clean["choice"], "ses")

    def test_insufficient_history_is_recorded_not_defaulted(self):
        from analysis import m11_origin_local as ol
        early = ol.choose_at_origin(self.records(), 1970, "error", ["naive", "ses"], "naive")
        self.assertIsNone(early["choice"])
        self.assertIn("insufficient history", early["reason"])
        validation = pd.DataFrame({"start": [1940, 1941], "method": ["T1", "T2"], "error": [0.1, 0.2]})
        self.assertIsNone(ol.choose_transform(validation, 1990)["choice"])


@unittest.skipUnless(OUT_BUILT, "M11 forecast outputs not built")
class SavedPostReviewTests(unittest.TestCase):
    @staticmethod
    def table(name):
        from analysis.m11_forecast import OUT
        return pd.read_csv(OUT / f"{name}.csv")

    def test_2025_band_is_not_a_95_percent_interval(self):
        check = self.table("m11_fc_check_2025")
        band = check[check["quantity"].str.contains("descriptive band")]
        self.assertEqual(len(band), 1)
        self.assertTrue(band[["lower95", "upper95"]].isna().all(axis=None))
        self.assertTrue(band[["band_lower", "band_upper"]].notna().all(axis=None))

    def test_saved_interval_labels(self):
        for name in ("m11_fc_tfr_forecast", "m11_fc_genz_endpoints_2040", "m11_fc_tfr_forecast_secondary_2025"):
            labels = set(self.table(name)["interval_label"])
            self.assertTrue(labels and all("not a validated probability interval" in t for t in labels), name)
        self.assertNotIn("empirical_calibrated", set(self.table("m11_fc_interval_calibration")["interval"]))

    def test_origin_local_exclusions_and_eligibility(self):
        choices = self.table("m11_pr_origin_local_choices")
        excluded = choices[~choices["eligible"]]
        self.assertTrue(excluded["exclusion_reason"].str.contains("insufficient history").all())
        self.assertTrue(excluded["tfr_choice"].isna().all() | excluded["shape_choice"].isna().all()
                        | excluded["transform_choice"].isna().all())
        eligible = choices[choices["eligible"]]
        self.assertTrue(eligible[["tfr_choice", "shape_choice", "transform_choice"]].notna().all(axis=None))
        self.assertEqual(eligible["origin"].min(), 1976)

    def test_chapter_reports_corrections(self):
        text = (Path(__file__).resolve().parents[1] / "docs" / "m11_fertility_forecasts.md").read_text(encoding="utf-8")
        self.assertIn(REQUIRED_SENTENCE, text)
        self.assertIn("5.8%", text)
        self.assertIn("Monte Carlo-sensitive", text)
        self.assertIn("not pre-specified", text)
        self.assertNotIn("reasonably calibrated at short horizons", text)


if __name__ == "__main__":
    unittest.main()
