"""ACS 1-year table B25070 (gross rent as a percentage of household income), by state.

M10 data acquisition and validation. Years 2014-2024 except 2020: the Census
Bureau did not release standard 2020 ACS 1-year estimates, and no
interpolation or 5-year substitution is made.

    python -m analysis.acs_housing --fetch   download (needs CENSUS_API_KEY), then validate
    python -m analysis.acs_housing           validate the saved responses only

The API key is read from the environment, sent only in the request, and never
written to disk, logs or provenance. Raw responses are saved unchanged in
data/raw/acs_b25070/ with provenance.json; the processed state-year table goes
to data/processed/m10/.

Derived measures (official B25070 categories):
- computed: households with burden computed = 001 - 011 (= 002 + ... + 010)
- burden 30%+: 007 + 008 + 009 + 010; severe 50%+: 010
- not computed share: 011 / 001

Margins of error are published at the 90% level. Derived MOEs use the Census
Bureau's approximation formulas (ACS General Handbook, 2020, ch. 8): the root
sum of squares for sums, and the proportion formula for shares, falling back to
the ratio formula when the term under the square root is negative. They ignore
covariance between categories and are approximations.
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.nlsy97 import PROJECT_ROOT

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "acs_b25070"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "m10"
OUTPUT_PATH = PROCESSED_DIR / "acs_b25070_state_year.csv"
PROVENANCE_PATH = RAW_DIR / "provenance.json"
API = "https://api.census.gov/data/{year}/acs/acs1"
TABLE = "B25070"
YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024]
EXCLUDED_YEARS = {2020: "no standard 2020 ACS 1-year release (experimental estimates only)"}
CATEGORIES = [f"{TABLE}_{i:03d}" for i in range(1, 12)]
COMPUTED = CATEGORIES[1:10]           # 002-010
BURDEN_30 = CATEGORIES[6:10]          # 007-010
SEVERE_50 = [CATEGORIES[9]]           # 010
NOT_COMPUTED = CATEGORIES[10]         # 011
TOTAL = CATEGORIES[0]                 # 001
EXPECTED_LABELS = {
    "001": "Total", "002": "Less than 10.0 percent", "003": "10.0 to 14.9 percent",
    "004": "15.0 to 19.9 percent", "005": "20.0 to 24.9 percent", "006": "25.0 to 29.9 percent",
    "007": "30.0 to 34.9 percent", "008": "35.0 to 39.9 percent", "009": "40.0 to 49.9 percent",
    "010": "50.0 percent or more", "011": "Not computed",
}
# 50 states and the District of Columbia; Puerto Rico (72) is excluded.
STATE_FIPS = ["01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16", "17",
              "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
              "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42", "44", "45", "46",
              "47", "48", "49", "50", "51", "53", "54", "55", "56"]
EXCLUDED_GEOGRAPHY = {"72": "Puerto Rico"}
Z90 = 1.645


# ---------------------------------------------------------------- acquisition

def raw_path(year: int, kind: str) -> Path:
    return RAW_DIR / f"acs1_{year}_{TABLE}_{kind}.json"


def _request(url: str, params: dict, key: str | None) -> tuple[int, bytes]:
    query = dict(params)
    if key:
        query["key"] = key
    full = url + "?" + urllib.parse.urlencode(query, safe=":*,()")
    request = urllib.request.Request(full, headers={"User-Agent": "acs-acquisition"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except Exception as error:  # the message may contain the URL, so never echo it
        raise RuntimeError(f"Request failed ({type(error).__name__})") from None


def fetch(years: list[int] = YEARS) -> dict:
    """Download data and variable metadata for each year; keep raw bytes and provenance."""
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise SystemExit("CENSUS_API_KEY is not set; nothing downloaded.")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    provenance = {"table": TABLE, "dataset": "ACS 1-year detailed tables", "years": {},
                  "excluded_years": {str(k): v for k, v in EXCLUDED_YEARS.items()},
                  "credentials": "API key sent in the request only; not stored"}
    for year in years:
        entries = {}
        for kind, url, params, keyed in (
                ("data", API.format(year=year), {"get": f"NAME,group({TABLE})",
                                                 "for": "state:*"}, True),
                ("variables", API.format(year=year) + f"/groups/{TABLE}.json", {}, False)):
            status, body = _request(url, params, key if keyed else None)
            if status != 200:
                text = body.decode(errors="replace").replace(key, "[REDACTED]")[:300]
                raise SystemExit(f"{year} {kind}: HTTP {status}: {text}")
            path = raw_path(year, kind)
            path.write_bytes(body)
            entries[kind] = {
                "url": url, "parameters": params, "http_status": status,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "file": path.relative_to(PROJECT_ROOT).as_posix(), "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest()}
        provenance["years"][str(year)] = entries
    PROVENANCE_PATH.write_text(json.dumps(provenance, indent=1) + "\n", encoding="utf-8")
    return provenance


# ---------------------------------------------------------------- loading

def normalize_label(label: str) -> str:
    parts = [p.strip().rstrip(":") for p in label.split("!!")]
    parts = [p for p in parts if p and p not in ("Estimate", "Margin of Error")]
    return parts[-1] if parts else ""


def load_year(year: int) -> tuple[pd.DataFrame, dict]:
    path = raw_path(year, "data")
    if not path.exists():
        raise FileNotFoundError(f"Missing raw ACS response: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    frame = pd.DataFrame(rows[1:], columns=rows[0])
    frame.insert(0, "year", year)
    labels = json.loads(raw_path(year, "variables").read_text(encoding="utf-8"))["variables"]
    return frame, labels


# ---------------------------------------------------------------- validation

def check_labels(labels: dict) -> list[str]:
    """Category labels against the official definitions; returns problems."""
    problems = []
    for code, expected in EXPECTED_LABELS.items():
        name = f"{TABLE}_{code}E"
        if name not in labels:
            problems.append(f"{name} absent")
            continue
        observed = normalize_label(labels[name]["label"])
        if observed != expected:
            problems.append(f"{name}: '{observed}' != '{expected}'")
    concept = {v.get("concept", "") for v in labels.values() if v.get("concept")}
    if not any("GROSS RENT AS A PERCENTAGE OF HOUSEHOLD INCOME" in c.upper() for c in concept):
        problems.append(f"unexpected concept {concept}")
    return problems


def validate_year(frame: pd.DataFrame, labels: dict) -> dict:
    """Structural and value checks for one release (before geography filtering)."""
    estimates = [f"{c}E" for c in CATEGORIES]
    moes = [f"{c}M" for c in CATEGORIES]
    report = {"rows": len(frame), "label_problems": check_labels(labels),
              "missing_columns": [c for c in estimates + moes if c not in frame]}
    fips = frame["state"].tolist()
    report["duplicate_states"] = sorted({f for f in fips if fips.count(f) > 1})
    report["missing_states"] = sorted(set(STATE_FIPS) - set(fips))
    report["extra_geographies"] = sorted(set(fips) - set(STATE_FIPS))
    present = [c for c in estimates + moes if c in frame]
    values = frame[present].apply(pd.to_numeric, errors="coerce")
    report["non_numeric_values"] = int(values.isna().sum().sum())
    report["negative_or_code_values"] = int((values < 0).sum().sum())
    annotations = [c for c in frame.columns if c.endswith(("EA", "MA"))]
    report["annotation_columns"] = len(annotations)
    report["non_null_annotations"] = int(frame[annotations].notna().sum().sum()) \
        if annotations else 0
    states = frame[frame["state"].isin(STATE_FIPS)]
    numbers = states[present].apply(pd.to_numeric, errors="coerce")
    categories = numbers[[f"{c}E" for c in CATEGORIES[1:]]].sum(axis=1)
    report["identity_failures"] = int((categories != numbers[f"{TOTAL}E"]).sum())
    return report


# ---------------------------------------------------------------- derivation

def moe_sum(moes: pd.DataFrame) -> pd.Series:
    return np.sqrt((moes ** 2).sum(axis=1))


def moe_proportion(numerator: pd.Series, numerator_moe: pd.Series, denominator: pd.Series,
                   denominator_moe: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Census proportion MOE; the ratio formula where the radicand is negative."""
    p = numerator / denominator
    radicand = numerator_moe ** 2 - p ** 2 * denominator_moe ** 2
    ratio = radicand < 0
    radicand = radicand.where(~ratio, numerator_moe ** 2 + p ** 2 * denominator_moe ** 2)
    return np.sqrt(radicand) / denominator, ratio


