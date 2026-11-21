"""Verification of the final synthesis (claim tracing, independent recomputation, release safety).

Every check is labelled with its kind:

- INDEPENDENT: recomputed here from raw or processed inputs with code that shares
  nothing with analysis/ or the chapter verifiers (own estimators, own parsing).
- RECONCILIATION: compares a reported value with the stored frozen output or
  frozen chapter text it claims to come from.
- REPRODUCIBILITY: re-runs project code and compares with stored outputs.
  This shows determinism, not correctness.

Respondent-level inputs are read in memory and only aggregates are printed.

    python audit/verify_final_synthesis.py [--require-data] [--archive PATH]
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "final_claim_evidence_matrix.csv"
SYNTHESIS_DOCS = [ROOT / "docs" / name for name in
                  ("final_synthesis_manuscript.md", "final_executive_summary.md", "final_limitations_register.md")]
NOMINAL_TOKENS = {"0%", "50%", "100%", "80%", "95%", "30%", "1,000"}
CLAIM_ID = re.compile(r"\[?\bC\d{2}\.\d{1,2}[a-z]?\b\]?")
NUMBER = re.compile(
    r"(?<![\w.,/-])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?(?!\w|\.\d)"
    r"|(?<![\w.,/])-?\d+\.\d+%?(?!\w|\.\d)"
    r"|(?<![\w.,/])-?\d+%(?!\w)")
MINUS = str.maketrans({"−": "-", "‒": "-"})


def _normalise(token: str) -> str:
    return token.translate(MINUS)


def numbers_in(text: str) -> set:
    """Material numeric tokens: decimals, percentages and thousands-separated counts."""
    text = CLAIM_ID.sub(" ", text.translate(MINUS))
    text = re.sub(r"https?://\S+|\b10\.\d{4,}/\S+", " ", text)
    text = re.sub(r"(?m)^(#+\s*)\d+(?:\.\d+)*\.?", r"\1", text)
    text = re.sub(r"\b[\w./-]*[A-Za-z_][\w./-]*\.(?:py|csv|json|md|png|txt|zip|sha256)\b", " ", text)
    return {m.group(0) for m in NUMBER.finditer(text)}


def _number(token: str) -> tuple[float, int]:
    token = _normalise(token).strip().rstrip("%").replace(",", "")
    decimals = len(token.split(".")[1]) if "." in token else 0
    return float(token), decimals


def matches(reported: float, value: float, scale: float = 1.0, decimals: int = 2) -> bool:
    """True if value * scale rounds to the reported figure at its printed precision."""
    return abs(value * scale - reported) <= 0.5 * 10 ** (-decimals) + 1e-9


def _json_get(path: Path, spec: str):
    value = json.loads(path.read_text(encoding="utf-8"))
    for part in re.findall(r"[^.\[\]]+|\[[^\]]+\]", spec):
        if part.startswith("["):
            inner = part[1:-1]
            if "=" in inner:
                key, wanted = inner.split("=", 1)
                hits = [item for item in value if str(item.get(key)) == wanted]
                if len(hits) != 1:
                    raise ValueError(f"{path.name}: [{inner}] matched {len(hits)} items")
                value = hits[0]
            else:
                value = value[int(inner)]
        else:
            value = value[part]
    return value


def _csv_get(path: Path, spec: str):
    filters, column = spec.rsplit("|", 1)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for clause in filter(None, filters.split(";")):
        key, wanted = clause.split("=", 1)
        rows = [r for r in rows if r[key] == wanted or _same_number(r[key], wanted)]
    if len(rows) != 1:
        raise ValueError(f"{path.name}: {filters} matched {len(rows)} rows")
    return float(rows[0][column])


def _same_number(a: str, b: str) -> bool:
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def resolve(path: Path, locator: str):
    """Value named by a locator: json:<path>, csv:<col=val;...>|<column>, text:<verbatim substring>,
    ratio:<locator> // <locator>. A leading @<relative file>:: overrides the file."""
    if locator.startswith("@"):
        file, locator = locator[1:].split("::", 1)
        path = ROOT / file
    kind, spec = locator.split(":", 1)
    if kind == "json":
        return _json_get(path, spec)
    if kind == "csv":
        return _csv_get(path, spec)
    if kind == "text":
        if spec not in path.read_text(encoding="utf-8"):
            raise ValueError(f"{path.name}: text not found: {spec[:60]}")
        return True
    if kind == "ratio":
        top, bottom = (s.strip() for s in spec.split(" // "))
        return resolve(path, top) / resolve(path, bottom)
    raise ValueError(f"unknown locator kind {kind}")


