"""M11 freeze-integrity tests.

audit/verify_freeze.py and tests/test_freeze_integrity.py are frozen M10 files.
They already discover every docs/*_freeze.sha256, so they check the M11 manifest
without being edited. These tests add M11-specific checks: the manifest covers
every required category, excludes the volatile run record, matches the files on
disk, and every frozen file is in the source-only archive with the same hash.
"""

import hashlib
import json
import unittest
import zipfile
from pathlib import Path

from audit import verify_freeze as vf

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "m11_freeze.sha256"
ARCHIVE = ROOT.parent / "intention-gap-review-source-M11.zip"
REQUIRED = ["analysis/m11_forecast.py", "analysis/m11_models.py", "analysis/m11_backtest.py", "analysis/m11_cohorts.py",
            "analysis/m11_scenarios.py", "analysis/m11_protocol.py", "analysis/m11_origin_local.py",
            "analysis/m11_figures.py", "analysis/hfd.py", "analysis/m11_sources.py", "analysis/m11_feasibility.py",
            "audit/verify_m11.py", "audit/verify_m11_forecast.py", "tests/test_m11_data.py",
            "tests/test_m11_forecast.py", "tests/test_m11_freeze.py", "docs/m11_forecast_protocol.md",
            "docs/m11_protocol_lock.json", "docs/m11_decision_log.md", "docs/m11_fertility_forecasts.md",
            "docs/m11_data_feasibility.md", "docs/m11_frozen_run_record.json",
            "data/public/m11/forecast/m11_fc_tfr_forecast.csv", "data/public/m11/forecast/m11_fc_genz_endpoints_2040.csv",
            "data/public/m11/forecast/m11_pr_origin_local_choices.csv", "assets/figures/m11_fc_tfr_forecast.png"]


@unittest.skipUnless(MANIFEST.exists(), "M11 not frozen")
class M11FreezeTests(unittest.TestCase):
    def setUp(self):
        self.entries = vf.read_manifest(MANIFEST)
        self.names = {name for _, name in self.entries}

    def test_manifest_is_discovered_and_passes(self):
        self.assertIn(MANIFEST, vf.manifests())
        result = vf.check_manifest(MANIFEST)
        self.assertTrue(result["ok"], result)

    def test_manifest_covers_required_categories_and_all_public_outputs(self):
        self.assertEqual([r for r in REQUIRED if r not in self.names], [])
        public = {p.relative_to(ROOT).as_posix() for p in (ROOT / "data" / "public" / "m11").rglob("*") if p.is_file()}
        public.discard("data/public/m11/forecast/m11_run_record.json")
        self.assertEqual(sorted(public - self.names), [])
        figures = {p.relative_to(ROOT).as_posix() for p in (ROOT / "assets" / "figures").glob("m11_*.png")}
        self.assertEqual(sorted(figures - self.names), [])

    def test_volatile_and_restricted_files_are_not_frozen(self):
        self.assertNotIn("data/public/m11/forecast/m11_run_record.json", self.names)
        self.assertFalse([n for n in self.names if n.startswith(("data/raw/", "data/processed/"))])

    def test_frozen_run_record_matches_frozen_code(self):
        record = json.loads((ROOT / "docs" / "m11_frozen_run_record.json").read_text(encoding="utf-8"))
        for path, digest in record["code_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest, path)
        lock = json.loads((ROOT / "docs" / "m11_protocol_lock.json").read_text(encoding="utf-8"))
        self.assertEqual(record["protocol_sha256"], lock["sha256"])
        self.assertLess(lock["locked_utc"], record["started_utc"])

    def test_chapter_marked_frozen(self):
        text = (ROOT / "docs" / "m11_fertility_forecasts.md").read_text(encoding="utf-8")
        self.assertIn("FROZEN, final scientific approval", text)

    @unittest.skipUnless(ARCHIVE.exists(), "review archive not built")
    def test_every_frozen_file_is_in_the_archive_with_its_hash(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            files = {n.split("/", 1)[1]: n for n in archive.namelist()}
            for digest, name in self.entries:
                self.assertIn(name, files)
                self.assertEqual(hashlib.sha256(archive.read(files[name])).hexdigest(), digest, name)


if __name__ == "__main__":
    unittest.main()
