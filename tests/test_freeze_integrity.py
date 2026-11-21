"""Freeze-integrity tests: frozen chapters (M09, M10) must match their manifests."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from audit import verify_freeze as vf


class FreezeCheckerTests(unittest.TestCase):
    def test_detects_changed_and_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "a.txt").write_text("frozen", encoding="utf-8")
            digest = hashlib.sha256(b"frozen").hexdigest()
            manifest = root / "docs" / "x_freeze.sha256"
            manifest.write_text(f"{digest}  a.txt\n{digest}  b.txt\n", encoding="utf-8")
            result = vf.check_manifest(manifest, root)
            self.assertEqual(result["missing"], ["b.txt"])
            (root / "a.txt").write_text("edited", encoding="utf-8")
            result = vf.check_manifest(manifest, root)
            self.assertEqual(result["changed"], ["a.txt"])
            self.assertFalse(result["ok"])

    def test_empty_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "empty_freeze.sha256"
            manifest.write_text("\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                vf.read_manifest(manifest)


class FrozenChapterTests(unittest.TestCase):
    def test_m09_and_m10_manifests_exist(self):
        names = {path.name for path in vf.manifests()}
        self.assertIn("nsfg_m09_freeze.sha256", names)
        self.assertIn("m10_freeze.sha256", names)

    def test_every_frozen_file_is_unchanged(self):
        for manifest in vf.manifests():
            result = vf.check_manifest(manifest)
            self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