def load_matrix() -> pd.DataFrame:
    return pd.read_csv(MATRIX, dtype=str, keep_default_na=False)


def _parse_check(entry: str):
    reported, locator = (s.strip() for s in entry.split(" ~ ", 1))
    scale = 1.0
    if locator.startswith("x") and " " in locator and locator[1].isdigit():
        factor, locator = locator.split(" ", 1)
        scale = float(factor[1:])
    return reported, scale, locator


def check_matrix() -> list:
    """Every check of every matrix row: the reported figure must equal its source at printed precision."""
    results = []
    for row in load_matrix().itertuples(index=False):
        source = ROOT / row.source_file
        entries = [e for e in row.checks.split(" && ") if e.strip()]
        if not entries:
            results.append({"claim_id": row.claim_id, "check": "", "ok": False, "detail": "no checks"})
        for entry in entries:
            try:
                reported, scale, locator = _parse_check(entry)
                value = resolve(source, locator)
                if value is True:
                    if reported == "-":
                        ok = True
                    else:
                        number, decimals = _number(reported)
                        passage = locator.split("text:", 1)[1].translate(MINUS)
                        candidates = [float(t.replace(",", "")) for t in
                                      re.findall(r"-?\d[\d,]*(?:\.\d+)?", passage)]
                        ok = any(matches(number, c, scale, decimals) for c in candidates)
                    detail = "text present"
                else:
                    number, decimals = _number(reported)
                    ok = matches(number, float(value), scale, decimals)
                    detail = f"source {float(value) * scale:.6g}"
            except (ValueError, KeyError, IndexError, StopIteration, FileNotFoundError) as error:
                ok, detail = False, f"{type(error).__name__}: {error}"
            results.append({"claim_id": row.claim_id, "check": entry[:90], "ok": bool(ok), "detail": detail})
    return results


def traced_tokens() -> set:
    tokens = set(NOMINAL_TOKENS)
    for checks in load_matrix()["checks"]:
        for entry in filter(str.strip, checks.split(" && ")):
            reported = _normalise(entry.split(" ~ ", 1)[0].strip())
            tokens |= {reported, reported.lstrip("-"), reported.rstrip("%"), reported.lstrip("-").rstrip("%")}
    return tokens


def untraced_numbers() -> dict:
    """Numbers in the synthesis documents that match no verified matrix figure."""
    traced = traced_tokens()
    missing = {}
    for doc in SYNTHESIS_DOCS:
        found = sorted(t for t in numbers_in(doc.read_text(encoding="utf-8"))
                       if not {t, t.lstrip("-"), t.rstrip("%"), t.lstrip("-").rstrip("%")} & traced)
        if found:
            missing[doc.name] = found
    return missing


def unknown_claim_ids() -> set:
    known = set(load_matrix()["claim_id"])
    cited = set()
    for doc in SYNTHESIS_DOCS:
        cited |= {m.strip("[]") for m in CLAIM_ID.findall(doc.read_text(encoding="utf-8"))}
    return cited - known


