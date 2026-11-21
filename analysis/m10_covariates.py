"""Supporting ACS 1-year tables for M10: B25072, B23025 and B19013, by state.

- B25072 (age of householder by gross rent as a percentage of household
  income): the secondary, age-specific exposure, used only if the protocol's
  validation criteria pass (docs/m10_analysis_protocol.md, section 7).
- B23025 (employment status, population 16+): unemployment rate, the model D
  control.
- B19013 (median household income): sensitivity control only (mechanical
  coupling with the burden ratio).

    python -m analysis.m10_covariates --fetch   download (needs CENSUS_API_KEY), then validate
    python -m analysis.m10_covariates           validate the saved responses only

Requests reuse analysis.acs_housing (same key handling: the key is never
written). Raw responses and provenance go to data/raw/acs_m10_covariates/;
the processed table goes to data/processed/m10/acs_m10_covariates.csv.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from analysis import acs_housing as acs
from analysis.nlsy97 import PROJECT_ROOT

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "acs_m10_covariates"
PROVENANCE_PATH = RAW_DIR / "provenance.json"
OUTPUT_PATH = acs.PROCESSED_DIR / "acs_m10_covariates.csv"
TABLES = ["B25072", "B23025", "B19013"]
YOUNG_BANDS = {  # band: (total, 30.0-34.9, 35.0+, not computed)
    "15_24": ("B25072_002", "B25072_006", "B25072_007", "B25072_008"),
    "25_34": ("B25072_009", "B25072_013", "B25072_014", "B25072_015"),
}
B25072_PARTS = {"B25072_002": [f"B25072_{i:03d}" for i in range(3, 9)],
                "B25072_009": [f"B25072_{i:03d}" for i in range(10, 16)],
                "B25072_016": [f"B25072_{i:03d}" for i in range(17, 23)],
                "B25072_023": [f"B25072_{i:03d}" for i in range(24, 30)]}
EXPECTED_B25072 = {
    "002": "Householder 15 to 24 years", "006": "30.0 to 34.9 percent",
    "007": "35.0 percent or more", "008": "Not computed", "009": "Householder 25 to 34 years",
    "013": "30.0 to 34.9 percent", "014": "35.0 percent or more", "015": "Not computed",
}
EXPECTED_B23025 = {"003": "Civilian labor force", "005": "Unemployed"}


def raw_path(table: str, year: int, kind: str):
    return RAW_DIR / f"acs1_{year}_{table}_{kind}.json"


def fetch(years: list[int] = acs.YEARS) -> dict:
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise SystemExit("CENSUS_API_KEY is not set; nothing downloaded.")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    provenance = {"dataset": "ACS 1-year detailed tables", "tables": TABLES, "files": {},
                  "credentials": "API key sent in the request only; not stored"}
    for table in TABLES:
        for year in years:
            for kind, url, params, keyed in (
                    ("data", acs.API.format(year=year),
                     {"get": f"NAME,group({table})", "for": "state:*"}, True),
                    ("variables", acs.API.format(year=year) + f"/groups/{table}.json", {}, False)):
                status, body = acs._request(url, params, key if keyed else None)
                if status != 200:
                    text = body.decode(errors="replace").replace(key, "[REDACTED]")[:300]
                    raise SystemExit(f"{table} {year} {kind}: HTTP {status}: {text}")
                path = raw_path(table, year, kind)
                path.write_bytes(body)
                provenance["files"][path.name] = {
                    "table": table, "year": year, "kind": kind, "url": url,
                    "parameters": params, "http_status": status,
                    "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    PROVENANCE_PATH.write_text(json.dumps(provenance, indent=1) + "\n", encoding="utf-8")
    return provenance


def load(table: str, year: int) -> tuple[pd.DataFrame, dict]:
    path = raw_path(table, year, "data")
    if not path.exists():
        raise FileNotFoundError(f"Missing raw ACS response: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    frame = pd.DataFrame(rows[1:], columns=rows[0])
    frame.insert(0, "year", year)
    labels = json.loads(raw_path(table, year, "variables").read_text(encoding="utf-8"))
    return frame, labels["variables"]


def label_problems(labels: dict, table: str, expected: dict) -> list[str]:
    problems = []
    for code, text in expected.items():
        name = f"{table}_{code}E"
        if name not in labels:
            problems.append(f"{name} absent")
        elif text not in [acs.normalize_label(labels[name]["label"])] + \
                [p.strip().rstrip(":") for p in labels[name]["label"].split("!!")]:
            problems.append(f"{name}: {labels[name]['label']!r}")
    return problems


def validate_table(table: str, frames: list[pd.DataFrame], labels: dict[int, dict]) -> dict:
    data = pd.concat(frames, ignore_index=True)
    states = data[data["state"].isin(acs.STATE_FIPS)]
    estimates = [c for c in data if c.startswith(table) and c.endswith(("E", "M"))]
    values = states[estimates].apply(pd.to_numeric, errors="coerce")
    report = {
        "records": len(states), "expected": len(acs.STATE_FIPS) * len(frames),
        "duplicate_keys": int(states.duplicated(["year", "state"]).sum()),
        "missing_state_years": int(len(acs.STATE_FIPS) * len(frames)
                                   - len(states[["year", "state"]].drop_duplicates())),
        "non_numeric_values": int(values.isna().sum().sum()),
        "negative_or_code_values": int((values < 0).sum().sum()),
        "label_sets_identical": len({tuple(sorted(acs.normalize_label(v["label"])
                                                  for k, v in lab.items()
                                                  if k.startswith(table) and k.endswith("E")))
                                     for lab in labels.values()}) == 1,
    }
    expected = {"B25072": EXPECTED_B25072, "B23025": EXPECTED_B23025}.get(table, {})
    report["label_problems"] = {str(y): label_problems(lab, table, expected)
                                for y, lab in labels.items() if label_problems(lab, table,
                                                                               expected)}
    if table == "B25072":
        failures = 0
        for total, parts in B25072_PARTS.items():
            failures += int((values[[f"{p}E" for p in parts]].sum(axis=1)
                             != values[f"{total}E"]).sum())
        top = values[[f"{t}E" for t in B25072_PARTS]].sum(axis=1) != values["B25072_001E"]
        report["identity_failures"] = failures + int(top.sum())
        report["zero_denominators"] = {
            band: int(((values[f"{tot}E"] - values[f"{nc}E"]) <= 0).sum())
            for band, (tot, _, _, nc) in YOUNG_BANDS.items()}
    if table == "B23025":
        report["identity_failures"] = int(
            (values["B23025_004E"] + values["B23025_005E"] != values["B23025_003E"]).sum())
    return report


def derive(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    key = ["year", "state"]
    young = frames["B25072"][frames["B25072"]["state"].isin(acs.STATE_FIPS)]
    out = young[key].copy()
    num = young.drop(columns=["NAME", *key]).apply(pd.to_numeric, errors="coerce")
    for band, (total, low, high, not_computed) in YOUNG_BANDS.items():
        computed = num[f"{total}E"] - num[f"{not_computed}E"]
        computed_moe = np.sqrt(num[f"{total}M"] ** 2 + num[f"{not_computed}M"] ** 2)
        burdened = num[f"{low}E"] + num[f"{high}E"]
        burdened_moe = np.sqrt(num[f"{low}M"] ** 2 + num[f"{high}M"] ** 2)
        moe, ratio = acs.moe_proportion(burdened, burdened_moe, computed, computed_moe)
        out[f"young{band}_households_computed"] = computed
        out[f"young{band}_burden30_pct"] = 100 * burdened / computed
        out[f"young{band}_burden30_pct_moe90"] = 100 * moe
        out[f"young{band}_burden30_pct_se"] = 100 * moe / acs.Z90
        out[f"young{band}_moe_ratio_formula"] = ratio.to_numpy()
        out[f"young{band}_not_computed_pct"] = 100 * num[f"{not_computed}E"] / num[f"{total}E"]
    labour = frames["B23025"][frames["B23025"]["state"].isin(acs.STATE_FIPS)]
    lab = labour.drop(columns=["NAME", "year", "state"]).apply(pd.to_numeric, errors="coerce")
    moe, _ = acs.moe_proportion(lab["B23025_005E"], lab["B23025_005M"], lab["B23025_003E"],
                                lab["B23025_003M"])
    unemployment = labour[key].assign(unemployment_pct=100 * lab["B23025_005E"]
                                      / lab["B23025_003E"],
                                      unemployment_pct_moe90=100 * moe)
    income = frames["B19013"][frames["B19013"]["state"].isin(acs.STATE_FIPS)]
    inc = income[["B19013_001E", "B19013_001M"]].apply(pd.to_numeric, errors="coerce")
    income = income[key].assign(median_household_income=inc["B19013_001E"],
                                median_household_income_moe90=inc["B19013_001M"],
                                log_median_household_income=np.log(inc["B19013_001E"]))
    out = out.merge(unemployment, on=key, validate="one_to_one").merge(
        income, on=key, validate="one_to_one")
    return out.rename(columns={"state": "state_fips"}).sort_values(
        ["year", "state_fips"]).reset_index(drop=True)


def build(years: list[int] = acs.YEARS) -> tuple[pd.DataFrame, dict]:
    frames, report = {}, {}
    for table in TABLES:
        loaded = [load(table, year) for year in years]
        frames[table] = pd.concat([f for f, _ in loaded], ignore_index=True)
        report[table] = validate_table(table, [f for f, _ in loaded],
                                       {y: lab for y, (_, lab) in zip(years, loaded)})
    table = derive(frames)
    b25072 = report["B25072"]
    report["B25072_passes_protocol"] = bool(
        b25072["label_sets_identical"] and not b25072["label_problems"]
        and b25072["identity_failures"] == 0 and b25072["negative_or_code_values"] == 0
        and b25072["non_numeric_values"] == 0 and b25072["missing_state_years"] == 0
        and b25072["duplicate_keys"] == 0 and b25072["records"] == b25072["expected"]
        and all(v == 0 for v in b25072["zero_denominators"].values()))
    for band in YOUNG_BANDS:
        se = table[f"young{band}_burden30_pct_se"]
        report[f"young{band}_reliability"] = {
            "se_median": float(se.median()), "se_max": float(se.max()),
            "share_se_over_5pp": float((se > 5).mean()),
            "ratio_formula_used": int(table[f"young{band}_moe_ratio_formula"].sum())}
    return table, report


def status(report: dict) -> str:
    controls_ok = all(report[t]["missing_state_years"] == 0 and report[t]["duplicate_keys"] == 0
                      and report[t]["negative_or_code_values"] == 0
                      and report[t]["non_numeric_values"] == 0 and not report[t]["label_problems"]
                      for t in ("B23025", "B19013"))
    if not controls_ok or report["B23025"].get("identity_failures"):
        return "FAIL"
    return "PASS" if report["B25072_passes_protocol"] else "WARN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M10 supporting ACS tables.")
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args(argv)
    if args.fetch:
        fetch()
    table, report = build()
    report["status"] = status(report)
    table.to_csv(OUTPUT_PATH, index=False, float_format="%.10g")
    (acs.PROCESSED_DIR / "acs_m10_covariates_validation.json").write_text(
        json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    for name in TABLES:
        print(f"{name}: {report[name]}")
    for band in YOUNG_BANDS:
        print(f"young {band}: {report[f'young{band}_reliability']}")
    print(f"B25072 passes protocol criteria: {report['B25072_passes_protocol']}")
    print(f"Status: {report['status']}")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
