"""M11 data-acquisition and feasibility tests.

Unit tests use small synthetic HFD files and fixed-width birth records, with no
network access. Integration tests validate the saved sources and the public
M11 tables; they skip when the raw data are absent.
"""

import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import hfd
from analysis import m11_feasibility as feas
from analysis import m11_sources as src

HFD_PRESENT = (src.HFD_DIR / "USAasfrRR.txt").exists()
PUF_PRESENT = src.puf_output(2025).exists() and src.puf_output(2024).exists()
CENSUS_PRESENT = (src.NP_DIR / "np2023_a5.csv").exists() and src.POPEST_FILES[2025].exists()
NCHS_PRESENT = (src.NCHS_DIR / "db571.txt").exists()
ALL_PRESENT = HFD_PRESENT and PUF_PRESENT and CENSUS_PRESENT and NCHS_PRESENT


def write_hfd(folder: Path, name: str, columns: str, rows: list[str]) -> None:
    text = "\n".join([f"United States, synthetic {name}", "Last modified: 27/06/2026", columns, *rows])
    (folder / f"{name}.txt").write_text(text + "\n", encoding="utf-8")


class HfdParserTests(unittest.TestCase):
    def test_open_ages_missing_cells_and_open_cohorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_hfd(folder, "USAasfrVV", "Year    ARDY   Cohort        ASFR",
                      ["2024     12-   2012-     0.00010", "2024     13    2011      0.00050",
                       "2024     55+   1969+     .", ])
            table = hfd.read_hfd("USAasfrVV", folder)
            self.assertEqual(table["ARDY"].tolist(), [12, 13, 55])
            self.assertEqual(table["age_open"].tolist(), ["lower", "", "upper"])
            self.assertEqual(table["cohort_open"].tolist(), ["-", "", "+"])
            self.assertEqual(table["Cohort"].tolist(), [2012, 2011, 1969])
            self.assertTrue(np.isnan(table["ASFR"].iloc[2]))
            self.assertEqual(table.attrs["last_modified"], "27/06/2026")

    def test_ragged_rows_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_hfd(Path(tmp), "USAtfrRR", "Year       TFR     TFR40", ["2024     1.593"])
            with self.assertRaises(ValueError):
                hfd.read_hfd("USAtfrRR", Path(tmp))

    def test_cohort_frame_keeps_open_ages_when_exposure_labels_differ(self):
        # HFD exposure files print "12"/"55" where births and rates print "12-"/"55+"
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_hfd(folder, "USAbirthsVH", "Cohort  Age   Total", ["2000  12-  10.00", "2000  13  20.00", "1960  55+  1.00"])
            write_hfd(folder, "USAexposVH", "Cohort  Age   Exposure",
                      ["2000  12  1000.00", "2000  13  1000.00", "1960  55  500.00"])
            write_hfd(folder, "USAasfrVH", "Cohort  Age   ASFR", ["2000  12-  0.01000", "2000  13  0.02000", "1960  55+  0.00200"])
            frame = hfd.cohort_frame(folder)
            self.assertEqual(len(frame), 3)
            self.assertEqual(sorted(frame["age_open"]), ["", "lower", "upper"])
            self.assertTrue(np.allclose(frame["Total"] / frame["Exposure"], frame["ASFR"]))

    def test_cumulative_follows_hfd_convention(self):
        # CCFR at exact age x excludes births at age x
        vh = pd.DataFrame({"Cohort": [2000, 2000, 2000], "Age": [15, 16, 17], "ASFR": [0.01, 0.02, 0.03]})
        cumulative = hfd.cumulative_by_exact_age(vh).set_index("Age")["cumulative"]
        self.assertAlmostEqual(cumulative[16], 0.01)
        self.assertAlmostEqual(cumulative[18], 0.06)
        self.assertNotIn(15, cumulative.index)


class PublicUseTests(unittest.TestCase):
    @staticmethod
    def record(year="2025", month="07", age="27", restatus="1", order="2", imputed=" "):
        chars = [" "] * 1345
        for (start, end), value in zip(src.PUF_FIELDS.values(), (year, month, imputed, age, restatus, order)):
            chars[start - 1:end] = list(value.rjust(end - start + 1))
        return "".join(chars).encode("ascii") + b"\r\n"

    def test_stream_tabulation_counts_keys_and_lengths(self):
        data = (self.record() * 3) + self.record(age="12", restatus="4") + self.record(order="9")
        counts, lengths = src.tabulate_puf_stream(io.BytesIO(data))
        self.assertEqual(sum(counts.values()), 5)
        self.assertEqual(counts[("2025", "07", "", "27", "1", "2")], 3)
        self.assertEqual(counts[("2025", "07", "", "12", "4", "2")], 1)
        self.assertEqual(dict(lengths), {1345: 5})


