"""Pyright policy check against the recorded diagnostic baseline.

Frozen research modules carry Pyright errors, almost all from pandas and NumPy union return types
(docs/environment_and_code_quality.md section 5). They are recorded here, not suppressed and not
edited. The check is a ratchet:
- publication tooling (tools/ and tests/test_release_tools.py) must report no error or warning;
- every other file must report exactly its baseline number of errors, so that a new error fails
  and a fixed error requires the baseline to be lowered with --update;
- the Pyright version must match the version that recorded the baseline.

    python -m tools.pyright_baseline              compare with tools/pyright_baseline.json
    python -m tools.pyright_baseline --update     rewrite the baseline (refused if tooling has findings)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tools" / "pyright_baseline.json"
STRICT_PREFIXES = ("tools/", "tests/test_release_tools.py")


def pyright_command() -> list[str]:
    exe = shutil.which("pyright")
    return [exe] if exe else [sys.executable, "-m", "pyright"]


def run_pyright() -> dict:
    command = pyright_command() + ["--outputjson", "--pythonpath", sys.executable,
                                   "-p", str(ROOT / "pyrightconfig.json")]
    try:
        result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    except FileNotFoundError as error:
        raise RuntimeError("pyright is not installed; run: python -m pip install -r requirements-dev.txt") from error
    start = result.stdout.find("{")
    try:
        return json.loads(result.stdout[start:] if start >= 0 else "")
    except json.JSONDecodeError as error:
        raise RuntimeError(f"pyright produced no JSON report (exit {result.returncode}): "
                           f"{(result.stderr or result.stdout)[:400]}") from error


def relative(file: str) -> str:
    path = Path(file.replace("\\", "/"))
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        text = path.as_posix()
        marker = "/" + ROOT.name + "/"
        return text.split(marker, 1)[1] if marker in text else text


def counts(report: dict) -> tuple[Counter, Counter]:
    """(errors per file, warnings per file) as repository-relative POSIX paths."""
    errors: Counter = Counter()
    warnings: Counter = Counter()
    for diagnostic in report.get("generalDiagnostics", []):
        target = errors if diagnostic.get("severity") == "error" else warnings
        if diagnostic.get("severity") in ("error", "warning"):
            target[relative(diagnostic["file"])] += 1
    return errors, warnings


def compare(errors: Counter, baseline: dict[str, int], warnings: Counter | None = None) -> list[str]:
    problems = []
    for rel, n in sorted((errors + (warnings or Counter())).items()):
        if rel.startswith(STRICT_PREFIXES):
            problems.append(f"{rel}: {n} diagnostic(s); publication tooling must have none")
    for rel in sorted(set(errors) | set(baseline)):
        if rel.startswith(STRICT_PREFIXES):
            continue
        current, recorded = errors.get(rel, 0), baseline.get(rel, 0)
        if current > recorded:
            problems.append(f"{rel}: {current} error(s), baseline {recorded} (new errors)")
        elif current < recorded:
            problems.append(f"{rel}: {current} error(s), baseline {recorded} (fixed; lower the baseline with --update)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pyright diagnostic baseline check")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_pyright()
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    errors, warnings = counts(report)
    version = report.get("version", "unknown")
    strict = compare(Counter({k: v for k, v in errors.items() if k.startswith(STRICT_PREFIXES)}), {}, warnings)
    if args.update:
        if strict:
            print("refused: publication tooling has diagnostics:\n  " + "\n  ".join(strict), file=sys.stderr)
            return 1
        BASELINE.write_text(json.dumps({"pyright": version, "total_errors": sum(errors.values()),
                                        "files": dict(sorted(errors.items()))}, indent=1) + "\n",
                            encoding="utf-8", newline="\n")
        print(f"baseline written: {sum(errors.values())} errors in {len(errors)} files (pyright {version})")
        return 0
    recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
    problems = compare(errors, recorded["files"], warnings)
    if version != recorded["pyright"]:
        problems.insert(0, f"pyright {version} differs from the baseline's {recorded['pyright']}; "
                           "install requirements-dev.txt")
    print(f"pyright {version}: {sum(errors.values())} errors in {len(errors)} files; "
          f"baseline {recorded['total_errors']} (pyright {recorded['pyright']})")
    for line in problems:
        print(f"  FAIL {line}")
    print("PASS" if not problems else "FAIL")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
