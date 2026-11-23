"""Build and validate the atlas's publication-safe derivative of the M10 panel."""

from __future__ import annotations

import argparse
import csv
import io
import math
from pathlib import Path
from statistics import mean, median

from analysis.acs_housing import BURDEN_30, COMPUTED, SEVERE_50, STATE_FIPS, YEARS

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data/processed/m10"
PUBLIC = ROOT / "data/public/m10"
OUTPUT = PUBLIC / "m10_geography.csv"
AGES = ("20-24", "25-29")
FIELDS: tuple[str, ...] = (
    "state_fips", "state_name", "year", "burden30_pct", "severe50_pct",
    "birth_rate_20_24", "birth_rate_25_29",
)
STATE_YEARS = {(fips, str(year)) for fips in STATE_FIPS for year in YEARS}
STATE_YEAR_AGES = {(*key, age) for key in STATE_YEARS for age in AGES}
SUMMARY_COLUMNS = {
    "burden30_pct": "burden30_pct", "severe50_pct": "severe50_pct",
    "birth_rate_20_24": "rate_20-24", "birth_rate_25_29": "rate_25-29",
}
Row = dict[str, str]


def read_index(
    path: Path, fields: tuple[str, ...], expected: set[tuple[str, ...]],
    *, exclude_2020: bool = False,
) -> dict[tuple[str, ...], Row]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = {}
        for row in csv.DictReader(stream):
            if exclude_2020 and row["year"] == "2020":
                continue
            key = tuple(row[field] for field in fields)
            if key in rows:
                raise ValueError(f"{path.name}: duplicate key {key}")
            rows[key] = row
    if rows.keys() != expected:
        raise ValueError(f"{path.name}: missing or unexpected jurisdiction, year or age keys")
    return rows


def publishable_rate(row: Row) -> str:
    """Withhold unpublished rates and rates representing fewer than ten births."""
    if any(row[f"{field}_status"] != "value" for field in
           ("births", "female_population", "rate_exported")):
        return ""
    births, population = int(row["births"]), int(row["female_population"])
    if births < 10 or population < 1:
        return ""
    rate = float(row["rate_exported"])
    if not math.isfinite(rate) or abs(rate - 1000 * births / population) > 0.000500001:
        raise ValueError("CDC exported rate does not match its source counts")
    return row["rate_exported"]


def burden_share(row: Row, categories: list[str], column: str) -> str:
    denominator = sum(int(row[f"{category}E"]) for category in COMPUTED)
    numerator = sum(int(row[f"{category}E"]) for category in categories)
    if not 0 <= numerator <= denominator or denominator < 1:
        raise ValueError("Invalid ACS B25070 estimate counts")
    if not math.isclose(float(row[column]), 100 * numerator / denominator, abs_tol=1e-7):
        raise ValueError(f"ACS B25070 counts do not reproduce {column}")
    return row[column]


def derive(processed: Path = PROCESSED) -> list[Row]:
    keys = ("state_fips", "year")
    age_keys = (*keys, "age_group")
    acs = read_index(processed / "acs_b25070_state_year.csv", keys, STATE_YEARS)
    cdc = read_index(
        processed / "cdc_natality_state_year_age.csv",
        age_keys, STATE_YEAR_AGES, exclude_2020=True,
    )
    panel = read_index(processed / "m10_panel_state_year_age.csv", age_keys, STATE_YEAR_AGES)
    output = []
    for fips, year in sorted(STATE_YEARS, key=lambda key: (key[1], key[0])):
        housing = acs[fips, year]
        burden = burden_share(housing, BURDEN_30, "burden30_pct")
        severe = burden_share(housing, SEVERE_50, "severe50_pct")
        row = {
            "state_fips": fips, "state_name": housing["state_name"], "year": year,
            "burden30_pct": burden, "severe50_pct": severe,
        }
        for age in AGES:
            key = (fips, year, age)
            source, study = cdc[key], panel[key]
            vintage = "original" if int(year) <= 2015 else "expanded"
            if source["source"] != vintage or source["state_name"] != housing["state_name"]:
                raise ValueError(f"Unexpected CDC source or name at {key}")
            if (study["state_name"] != housing["state_name"] or study["state_name_agrees"] != "True"
                    or study["burden30_pct"] != burden or study["severe50_pct"] != severe
                    or any(study[field] != source[field] for field in (
                        "births", "births_status", "female_population", "female_population_status",
                        "rate_exported", "rate_exported_status", "source",
                    )) or study["outcome_rate"] != source["rate_exported"]):
                raise ValueError(f"M10 panel differs from its verified ACS or CDC input at {key}")
            row[f"birth_rate_{age.replace('-', '_')}"] = publishable_rate(source)
        output.append(row)
    return output


def validate_public(rows: list[Row], summary: Path = PUBLIC / "m10_desc_by_year.csv") -> None:
    """Check rectangular coverage and compare values with frozen annual summaries."""
    keys = {(row["state_fips"], row["year"]) for row in rows}
    if len(keys) != len(rows) or keys != STATE_YEARS:
        raise ValueError("Atlas must cover 50 states and DC once per supported year")
    names: dict[str, str] = {}
    values: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        if tuple(row) != FIELDS:
            raise ValueError("Atlas contains an unexpected or missing field")
        name = row["state_name"]
        if not name or names.setdefault(row["state_fips"], name) != name:
            raise ValueError("Inconsistent jurisdiction name")
        if not 0 <= float(row["severe50_pct"]) <= float(row["burden30_pct"]) <= 100:
            raise ValueError("Rent burden must be a percentage, with severe burden a subset")
        for column, variable in SUMMARY_COLUMNS.items():
            if row[column]:
                value = float(row[column])
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid atlas value in {column}")
                values.setdefault((row["year"], variable), []).append(value)
    expected = {(str(year), variable) for year in YEARS for variable in SUMMARY_COLUMNS.values()}
    verified = set()
    with summary.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (row["year"], row["variable"])
            if key not in expected:
                continue
            series = values.get(key, [])
            if len(series) != int(row["states"]):
                raise ValueError(f"Atlas coverage differs from the frozen annual summary at {key}")
            for field, value in (
                ("mean", mean(series)), ("median", median(series)), ("min", min(series)), ("max", max(series)),
            ):
                if not math.isclose(value, float(row[field]), abs_tol=1e-7):
                    raise ValueError(f"Atlas {field} differs from the frozen annual summary at {key}")
            verified.add(key)
    if verified != expected:
        raise ValueError("Atlas frozen annual summary is incomplete")


def encode(rows: list[Row]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def read_public(path: Path = OUTPUT) -> list[Row]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("Atlas contains an unexpected or missing field")
        return list(reader)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="regenerate from local M10 inputs")
    mode.add_argument("--verify-source", action="store_true", help="verify against local M10 inputs")
    args = parser.parse_args()
    source_rows: list[Row] | None = None
    if args.write or args.verify_source:
        source_rows = derive()
        validate_public(source_rows)
        if args.write:
            OUTPUT.write_bytes(encode(source_rows).encode("utf-8"))
    rows = read_public()
    validate_public(rows)
    if args.verify_source and rows != source_rows:
        raise ValueError("Atlas differs from the local M10 inputs")
    print(f"M10 atlas validated: {len(rows)} state-year rows, {len(YEARS)} years, {len(STATE_FIPS)} jurisdictions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
