"""Check every frozen-chapter manifest (docs/*_freeze.sha256) against the files on disk.

Each manifest uses the `sha256sum` format ("<hash>  <relative path>"), so
`sha256sum -c docs/<chapter>_freeze.sha256` gives the same answer. Any missing
or changed file is a failure: editing a frozen file needs a new, recorded
decision and a new manifest.

    python audit/verify_freeze.py              all manifests
    python audit/verify_freeze.py docs/m10_freeze.sha256
"""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_manifest(path: Path) -> list[tuple[str, str]]:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        entries.append((digest, name.lstrip("*").strip()))
    if not entries:
        raise ValueError(f"Empty manifest: {path}")
    return entries


def check_manifest(path: Path, root: Path = ROOT) -> dict:
    missing, changed = [], []
    entries = read_manifest(path)
    for digest, name in entries:
        target = root / name
        if not target.is_file():
            missing.append(name)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            changed.append(name)
    return {"manifest": path.name, "files": len(entries), "missing": missing,
            "changed": changed, "ok": not missing and not changed}


def manifests(root: Path = ROOT) -> list[Path]:
    return sorted((root / "docs").glob("*_freeze.sha256"))


def main(argv: list[str] | None = None) -> int:
    paths = [Path(a) for a in (argv if argv is not None else sys.argv[1:])] or manifests()
    if not paths:
        print("No freeze manifests found")
        return 2
    failures = 0
    for path in paths:
        result = check_manifest(path if path.is_absolute() else ROOT / path)
        status = "OK" if result["ok"] else "FAILED"
        print(f"{result['manifest']}: {result['files']} files {status}"
              + (f"; missing {result['missing']}" if result["missing"] else "")
              + (f"; changed {result['changed']}" if result["changed"] else ""))
        failures += not result["ok"]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
