"""Tests for the final synthesis: claim tracing, number scanning, cohort arithmetic
and the collated evidence tables.

The integration tests read only frozen aggregate outputs in data/public/ and the
synthesis documents, so they run without the survey data.
"""

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from analysis import final_synthesis as fs
from audit import verify_final_synthesis as vfs


class LocatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_json_path_with_index_and_selector(self):
        path = self.dir / "x.json"
        path.write_text(json.dumps({"a": {"rows": [{"k": "0", "v": 1.5}, {"k": "1", "v": 2.5}],
                                          "ci": [0.1, 0.2]}}), encoding="utf-8")
        self.assertEqual(vfs.resolve(path, "json:a.rows[k=1].v"), 2.5)
        self.assertEqual(vfs.resolve(path, "json:a.rows[0].v"), 1.5)
        self.assertEqual(vfs.resolve(path, "json:a.ci[1]"), 0.2)

    def test_csv_filter_selects_one_row(self):
        path = self.dir / "x.csv"
        pd.DataFrame({"cohort": ["c", "c", "d"], "measure": ["wants", "intends", "wants"],
                      "estimate": [0.7, 0.6, 0.5]}).to_csv(path, index=False)
        self.assertAlmostEqual(vfs.resolve(path, "csv:cohort=c;measure=intends|estimate"), 0.6)

    def test_csv_filter_matching_several_rows_is_an_error(self):
        path = self.dir / "x.csv"
        pd.DataFrame({"cohort": ["c", "c"], "estimate": [0.7, 0.6]}).to_csv(path, index=False)
        with self.assertRaises(ValueError):
            vfs.resolve(path, "csv:cohort=c|estimate")

    def test_csv_numeric_key_matches_its_text_form(self):
        path = self.dir / "x.csv"
        pd.DataFrame({"cohort": [1995, 2012], "projected": [1.75, 0.62]}).to_csv(path, index=False)
        self.assertAlmostEqual(vfs.resolve(path, "csv:cohort=2012|projected"), 0.62)

    def test_text_locator_requires_verbatim_presence(self):
        path = self.dir / "x.md"
        path.write_text("The linear calibration slope is 0.476.", encoding="utf-8")
        self.assertTrue(vfs.resolve(path, "text:slope is 0.476"))
        with self.assertRaises(ValueError):
            vfs.resolve(path, "text:slope is 0.5")

    def test_comparison_uses_scale_and_rounding(self):
        self.assertTrue(vfs.matches(18.4, 0.183621, scale=100, decimals=1))
        self.assertFalse(vfs.matches(18.5, 0.183621, scale=100, decimals=1))
        self.assertTrue(vfs.matches(-2.77, -2.774364, scale=1, decimals=2))


class NumberScanTests(unittest.TestCase):
    def test_decimals_percentages_and_thousands_are_extracted(self):
        text = "18.4% of 1,160 women; −2.77 (95% CI −5.81 to 0.26) in 2040; about 70%; section 4."
        self.assertEqual(vfs.numbers_in(text), {"18.4%", "1,160", "-2.77", "95%", "-5.81", "0.26", "70%"})

    def test_years_and_plain_integers_are_ignored(self):
        self.assertEqual(vfs.numbers_in("born 1995-2012, ages 18 to 27, in 2 chapters"), set())

    def test_claim_ids_and_file_names_are_ignored(self):
        self.assertEqual(vfs.numbers_in("[C11.3] see m11_fc_summary.json and v1.2 of docs"), set())

    def test_urls_dois_and_heading_numbers_are_ignored(self):
        text = "### 4.1 Results\nSee https://example.org/a/1.2 and doi 10.1080/01621459.1992.10475265; slope 0.48."
        self.assertEqual(vfs.numbers_in(text), {"0.48"})

    def test_scanner_source_has_no_control_characters(self):
        source = Path(vfs.__file__).read_text(encoding="utf-8")
        self.assertFalse([c for c in source if ord(c) < 32 and c not in "\n\r\t"])


class ProvenanceTests(unittest.TestCase):
    def test_missing_inputs_are_counted_separately_from_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "data" / "raw" / "src"
            source.mkdir(parents=True)
            (source / "match.txt").write_bytes(b"same")
            (source / "changed.txt").write_bytes(b"edited")
            digest = lambda data: hashlib.sha256(data).hexdigest()  # noqa: E731
            record = {"files": {"match.txt": {"sha256": digest(b"same")},
                                "changed.txt": {"sha256": digest(b"original")},
                                "absent.txt": {"sha256": digest(b"never downloaded")}},
                      "rooted": {"file": "data/raw/src/match.txt", "sha256": digest(b"same")}}
            (source / "provenance.json").write_text(json.dumps(record), encoding="utf-8")
            self.assertEqual(vfs.provenance_hashes(Path(tmp) / "data" / "raw"), {"src": (4, 1, 1)})

    def test_unavailable_inputs_skip_only_without_require_data(self):
        self.assertEqual(vfs.provenance_status(10, 0, 10, require_data=False), "SKIP")
        self.assertEqual(vfs.provenance_status(10, 0, 10, require_data=True), "FAIL")
        self.assertEqual(vfs.provenance_status(10, 1, 0, require_data=False), "FAIL")
        self.assertEqual(vfs.provenance_status(10, 1, 9, require_data=False), "FAIL")
        self.assertEqual(vfs.provenance_status(10, 0, 0, require_data=True), "PASS")
        self.assertEqual(vfs.provenance_status(0, 0, 0, require_data=False), "FAIL")


