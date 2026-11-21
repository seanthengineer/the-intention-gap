"""Tests for the out-of-period validation, using synthetic data.

Run with:  python -m unittest -v
"""

import unittest

import numpy as np
import pandas as pd

from analysis import analyze_calibration as ac
from analysis import build_outcomes as bo
from analysis import population_validity as pv
from analysis import temporal_validation as tv
from analysis.nlsy97 import (
    BIRTH_MONTH, BIRTH_YEAR, CHILD_BIRTH_MONTH, HOUSEHOLD_ID, INTERVIEW_MONTH, RESPONDENT_ID,
    SEX,
    cmonth_from_date,
)
from tests.test_population_validity import synthetic_frame

BASELINE = cmonth_from_date(2016, 1)
AFTER = {2021: cmonth_from_date(2021, 11), 2023: cmonth_from_date(2023, 11)}
SLOTS = {2015: 12, 2021: 13, 2023: 13}


def roster(year, *births):
    return list(births) + [-4] * (SLOTS[year] - len(births))


def later_outcome(r2015, r2021, r2023, months=AFTER):
    return bo.classify_outcome(BASELINE, {2015: r2015, 2021: r2021, 2023: r2023},
                               {2015: BASELINE, **months}, bo.PRIMARY_RULES,
                               tv.LATER_BASELINE, tv.LATER_FOLLOWUP)


class LaterOutcomeTests(unittest.TestCase):
    def test_birth_inside_the_window_is_positive(self):
        birth = BASELINE + 30
        result = later_outcome(roster(2015), roster(2021, birth), roster(2023, birth))
        self.assertEqual(result.outcome, 1)
        self.assertEqual(result.rounds_used, (2021, 2023))

    def test_no_new_birth_after_the_anniversary_is_negative(self):
        earlier = BASELINE - 40
        result = later_outcome(roster(2015, earlier), roster(2021, earlier), roster(2023, earlier))
        self.assertEqual(result.outcome, 0)

    def test_interview_before_the_anniversary_cannot_establish_no_birth(self):
        early = {2021: BASELINE + 59, 2023: -5}
        result = later_outcome(roster(2015), roster(2021), [-5] * SLOTS[2023], early)
        self.assertIsNone(result.outcome)
        self.assertEqual(result.unknown_reason, bo.INCOMPLETE_FOLLOWUP)

    def test_disagreeing_rounds_stay_unknown(self):
        result = later_outcome(roster(2015), roster(2021, BASELINE + 30), roster(2023))
        self.assertIsNone(result.outcome)
        self.assertTrue(result.flags["flag_followup_window_records_differ"])


def codebook(*rows):
    return pd.DataFrame(rows, columns=["reference_number", "question_name", "survey_year"])


class LocateItemTests(unittest.TestCase):
    def full_codebook(self):
        rows = [("X0000001", "YFER-4861", "2009"), ("X0000002", "YFER-4861", "2015"),
                ("X0000003", "CV_MARSTAT_COLLAPSED", "2015"),
                ("X0000004", "SAMPLING_WEIGHT_CC", "2015"),
                ("X0000005", "CV_INTERVIEW_CMONTH", "2021"),
                ("X0000006", "CV_INTERVIEW_CMONTH", "2023"),
                ("R1489700", "VSTRAT", "1997"), ("R1489800", "VPSU", "1997"),
                ("X0000102", "CV_CHILD_BIRTH_MONTH.02", "2021"),
                ("X0000101", "CV_CHILD_BIRTH_MONTH.01", "2021"),
                ("X0000201", "CV_CHILD_BIRTH_MONTH.01", "2023")]
        return codebook(*rows)

    def test_items_are_found_by_name_and_year(self):
        found, missing = tv.locate_items(self.full_codebook())
        self.assertEqual(missing, [])
        self.assertEqual(found["expectation"], "X0000002")
        self.assertEqual(found["roster_2021"], ["X0000101", "X0000102"])

    def test_missing_or_mismatched_items_are_reported(self):
        table = self.full_codebook()
        table = table[table["survey_year"] != "2023"]
        table.loc[table["question_name"] == "VSTRAT", "reference_number"] = "R0000000"
        _, missing = tv.locate_items(table)
        self.assertIn("CV_INTERVIEW_CMONTH (2023)", missing)
        self.assertIn("CV_CHILD_BIRTH_MONTH.01 onward (2023)", missing)
        self.assertTrue(any(m.startswith("VSTRAT is R0000000") for m in missing))

    def test_grade_item_is_required_only_when_named(self):
        found, missing = tv.locate_items(self.full_codebook(), ("CV_HGC_EXAMPLE", "2015"))
        self.assertNotIn("grade", found)
        self.assertIn("CV_HGC_EXAMPLE (2015)", missing)


