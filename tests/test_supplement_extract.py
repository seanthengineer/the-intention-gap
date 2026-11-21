"""Tests for joining a supplementary extract, using synthetic data.

Run with:  python -m unittest -v
"""

import unittest

import pandas as pd

from analysis import supplement_extract as se
from analysis.nlsy97 import RESPONDENT_ID


def frames():
    original = pd.DataFrame({RESPONDENT_ID: [1, 2, 3], "T4356900": [0, 50, 100]})
    supplement = pd.DataFrame({RESPONDENT_ID: [3, 1, 2], "T4531300": [1, -4, -5]})
    return original, supplement


class JoinTests(unittest.TestCase):
    def test_join_is_one_to_one_on_pubid(self):
        original, supplement = frames()
        joined = se.join_extracts(original, supplement)
        values = joined.set_index(RESPONDENT_ID)["T4531300"].to_dict()
        self.assertEqual(values, {1: -4, 2: -5, 3: 1})

    def test_duplicate_ids_rejected(self):
        original, supplement = frames()
        supplement.loc[0, RESPONDENT_ID] = 1
        with self.assertRaises(ValueError):
            se.join_extracts(original, supplement)

    def test_different_respondents_rejected(self):
        original, supplement = frames()
        with self.assertRaises(ValueError):
            se.join_extracts(original, supplement.iloc[:2])

    def test_conflicting_shared_column_rejected(self):
        original, supplement = frames()
        supplement["T4356900"] = [100, 0, 51]
        with self.assertRaises(ValueError):
            se.join_extracts(original, supplement)

    def test_identical_shared_column_kept_once(self):
        original, supplement = frames()
        supplement["T4356900"] = [100, 0, 50]
        joined = se.join_extracts(original, supplement)
        self.assertEqual(list(joined.columns).count("T4356900"), 1)


class AvailabilityTests(unittest.TestCase):
    def test_codes_are_counted_not_recoded(self):
        frame = pd.DataFrame({"x": [0, 1, -4, -4, -5, -3, -1, -2, -7]})
        counts = se.code_availability(frame, ["x"]).loc["x"]
        self.assertEqual(counts["substantive (>= 0)"], 2)
        self.assertEqual(counts["-4 valid skip"], 2)
        self.assertEqual(counts["other negative"], 1)
        self.assertEqual(counts.sum(), len(frame))


class ManifestTests(unittest.TestCase):
    def test_manifest_has_no_invented_reference_numbers(self):
        manifest = se.load_manifest()
        unverified = manifest["status"].str.startswith("reference number not yet located")
        self.assertTrue(manifest.loc[unverified, "reference_number"].isna().all())
        located = manifest.loc[~unverified, "reference_number"]
        self.assertTrue(located.str.fullmatch(r"[A-Z]\d{7}").all())

    def test_manifest_lists_original_extract(self):
        manifest = se.load_manifest()
        self.assertEqual((manifest["extract"] == "v2").sum(), 48)

    def test_variable_map_matches_manifest_names(self):
        manifest = se.load_manifest().dropna(subset=["reference_number"])
        names = manifest.drop_duplicates("reference_number").set_index("reference_number")
        expected = {se.EVER_PREGNANT: ("YSAQ2-314", "2009"),
                    se.PREGNANT_SINCE_LAST: ("YSAQ2-314C", "2009"),
                    se.PREGNANT_NOW: ("YSAQ2-315", "2009"),
                    se.WEEKS_PREGNANT: ("YSAQ2-316", "2009"),
                    se.LAST_PERIOD_MONTH: ("YSAQ2-317", "2009")}
        for year, column in se.SUPPLEMENT_INTERVIEW_MONTH.items():
            expected[column] = ("CV_INTERVIEW_CMONTH", str(year))
        for year, slots in se.SUPPLEMENT_CHILD_BIRTH_MONTH.items():
            for k, column in enumerate(slots, start=1):
                expected[column] = (f"CV_CHILD_BIRTH_MONTH.{k:02d}", str(year))
        for year, (resident, nonresident) in se.BIO_CHILD_COUNTS.items():
            expected[resident] = ("CV_BIO_CHILD_HH", str(year))
            expected[nonresident] = ("CV_BIO_CHILD_NR", str(year))
        for ref, (name, year) in expected.items():
            self.assertEqual((names.loc[ref, "question_name"], names.loc[ref, "survey_year"]),
                             (name, year), ref)
        self.assertEqual(names.loc[se.TOTAL_BIO_CHILD, "question_name"], "CVC_TTL_BIO_CHILD")

    def test_check_flags_missing_and_misnamed_variables(self):
        manifest = se.load_manifest()
        codebook = pd.DataFrame({"reference_number": ["T4531300"],
                                 "question_name": ["YSAQ2-999"], "survey_year": ["2009"]})
        problems = se.check_supplement([RESPONDENT_ID, "T4531300"], codebook, manifest)
        self.assertTrue(any("T4531100" in p for p in problems))
        self.assertTrue(any("YSAQ2-999" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
