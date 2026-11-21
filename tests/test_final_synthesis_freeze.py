"""Final synthesis freeze-integrity tests.

audit/verify_freeze.py and tests/test_freeze_integrity.py are frozen M10 files. They discover every
docs/*_freeze.sha256, so they check the final synthesis manifest without being edited. These tests
add synthesis-specific checks: required coverage, exclusion of mutable and restricted files, no file
frozen twice, the four earlier manifests unchanged (206 files), and every frozen file of all five
manifests present in the source-only archive with its hash.
"""

import hashlib
import unittest
import zipfile
from pathlib import Path

from audit import verify_freeze as vf

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "final_synthesis_freeze.sha256"
ARCHIVE = ROOT.parent / "intention-gap-review-source-final.zip"
REQUIRED = ["docs/final_synthesis_manuscript.md", "docs/final_executive_summary.md",
            "docs/final_claim_evidence_matrix.csv", "docs/final_limitations_register.md", "docs/final_sources.md",
            "docs/final_reproducibility_guide.md", "docs/final_readiness_assessment.md",
            "analysis/final_synthesis.py", "audit/verify_final_synthesis.py", "tests/test_final_synthesis.py",
            "tests/test_final_synthesis_freeze.py", "data/public/final/final_evidence_table.csv",
            "data/public/final/final_population_map.csv", "assets/figures/final_evidence_map.png",
            "assets/figures/final_headline_panels.png"]
PRIOR_MANIFESTS = {
    "m01_m08_freeze.sha256": ("cb95beeb01ad5f912c3b23126dde5e9b89daa27504c77e41fcb9f666fc7ba71f", 34),
    "nsfg_m09_freeze.sha256": ("be74ecec815f7ba221b0b978c4123f689dd54f5dbcd9919601f6f69c00c3e9e0", 39),
    "m10_freeze.sha256": ("716d4f937492b0b10fb4ebb9ee10a84a9d687a60dbc772cb36bb3431b7bcb979", 30),
    "m11_freeze.sha256": ("ccf4df145e75ad89933532cb1a5e759be443b2c22e0d09ea8bd32f601a0e34e0", 103),
}
MUTABLE = ["README.md", "CLAUDE.md", "audit/scientific-audit.md", "streamlit_app.py", "requirements.txt"]


@unittest.skipUnless(MANIFEST.exists(), "final synthesis not frozen")
class FinalSynthesisFreezeTests(unittest.TestCase):
    def setUp(self):
        self.entries = vf.read_manifest(MANIFEST)
        self.names = [name for _, name in self.entries]

    def test_manifest_is_discovered_and_passes(self):
        self.assertIn(MANIFEST, vf.manifests())
        result = vf.check_manifest(MANIFEST)
        self.assertTrue(result["ok"], result)

    def test_manifest_covers_required_files_and_all_synthesis_outputs(self):
        self.assertEqual(sorted(self.names), sorted(REQUIRED))
        outputs = {p.relative_to(ROOT).as_posix() for p in (ROOT / "data" / "public" / "final").glob("*") if p.is_file()}
        figures = {p.relative_to(ROOT).as_posix() for p in (ROOT / "assets" / "figures").glob("final_*.png")}
        self.assertEqual(sorted((outputs | figures) - set(self.names)), [])

    def test_mutable_and_restricted_files_are_not_frozen(self):
        self.assertFalse(set(MUTABLE) & set(self.names))
        self.assertFalse([n for n in self.names if n.startswith(("data/raw/", "data/processed/", ".venv/"))])

    def test_earlier_manifests_unchanged_and_no_file_frozen_twice(self):
        counts = {}
        for name, (digest, count) in PRIOR_MANIFESTS.items():
            path = ROOT / "docs" / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)
            counts[name] = len(vf.read_manifest(path))
            self.assertEqual(counts[name], count, name)
        self.assertEqual(sum(counts.values()), 206)
        frozen = [n for m in vf.manifests() for _, n in vf.read_manifest(m)]
        self.assertEqual(len(frozen), len(set(frozen)))
        self.assertEqual(len(vf.manifests()), 5)

    def test_documents_record_the_freeze(self):
        for name in ("docs/final_synthesis_manuscript.md", "docs/final_readiness_assessment.md"):
            self.assertIn("FROZEN, final scientific approval", (ROOT / name).read_text(encoding="utf-8"), name)
        self.assertIn("## 22. ", (ROOT / "audit" / "scientific-audit.md").read_text(encoding="utf-8"))

    def test_synthesis_files_use_lf_line_endings(self):
        for name in self.names:
            if not name.endswith(".png"):
                self.assertNotIn(b"\r\n", (ROOT / name).read_bytes(), name)

    @unittest.skipUnless(ARCHIVE.exists(), "final review archive not built")
    def test_every_file_of_all_five_manifests_is_in_the_archive_with_its_hash(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            files = {n.split("/", 1)[1]: n for n in archive.namelist()}
            for manifest in vf.manifests():
                for digest, name in vf.read_manifest(manifest):
                    self.assertIn(name, files, name)
                    self.assertEqual(hashlib.sha256(archive.read(files[name])).hexdigest(), digest, name)


if __name__ == "__main__":
    unittest.main()