ITEMS = {"expectation": "E15", "marital_status": "M15", "weight": "W15",
         "interview_2021": "I21", "interview_2023": "I23",
         "roster_2021": [f"R21_{k}" for k in range(SLOTS[2021])],
         "roster_2023": [f"R23_{k}" for k in range(SLOTS[2023])]}


def later_frame():
    """Four women and one man; one woman gives no expectation answer."""
    birth = BASELINE + 24
    rows = []
    for k, (sex, answer, born) in enumerate([(2, 80, True), (2, 0, False), (2, -2, False),
                                             (1, 50, False), (2, 50, False)]):
        r21 = roster(2021, BASELINE - 50, birth) if born else roster(2021, BASELINE - 50)
        row = {RESPONDENT_ID: 100 + k, SEX: sex, HOUSEHOLD_ID: k, BIRTH_YEAR: 1983,
               BIRTH_MONTH: 6,
               INTERVIEW_MONTH[2015]: BASELINE, "E15": answer, "M15": 1, "W15": 123456,
               "I21": AFTER[2021], "I23": AFTER[2023] if k != 4 else -5}
        row.update(zip(CHILD_BIRTH_MONTH[2015], roster(2015, BASELINE - 50)))
        row.update(zip(ITEMS["roster_2021"], r21))
        row.update(zip(ITEMS["roster_2023"], r21 if k != 4 else [-5] * SLOTS[2023]))
        rows.append(row)
    return pd.DataFrame(rows)


class LaterCohortTests(unittest.TestCase):
    def test_eligibility_excludes_men_and_item_nonresponse(self):
        status = tv.later_eligibility(later_frame(), "E15")
        self.assertEqual(list(status), ["eligible", "eligible", "expectation item nonresponse",
                                        "not female", "eligible"])

    def test_features_are_measured_at_the_later_baseline(self):
        cohort = tv.later_cohort(later_frame(), ITEMS)
        self.assertEqual(len(cohort), 3)
        self.assertEqual(list(cohort["outcome"]), [1, 0, 0])
        self.assertEqual(list(cohort["respondent_id"]), [100, 101, 104])
        self.assertTrue((cohort["parity_at_baseline"] == 1).all())
        self.assertTrue((cohort["marital_status_2009"] == 1).all())
        expected_age = round((BASELINE - cmonth_from_date(1983, 6)) / 12, 2)
        self.assertTrue((cohort["age_at_baseline"] == expected_age).all())
        self.assertTrue(cohort["highest_grade_2009"].isna().all())
        self.assertAlmostEqual(cohort["sampling_weight_2015"].iloc[0], 1234.56)


def fitted_models(training_households=frozenset({0, 1, 2})):
    train = synthetic_frame(n=300, seed=3).dropna(subset=["outcome"])
    y = train["outcome"].astype(int)
    return tv.FrozenModels(
        prevalence=float(y.mean()),
        model_c=ac.stated_only_model().fit(train[[ac.STATED]], y),
        model_d=ac.covariate_model().fit(train[ac.MODEL_D_FEATURES], y),
        training_households=frozenset(training_households),
        test_households=frozenset({3}), cohort_households=frozenset({0, 1, 2, 3, 4}))


class FrozenModelTests(unittest.TestCase):
    def test_prediction_applies_without_refitting(self):
        models = fitted_models()
        before = tv.model_parameters(models)
        later = synthetic_frame(n=80, seed=11).assign(age_at_baseline=33.0)
        predictions = tv.predict(models, later, include_d=True)
        self.assertEqual(tv.parameter_differences(tv.model_parameters(models), before), [])
        np.testing.assert_allclose(predictions["C"],
                                   models.model_c.predict_proba(later[[ac.STATED]])[:, 1])
        self.assertTrue((predictions["A"] == models.prevalence).all())
        np.testing.assert_array_equal(predictions["B"], later[ac.STATED])

    def test_fingerprint_detects_a_changed_coefficient(self):
        stored = tv.model_parameters(fitted_models())
        changed = tv.model_parameters(fitted_models())
        changed["C"]["coef"] = [changed["C"]["coef"][0] + 1e-4]
        self.assertEqual(tv.parameter_differences(changed, stored), ["C.coef"])

    def test_setting_b_drops_training_households(self):
        models = fitted_models(training_households={0, 1})
        later = pd.DataFrame({"household_id": [0, 1, 2, 3], "outcome": [1, 0, 1, pd.NA]},
                             dtype="Int64")
        groups = tv.settings(later, models)
        a, b = groups.values()
        self.assertEqual(list(a["household_id"]), [0, 1, 2])
        self.assertEqual(list(b["household_id"]), [2])
        self.assertEqual(list(tv.overlap_with_2009(later, models)),
                         ["2009 training household", "2009 training household",
                          "2009 cohort, unlabelled household", "2009 test household"])