class RateConventionTests(unittest.TestCase):
    def setUp(self):
        self.female = pd.Series(1000.0, index=range(10, 56))
        self.births = pd.Series(0.0, index=range(12, 51))

    def test_nchs_open_group_conventions(self):
        self.births[12] = 5          # births at 10-12 count towards 10-14
        self.births[50] = 10         # births at 50-54 count towards 45-49
        rates = src.nchs_style_rates(self.births, self.female)
        self.assertAlmostEqual(rates["10-14"], 1000 * 5 / 5000)
        self.assertAlmostEqual(rates["45-49"], 1000 * 10 / 5000)
        self.assertAlmostEqual(rates["tfr"], 5 * (rates["10-14"] + rates["45-49"]))

    def test_single_year_rates_use_matching_age(self):
        self.births[30] = 100
        rates = src.single_year_rates(self.births, self.female)
        self.assertAlmostEqual(rates[30], 0.1)
        self.assertEqual(list(rates.index), list(range(12, 51)))


class DesignTests(unittest.TestCase):
    def test_backtest_origin_counts(self):
        design = feas.backtest_design(last_year=2024, min_train=20).set_index(["training_start", "horizon"])
        row = design.loc[(1933, 15)]
        self.assertEqual((row["first_origin"], row["last_origin"], row["origins"]), (1952, 2009, 58))
        self.assertEqual(row["non_overlapping_windows"], 4)          # origins 1952, 1967, 1982, 1997
        self.assertEqual(design.loc[(1990, 15), "origins"], 1)
        self.assertEqual(design.loc[(1977, 10), "non_overlapping_windows"], 2)

    def test_decision_rule(self):
        status = pd.DataFrame({"status": ["PASS", "PASS"]})
        self.assertEqual(feas.decision(status), "READY")
        self.assertEqual(feas.decision(status.assign(status=["PASS", "WARN"])), "CONDITIONAL")
        self.assertEqual(feas.decision(status.assign(status=["WARN", "FAIL"])), "BLOCKED")


@unittest.skipUnless(ALL_PRESENT, "M11 raw data not present")
class SavedDataTests(unittest.TestCase):
    def test_hfd_internal_checks_have_no_failure(self):
        results = hfd.validate()
        self.assertFalse([r for r in results if r["status"] == "FAIL"], results)

    def test_hfd_period_coverage(self):
        missing = hfd.period_missing_by_year()
        self.assertEqual((missing["year"].min(), missing["year"].max(), len(missing)), (1933, 2024, 92))
        self.assertEqual(int(missing[["missing_asfr", "missing_births", "missing_exposure"]].sum().sum()), 0)

    def test_public_use_totals_equal_official_counts(self):
        official = src.parse_db571()["births"]
        for year in (2024, 2025):
            self.assertEqual(int(src.puf_births_by_age(year).sum()), official[year]["births"])

    def test_final_2025_rates_reproduce_from_vintage_2025(self):
        rates = src.nchs_style_rates(src.puf_births_by_age(2025),
                                     src.load_popest(2025).query("year == 2025").set_index("age")["population"])
        for group, value in src.parse_db571()["rates"].items():
            self.assertAlmostEqual(round(rates[group], 1), value[2025], places=9, msg=group)

    def test_census_projection_files_consistent(self):
        self.assertTrue(all(check["ok"] for check in src.np_checks()))

    def test_nvsr_tfr_convention(self):
        for report in src.NVSR_REPORTS:
            table = src.parse_nvsr_table2(report)
            self.assertEqual(table["year"].min(), 2010)
            self.assertLess((5 * table[feas.NCHS_GROUPS].sum(axis=1) - table["tfr"]).abs().max(), 1e-6)

    def test_observability_matrix(self):
        matrix = hfd.cohort_observability()
        self.assertEqual(matrix["cohort"].tolist(), list(range(1995, 2013)))
        self.assertTrue((matrix["age_reached_in_2040"] == 2040 - matrix["cohort"]).all())
        self.assertEqual(matrix.set_index("cohort").loc[2012, "hfd_complete_ages"], "none")


@unittest.skipUnless((feas.PUBLIC_DIR / "m11_source_status.csv").exists(), "M11 public tables not built")
class PublicTableTests(unittest.TestCase):
    def test_statuses_and_decision(self):
        status = pd.read_csv(feas.PUBLIC_DIR / "m11_source_status.csv")
        self.assertEqual(set(status["status"]) - {"PASS", "WARN", "FAIL"}, set())
        self.assertNotIn("FAIL", set(status["status"]))
        self.assertEqual(feas.decision(status), "CONDITIONAL")

    def test_public_tables_hold_no_record_level_data(self):
        for path in feas.PUBLIC_DIR.glob("m11_*.csv"):
            table = pd.read_csv(path)
            self.assertLess(len(table), 5000, path.name)
            self.assertFalse({"restatus", "lbo_rec", "age_imputed"} & set(table.columns), path.name)


if __name__ == "__main__":
    unittest.main()
