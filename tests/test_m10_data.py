"""M10 acquisition, parsing and panel tests.

Unit tests use synthetic Census responses and a synthetic CDC WONDER export,
with no network access. Integration tests skip when the saved data are absent.
"""

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from analysis import acs_housing as acs
from analysis import cdc_natality as cdc
from analysis import m10_panel as panel

FAKE_KEY = "test-key-not-real-0123456789"


def acs_rows(states=("01", "02", "72"), total=1000, broken=None) -> list[list[str]]:
    header = ["NAME"] + [f"{c}{s}" for c in acs.CATEGORIES for s in ("E", "EA", "M", "MA")]
    header += ["state"]
    counts = [100, 100, 100, 100, 100, 100, 100, 100, 50, 50]  # 002-011, sums to 900
    rows = [header]
    for fips in states:
        values = [total if total is not None else 900, *counts]
        row = [f"State {fips}"]
        for i, value in enumerate(values):
            row += [str(value), None, str(10 + i), None]
        row += [fips]
        rows.append(row)
    if broken:
        broken(rows)
    return rows


def acs_labels() -> dict:
    variables = {f"{acs.TABLE}_{code}E": {"label": f"Estimate!!Total:!!{label}",
                                         "concept": "Gross Rent as a Percentage of Household "
                                                    "Income in the Past 12 Months"}
                 for code, label in acs.EXPECTED_LABELS.items() if code != "001"}
    variables[f"{acs.TABLE}_001E"] = {"label": "Estimate!!Total:", "concept": "Gross Rent"}
    return variables


class AcsTests(unittest.TestCase):
    def frame(self, rows):
        frame = pd.DataFrame(rows[1:], columns=rows[0])
        frame.insert(0, "year", 2019)
        return frame

    def test_labels_and_identity_pass(self):
        report = acs.validate_year(self.frame(acs_rows(total=900)), acs_labels())
        self.assertEqual(report["label_problems"], [])
        self.assertEqual(report["identity_failures"], 0)
        self.assertEqual(report["extra_geographies"], ["72"])
        self.assertEqual(len(report["missing_states"]), len(acs.STATE_FIPS) - 2)

    def test_identity_failure_and_codes_detected(self):
        def poison(rows):
            rows[1][rows[0].index("B25070_005E")] = "-666666666"
        report = acs.validate_year(self.frame(acs_rows(total=900, broken=poison)), acs_labels())
        self.assertEqual(report["negative_or_code_values"], 1)
        self.assertEqual(report["identity_failures"], 1)

    def test_label_change_detected(self):
        labels = acs_labels()
        labels["B25070_007E"]["label"] = "Estimate!!Total:!!30.0 percent or more"
        self.assertTrue(acs.check_labels(labels))

    def test_duplicate_state_detected(self):
        report = acs.validate_year(self.frame(acs_rows(("01", "01"), total=900)), acs_labels())
        self.assertEqual(report["duplicate_states"], ["01"])

    def test_derived_measures(self):
        frame = self.frame(acs_rows(("01",), total=900))
        out = acs.derive(frame)
        row = out.iloc[0]
        self.assertEqual(row["households_computed"], 850)
        self.assertAlmostEqual(row["burden30_pct"], 100 * 350 / 850)
        self.assertAlmostEqual(row["severe50_pct"], 100 * 50 / 850)
        self.assertAlmostEqual(row["not_computed_pct"], 100 * 50 / 900)

    def test_census_moe_formulas(self):
        moe, ratio = acs.moe_proportion(pd.Series([100.0]), pd.Series([10.0]),
                                        pd.Series([1000.0]), pd.Series([20.0]))
        self.assertAlmostEqual(moe.iloc[0], np.sqrt(100 - 0.01 * 400) / 1000)
        self.assertFalse(ratio.iloc[0])
        moe, ratio = acs.moe_proportion(pd.Series([500.0]), pd.Series([1.0]),
                                        pd.Series([1000.0]), pd.Series([100.0]))
        self.assertTrue(ratio.iloc[0])
        self.assertAlmostEqual(moe.iloc[0], np.sqrt(1 + 0.25 * 10000) / 1000)
        self.assertAlmostEqual(acs.moe_sum(pd.DataFrame({"a": [3.0], "b": [4.0]})).iloc[0], 5.0)

    def test_fetch_requires_key(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(acs, "_request") as request:
            with self.assertRaises(SystemExit):
                acs.fetch([2019])
            request.assert_not_called()

    def test_fetch_never_writes_the_key(self):
        def fake(url, params, key):
            body = json.dumps(acs_rows()) if "groups" not in url else json.dumps(
                {"variables": acs_labels()})
            return 200, body.encode()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"CENSUS_API_KEY": FAKE_KEY}), \
                mock.patch.object(acs, "_request", side_effect=fake), \
                mock.patch.object(acs, "RAW_DIR", Path(tmp)), \
                mock.patch.object(acs, "PROJECT_ROOT", Path(tmp)), \
                mock.patch.object(acs, "PROVENANCE_PATH", Path(tmp) / "provenance.json"):
            provenance = acs.fetch([2019])
            for path in Path(tmp).iterdir():
                self.assertNotIn(FAKE_KEY.encode(), path.read_bytes(), path.name)
            self.assertNotIn(FAKE_KEY, json.dumps(provenance))
            self.assertIn("sha256", provenance["years"]["2019"]["data"])

    def test_http_error_body_is_scrubbed(self):
        def fail(url, params, key):
            return 400, f"bad key {FAKE_KEY}".encode()
        with mock.patch.dict(os.environ, {"CENSUS_API_KEY": FAKE_KEY}), \
                mock.patch.object(acs, "_request", side_effect=fail), \
                tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(acs, "RAW_DIR", Path(tmp)):
            with self.assertRaises(SystemExit) as raised:
                acs.fetch([2019])
            self.assertNotIn(FAKE_KEY, str(raised.exception))


