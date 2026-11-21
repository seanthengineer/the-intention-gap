"""Public-release checks, inventory, staging and review archive for The Intention Gap.

    python -m tools.release check                 all release checks (exit 1 on any failure)
    python -m tools.release inventory [--write]   print or rewrite docs/release_inventory.csv
    python -m tools.release excluded              list excluded local files with reasons
    python -m tools.release restore-run-record    recreate the gitignored live M11 run record from its
                                                  frozen copy (needed by one frozen test in a fresh clone)
    python -m tools.release stage DEST [--archive ZIP]
                                                  run every check, then copy the release files byte for
                                                  byte to DEST and optionally write a review archive

The release set is every file in the working tree that no exclusion rule matches. The rules mirror
.gitignore (tested against `git ls-files` in a disposable repository); the check confirms that the
committed inventory agrees with them. Frozen research files are only hashed and copied, never changed.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = "docs/release_inventory.csv"
ARCHIVE_PREFIX = "the-intention-gap"
ZIP_TIME = (2026, 11, 20, 0, 0, 0)
SYMLINK = "symbolic link (not allowed in the release)"

ANY_DEPTH_DIRS = {
    ".git": "version-control metadata",
    ".claude": "local AI-assistant configuration",
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "test cache",
    ".mypy_cache": "type-checker cache",
    ".ruff_cache": "linter cache",
    ".ipynb_checkpoints": "notebook cache",
}
ROOT_DIRS = {
    ".venv": "local virtual environment",
    "venv": "local virtual environment",
    "env": "local virtual environment",
    ".vscode": "editor settings",
    ".idea": "editor settings",
    "htmlcov": "coverage output",
    "build": "build output",
    "dist": "build output",
    "output": "local output",
    "outputs": "local output",
}
DATA_REASONS = {
    "data/raw/": "restricted or licensed source data; kept local (see docs/licensing_and_attribution.md)",
    "data/processed/": "respondent-level or intermediate derived data; kept local",
}
EXCLUDE_FILES = {
    "inspect_data.py": "owner's local exploratory script that reads respondent-level rows",
    "audit_data.py": "owner's local exploratory script that reads respondent-level rows",
    "data/public/m11/forecast/m11_run_record.json": "volatile run record rewritten by every run; frozen copy is docs/m11_frozen_run_record.json",
    ".streamlit/secrets.toml": "application secrets",
    "streamlit_app.py": "Streamlit prototype deferred: kept local until a dashboard phase is authorized",
    "tests/test_dashboard.py": "Streamlit prototype deferred: kept local until a dashboard phase is authorized (tests only the dashboard)",
    "assets/dashboard.png": "Streamlit prototype deferred: kept local until a dashboard phase is authorized (screenshot)",
    ".streamlit/config.toml": "Streamlit prototype deferred: kept local until a dashboard phase is authorized (configuration)",
}
ANY_DEPTH_NAMES = {
    "CLAUDE.md": "local AI-assistant orchestration instructions (not part of the public project)",
    ".env": "environment secrets",
    ".env.*": "environment secrets",
    "intention_gap_nlsy97*": "respondent-level NLSY97 extract",
    "intention_gap_cohort*": "respondent-level analysis cohort",
    "*-value-labels.do": "survey extract program",
    "*.py[cod]": "Python bytecode",
    "*.egg-info": "build metadata",
    "*.zip": "local archive",
    "*.7z": "local archive",
    "*.log": "local log",
    "*.tmp": "temporary file",
    ".coverage": "coverage data",
    ".DS_Store": "operating-system file",
    "Thumbs.db": "operating-system file",
}
RESTRICTED_SUFFIXES = (".dat", ".cdb", ".dct", ".sas", ".sps", ".nlsy97", ".xls", ".xlsx", ".sav", ".dta",
                       ".parquet", ".pdf", ".gz", ".pkl", ".pickle", ".joblib")
DIRECT_PATTERNS = {
    "audit/*.txt": "local audit output",
    "audit/*.csv": "local audit output",
}
TEXT_SUFFIXES = (".py", ".md", ".csv", ".json", ".txt", ".toml", ".cfg", ".ini", ".yml", ".yaml", ".cff",
                 ".sha256", ".svg", ".html")
TEXT_NAMES = (".gitignore", ".gitattributes", ".python-version")
BINARY_SUFFIXES = (".png",)
RESPONDENT_COLUMNS = {"respondent_id", "pubid", "caseid", "household_id", "sidcode", "secu", "sest", "hhid"}
RESPONDENT_PATTERN = re.compile(r"^(pubid|caseid)(_\w+)?$|^respondent_?id$|^[a-z]\d{7}$")

SECRET_PATTERNS = {
    "assignment of a credential-like value": re.compile(
        r"(?i)\b(api[_-]?key|secret|client[_-]?secret|password|passwd|token|access[_-]?key)\b['\"]?\s*[=:]\s*"
        r"['\"]?[A-Za-z0-9/+_\-]{20,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{40,}"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "secret-key prefix (sk-, sk_live_)": re.compile(r"\bsk(-|_live_|_test_)[A-Za-z0-9_-]{20,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "JSON web token": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
HEX40 = re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{40}(?![0-9a-fA-F])")
PERSONAL_PATH = re.compile(r"(?i)\b[A-Z]:(?:\\|/)+Users(?:\\|/)+[^\\/\s\"']+|(?<![\w.])/(home|Users)/[A-Za-z][\w.-]+")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
ALLOWED_EMAIL = re.compile(r"(?i)^(noreply|no-reply)@|@users\.noreply\.github\.com$|@example\.(com|org|invalid)$")
MD_LINK = re.compile(r"\[(?:[^\]\[]|\[[^\]]*\])*\]\(\s*<?((?:[^()\s<>]|\([^()\s]*\))+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
MD_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^()\s<>]+)>?")
MD_REFDEF = re.compile(r"(?m)^ {0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$")
HTML_REF = re.compile(r"""(?i)\b(?:src|href|srcset)\s*=\s*["']([^"']+)["']""")
HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.check}] {self.path}: {self.detail}"


def _directory_reason(rel_dir: str) -> str | None:
    """Reason a directory (POSIX path ending in '/') is excluded, else None."""
    name = rel_dir.rstrip("/").split("/")[-1]
    if name in ANY_DEPTH_DIRS:
        return ANY_DEPTH_DIRS[name]
    if "/" not in rel_dir.rstrip("/") and name in ROOT_DIRS:
        return ROOT_DIRS[name]
    if fnmatch.fnmatchcase(name, "*.egg-info"):
        return ANY_DEPTH_NAMES["*.egg-info"]
    if rel_dir.startswith("data/") and rel_dir.count("/") == 2 and rel_dir != "data/public/":
        return DATA_REASONS.get(rel_dir, "local data outside data/public (kept out of the release)")
    return None


def exclusion_reason(rel: str) -> str | None:
    """Reason a repository-relative POSIX file path is excluded from the public release, else None."""
    parts = rel.split("/")
    for depth in range(1, len(parts)):
        reason = _directory_reason("/".join(parts[:depth]) + "/")
        if reason:
            return reason
    if len(parts) == 2 and parts[0] == "data":
        return "local data outside data/public (kept out of the release)"
    if rel in EXCLUDE_FILES:
        return EXCLUDE_FILES[rel]
    for pattern, reason in ANY_DEPTH_NAMES.items():
        if fnmatch.fnmatchcase(parts[-1], pattern):
            return reason
    if parts[-1].lower().endswith(RESTRICTED_SUFFIXES):
        return "restricted or raw-data file type"
    for pattern, reason in DIRECT_PATTERNS.items():
        directory, name = pattern.rsplit("/", 1)
        if "/".join(parts[:-1]) == directory and fnmatch.fnmatchcase(parts[-1], name):
            return reason
    return None


def walk(root: Path = ROOT) -> tuple[list[str], dict[str, str]]:
    """Return (included paths, {excluded path or directory: reason}) without entering excluded trees."""
    included: list[str] = []
    excluded: dict[str, str] = {}
    for current, dirs, files in os.walk(root):
        rel_dir = Path(current).relative_to(root).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        keep = []
        for name in sorted(dirs):
            rel = rel_dir + name + "/"
            reason = SYMLINK if (Path(current) / name).is_symlink() else _directory_reason(rel)
            if reason:
                excluded[rel] = reason
            else:
                keep.append(name)
        dirs[:] = keep
        for name in sorted(files):
            rel = rel_dir + name
            reason = exclusion_reason(rel)
            if reason is None and (Path(current) / name).is_symlink():
                reason = SYMLINK
            if reason:
                excluded[rel] = reason
            else:
                included.append(rel)
    return sorted(included), excluded


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def frozen_entries(root: Path = ROOT) -> dict[str, tuple[str, str]]:
    """{frozen path: (sha256, manifest name)} across every docs/*_freeze.sha256 manifest."""
    entries: dict[str, tuple[str, str]] = {}
    for manifest in sorted((root / "docs").glob("*_freeze.sha256")):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip():
                digest, name = line.split(maxsplit=1)
                entries[name.lstrip("*").strip()] = (digest, manifest.name)
    return entries


def category(rel: str) -> str:
    if rel.startswith(".github/"):
        return "continuous integration"
    if rel.startswith(("analysis/", "audit/", "tools/")):
        return "code"
    if rel.startswith("tests/"):
        return "tests"
    if rel.startswith("data/public/"):
        return "public aggregate data"
    if rel.startswith("assets/"):
        return "figure"
    if rel.startswith("docs/") and not rel.endswith(".md"):
        return "research record"
    if rel.endswith((".md", ".cff")):
        return "documentation"
    return "configuration"


def licence_class(rel: str) -> str:
    """Proposed licence class; see docs/licensing_and_attribution.md section 4."""
    if rel.startswith("data/public/m11/"):
        return "derived data: HFD CC BY 4.0 attribution; NCHS and Census sources"
    if rel.startswith("data/public/m10/"):
        return "derived data: Census ACS and CDC WONDER natality terms"
    if rel.startswith("data/public/nsfg_m09/"):
        return "derived data: NCHS NSFG data-use terms"
    if rel == "data/public/dashboard_summary.json":
        return "derived data: NLSY97 (BLS) public-use terms"
    if rel.startswith("data/public/"):
        return "derived data: mixed sources (all of the above)"
    if rel.startswith("docs/source_terms/"):
        return "third-party terms quoted for the record"
    if rel.startswith("assets/figures/m11_") or rel.startswith("assets/readme/"):
        return "project figure with HFD-derived values (CC BY 4.0 attribution)"
    if rel.startswith("assets/"):
        return "project figure"
    if category(rel) in ("code", "tests", "continuous integration", "configuration"):
        return "project code"
    return "project documentation"


def inventory_rows(root: Path = ROOT) -> list[dict[str, str]]:
    included, _ = walk(root)
    frozen = frozen_entries(root)
    return [{"path": rel, "category": category(rel), "frozen_manifest": frozen.get(rel, ("", ""))[1],
             "licence_class": licence_class(rel)} for rel in included if rel != INVENTORY]


def render_inventory(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["path", "category", "frozen_manifest", "licence_class"],
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def check_inventory(root: Path = ROOT) -> list[Finding]:
    path = root / INVENTORY
    if not path.exists():
        return [Finding("inventory", INVENTORY, "missing; run python -m tools.release inventory --write")]
    expected = render_inventory(inventory_rows(root))
    actual = path.read_text(encoding="utf-8")
    if actual == expected:
        return []
    listed = {row["path"] for row in csv.DictReader(io.StringIO(actual))}
    present = {row["path"] for row in csv.DictReader(io.StringIO(expected))}
    findings = [Finding("inventory", p, "present but not in the inventory") for p in sorted(present - listed)]
    findings += [Finding("inventory", p, "listed but absent or excluded") for p in sorted(listed - present)]
    return findings or [Finding("inventory", INVENTORY, "classification columns out of date")]


def check_symlinks(root: Path = ROOT) -> list[Finding]:
    return [Finding("disclosure", rel, SYMLINK) for rel, reason in walk(root)[1].items() if reason == SYMLINK]


def check_frozen(root: Path = ROOT, included: list[str] | None = None) -> list[Finding]:
    included_set = set(included if included is not None else walk(root)[0])
    findings = []
    for rel, (digest, manifest) in sorted(frozen_entries(root).items()):
        if rel not in included_set:
            findings.append(Finding("frozen", rel, f"frozen in {manifest} but excluded from the release"))
        elif sha256(root / rel) != digest:
            findings.append(Finding("frozen", rel, f"hash differs from {manifest}"))
    for manifest in sorted((root / "docs").glob("*_freeze.sha256")):
        if manifest.relative_to(root).as_posix() not in included_set:
            findings.append(Finding("frozen", manifest.name, "manifest excluded from the release"))
    return findings


def csv_header(text: str) -> set[str]:
    first = text.lstrip("﻿").splitlines()[0] if text.strip() else ""
    return {cell.strip().strip('"').strip("'").lower() for cell in re.split(r"[,;\t|]", first)}


def scan_text(rel: str, text: str) -> list[Finding]:
    findings = []
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(line):
                findings.append(Finding("secret", rel, f"line {number}: possible {label}"))
        if not rel.endswith(".sha256") and "uses:" not in line and HEX40.search(line):
            findings.append(Finding("secret", rel, f"line {number}: 40-character hex string (possible API key)"))
        if PERSONAL_PATH.search(line):
            findings.append(Finding("privacy", rel, f"line {number}: personal filesystem path"))
        for email in EMAIL.findall(line):
            if not ALLOWED_EMAIL.search(email):
                findings.append(Finding("privacy", rel, f"line {number}: e-mail address"))
    if rel.endswith(".csv") and lines:
        header = csv_header(text)
        flagged = sorted(c for c in header if c in RESPONDENT_COLUMNS or RESPONDENT_PATTERN.match(c))
        if flagged:
            findings.append(Finding("disclosure", rel, f"respondent-level column(s) {flagged}"))
    return findings


def scan_binary(rel: str, data: bytes) -> list[Finding]:
    """Metadata chunks of images can carry paths or e-mail addresses; scan the raw bytes for them."""
    text = data.decode("latin-1")
    findings = []
    if PERSONAL_PATH.search(text):
        findings.append(Finding("privacy", rel, "personal filesystem path in binary metadata"))
    if any(not ALLOWED_EMAIL.search(e) for e in EMAIL.findall(text)):
        findings.append(Finding("privacy", rel, "e-mail address in binary metadata"))
    return findings


def check_content(root: Path = ROOT, included: list[str] | None = None) -> list[Finding]:
    findings = []
    for rel in included if included is not None else walk(root)[0]:
        lower = rel.lower()
        if lower.endswith(RESTRICTED_SUFFIXES) or lower.endswith((".do", ".zip", ".7z")):
            findings.append(Finding("disclosure", rel, "restricted or raw-data file type"))
            continue
        if lower.endswith(BINARY_SUFFIXES):
            findings += scan_binary(rel, (root / rel).read_bytes())
            continue
        if not (lower.endswith(TEXT_SUFFIXES) or Path(rel).name in TEXT_NAMES):
            findings.append(Finding("disclosure", rel, "unrecognised file type; add it to the release rules"))
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(Finding("disclosure", rel, "not valid UTF-8 text"))
            continue
        findings += scan_text(rel, text)
    return findings


def github_slug(heading: str) -> str:
    text = re.sub(r"<[^>]+>", "", heading)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(\*{1,3}|_{1,3})(?=\S)(.+?)(?<=\S)\1", r"\2", text)
    text = text.replace("`", "").strip().lower()
    text = "".join(ch for ch in text if ch in " -_" or unicodedata.category(ch)[0] in "LNM")
    return text.replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Heading anchors as GitHub generates them, plus explicit <a name/id> anchors."""
    found: set[str] = set()
    counts: dict[str, int] = {}
    fence: str | None = None
    lines = text.splitlines()

    def add(title: str) -> None:
        slug = github_slug(title)
        n = counts.get(slug, 0)
        counts[slug] = n + 1
        found.add(slug if n == 0 else f"{slug}-{n}")

    for index, line in enumerate(lines):
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not line.strip().strip(token[0]):
                fence = None
            continue
        if fence:
            continue
        match = HEADING.match(line)
        if match:
            add(match.group(2))
        elif (line.strip() and index + 1 < len(lines) and re.match(r"^ {0,3}(=+|-+)\s*$", lines[index + 1])
              and not re.match(r"^ {0,3}([-*+]|\d+[.)])\s|^ {0,3}[|>]", line)):
            add(line.strip())
    found.update(re.findall(r"""<a\s+(?:name|id)=["']([^"']+)["']""", text))
    return found


def _targets(text: str) -> list[str]:
    body = re.sub(r"(?ms)^ {0,3}(`{3,}|~{3,}).*?^ {0,3}\1", "", text)
    body = re.sub(r"`[^`\n]*`", "", body)
    refs = MD_LINK.findall(body) + MD_IMAGE.findall(body) + MD_REFDEF.findall(body)
    for value in HTML_REF.findall(body):
        refs += [part.strip().split()[0] for part in value.split(",") if part.strip()]
    return refs


def check_links(root: Path = ROOT, included: list[str] | None = None) -> list[Finding]:
    included_set = set(included if included is not None else walk(root)[0])
    cache: dict[str, set[str]] = {}
    findings = []
    for rel in sorted(p for p in included_set if p.endswith(".md")):
        text = (root / rel).read_text(encoding="utf-8")
        for target in sorted(set(_targets(text))):
            if re.match(r"(?i)^(https?:|mailto:|data:)", target):
                continue
            path_part, _, fragment = target.partition("#")
            path_part, fragment = unquote(path_part), unquote(fragment)
            if path_part:
                resolved = os.path.normpath(os.path.join(os.path.dirname(rel), path_part)).replace("\\", "/")
                if resolved == ".." or resolved.startswith("../"):
                    findings.append(Finding("links", rel, f"link leaves the repository: {target}"))
                    continue
                is_dir = any(p.startswith(resolved.rstrip("/") + "/") for p in included_set)
                if resolved not in included_set and not is_dir:
                    findings.append(Finding("links", rel, f"target not in the release: {target}"))
                    continue
            else:
                resolved = rel
            if fragment and resolved.endswith(".md"):
                if resolved not in cache:
                    cache[resolved] = anchors((root / resolved).read_text(encoding="utf-8"))
                if fragment not in cache[resolved] and fragment.lower() not in cache[resolved]:
                    findings.append(Finding("links", rel, f"anchor not found: {target}"))
    return findings


GIT_PROTECTED = ("text", "eol", "filter", "ident", "working-tree-encoding")


def check_gitattributes(root: Path = ROOT) -> list[Finding]:
    """The first rule must unset conversion attributes for every path, and no later rule may set them."""
    path = root / ".gitattributes"
    if not path.exists():
        return [Finding("git", ".gitattributes", "missing")]
    rules = [line.split() for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    findings = []
    if not rules or rules[0][0] != "*" or not {f"-{a}" for a in GIT_PROTECTED} <= set(rules[0][1:]):
        findings.append(Finding("git", ".gitattributes", "first rule must be: * " + " ".join(f"-{a}" for a in GIT_PROTECTED)))
    for rule in rules[1:]:
        for attr in rule[1:]:
            name = attr.lstrip("!").split("=")[0]
            if name in GIT_PROTECTED and not attr.startswith("-"):
                findings.append(Finding("git", ".gitattributes", f"rule '{' '.join(rule)}' re-enables {name}"))
    return findings


def run_checks(root: Path = ROOT) -> list[tuple[str, list[Finding]]]:
    included, _ = walk(root)
    return [("inventory matches the working tree", check_inventory(root)),
            ("frozen files present with their manifest hashes", check_frozen(root, included)),
            ("content scan: credentials, personal data, restricted files", check_content(root, included)
             + check_symlinks(root)),
            ("relative links and anchors resolve within the release", check_links(root, included)),
            ("Git attributes preserve file bytes", check_gitattributes(root))]


LIVE_RUN_RECORD = "data/public/m11/forecast/m11_run_record.json"
FROZEN_RUN_RECORD = "docs/m11_frozen_run_record.json"


def restore_run_record(root: Path = ROOT) -> str:
    """Copy the frozen M11 run record to its live, gitignored location after verifying its frozen hash.

    tests/test_m11_forecast.py (frozen) reads the live record, which is excluded from the release
    because every run rewrites it. At the freeze the two files were byte-identical.
    """
    live, frozen = root / LIVE_RUN_RECORD, root / FROZEN_RUN_RECORD
    entry = frozen_entries(root).get(FROZEN_RUN_RECORD)
    if entry is None or not frozen.exists():
        raise ValueError(f"{FROZEN_RUN_RECORD} is missing or not listed in a freeze manifest")
    digest = entry[0]
    if sha256(frozen) != digest:
        raise ValueError(f"{FROZEN_RUN_RECORD} does not match its freeze manifest")
    if live.exists():
        return "unchanged" if sha256(live) == digest else "kept (differs: written by a local rerun)"
    live.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=live.parent, prefix=".run_record_")
    os.close(handle)
    try:
        shutil.copyfile(frozen, temporary)
        os.replace(temporary, live)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return "restored"


def stage(dest: Path, root: Path = ROOT, checked: bool = True) -> list[str]:
    """Run every release check, then copy the release files byte for byte into dest (which must not exist)."""
    if dest.exists():
        raise FileExistsError(f"{dest} already exists")
    if dest.resolve().is_relative_to(root.resolve()):
        raise ValueError("the staging directory must be outside the repository")
    if checked:
        failures = [str(f) for _, findings in run_checks(root) for f in findings]
        if failures:
            raise RuntimeError("release checks failed:\n" + "\n".join(failures[:50]))
    included, _ = walk(root)
    for rel in included:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, target)
    return included


def write_archive(source: Path, archive: Path, files: list[str]) -> str:
    """Deterministic ZIP of files under source, with ARCHIVE_MANIFEST.sha256; returns the archive SHA-256.

    Entry order, timestamps, permissions and the creating system are fixed, so the same files give
    the same archive bytes given the same zlib build.
    """
    manifest = "".join(f"{sha256(source / rel)}  {rel}\n" for rel in files)
    entries = [(rel, (source / rel).read_bytes()) for rel in files]
    entries.append(("ARCHIVE_MANIFEST.sha256", manifest.encode("utf-8")))
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for rel, data in sorted(entries):
            info = zipfile.ZipInfo(f"{ARCHIVE_PREFIX}/{rel}", date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            handle.writestr(info, data)
    return sha256(archive)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Public-release tooling for The Intention Gap")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    inv = sub.add_parser("inventory")
    inv.add_argument("--write", action="store_true")
    sub.add_parser("excluded")
    sub.add_parser("restore-run-record")
    stg = sub.add_parser("stage")
    stg.add_argument("dest", type=Path)
    stg.add_argument("--archive", type=Path)
    args = parser.parse_args(argv)

    if args.command == "check":
        failed = 0
        for name, findings in run_checks():
            print(f"{'PASS' if not findings else 'FAIL'}  {name}" + (f" ({len(findings)} finding(s))" if findings else ""))
            for finding in findings[:50]:
                print(f"      {finding}")
            failed += bool(findings)
        included, _ = walk()
        print(f"release files: {len(included)}; frozen files: {len(frozen_entries())}")
        return 1 if failed else 0
    if args.command == "inventory":
        text = render_inventory(inventory_rows())
        if args.write:
            (ROOT / INVENTORY).write_bytes(text.encode("utf-8"))
            print(f"wrote {INVENTORY} ({text.count(chr(10)) - 1} files)")
        else:
            sys.stdout.write(text)
        return 0
    if args.command == "excluded":
        for rel, reason in sorted(walk()[1].items()):
            print(f"{rel}\t{reason}")
        return 0
    if args.command == "restore-run-record":
        try:
            print(f"{LIVE_RUN_RECORD}: {restore_run_record()}")
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        return 0
    try:
        files = stage(args.dest)
    except (RuntimeError, ValueError, FileExistsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"staged {len(files)} files in {args.dest}")
    if args.archive:
        print(f"archive {args.archive} sha256 {write_archive(args.dest, args.archive, files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