class ArchiveScanTests(unittest.TestCase):
    def test_restricted_content_is_flagged_and_provenance_metadata_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("p/data/raw/acs/provenance.json", '{"sha256": "x"}')
                archive.writestr("p/data/raw/extract.csv", "a,b\n1,2\n")
                archive.writestr("p/docs/rows.csv", "respondent_id,outcome\n1,0\n")
                archive.writestr("p/CLAUDE.md", "local")
                archive.writestr("p/analysis/k.py", 'API_KEY = "' + "x" * 32 + '"')
            problems = vfs.check_archive(path)
        text = "\n".join(problems)
        self.assertIn("restricted path: data/raw/extract.csv", text)
        self.assertIn("respondent-level column in docs/rows.csv", text)
        self.assertIn("restricted path: CLAUDE.md", text)
        self.assertIn("possible credential in analysis/k.py", text)
        self.assertIn("ARCHIVE_MANIFEST.sha256 missing", text)
        self.assertNotIn("restricted path: data/raw/acs/provenance.json", text)


class CohortArithmeticTests(unittest.TestCase):
    def test_nsfg_age_proxy_bounds_birth_years(self):
        self.assertEqual(fs.birth_cohort_bounds([(2022, 18, 26), (2023, 18, 27)]), (1995, 2005))

    def test_m10_recent_window_ages_20_24(self):
        windows = [(year, 20, 24) for year in range(2021, 2025)]
        self.assertEqual(fs.birth_cohort_bounds(windows), (1996, 2004))

    def test_inverted_age_window_is_rejected(self):
        with self.assertRaises(ValueError):
            fs.birth_cohort_bounds([(2022, 27, 18)])


class EvidenceTableTests(unittest.TestCase):
    def test_population_map_covers_every_chapter(self):
        frame = fs.population_map()
        self.assertEqual(list(frame["chapter"]), ["M01-M08", "M09", "M10", "M11"])
        self.assertTrue(frame["birth_cohorts"].str.match(r"^\d{4}-\d{4}").all())

    def test_evidence_table_matches_frozen_sources(self):
        table = fs.evidence_table().set_index("id")
        self.assertAlmostEqual(table.loc["M09.divergence", "estimate"], 0.112373, places=6)
        self.assertAlmostEqual(table.loc["M10.primary_20_24", "estimate"], -2.774364, places=6)
        self.assertAlmostEqual(table.loc["M11.tfr_2040", "upper"], 2.4239129187863075, places=9)
        self.assertAlmostEqual(table.loc["M01.slope", "estimate"], 0.476, places=3)
        self.assertTrue(table["estimand_type"].notna().all())
        self.assertTrue(table["uncertainty_type"].notna().all())

    def test_stored_public_tables_equal_a_fresh_build(self):
        for name, frame in (("final_evidence_table", fs.evidence_table()),
                            ("final_population_map", fs.population_map())):
            stored = pd.read_csv(fs.OUT / f"{name}.csv")
            fresh = pd.read_csv(io.StringIO(frame.to_csv(index=False)))
            pd.testing.assert_frame_equal(stored, fresh, check_dtype=False)


class ClaimMatrixTests(unittest.TestCase):
    def test_every_matrix_claim_resolves_to_its_source(self):
        failures = [r for r in vfs.check_matrix() if not r["ok"]]
        self.assertEqual(failures, [])

    def test_matrix_rows_are_complete(self):
        matrix = vfs.load_matrix()
        required = ["claim_id", "claim", "estimand_type", "population", "denominator", "uncertainty",
                    "source_file", "verification_kind", "status", "interpretation_support"]
        for column in required:
            self.assertTrue(matrix[column].fillna("").str.strip().ne("").all(), column)
        self.assertTrue(matrix["claim_id"].is_unique)

    def test_every_number_in_the_synthesis_documents_is_traceable(self):
        self.assertEqual(vfs.untraced_numbers(), {})

    def test_every_claim_id_cited_in_the_synthesis_documents_exists(self):
        self.assertEqual(vfs.unknown_claim_ids(), set())


if __name__ == "__main__":
    unittest.main()