EXPORT_HEADER = "\t".join(f'"{c}"' if c not in ("Births", "Female Population",
                                                "Fertility Rate") else c
                          for c in cdc.EXPECTED_HEADER)
FOOTER = ['"---"', '"Dataset: Natality, 2007-2024"', '"Group By: Year; State; Age of Mother 9"',
          '"Show Suppressed: False"', '"Calculate Rates Per: 1,000"', '"---"', "Caveats:",
          '"1. \'Not Available\' appears when the denominator population is not available."']


def export_text(rows: list[tuple]) -> str:
    lines = [EXPORT_HEADER]
    for year, fips, age, births, population in rows:
        rate = (f"{1000 * births / population:.3f}" if isinstance(population, int)
                else population)
        label = f"{age} years" if age else ""
        lines.append("\t".join(["", f'"{year}"', f'"{year}"', f'"State {fips}"', f'"{fips}"',
                                f'"{label}"', f'"{age}"', str(births), str(population), rate]))
    return "\n".join(lines + FOOTER) + "\n"


class CdcTests(unittest.TestCase):
    def write(self, text: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".xls", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_parse_and_recalculate(self):
        path = self.write(export_text([(2019, "01", "20-24", 100, 1000),
                                       (2019, "01", "25-29", 200, 2000),
                                       (2021, "01", "20-24", 90, "Not Available")]))
        self.assertEqual(cdc.file_format(path), "tab-delimited text")
        frame, metadata = cdc.parse_export(path)
        detail, totals = cdc.tidy(frame)
        report = cdc.validate(detail, totals, metadata)
        self.assertEqual(report["rates_recalculated"], 2)
        self.assertEqual(report["rate_mismatches"], 0)
        self.assertEqual(report["value_status"]["rate_exported"].get("Not Available"), 1)
        self.assertEqual(metadata["fields"]["Calculate Rates Per"], "1,000")
        self.assertGreater(len(report["missing_combinations"]), 0)

    def test_duplicates_suppression_and_bad_rates_detected(self):
        text = export_text([(2019, "01", "20-24", 100, 1000), (2019, "01", "20-24", 100, 1000),
                            (2019, "02", "25-29", 5, "Suppressed")])
        text = text.replace("\t100\t1000\t100.000", "\t100\t1000\t150.000", 1)
        frame, metadata = cdc.parse_export(self.write(text))
        detail, totals = cdc.tidy(frame)
        report = cdc.validate(detail, totals, metadata)
        self.assertEqual(report["duplicate_keys"], 1)
        self.assertEqual(report["rate_mismatches"], 1)
        self.assertEqual(report["suppressed_cells"], 2)

    def test_state_of_residence_header_is_accepted(self):
        text = export_text([(2019, "01", "20-24", 100, 1000)])
        text = text.replace('"State"', '"State of Residence"', 1).replace(
            '"State Code"', '"State of Residence Code"', 1)
        frame, metadata = cdc.parse_export(self.write(text))
        self.assertEqual(metadata["state_header"], "State of Residence")
        detail, _ = cdc.tidy(frame)
        self.assertEqual(detail.loc[0, "state_fips"], "01")

    def test_reconcile_detects_disagreement(self):
        rows = [(2019, "01", "20-24", 100, 1000), (2021, "01", "20-24", 90, "Not Available")]
        original, _ = cdc.tidy(cdc.parse_export(self.write(export_text(rows)))[0])
        expanded_rows = [(2019, "01", "20-24", 100, 1000), (2021, "01", "20-24", 90, 900)]
        expanded, _ = cdc.tidy(cdc.parse_export(self.write(export_text(expanded_rows)))[0])
        agreed = cdc.reconcile(original, expanded)
        self.assertTrue(agreed["agree"])
        self.assertEqual(agreed["expanded_fills_original_gaps"], 1)
        changed = expanded.copy()
        changed.loc[changed["year"].eq(2019), "births"] = 101
        disagreed = cdc.reconcile(original, changed)
        self.assertFalse(disagreed["agree"])
        self.assertEqual(disagreed["comparisons"]["births"]["disagreements"], 1)

    def test_combine_takes_each_year_from_one_source(self):
        frames = {name: pd.DataFrame({"year": list(range(2014, 2025)), "state_fips": "01",
                                      "age_group": "20-24", "births": 1})
                  for name in ("original", "expanded")}
        frames["expanded"] = frames["expanded"][frames["expanded"]["year"].ge(2016)]
        combined = cdc.combine(frames)
        self.assertEqual(len(combined), 11)
        self.assertEqual(set(combined.loc[combined["year"].lt(2016), "source"]), {"original"})
        self.assertEqual(set(combined.loc[combined["year"].ge(2016), "source"]), {"expanded"})

    def test_total_rows_never_enter_detail(self):
        text = export_text([(2019, "01", "20-24", 100, 1000), (2019, "01", "25-29", 50, 500)])
        text = text.replace(EXPORT_HEADER + "\n", EXPORT_HEADER + "\n" + "\t".join(
            ['"Total"', '"2019"', '"2019"', '"State 01"', '"01"', '""', '""', "150", "1500",
             "100.000"]) + "\n", 1)
        detail, totals = cdc.tidy(cdc.parse_export(self.write(text))[0])
        self.assertEqual(len(detail), 2)
        self.assertEqual(len(totals), 1)

    def test_unexpected_header_and_missing_file(self):
        with self.assertRaises(ValueError):
            cdc.parse_export(self.write("a\tb\n1\t2\n"))
        with self.assertRaises(FileNotFoundError):
            cdc.parse_export(Path("missing.xls"))

    def test_nvsr_table_parsers(self):
        text = ("Table 2. Birth rates, by age of mother: United States, 2010-2023\n"
                "2023 1,621.0   0.2  13.1  5.5   24.6  57.7   91.0    94.3  54.3  12.5  1.1\n"
                "Non-Hispanic\nTable 3. x\n"
                "Table 8. Birth rates, by age of mother: United States, each state\n"
                "United States2  10.7  54.5  1,621.0  0.2  13.1  5.5  24.6  57.7  91.0  94.3\n"
                "Alaska 12.3     62.4  1,832.5  *     16.0  4.8  37.1  84.0  106.5  92.3\n"
                "Table 9. x\n")
        table8 = cdc.parse_nvsr_table8(text).set_index("area")
        self.assertEqual(table8.loc["Alaska", "rate_25_29"], 106.5)
        self.assertEqual(table8.loc["United States", "rate_20_24"], 57.7)
        self.assertEqual(cdc.parse_nvsr_table2(text).iloc[0]["rate_25_29"], 91.0)


class NoiseAssessmentTests(unittest.TestCase):
    def frame(self, se: float):
        rng = np.random.default_rng(1)
        rows = [{"state_fips": f"{s:02d}", "year": y, "burden30_pct": 40 + s + y - 2014
                 + rng.normal(0, 1), "burden30_pct_se": se}
                for s in range(1, 11) for y in range(2014, 2020)]
        return pd.DataFrame(rows)

    def test_zero_se_gives_zero_noise(self):
        result = panel.sampling_noise_assessment(self.frame(0.0), draws=50)
        self.assertEqual(result["se_x1.0"]["noise_share"], 0.0)
        self.assertTrue(result["assumptions"])

    def test_noise_share_scales_with_se(self):
        result = panel.sampling_noise_assessment(self.frame(0.5), draws=200)
        shares = [result[k]["noise_share"] for k in ("se_x0.75", "se_x1.0", "se_x1.25")]
        self.assertTrue(shares[0] < shares[1] < shares[2])

    def test_unbalanced_panel_rejected(self):
        with self.assertRaises(ValueError):
            panel.sampling_noise_assessment(self.frame(0.5).iloc[1:], draws=10)


class PanelTests(unittest.TestCase):
    def frames(self):
        years = [2014, 2015, 2019, 2021, 2022]
        acs_frame = pd.DataFrame([{"state_fips": f, "year": y, "state_name": f"S{f}",
                                   **{c: float(y - 2000 + int(f)) for c in panel.HOUSING}}
                                  for f in ("01", "02") for y in years])
        cdc_frame = pd.DataFrame([{"state_fips": f, "year": y, "state_name": f"S{f}",
                                   "age_group": a, "births": 10, "rate_exported": 50.0}
                                  for f in ("01", "02") for y in [*years, 2020]
                                  for a in ("20-24", "25-29")])
        return acs_frame, cdc_frame

    def test_lag_does_not_bridge_2020(self):
        acs_frame, cdc_frame = self.frames()
        built = panel.build_panel(acs_frame, cdc_frame)
        self.assertNotIn(2020, set(built["year"]))
        lag = built.set_index(["state_fips", "year", "age_group"])["burden30_pct_lag1"]
        self.assertTrue(np.isnan(lag[("01", 2021, "20-24")]))
        self.assertTrue(np.isnan(lag[("01", 2019, "20-24")]))  # 2018 absent here
        self.assertEqual(lag[("01", 2015, "20-24")], 2014 - 2000 + 1)
        self.assertEqual(lag[("01", 2022, "25-29")], 2021 - 2000 + 1)

    def test_duplicate_keys_raise(self):
        acs_frame, cdc_frame = self.frames()
        with self.assertRaises(ValueError):
            panel.build_panel(pd.concat([acs_frame, acs_frame.iloc[:1]]), cdc_frame)
        with self.assertRaises(ValueError):
            panel.build_panel(acs_frame, pd.concat([cdc_frame, cdc_frame.iloc[:1]]))

    def test_missing_inputs_raise(self):
        with self.assertRaises(FileNotFoundError):
            panel.load(Path("missing_acs.csv"), Path("missing_cdc.csv"))


HAS_ACS = acs.raw_path(2024, "data").exists()
HAS_CDC = cdc.EXPORT_PATH.exists() and cdc.EXPANDED_PATH.exists()


@unittest.skipUnless(HAS_ACS, "saved ACS responses not present")
class AcsIntegrationTests(unittest.TestCase):
    def test_full_series(self):
        table, summary = acs.build()
        self.assertEqual(summary["records"], 510)
        self.assertEqual(acs.status(summary), "PASS")
        self.assertNotIn("72", set(table["state_fips"]))
        self.assertNotIn(2020, set(table["year"]))

    def test_no_key_in_saved_files(self):
        key = os.environ.get("CENSUS_API_KEY")
        if not key:
            self.skipTest("CENSUS_API_KEY not set")
        for path in acs.RAW_DIR.iterdir():
            self.assertNotIn(key.encode(), path.read_bytes(), path.name)


def read_raw_detail(path: Path) -> dict:
    """Detail rows of a WONDER export, read with the csv module only (independent parser)."""
    rows = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        for row in reader:
            if not row or row[0] == "---":
                break
            if row[0] == "":
                record = dict(zip(header, row))
                state = record.get("State Code") or record.get("State of Residence Code")
                rows[(record["Year Code"], state, record["Age of Mother 9 Code"])] = (
                    record["Births"], record["Female Population"], record["Fertility Rate"])
    return rows


@unittest.skipUnless(HAS_CDC, "CDC WONDER exports not present")
class CdcIntegrationTests(unittest.TestCase):
    def test_overlap_agrees_exactly(self):
        """Independent of analysis.cdc_natality: any disagreement fails loudly."""
        original = read_raw_detail(cdc.EXPORT_PATH)
        expanded = read_raw_detail(cdc.EXPANDED_PATH)
        self.assertEqual(len(original), 1122)
        self.assertEqual(len(expanded), 918)
        shared = sorted(set(original) & set(expanded))
        self.assertEqual(len(shared), 918)
        full = [k for k in shared if int(k[0]) <= 2020]
        self.assertEqual(len(full), 510)
        mismatched = [k for k in full if original[k] != expanded[k]]
        self.assertEqual(mismatched, [], f"2016-2020 disagreements: {mismatched[:5]}")
        births = [k for k in shared if original[k][0] != expanded[k][0]]
        self.assertEqual(births, [], f"birth-count disagreements: {births[:5]}")
        later = [k for k in shared if int(k[0]) >= 2021]
        self.assertTrue(all(original[k][2] == "Not Available" for k in later))
        self.assertTrue(all(float(expanded[k][2]) > 0 for k in later))
        recalculated = [abs(1000 * int(b) / int(p) - float(r)) for b, p, r in expanded.values()]
        self.assertLessEqual(max(recalculated), 0.0005 + 1e-9)

    def test_pipeline(self):
        detail, report = cdc.build()
        self.assertEqual(len(detail), 1122)
        self.assertTrue(report["reconciliation"]["agree"])
        self.assertEqual(report["combined"]["rows_without_rate"], 0)
        self.assertEqual(report["combined"]["rows_by_source"],
                         {"expanded": 918, "original": 204})
        self.assertEqual(report["status"], "PASS")
        for table8 in report["official_comparison"]["state_table8"].values():
            self.assertEqual(table8.get("outside_published_precision", 0), 0)

    def test_source_files_untouched(self):
        provenance = json.loads((cdc.CDC_DIR / "provenance.json").read_text(encoding="utf-8")) \
            if (cdc.CDC_DIR / "provenance.json").exists() else None
        if provenance is None:
            self.skipTest("Run python -m analysis.cdc_natality first")
        import hashlib
        for name, entry in provenance["files"].items():
            digest = hashlib.sha256((cdc.CDC_DIR / name).read_bytes()).hexdigest()
            self.assertEqual(digest, entry["sha256"], name)


@unittest.skipUnless(HAS_ACS and HAS_CDC and panel.ACS_PATH.exists()
                     and panel.CDC_PATH.exists(), "processed M10 tables not present")
class PanelIntegrationTests(unittest.TestCase):
    def test_panel(self):
        acs_frame, cdc_frame = panel.load()
        built = panel.build_panel(acs_frame, cdc_frame)
        report = panel.feasibility(built, acs_frame, cdc_frame)
        self.assertEqual(report["records"], 1020)
        self.assertEqual(report["unmatched_to_acs"], 0)
        self.assertEqual(report["lag1_2021_rows_with_value"], 0)
        self.assertEqual(report["lag1_value_mismatches"], 0)
        self.assertEqual(report["years_with_incomplete_geography"], [])
        self.assertEqual(report["rate_and_housing_complete"], 1020)
        self.assertEqual(panel.status(report), "PASS")


if __name__ == "__main__":
    unittest.main()
