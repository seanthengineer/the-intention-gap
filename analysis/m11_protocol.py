"""M11 forecasting protocol: configuration loading and the hash lock.

docs/m11_forecast_protocol.md holds the protocol and, between the
<!-- config:start --> and <!-- config:end --> markers, the JSON settings every
M11 forecasting module uses. docs/m11_protocol_lock.json records the file's
SHA-256, when it was locked, and every amendment. Forecasting code calls
verify_lock() first and stops if the protocol has changed since the lock.

The lock is internal: it shows the file has not changed since the recorded
time on this machine. It is not an external preregistration.

    python -m analysis.m11_protocol --lock                 # once, before any model is fitted
    python -m analysis.m11_protocol --status
    python -m analysis.m11_protocol --amend "reason" [--results-seen]
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = PROJECT_ROOT / "docs" / "m11_forecast_protocol.md"
LOCK_PATH = PROJECT_ROOT / "docs" / "m11_protocol_lock.json"
CONFIG_PATTERN = re.compile(r"<!-- config:start -->\s*```json\s*(\{.*?\})\s*```\s*<!-- config:end -->", re.S)
STATE = ("No forecasting model fitted and no forecast error, backtest metric, interval coverage or "
         "cohort projection computed before locking; HFD series inspected descriptively in the "
         "feasibility stage; internal lock, not external preregistration")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def protocol_sha(path: Path = PROTOCOL_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = PROTOCOL_PATH) -> dict:
    match = CONFIG_PATTERN.search(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{path.name}: configuration block not found")
    return json.loads(match.group(1))


def read_lock(path: Path = LOCK_PATH) -> dict:
    if not path.exists():
        raise SystemExit(f"{path.name} not found: lock the protocol before fitting any model")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_lock(protocol: Path = PROTOCOL_PATH, lock_path: Path = LOCK_PATH) -> dict:
    """Return the lock record, or stop if the protocol differs from its locked hash."""
    lock = read_lock(lock_path)
    digest = protocol_sha(protocol)
    if digest != lock["sha256"]:
        raise SystemExit(f"{protocol.name} does not match its lock ({digest[:12]} vs {lock['sha256'][:12]}); "
                         "record an amendment with `python -m analysis.m11_protocol --amend` first")
    return lock


def create_lock(protocol: Path = PROTOCOL_PATH, lock_path: Path = LOCK_PATH, drafted_utc: str = "") -> dict:
    if lock_path.exists():
        raise SystemExit(f"{lock_path.name} already exists; use --amend to change the protocol")
    load_config(protocol)                       # a protocol without a readable config cannot be locked
    lock = {"protocol": protocol.relative_to(PROJECT_ROOT).as_posix() if protocol.is_relative_to(PROJECT_ROOT)
            else protocol.name, "sha256": protocol_sha(protocol), "drafted_utc": drafted_utc,
            "locked_utc": utc_now(), "state": STATE, "amendments": []}
    lock_path.write_text(json.dumps(lock, indent=1) + "\n", encoding="utf-8")
    return lock


def amend(reason: str, results_seen: bool, protocol: Path = PROTOCOL_PATH, lock_path: Path = LOCK_PATH) -> dict:
    lock = read_lock(lock_path)
    digest = protocol_sha(protocol)
    if digest == lock["sha256"]:
        raise SystemExit("protocol unchanged; nothing to amend")
    load_config(protocol)
    lock["amendments"].append({"utc": utc_now(), "previous_sha256": lock["sha256"], "sha256": digest,
                               "reason": reason, "forecast_results_seen": bool(results_seen)})
    lock["sha256"] = digest
    lock_path.write_text(json.dumps(lock, indent=1) + "\n", encoding="utf-8")
    return lock


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", action="store_true")
    parser.add_argument("--drafted", default="", help="UTC time the protocol was drafted")
    parser.add_argument("--amend")
    parser.add_argument("--results-seen", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    if args.lock:
        lock = create_lock(drafted_utc=args.drafted)
    elif args.amend:
        lock = amend(args.amend, args.results_seen)
    else:
        lock = verify_lock()
    print(json.dumps(lock, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
