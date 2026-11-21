"""M01-M08 freeze-integrity tests.

The M01-M08 manifest (docs/m01_m08_freeze.sha256) was created on 2026-11-20 from the
M08 release candidate, intention-gap-release-candidate-M08.zip. audit/verify_freeze.py
and tests/test_freeze_integrity.py are frozen M10 files that already discover every
docs/*_freeze.sha256, so they check this manifest without being edited. These tests
add the M01-M08 specific checks. docs/m01_m08_freeze_record.md explains each decision.
"""

import hashlib
import unittest
import zipfile
from pathlib import Path

from audit import verify_freeze as vf

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "m01_m08_freeze.sha256"
M09_MANIFEST = ROOT / "docs" / "nsfg_m09_freeze.sha256"
ARCHIVE = ROOT.parent / "intention-gap-release-candidate-M08.zip"

FROZEN = [
    "analysis/__init__.py", "analysis/analyze_calibration.py", "analysis/birth_history_audit.py",
    "analysis/build_outcomes.py", "analysis/expanded_histories.py", "analysis/export_dashboard_data.py",
    "analysis/nlsy97.py", "analysis/population_validity.py", "analysis/pregnancy_status.py",
    "analysis/robustness_analysis.py", "analysis/supplement_extract.py", "analysis/temporal_validation.py",
    "audit/__init__.py", "audit/verify_models.py", "audit/verify_outcomes.py", "audit/verify_temporal.py",
    "tests/__init__.py", "tests/test_analyze_calibration.py", "tests/test_build_outcomes.py",
    "tests/test_expanded_histories.py", "tests/test_population_validity.py", "tests/test_pregnancy_status.py",
    "tests/test_robustness_analysis.py", "tests/test_supplement_extract.py", "tests/test_survey_design.py",
    "tests/test_temporal_validation.py",
    "docs/methodology.md", "docs/extract_manifest.csv", "docs/temporal_extract_manifest.csv",
    "docs/frozen_model_parameters.json", "data/public/dashboard_summary.json",
    "assets/figures/baseline_comparison.png", "assets/figures/stated_expectation_calibration.png",
    "assets/figures/stated_expectation_distribution.png",
]

# M08 release files deliberately left out of this manifest (owner decision 2026-11-20, or editable config).
EXCLUDED = {
    "README.md": "not frozen; editable in its authorized phase",
    "streamlit_app.py": "not frozen; editable in the dashboard phase",
    "tests/test_dashboard.py": "tests the editable dashboard",
    "assets/dashboard.png": "dashboard screenshot",
    "requirements.txt": "dashboard environment",
    ".streamlit/config.toml": "dashboard configuration",
    ".gitignore": "repository configuration",
}

# M08 release files that changed after M08 for a recorded reason and are checked another way.
SURVEY_DESIGN = "analysis/survey_design.py"  # refactored and extended in M09; frozen by the M09 manifest
AUDIT_LOG = "audit/scientific-audit.md"      # living audit log; M08 sections 0-16 checked below
M08_AUDIT_LOG_SHA256 = "18413daab284afe0f33f3a285030c478ff65e9bf4972f29bcaf0ab2710e1a845"
M08_AUDIT_LOG_BYTES = 31101


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class M01M08FreezeTests(unittest.TestCase):
    def test_manifest_is_discovered_and_passes(self):
        self.assertIn(MANIFEST, vf.manifests())
        result = vf.check_manifest(MANIFEST)
        self.assertTrue(result["ok"], result)

    def test_manifest_lists_exactly_the_frozen_files(self):
        names = [name for _, name in vf.read_manifest(MANIFEST)]
        self.assertEqual(sorted(names), sorted(FROZEN))
        self.assertEqual(len(names), len(set(names)))

    def test_changed_shared_module_is_frozen_by_m09(self):
        m09 = {name for _, name in vf.read_manifest(M09_MANIFEST)}
        self.assertIn(SURVEY_DESIGN, m09)

    def test_m08_sections_of_audit_log_are_unchanged(self):
        text = (ROOT / AUDIT_LOG).read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(sha256(text[:M08_AUDIT_LOG_BYTES]), M08_AUDIT_LOG_SHA256)
        self.assertTrue(text[M08_AUDIT_LOG_BYTES:].startswith(b"\n## 17."))

    @unittest.skipUnless(ARCHIVE.exists(), "M08 release archive not available")
    def test_release_archive_is_fully_accounted_for(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            released = {n.split("/", 1)[1] for n in archive.namelist() if not n.endswith("/")}
        accounted = set(FROZEN) | set(EXCLUDED) | {SURVEY_DESIGN, AUDIT_LOG}
        self.assertEqual(sorted(released ^ accounted), [])

    @unittest.skipUnless(ARCHIVE.exists(), "M08 release archive not available")
    def test_every_frozen_file_matches_the_m08_release(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            files = {n.split("/", 1)[1]: n for n in archive.namelist()}
            for digest, name in vf.read_manifest(MANIFEST):
                self.assertEqual(sha256(archive.read(files[name])), digest, name)
            self.assertEqual(sha256(archive.read(files[AUDIT_LOG])), M08_AUDIT_LOG_SHA256)
            self.assertEqual(len(archive.read(files[AUDIT_LOG])), M08_AUDIT_LOG_BYTES)


if __name__ == "__main__":
    unittest.main()