def _average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    ranks = np.empty(len(values))
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and sorted_values[end + 1] == sorted_values[start]:
            end += 1
        ranks[order[start:end + 1]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def independent_nlsy97() -> dict:
    frame = pd.read_csv(ROOT / "data" / "processed" / "intention_gap_cohort.csv",
                        usecols=["outcome", "expectation_prob"]).dropna(subset=["outcome"])
    y, p = frame["outcome"].to_numpy(float), frame["expectation_prob"].to_numpy(float)
    ranks = _average_ranks(p)
    n1, n0 = int(y.sum()), int(len(y) - y.sum())
    auc = (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    slope = np.sum((p - p.mean()) * (y - y.mean())) / np.sum((p - p.mean()) ** 2)
    return {"n": len(y), "brier": float(np.mean((p - y) ** 2)), "auc": float(auc), "slope": float(slope),
            "at_0": float(y[p == 0].mean()), "at_100": float(y[p == 1].mean())}


def independent_nsfg() -> dict:
    base = ROOT / "data" / "raw" / "nsfg_2022_2023"
    parts = []
    for file in (base / "female" / "NSFG_2022_2023_FemRespPUFData.csv",
                 base / "male" / "NSFG_2022_2023_MaleRespPUFData.csv"):
        parts.append(pd.read_csv(file, usecols=["RWANT", "INTENT", "AGER", "YEAR", "WGT2022_2023"]))
    f = pd.concat(parts, ignore_index=True)
    upper = np.where(f["YEAR"] == 1, 26, np.where(f["YEAR"] == 2, 27, -1))
    cohort = f[(f["AGER"] >= 18) & (f["AGER"] <= upper)]
    w = cohort["WGT2022_2023"].to_numpy(float)
    wants = (cohort["RWANT"] == 1).to_numpy()
    share = lambda mask, within: float(w[mask & within].sum() / w[within].sum())  # noqa: E731
    everyone = np.ones(len(cohort), dtype=bool)
    return {"n": len(cohort), "wanters": int(wants.sum()), "wants": share(wants, everyone),
            "intends": share((cohort["INTENT"] == 1).to_numpy(), everyone),
            "divergence": share((cohort["INTENT"] == 2).to_numpy(), wants)}


def independent_m10() -> dict:
    """Least-squares dummy variables (not demeaning) with a hand-built CR1 sandwich."""
    panel = pd.read_csv(ROOT / "data" / "processed" / "m10" / "m10_panel_state_year_age.csv")
    out = {}
    for age in ("20-24", "25-29"):
        d = panel[panel["age_group"] == age].reset_index(drop=True)
        states = sorted(d["state_fips"].unique())
        years = sorted(d["year"].unique())
        x = np.column_stack([np.ones(len(d)), d["burden30_pct"].to_numpy(float)]
                            + [(d["state_fips"] == s).to_numpy(float) for s in states[1:]]
                            + [(d["year"] == t).to_numpy(float) for t in years[1:]])
        y = d["outcome_rate"].to_numpy(float)
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        resid = y - x @ beta
        bread = np.linalg.inv(x.T @ x)
        meat = np.zeros_like(bread)
        for s in states:
            score = x[(d["state_fips"] == s).to_numpy()].T @ resid[(d["state_fips"] == s).to_numpy()]
            meat += np.outer(score, score)
        n, k, g = len(y), x.shape[1], len(states)
        cov = bread @ meat @ bread * g / (g - 1) * (n - 1) / (n - k)
        se = float(np.sqrt(cov[1, 1]))
        t = float(stats.t.ppf(0.975, g - 1))
        out[age] = {"estimate": 10 * beta[1], "se": 10 * se, "ci_low": 10 * (beta[1] - t * se),
                    "ci_high": 10 * (beta[1] + t * se), "n": n, "k": k}
    return out


def _hfd(name: str) -> pd.DataFrame:
    text = (ROOT / "data" / "raw" / "hfd_usa" / f"{name}.txt").read_text(encoding="utf-8")
    frame = pd.read_csv(io.StringIO(text), sep=r"\s+", skiprows=2, dtype=str)
    for column in frame.columns:
        if column != "Cohort":
            frame[column] = pd.to_numeric(frame[column].str.rstrip("+-"), errors="coerce")
    return frame


def independent_m11() -> dict:
    """2024 TFR from raw HFD, the 2040 interval from the public backtest errors, and an
    approximate period-to-cohort projection for the 1995 and 2012 cohorts."""
    rr = _hfd("USAasfrRR")
    vv = _hfd("USAasfrVV")
    rate = rr[rr["Year"] == 2024].set_index("Age")["ASFR"]
    records = pd.read_csv(ROOT / "data" / "public" / "m11" / "forecast" / "m11_fc_tfr_backtest_records.csv")
    errors = records[(records["method"] == "naive") & (records["h"] == 16)]["log_error"].to_numpy(float)
    sigma = float(np.sqrt(np.mean(errors ** 2)))
    tfr = float(rate.sum())
    z80, z95 = stats.norm.ppf(0.9), stats.norm.ppf(0.975)
    out = {"tfr_2024": tfr, "errors_h16": len(errors), "lower80": tfr * np.exp(-z80 * sigma),
           "upper80": tfr * np.exp(z80 * sigma), "lower95": tfr * np.exp(-z95 * sigma),
           "upper95": tfr * np.exp(z95 * sigma)}
    vv["Cohort"] = pd.to_numeric(vv["Cohort"].str.rstrip("+-"), errors="coerce")
    ratio = {}
    for age in range(13, 56):
        cells = []
        for year in range(2020, 2025):
            period = rr[rr["Year"] == year].set_index("Age")["ASFR"]
            t1 = (period.get(age - 1, 0.0) + period.get(age, 0.0)) / 2
            cell = vv[(vv["Year"] == year) & (vv["ARDY"] == age)]["ASFR"]
            if t1 > 0 and len(cell):
                cells.append(float(cell.iloc[0]) / t1)
        ratio[age] = float(np.mean(cells)) if cells else 1.0
    for cohort in (1995, 2012):
        observed = float(vv[(vv["Cohort"] == cohort) & (vv["Year"] <= 2024)]["ASFR"].sum())
        t1 = sum((rate.get(y - cohort - 1, 0.0) + rate.get(y - cohort, 0.0)) / 2 for y in range(2025, 2041))
        t2 = sum((rate.get(y - cohort - 1, 0.0) + rate.get(y - cohort, 0.0)) / 2 * ratio.get(y - cohort, 1.0)
                 for y in range(2025, 2041))
        out[f"cohort_{cohort}"] = {"observed_2024": observed, "t1": observed + t1, "t2": observed + t2}
    return out


def manifest_hashes() -> dict:
    """Own SHA-256 pass over every docs/*_freeze.sha256 manifest (separate from audit/verify_freeze.py)."""
    status = {}
    for manifest in sorted((ROOT / "docs").glob("*_freeze.sha256")):
        bad = 0
        lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in lines:
            digest, name = line.split(maxsplit=1)
            path = ROOT / name.lstrip("*")
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                bad += 1
        status[manifest.name] = (len(lines), bad)
    return status


def provenance_hashes(raw_dir: Path | None = None) -> dict:
    """Re-hash every raw file whose SHA-256 is recorded in a data/raw/*/provenance.json.

    Returns {folder: (recorded, mismatched, missing)}. A missing file is an input that is
    not present (for example in a source-only package); a mismatch is a file that is present
    with a different hash.
    """
    raw_dir = raw_dir if raw_dir is not None else ROOT / "data" / "raw"
    root = raw_dir.parent.parent
    status = {}
    for record in sorted(raw_dir.glob("*/provenance.json")):
        folder = record.parent
        checked = mismatched = missing = 0

        def walk(node, key=None):
            nonlocal checked, mismatched, missing
            if isinstance(node, dict):
                if "sha256" in node and isinstance(node["sha256"], str):
                    target = root / node["file"] if "file" in node else folder / str(key)
                    checked += 1
                    if not target.is_file():
                        missing += 1
                    elif hashlib.sha256(target.read_bytes()).hexdigest() != node["sha256"]:
                        mismatched += 1
                for child_key, child in node.items():
                    walk(child, child_key)
            elif isinstance(node, list):
                for child in node:
                    walk(child, key)

        walk(json.loads(record.read_text(encoding="utf-8")))
        status[folder.name] = (checked, mismatched, missing)
    return status


def provenance_status(checked: int, mismatched: int, missing: int, require_data: bool) -> str:
    """PASS, FAIL or SKIP for one provenance record. A hash mismatch always fails; inputs that are
    simply absent are skipped only when --require-data is not set."""
    if checked == 0 or mismatched:
        return "FAIL"
    if missing:
        return "FAIL" if require_data else "SKIP"
    return "PASS"


FORBIDDEN_PARTS = ("data/raw/", "data/processed/", ".venv/", "__pycache__/", ".claude/")
FORBIDDEN_NAMES = {"CLAUDE.md", "inspect_data.py", "audit_data.py", ".env", "secrets.toml"}
RESPONDENT_COLUMNS = {"respondent_id", "pubid", "caseid", "r0000100", "household_id", "sidcode"}
SECRET = re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*['\"]?[A-Za-z0-9]{20,}")
HEX40 = re.compile(r"\b[0-9a-f]{40}\b")


def check_archive(path: Path) -> list:
    """Release-safety scan of a review archive: restricted paths, respondent-level columns, secrets."""
    problems = []
    with zipfile.ZipFile(path) as archive:
        files = {(n.split("/", 1)[1] if "/" in n else n): n for n in archive.namelist() if not n.endswith("/")}
        for manifest in sorted((ROOT / "docs").glob("*_freeze.sha256")):
            for line in filter(str.strip, manifest.read_text(encoding="utf-8").splitlines()):
                digest, frozen = line.split(maxsplit=1)
                frozen = frozen.lstrip("*")
                if frozen not in files:
                    problems.append(f"frozen file missing from archive: {frozen}")
                elif hashlib.sha256(archive.read(files[frozen])).hexdigest() != digest:
                    problems.append(f"frozen file differs in archive: {frozen}")
        if "ARCHIVE_MANIFEST.sha256" in files:
            for line in filter(str.strip, archive.read(files["ARCHIVE_MANIFEST.sha256"]).decode("utf-8").splitlines()):
                digest, listed = line.split(maxsplit=1)
                if listed not in files or hashlib.sha256(archive.read(files[listed])).hexdigest() != digest:
                    problems.append(f"archive manifest entry does not match: {listed}")
        else:
            problems.append("ARCHIVE_MANIFEST.sha256 missing")
        if "data/public/m11/forecast/m11_run_record.json" in files:
            problems.append("volatile live run record included")
        for name in archive.namelist():
            inner = name.split("/", 1)[1] if "/" in name else name
            provenance_record = inner.startswith("data/raw/") and inner.count("/") == 3 and inner.endswith("/provenance.json")
            if (any(part in inner for part in FORBIDDEN_PARTS) and not provenance_record) or Path(inner).name in FORBIDDEN_NAMES:
                problems.append(f"restricted path: {inner}")
            if inner.endswith((".zip", ".dat", ".cdb", ".dct", ".sas", ".sps", ".log")):
                problems.append(f"restricted file type: {inner}")
            if inner.endswith((".csv", ".py", ".md", ".json", ".txt", ".toml", ".sha256")):
                text = archive.read(name).decode("utf-8", errors="replace")
                if inner.endswith(".csv"):
                    header = {h.strip().strip('"').lower() for h in text.splitlines()[0].split(",")} if text else set()
                    if header & RESPONDENT_COLUMNS:
                        problems.append(f"respondent-level column in {inner}: {sorted(header & RESPONDENT_COLUMNS)}")
                if SECRET.search(text):
                    problems.append(f"possible credential in {inner}")
                if not inner.endswith(".sha256") and not inner.endswith(".json") and HEX40.search(text):
                    problems.append(f"40-hex string (possible API key) in {inner}")
    return problems


def run(require_data: bool, archive: Path | None) -> int:
    rows = []

    def record(kind, name, ok, detail=""):
        rows.append((kind, name, "PASS" if ok else ("SKIP" if ok is None else "FAIL"), detail))

    matrix = check_matrix()
    record("RECONCILIATION", f"claim matrix: {len(matrix)} checks against frozen sources",
           all(r["ok"] for r in matrix), "; ".join(f"{r['claim_id']}: {r['detail']}" for r in matrix if not r["ok"])[:400])
    missing = untraced_numbers()
    record("RECONCILIATION", "token coverage: every numeric token in the synthesis documents is represented among "
           "verified matrix figures (not a check of the semantic correctness of each statement)",
           not missing, json.dumps(missing)[:400])
    unknown = unknown_claim_ids()
    record("RECONCILIATION", "every cited claim ID exists in the matrix", not unknown, str(sorted(unknown)))
    stored = pd.read_csv(ROOT / "data" / "public" / "final" / "final_evidence_table.csv")
    bad = []
    for row in stored.itertuples(index=False):
        try:
            value = float(resolve(ROOT / row.source_file, row.locator)) * row.source_scale
            if not np.isclose(value, row.estimate, rtol=1e-9, atol=1e-9):
                bad.append(row.id)
        except ValueError:
            bad.append(row.id)
    record("RECONCILIATION", f"evidence table: {len(stored)} estimates equal their frozen sources", not bad, str(bad))
    for name, (count, failed) in manifest_hashes().items():
        record("RECONCILIATION", f"freeze manifest {name}: {count} files", failed == 0, f"{failed} mismatched")
    if (ROOT / "data" / "raw").is_dir():
        for name, (count, mismatched, absent) in provenance_hashes().items():
            outcome = provenance_status(count, mismatched, absent, require_data)
            record("RECONCILIATION", f"provenance hashes data/raw/{name}: {count} files",
                   {"PASS": True, "FAIL": False, "SKIP": None}[outcome],
                   f"{mismatched} mismatched; {absent} inputs not present"
                   + (" (source-only package; use --require-data to fail)" if outcome == "SKIP" else ""))
    else:
        record("RECONCILIATION", "provenance hashes", False if require_data else None, "data/raw absent")

    def independent(name, function, checks):
        try:
            result = function()
        except FileNotFoundError as error:
            record("INDEPENDENT", name, False if require_data else None, f"input missing: {Path(str(error)).name}")
            return
        for label, got, expected, tol in checks(result):
            record("INDEPENDENT", f"{name}: {label}", abs(got - expected) <= tol, f"{got:.6f} vs {expected}")

    independent("NLSY97 stated forecasts (own rank AUC, closed-form slope)", independent_nlsy97, lambda r: [
        ("labelled n", r["n"], 3404, 0), ("Brier", r["brier"], 0.241457, 5e-7), ("AUC", r["auc"], 0.726327, 5e-7),
        ("linear slope", r["slope"], 0.476, 5e-4), ("birth rate after 0%", r["at_0"], 0.183621, 5e-7),
        ("birth rate after 100%", r["at_100"], 0.730392, 5e-7)])
    independent("NSFG 2022-23 weighted shares (numpy, own recode)", independent_nsfg, lambda r: [
        ("cohort n", r["n"], 2429, 0), ("wanters", r["wanters"], 1703, 0), ("wants", r["wants"], 0.698867, 5e-7),
        ("intends", r["intends"], 0.627737, 5e-7), ("divergence among wanters", r["divergence"], 0.112373, 5e-7)])
    independent("M10 two-way FE by dummy-variable least squares, CR1 by hand", independent_m10, lambda r: [
        ("20-24 estimate", r["20-24"]["estimate"], -2.774364, 5e-6), ("20-24 SE", r["20-24"]["se"], 1.512287, 5e-6),
        ("20-24 CI low", r["20-24"]["ci_low"], -5.811882, 5e-6), ("20-24 CI high", r["20-24"]["ci_high"], 0.263153, 5e-6),
        ("25-29 estimate", r["25-29"]["estimate"], -0.055660, 5e-6), ("parameters", r["20-24"]["k"], 61, 0)])
    independent("M11 TFR and 2040 interval (raw HFD, public backtest errors)", independent_m11, lambda r: [
        ("2024 TFR", r["tfr_2024"], 1.59315, 1e-9), ("h=16 errors", r["errors_h16"], 57, 0),
        ("2040 lower80", r["lower80"], 1.0471196810861012, 1e-6), ("2040 upper80", r["upper80"], 2.4239129187863075, 1e-6),
        ("2040 lower95", r["lower95"], 0.8385201891444058, 1e-6), ("2040 upper95", r["upper95"], 3.026912118943502, 1e-6),
        ("1995 observed by end-2024", r["cohort_1995"]["observed_2024"], 0.88243, 5e-6),
        ("1995 by end-2040, approximate T2 (tolerance 0.005)", r["cohort_1995"]["t2"], 1.748366, 0.005),
        ("2012 by end-2040, approximate T2 (tolerance 0.005)", r["cohort_2012"]["t2"], 0.624926, 0.005)])

    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from analysis import final_synthesis as fs
        fresh = pd.read_csv(io.StringIO(fs.evidence_table().to_csv(index=False, float_format="%.10g")))
        same = fresh.equals(stored) or np.allclose(fresh["estimate"], stored["estimate"], rtol=1e-12)
        record("REPRODUCIBILITY", "evidence table rebuilt by analysis.final_synthesis equals the stored table", same)
    except Exception as error:  # noqa: BLE001
        record("REPRODUCIBILITY", "evidence table rebuild", False, f"{type(error).__name__}: {error}")

    if archive is not None:
        if archive.exists():
            problems = check_archive(archive)
            record("RECONCILIATION", f"release safety scan of {archive.name}", not problems, "; ".join(problems)[:400])
        else:
            record("RECONCILIATION", f"release safety scan of {archive.name}", False, "archive not found")

    for kind, name, status, detail in rows:
        print(f"[{status}] {kind:<15} {name}" + (f"  ({detail})" if detail and status != "PASS" else ""))
    counts = {s: sum(1 for r in rows if r[2] == s) for s in ("PASS", "FAIL", "SKIP")}
    kinds = {k: sum(1 for r in rows if r[0] == k) for k in ("INDEPENDENT", "RECONCILIATION", "REPRODUCIBILITY")}
    print(f"\n{counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['SKIP']} SKIP  |  by kind: {kinds}")
    return 1 if counts["FAIL"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verification of the final synthesis")
    parser.add_argument("--require-data", action="store_true", help="fail instead of skipping when local data are absent")
    parser.add_argument("--archive", type=Path, help="review archive to scan for restricted content")
    args = parser.parse_args()
    return run(args.require_data, args.archive)


if __name__ == "__main__":
    sys.exit(main())