def derive(states: pd.DataFrame) -> pd.DataFrame:
    out = states[["year", "state", "NAME"]].rename(columns={"state": "state_fips",
                                                            "NAME": "state_name"}).copy()
    for c in CATEGORIES:
        out[f"{c}E"] = pd.to_numeric(states[f"{c}E"]).astype(int)
        out[f"{c}M"] = pd.to_numeric(states[f"{c}M"]).astype(float)
    estimate = {c: out[f"{c}E"] for c in CATEGORIES}
    moe = {c: out[f"{c}M"] for c in CATEGORIES}
    out["households_total"] = estimate[TOTAL]
    out["households_computed"] = sum(estimate[c] for c in COMPUTED)
    out["households_computed_moe"] = moe_sum(pd.concat([moe[c] for c in COMPUTED], axis=1))
    for name, members in (("burden30", BURDEN_30), ("severe50", SEVERE_50)):
        count = sum(estimate[c] for c in members)
        count_moe = moe_sum(pd.concat([moe[c] for c in members], axis=1))
        out[f"{name}_households"] = count
        out[f"{name}_households_moe"] = count_moe
        share, ratio = moe_proportion(count, count_moe, out["households_computed"],
                                      out["households_computed_moe"])
        out[f"{name}_pct"] = 100 * count / out["households_computed"]
        out[f"{name}_pct_moe90"] = 100 * share
        out[f"{name}_pct_se"] = 100 * share / Z90
        out[f"{name}_moe_ratio_formula"] = ratio
    share, ratio = moe_proportion(estimate[NOT_COMPUTED], moe[NOT_COMPUTED], estimate[TOTAL],
                                  moe[TOTAL])
    out["not_computed_pct"] = 100 * estimate[NOT_COMPUTED] / estimate[TOTAL]
    out["not_computed_pct_moe90"] = 100 * share
    out["not_computed_moe_ratio_formula"] = ratio
    return out


