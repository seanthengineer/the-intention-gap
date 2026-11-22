"""Tests for the publication tooling in tools/ (release checks, README header, Pyright policy).

Credential-like and personal strings are assembled at run time so that this file itself passes the
release content scan.
"""

import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from tools import pyright_baseline, readme_header, release

ROOT = Path(__file__).resolve().parents[1]


class ExclusionRuleTests(unittest.TestCase):
    def test_restricted_and_local_files_are_excluded(self):
        for rel in ("CLAUDE.md", ".claude/settings.local.json", "inspect_data.py", "audit_data.py",
                    "data/raw/hfd_usa/USA.zip", "data/processed/intention_gap_cohort.csv",
                    ".venv/Lib/site.py", "analysis/__pycache__/hfd.cpython-315.pyc", "release.zip",
                    "data/public/m11/forecast/m11_run_record.json", ".env", ".streamlit/secrets.toml",
                    "audit/local_output.csv", "extract.log", "streamlit_app.py", "tests/test_dashboard.py",
                    "assets/dashboard.png", ".streamlit/config.toml"):
            self.assertIsNotNone(release.exclusion_reason(rel), rel)

    def test_research_files_are_included(self):
        for rel in ("analysis/hfd.py", "docs/m11_freeze.sha256", "data/public/m10/m10_models.csv",
                    "assets/figures/m10_trends.png", "README.md", ".gitattributes",
                    "docs/output/notes.md", "docs/build/x.md", "audit/sub/notes.txt"):
            self.assertIsNone(release.exclusion_reason(rel), rel)

    def test_rules_mirror_gitignore_at_any_depth(self):
        for rel in ("docs/CLAUDE.md", "data/interim/x.csv", "data/notes.txt", "sub/intention_gap_cohort.csv",
                    "docs/report.pdf", "data/public/x.parquet", "tools/.env.local", ".mypy_cache/x.json"):
            self.assertIsNotNone(release.exclusion_reason(rel), rel)

    def test_website_dependencies_and_build_outputs_are_excluded(self):
        for rel in ("website/node_modules/d3/package.json", "website/dist/index.html",
                    "website/.astro/types.d.ts", "website/public/figures/m10_trends.png",
                    "website/src/data/site-data.json", "website/src/data/provenance.json",
                    "sub/node_modules/x.js"):
            self.assertIsNotNone(release.exclusion_reason(rel), rel)

    def test_website_source_is_included(self):
        for rel in ("website/package.json", "website/package-lock.json", "website/scripts/prepare-data.mjs",
                    "website/src/pages/index.astro", "website/src/scripts/main.ts",
                    "website/src/styles/global.css", "website/public/photos/photo.jpg",
                    "website/public/favicon.svg", "docs/dist/x.md"):
            self.assertIsNone(release.exclusion_reason(rel), rel)

    def test_walk_prunes_excluded_trees_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("data/raw/a.csv", "data/public/b.csv", ".venv/c.py", "analysis/d.py"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("x\n", encoding="utf-8")
            try:
                (root / "linked").symlink_to(root / "data" / "raw", target_is_directory=True)
            except OSError:
                linked = False
            else:
                linked = True
            included, excluded = release.walk(root)
        self.assertEqual(included, ["analysis/d.py", "data/public/b.csv"])
        self.assertIn("data/raw/", excluded)
        if linked:
            self.assertEqual(excluded["linked/"], release.SYMLINK)


class ContentScanTests(unittest.TestCase):
    def kinds(self, rel, text):
        return {finding.check for finding in release.scan_text(rel, text)}

    def test_detects_credentials(self):
        self.assertIn("secret", self.kinds("a.py", 'API_KEY = "' + "x" * 32 + '"'))
        self.assertIn("secret", self.kinds("a.json", '{"api_key": "' + "y" * 30 + '"}'))
        self.assertIn("secret", self.kinds("a.yml", "client_secret: " + "z" * 24))
        self.assertIn("secret", self.kinds("a.md", "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12))
        self.assertIn("secret", self.kinds("a.md", "AIza" + "q" * 35))
        self.assertIn("secret", self.kinds("a.md", "key " + "ab" * 20))
        self.assertIn("secret", self.kinds("a.txt", "AKIA" + "A" * 16))
        self.assertIn("secret", self.kinds("a.txt", "-----BEGIN " + "RSA PRIVATE KEY-----"))

    def test_pinned_action_sha_and_hash_files_are_not_credentials(self):
        self.assertEqual(self.kinds("ci.yml", "      - uses: actions/checkout@" + "ab" * 20), set())
        self.assertEqual(self.kinds("docs/x.sha256", "ab" * 32 + "  analysis/x.py"), set())

    def test_detects_personal_paths_and_email(self):
        self.assertIn("privacy", self.kinds("a.md", "see C:" + "\\Users\\someone\\data.csv"))
        self.assertIn("privacy", self.kinds("a.md", "see /" + "home/someone/data.csv"))
        self.assertIn("privacy", self.kinds("a.md", "contact someone@" + "university.edu"))
        self.assertEqual(self.kinds("a.md", "placeholder someone@" + "example.org"), set())
        self.assertIn("privacy", self.kinds("a.json", '"C:' + '\\\\Users\\\\someone\\\\x"'))
        self.assertIn("privacy", self.kinds("a.md", "see C:/" + "Users/someone/x"))
        self.assertEqual(self.kinds("a.md", "Co-Authored-By: bot <" + "noreply@" + "example.com>"), set())

    def test_detects_respondent_columns(self):
        self.assertIn("disclosure", self.kinds("data/public/x.csv", "PUBID,birth\n1,0\n"))
        self.assertIn("disclosure", self.kinds("data/public/x.csv", "\ufeffpubid_1997;birth\n"))
        self.assertIn("disclosure", self.kinds("data/public/x.csv", "R0000100\tbirth\n"))
        self.assertEqual(self.kinds("data/public/x.csv", "state,year,rate\n"), set())
        self.assertEqual(self.kinds("data/public/x.csv", "id,respondents,births\n"), set())

    def test_detects_personal_data_in_image_metadata(self):
        data = b"\x89PNG\r\n" + b"tEXtAuthor\x00" + ("C:" + "\\Users\\someone\\pic").encode()
        self.assertEqual({f.check for f in release.scan_binary("a.png", data)}, {"privacy"})
        self.assertEqual(release.scan_binary("a.png", b"\x89PNG\r\ntEXtSoftware matplotlib"), [])


class LinkTests(unittest.TestCase):
    def test_slug_matches_github(self):
        self.assertEqual(release.github_slug("9. Reproduction"), "9-reproduction")
        self.assertEqual(release.github_slug("Data & limitations: `M10`"), "data--limitations-m10")
        self.assertEqual(release.anchors("# A\n# A\n```\n# not\n```\n"), {"a", "a-1"})
        self.assertEqual(release.github_slug("The *visual* atlas: __M11__"), "the-visual-atlas-m11")
        self.assertEqual(release.github_slug("snake_case name"), "snake_case-name")
        self.assertEqual(release.github_slug("Caf\u00e9 \u00fcber"), "caf\u00e9-\u00fcber")
        self.assertEqual(release.anchors("Title\n=====\n~~~\n# hidden\n~~~\n  ## Indented\n"),
                         {"title", "indented"})

    def test_broken_links_and_anchors_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "b.md").write_text("# Section one\n", encoding="utf-8")
            (root / "a.md").write_text(
                "[ok](docs/b.md#section-one) [bad anchor](docs/b.md#missing) [gone](missing.md) "
                "[web](https://example.org) `[code](nowhere.md)` [up](../outside.md) "
                "[![badge](img/badge.svg)](docs/b.md) [titled](docs/b.md 'title')\n"
                '<img src="docs/none.png" alt="x">\n\n[ref]: docs/ref.md\n', encoding="utf-8")
            details = sorted(f.detail for f in release.check_links(root, ["a.md", "docs/b.md"]))
        self.assertEqual(details, ["anchor not found: docs/b.md#missing",
                                   "link leaves the repository: ../outside.md",
                                   "target not in the release: docs/none.png",
                                   "target not in the release: docs/ref.md",
                                   "target not in the release: img/badge.svg",
                                   "target not in the release: missing.md"])


class GitAttributesTests(unittest.TestCase):
    def check(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gitattributes").write_text(text, encoding="utf-8")
            return release.check_gitattributes(Path(tmp))

    def test_requires_global_unset_rule_first(self):
        good = "* -text -eol -filter -ident -working-tree-encoding\n*.png binary\n"
        self.assertEqual(self.check(good), [])
        self.assertTrue(self.check("*.png binary\n* -text\n"))

    def test_rejects_later_rules_that_reenable_conversion(self):
        base = "* -text -eol -filter -ident -working-tree-encoding\n"
        for rule in ("*.md text\n", "*.py eol=lf\n", "*.csv filter=lfs\n", "*.txt working-tree-encoding=UTF-16\n"):
            self.assertTrue(self.check(base + rule), rule)


class RepositoryReleaseTests(unittest.TestCase):
    def test_release_checks_pass_on_this_repository(self):
        for name, findings in release.run_checks(ROOT):
            self.assertEqual([str(f) for f in findings], [], name)

    def test_every_frozen_file_is_released(self):
        included = set(release.walk(ROOT)[0])
        frozen = release.frozen_entries(ROOT)
        self.assertGreaterEqual(len(frozen), 221)
        self.assertFalse(set(frozen) - included)

    def test_tampered_frozen_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "x.md").write_bytes(b"frozen\n")
            digest = release.sha256(root / "docs" / "x.md")
            (root / "docs" / "x_freeze.sha256").write_text(f"{digest}  docs/x.md\n", encoding="utf-8")
            self.assertEqual(release.check_frozen(root), [])
            (root / "docs" / "x.md").write_bytes(b"frozen\r\n")
            self.assertEqual([f.detail for f in release.check_frozen(root)], ["hash differs from x_freeze.sha256"])

    def test_stage_refuses_a_destination_inside_the_repository(self):
        with self.assertRaises(ValueError):
            release.stage(ROOT / "docs" / "staging-test", ROOT, checked=False)

    def test_lock_file_pins_every_direct_requirement_with_hashes(self):
        lock = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
        pinned = dict(re.findall(r"(?m)^([A-Za-z0-9_.-]+)==([^\s\\]+)", lock))
        normal = {k.lower().replace("_", "-"): v for k, v in pinned.items()}
        for name in ("requirements.txt", "requirements-research.txt"):
            for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
                match = re.match(r"([A-Za-z0-9_.-]+)==(\S+)", line)
                if match:
                    self.assertEqual(normal.get(match.group(1).lower().replace("_", "-")), match.group(2), line)
        blocks = re.split(r"(?m)^(?=[A-Za-z0-9_.-]+==)", lock)[1:]
        self.assertTrue(blocks)
        self.assertTrue(all("--hash=sha256:" in block for block in blocks))

    def test_archive_is_deterministic_and_passes_the_frozen_safety_scan(self):
        from audit import verify_final_synthesis as vfs
        with tempfile.TemporaryDirectory() as tmp:
            staged = release.stage(Path(tmp) / "stage", ROOT)
            first = release.write_archive(Path(tmp) / "stage", Path(tmp) / "a.zip", staged)
            second = release.write_archive(Path(tmp) / "stage", Path(tmp) / "b.zip", staged)
            self.assertEqual(first, second)
            self.assertEqual(vfs.check_archive(Path(tmp) / "a.zip"), [])


class RunRecordRestoreTests(unittest.TestCase):
    def test_restores_only_a_hash_verified_frozen_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            frozen = root / release.FROZEN_RUN_RECORD
            frozen.write_bytes(b'{"started_utc": "x"}\n')
            (root / "docs" / "m11_freeze.sha256").write_text(
                f"{release.sha256(frozen)}  {release.FROZEN_RUN_RECORD}\n", encoding="utf-8")
            self.assertEqual(release.restore_run_record(root), "restored")
            self.assertEqual((root / release.LIVE_RUN_RECORD).read_bytes(), frozen.read_bytes())
            self.assertEqual(release.restore_run_record(root), "unchanged")
            frozen.write_bytes(b"tampered\n")
            with self.assertRaises(ValueError):
                release.restore_run_record(root)
            (root / "docs" / "m11_freeze.sha256").write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                release.restore_run_record(root)


class ReadmeHeaderTests(unittest.TestCase):
    def test_header_uses_frozen_values_and_is_current(self):
        observed = readme_header.observed_tfr()
        self.assertEqual((observed[0][0], observed[-1][0], len(observed)), (1953, 2024, 72))
        self.assertEqual(max(observed, key=lambda item: item[1]), (1957, 3.73803))
        self.assertEqual(readme_header.forecast_tfr()[-1], (2040, 1.59315))
        for path, text in readme_header.outputs().items():
            self.assertEqual(path.read_bytes(), text.encode("utf-8"), path.name)
            self.assertIn("1.593 in 2040", text)

    def test_gaps_in_the_observed_series_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.csv"
            path.write_text("method,target,observed\nnaive,2000,2.0\nnaive,2002,2.1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                readme_header.observed_tfr(path)


class PyrightPolicyTests(unittest.TestCase):
    def test_tooling_must_be_clean_and_baseline_may_not_grow(self):
        baseline = {"analysis/hfd.py": 3}
        same = Counter({"analysis/hfd.py": 3})
        self.assertEqual(pyright_baseline.compare(same, baseline), [])
        self.assertEqual(len(pyright_baseline.compare(Counter({"analysis/hfd.py": 4}), baseline)), 1)
        self.assertEqual(len(pyright_baseline.compare(Counter({"analysis/hfd.py": 2}), baseline)), 1)
        self.assertEqual(len(pyright_baseline.compare(same + Counter({"tools/release.py": 1}), baseline)), 1)
        self.assertEqual(len(pyright_baseline.compare(same + Counter({"analysis/new.py": 1}), baseline)), 1)
        self.assertEqual(len(pyright_baseline.compare(same, baseline, Counter({"tools/x.py": 1}))), 1)

    def test_report_paths_are_normalised_on_both_platforms(self):
        windows = str(ROOT / "analysis" / "hfd.py").replace("/", "\\")
        report = {"generalDiagnostics": [{"file": windows, "severity": "error"},
                                         {"file": (ROOT / "tools" / "x.py").as_posix(), "severity": "warning"}]}
        errors, warnings = pyright_baseline.counts(report)
        self.assertEqual(errors, Counter({"analysis/hfd.py": 1}))
        self.assertEqual(warnings, Counter({"tools/x.py": 1}))


if __name__ == "__main__":
    unittest.main()