class EvaluationTests(unittest.TestCase):
    def test_contrasts_are_paired_brier_differences(self):
        sample = synthetic_frame(n=300, seed=5).dropna(subset=["outcome"])
        sample = sample.assign(outcome=sample["outcome"].astype(int))
        predictions = tv.predict(fitted_models(), sample, include_d=False)
        metrics, contrasts = tv.evaluate(sample, predictions, n_bootstrap=50, seed=1)
        brier = metrics.set_index("model")["brier"]
        row = contrasts.set_index("comparison").loc["C - B"]
        self.assertAlmostEqual(row["brier_difference"], brier["C"] - brier["B"])
        self.assertLessEqual(row["ci"][0], row["ci"][1])
        self.assertNotIn("D - C", contrasts["comparison"].tolist())

    def test_interpretation_rules_use_the_fixed_thresholds(self):
        metrics = pd.DataFrame([{"model": "C", "auc": 0.65, "auc_ci": (0.6, 0.7),
                                 "mean_error": 0.06}])
        contrasts = pd.DataFrame({"comparison": ["C - B", "C - A"],
                                  "ci": [(-0.05, -0.01), (-0.01, 0.002)]})
        rules = list(tv.interpret(metrics, contrasts, reference_auc=0.708).values())
        self.assertEqual(rules, [True, True, True, True, False])


class UnknownOutcomeTests(unittest.TestCase):
    def frame(self):
        later = synthetic_frame(n=300, seed=9)
        return later.assign(outcome=later["outcome"].astype("Int64").where(
            later["outcome"].notna(), pd.NA))

    def test_bounds_bracket_every_filled_scenario(self):
        table = tv.unknown_outcome_sensitivity(self.frame(), fitted_models()).set_index("scenario")
        low = table.loc["Most favourable to C (each unknown chosen)", "c_minus_b"]
        high = table.loc["Least favourable to C (each unknown chosen)", "c_minus_b"]
        filled = table[table.index != "Complete cases (unknowns excluded)"]["c_minus_b"]
        self.assertTrue(((filled >= low - 1e-12) & (filled <= high + 1e-12)).all())

    def test_complete_cases_match_a_direct_calculation(self):
        later, models = self.frame(), fitted_models()
        known = later[later["outcome"].notna()]
        y = known["outcome"].to_numpy(dtype=float)
        p_b = known[ac.STATED].to_numpy()
        p_c = models.model_c.predict_proba(known[[ac.STATED]])[:, 1]
        row = tv.unknown_outcome_sensitivity(later, models).iloc[0]
        self.assertEqual(row["n"], len(known))
        self.assertAlmostEqual(row["c_minus_b"], np.mean((p_c - y) ** 2) - np.mean((p_b - y) ** 2))

    def test_parenthood_groups_partition_women_with_a_known_roster(self):
        frame = pd.DataFrame({"parity_at_baseline": pd.array([0, 1, 3, pd.NA], dtype="Int64")})
        masks = [select(frame).fillna(False).to_numpy(dtype=bool)
                 for select in tv.PARENTHOOD_2015.values()]
        self.assertEqual([m.tolist() for m in masks],
                         [[True, False, False, False], [False, True, True, False]])


class ResponseModelTests(unittest.TestCase):
    def test_cross_validated_auc_is_reported_per_repeat(self):
        result = pv.cross_validated_response_auc(synthetic_frame(), "outcome", seeds=(1, 2),
                                                 n_splits=3)
        self.assertEqual(result["repeats"], 2)
        self.assertTrue(0 <= result["min"] <= result["mean"] <= result["max"] <= 1)
        # In the synthetic frame, age alone identifies unknown outcomes.
        self.assertGreater(result["mean"], 0.9)


if __name__ == "__main__":
    unittest.main()