def build(years: list[int] = YEARS) -> tuple[pd.DataFrame, dict]:
    frames, reports = [], {}
    for year in years:
        frame, labels = load_year(year)
        reports[year] = validate_year(frame, labels)
        frames.append(frame[frame["state"].isin(STATE_FIPS)])
    states = pd.concat(frames, ignore_index=True)
    table = derive(states).sort_values(["year", "state_fips"]).reset_index(drop=True)
    keys = table[["year", "state_fips"]]
    summary = {
        "records": len(table), "years": sorted(table["year"].unique().tolist()),
        "jurisdictions": int(table["state_fips"].nunique()),
        "duplicate_keys": int(keys.duplicated().sum()),
        "expected_records": len(STATE_FIPS) * len(years),
        "missing_state_years": int(len(STATE_FIPS) * len(years) - len(keys.drop_duplicates())),
        "zero_or_negative_denominators": int((table["households_computed"] <= 0).sum()),
        "ratio_formula_used": int(table[[c for c in table if c.endswith("ratio_formula")]]
                                  .to_numpy().sum()),
        "releases": {str(y): r for y, r in reports.items()},
    }
    return table, summary


def status(summary: dict) -> str:
    releases = summary["releases"].values()
    hard = (summary["duplicate_keys"] or summary["missing_state_years"]
            or summary["zero_or_negative_denominators"]
            or any(r["label_problems"] or r["missing_columns"] or r["non_numeric_values"]
                   or r["negative_or_code_values"] or r["identity_failures"]
                   or r["duplicate_states"] or r["missing_states"] for r in releases))
    return "FAIL" if hard else "PASS"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACS B25070 acquisition and validation.")
    parser.add_argument("--fetch", action="store_true", help="download from the Census API")
    args = parser.parse_args(argv)
    if args.fetch:
        fetch()
    table, summary = build()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT_PATH, index=False, float_format="%.10g")
    summary["status"] = status(summary)
    (PROCESSED_DIR / "acs_b25070_validation.json").write_text(
        json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"ACS B25070 | {summary['records']} state-year records, "
          f"{summary['jurisdictions']} jurisdictions, years {summary['years']}")
    for year, report in summary["releases"].items():
        print(f"  {year}: rows {report['rows']}, extra {report['extra_geographies']}, "
              f"labels {report['label_problems'] or 'OK'}, codes "
              f"{report['negative_or_code_values']}, identity failures "
              f"{report['identity_failures']}")
    print(f"Status: {summary['status']}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
