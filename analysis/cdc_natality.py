"""CDC WONDER natality exports: parsing, validation and reconciliation for M10.

Two exports in data/raw/cdc_natality/ are read without modification. Both have
an .xls extension but are tab-delimited text files (CDC WONDER's "Export"
format): a data block, a "---" separator, then the query parameters, citation
and caveats.

- original: "Natality, 2007-2024", 2014-2024, column "State". Its age-specific
  denominators are bridged-race, so female population and rates are "Not
  Available" for 2021-2024.
- expanded: "Natality, 2016-2024 expanded", 2016-2024, column "State of
  Residence", with single-race denominators for every year.

The analytical series takes 2014-2015 from the original export and 2016-2024
from the expanded export. Where both exist, the two must agree exactly
(births, female population and rate for 2016-2020; births for 2021-2024);
any disagreement makes the status FAIL. Subtotal and grand-total rows are
validated against the detail rows and never enter the analytical data.

Rows are births to mothers aged 20-24 and 25-29 ("Age of Mother 9"), by year
and state of the mother's legal residence (CDC WONDER natality help). The
exported "Fertility Rate" for an age group is births per 1,000 women in that
age group, which NCHS reports call the age-specific birth rate.

Independent checks use the NCHS "Births: Final Data" reports saved in
data/raw/nchs_nvsr/ (Table 8: state birth rates by age, by place of residence;
Table 2: national birth rates by age).

    python -m analysis.cdc_natality
"""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.acs_housing import PROCESSED_DIR, STATE_FIPS
from analysis.nlsy97 import PROJECT_ROOT

CDC_DIR = PROJECT_ROOT / "data" / "raw" / "cdc_natality"
EXPORT_PATH = CDC_DIR / "cdc_wonder_natality_state_age_2014_2024.xls"
EXPANDED_PATH = CDC_DIR / "cdc_wonder_natality_expanded_state_age_2016_2024.xls"
SOURCES = {
    "original": {"path": EXPORT_PATH, "years": list(range(2014, 2025)),
                 "dataset": "Natality, 2007-2024"},
    "expanded": {"path": EXPANDED_PATH, "years": list(range(2016, 2025)),
                 "dataset": "Natality, 2016-2024 expanded"},
}
ANALYTIC_SOURCE = {year: "original" if year < 2016 else "expanded" for year in range(2014, 2025)}
NVSR_DIR = PROJECT_ROOT / "data" / "raw" / "nchs_nvsr"
NVSR_REPORTS = {2019: NVSR_DIR / "nvsr70-02-508.txt", 2023: NVSR_DIR / "nvsr74-1.txt",
                2024: NVSR_DIR / "nvsr75-02.txt"}
OUTPUT_PATH = PROCESSED_DIR / "cdc_natality_state_year_age.csv"
YEARS = list(range(2014, 2025))
AGE_GROUPS = {"20-24": "20-24 years", "25-29": "25-29 years"}
EXPECTED_HEADER = ["Notes", "Year", "Year Code", "State", "State Code", "Age of Mother 9",
                   "Age of Mother 9 Code", "Births", "Female Population", "Fertility Rate"]
HEADER_ALIASES = {"State of Residence": "State", "State of Residence Code": "State Code"}
SPECIAL_VALUES = {"Not Available", "Suppressed", "Unreliable", "Not Applicable", "Missing"}
RATE_TOLERANCE = 0.0005 + 1e-9   # exported rates carry three decimals


# ---------------------------------------------------------------- parsing

def file_format(path: Path) -> str:
    head = Path(path).read_bytes()[:8]
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "OLE2 binary Excel"
    if head.startswith(b"PK"):
        return "zip-based (xlsx)"
    return "tab-delimited text" if b"\t" in Path(path).read_bytes()[:2000] else "text"


def parse_export(path: Path = EXPORT_PATH) -> tuple[pd.DataFrame, dict]:
    """Data rows (detail and totals) and the metadata block, read as text."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CDC WONDER export not found: {path}")
    with open(path, newline="", encoding="utf-8") as handle:
        lines = list(csv.reader(handle, delimiter="\t"))
    split = next((i for i, row in enumerate(lines) if row and row[0] == "---"), len(lines))
    raw_header, body = lines[0], [row for row in lines[1:split] if row]
    header = [HEADER_ALIASES.get(column, column) for column in raw_header]
    if header != EXPECTED_HEADER:
        raise ValueError(f"Unexpected export columns: {raw_header}")
    frame = pd.DataFrame(body, columns=header)
    footer = [row[0] if row else "" for row in lines[split:]]
    metadata = {"format": file_format(path), "data_rows": len(frame), "footer": footer,
                "state_header": raw_header[3]}
    for line in footer:
        if ": " in line and not line.startswith(("Caveats", "Help")):
            key, value = line.split(": ", 1)
            metadata.setdefault("fields", {})[key.strip('"')] = value
    metadata["caveats"] = [line for line in footer if re.match(r"^\d+\. ", line)]
    return frame, metadata


def tidy(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Detail rows (one per year-state-age) and total rows, with numeric columns."""
    detail = frame[frame["Notes"].eq("")].copy()
    totals = frame[frame["Notes"].eq("Total")].copy()
    other = frame[~frame["Notes"].isin(["", "Total"])]
    if len(other):
        raise ValueError(f"Unexpected Notes values: {sorted(other['Notes'].unique())}")
    if (detail["State Code"].eq("") | detail["Age of Mother 9 Code"].eq("")).any():
        raise ValueError("A detail row lacks a state or age code")
    out = pd.DataFrame({
        "year": pd.to_numeric(detail["Year Code"]).astype(int),
        "state_fips": detail["State Code"], "state_name": detail["State"],
        "age_group": detail["Age of Mother 9 Code"],
        "age_label": detail["Age of Mother 9"]})
    for column, name in (("Births", "births"), ("Female Population", "female_population"),
                         ("Fertility Rate", "rate_exported")):
        raw = detail[column]
        out[name] = pd.to_numeric(raw, errors="coerce")
        out[f"{name}_status"] = np.where(out[name].notna(), "value", raw)
    return out.reset_index(drop=True), totals


# ---------------------------------------------------------------- validation

def validate(detail: pd.DataFrame, totals: pd.DataFrame, metadata: dict,
             years: list[int] = YEARS) -> dict:
    fields = metadata.get("fields", {})
    keys = detail[["year", "state_fips", "age_group"]]
    expected = pd.MultiIndex.from_product([years, STATE_FIPS, list(AGE_GROUPS)])
    present = pd.MultiIndex.from_frame(keys)
    statuses = {c: detail[f"{c}_status"].value_counts().to_dict()
                for c in ("births", "female_population", "rate_exported")}
    unexpected_special = sorted({v for c in statuses.values() for v in c}
                                - {"value"} - SPECIAL_VALUES)
    report = {
        "format": metadata["format"],
        "dataset": fields.get("Dataset"), "state_header": metadata.get("state_header"),
        "group_by": fields.get("Group By"), "rates_per": fields.get("Calculate Rates Per"),
        "show_suppressed": fields.get("Show Suppressed"),
        "show_zero_values": fields.get("Show Zero Values"),
        "query_date": fields.get("Query Date"),
        "age_filter": fields.get("Age of Mother 9"), "year_filter": fields.get("Year"),
        "residence_basis": "mother's legal residence (CDC WONDER natality help); the "
                           "export itself does not state it",
        "detail_rows": len(detail), "total_rows": len(totals),
        "expected_combinations": len(expected),
        "duplicate_keys": int(keys.duplicated().sum()),
        "missing_combinations": [list(k) for k in expected.difference(present)],
        "unexpected_combinations": [list(k) for k in present.difference(expected)],
        "unexpected_age_labels": sorted(set(detail["age_label"]) - set(AGE_GROUPS.values())),
        "value_status": statuses, "unexpected_special_values": unexpected_special,
        "suppressed_cells": int(sum(c.get("Suppressed", 0) for c in statuses.values())),
        "births_min": int(detail["births"].min()),
        "zero_or_negative_births": int((detail["births"] <= 0).sum()),
        "rate_available_by_year": detail.groupby("year")["rate_exported"].apply(
            lambda s: int(s.notna().sum())).to_dict(),
    }
    names = detail.groupby("state_fips")["state_name"].nunique()
    report["inconsistent_state_names"] = names[names > 1].index.tolist()

    has_rate = detail["rate_exported"].notna() & detail["female_population"].gt(0)
    recalculated = 1000 * detail["births"] / detail["female_population"]
    difference = (recalculated - detail["rate_exported"]).abs()[has_rate]
    report["rates_recalculated"] = int(has_rate.sum())
    report["rate_max_abs_difference"] = float(difference.max()) if len(difference) else None
    report["rate_mismatches"] = int((difference > RATE_TOLERANCE).sum())
    report["rate_without_population"] = int((detail["rate_exported"].notna()
                                             & detail["female_population"].isna()).sum())
    report["totals"] = check_totals(detail, totals)
    return report


def check_totals(detail: pd.DataFrame, totals: pd.DataFrame) -> dict:
    """Exported state-year, year and grand totals against sums of the detail rows."""
    t = totals.assign(year=pd.to_numeric(totals["Year Code"], errors="coerce"),
                      births=pd.to_numeric(totals["Births"], errors="coerce"),
                      population=pd.to_numeric(totals["Female Population"], errors="coerce"))
    state_year = t[t["State Code"].ne("") & t["year"].notna()]
    sums = detail.groupby(["year", "state_fips"])["births"].sum()
    merged = state_year.set_index(["year", "State Code"])["births"]
    merged.index = merged.index.set_names(["year", "state_fips"])
    year_rows = t[t["State Code"].eq("") & t["year"].notna()].set_index("year")["births"]
    grand = t[t["year"].isna()]
    pop_sums = detail.groupby(["year", "state_fips"])["female_population"].sum(min_count=2)
    pops = state_year.set_index(["year", "State Code"])["population"]
    pops.index = pops.index.set_names(["year", "state_fips"])
    pop_diff = (pops - pop_sums.reindex(pops.index)).abs().dropna()
    return {
        "state_year_rows": len(state_year),
        "state_year_birth_mismatches": int((merged - sums.reindex(merged.index)).abs()
                                           .gt(0).sum()),
        "state_year_population_mismatches": int(pop_diff.gt(0).sum()),
        "year_rows": len(year_rows),
        "year_birth_mismatches": int((year_rows - detail.groupby("year")["births"].sum()
                                      .reindex(year_rows.index)).abs().gt(0).sum()),
        "grand_total_rows": len(grand),
        "grand_total_matches": bool(len(grand) == 1
                                    and grand["births"].iloc[0] == detail["births"].sum()),
        "national_totals_by_year": {int(k): int(v) for k, v in year_rows.items()},
    }


# ------------------------------------------------- independent official sources

STATE_TABLE = re.compile(
    r"Table (\d+)\. Birth rates, by age of mother: United States, each state")
DOT_LEADERS = re.compile(r"(\s?\.){2,}")


def parse_nvsr_state_table(text: str) -> pd.DataFrame:
    """State birth rates for ages 20-24 and 25-29 from the NVSR "each state" rate table.

    The table is Table 8 in the 2019 and 2023 reports and Table 6 in the 2024 report;
    the 2024 layout adds dot leaders after area names (pdftotext -layout text).
    """
    match = STATE_TABLE.search(text)
    if match is None:
        raise ValueError("No state birth-rate table found")
    number = match.group(1)
    following = re.search(rf"\nTable (?!{number}\.)\d+\. ", text[match.start():])
    end = match.start() + following.start() if following else len(text)
    block = text[match.start():end]
    rows = []
    for line in block.splitlines():
        line = DOT_LEADERS.sub(" ", line)
        found = re.match(r"^\s*([A-Z][A-Za-z .]+?)\d?\s{1,}(\d.*)$", line)
        if not found:
            continue
        tokens = found.group(2).split()
        if len(tokens) < 9 or not all(re.match(r"^[\d.,*]+$", t) for t in tokens[:9]):
            continue
        rows.append({"area": found.group(1).strip(), "rate_20_24": float(tokens[7]),
                     "rate_25_29": float(tokens[8])})
    return pd.DataFrame(rows).drop_duplicates("area")


def parse_nvsr_table8(text: str) -> pd.DataFrame:
    """Backward-compatible name for parse_nvsr_state_table."""
    return parse_nvsr_state_table(text)


def parse_nvsr_table2(text: str) -> pd.DataFrame:
    """National birth rates for ages 20-24 and 25-29 by year (NVSR Table 2, all races)."""
    start = text.index("Table 2. Birth rates, by age of mother: United States")
    block = text[start:text.index("Table 3.", start)]
    rows = []
    for line in block.splitlines():
        line = DOT_LEADERS.sub(" ", line)
        match = re.match(r"^\s*(20[12]\d)\s+([\d,]+\.\d)\s+(.*)$", line)
        if match:
            tokens = match.group(3).split()
            rows.append({"year": int(match.group(1)), "rate_20_24": float(tokens[4]),
                         "rate_25_29": float(tokens[5])})
        if rows and "Non-Hispanic" in line:
            break
    return pd.DataFrame(rows).drop_duplicates("year")


PUBLISHED_HALF_UNIT = 0.05 + 1e-9   # NVSR rates are printed to one decimal
# NVSR rates for 2020 use April 1, 2020 populations; WONDER uses July 1, 2020 estimates.
DENOMINATOR_DIFFERENCE_YEARS = {2020: "NVSR 2020 rates use April 1, 2020 populations; "
                                      "CDC WONDER uses July 1, 2020 estimates"}


def compare_official(detail: pd.DataFrame) -> dict:
    """Exported and recalculated rates against NCHS final-data reports.

    State rates (Table 8) are compared for each report year that has exported
    rates; an unrounded exported rate agrees when it lies within half a unit of
    the published one-decimal value. National rates (Table 2 of the latest
    report) are compared with births / female population summed over the 51
    jurisdictions.
    """
    results = {"state_table8": {}, "national_table2": None}
    names = detail.drop_duplicates("state_fips").set_index("state_name")["state_fips"]
    texts = {y: p.read_text(encoding="utf-8", errors="replace")
             for y, p in NVSR_REPORTS.items() if p.exists()}
    for year, path in NVSR_REPORTS.items():
        if year not in texts:
            results["state_table8"][str(year)] = {"status": "SKIP",
                                                  "reason": f"missing {path.name}"}
            continue
        table8 = parse_nvsr_state_table(texts[year])
        table8 = table8[table8["area"].isin(names.index)].assign(
            state_fips=lambda t: t["area"].map(names))
        mine = detail[detail["year"].eq(year)].pivot(index="state_fips", columns="age_group",
                                                     values="rate_exported")
        joined = table8.set_index("state_fips").join(mine)
        diffs = pd.concat([(joined["20-24"] - joined["rate_20_24"]).abs(),
                           (joined["25-29"] - joined["rate_25_29"]).abs()]).dropna()
        results["state_table8"][str(year)] = {
            "report": path.name, "jurisdictions_in_table8": int(len(table8)),
            "rates_compared": int(diffs.size),
            "max_abs_difference": float(diffs.max()) if diffs.size else None,
            "outside_published_precision": int((diffs > PUBLISHED_HALF_UNIT).sum()),
            "official_rates_without_export_rate": int(2 * len(table8) - diffs.size),
        }
    if texts:
        latest = max(texts)
        national = parse_nvsr_table2(texts[latest]).set_index("year")
        sums = detail.groupby(["year", "age_group"])[["births", "female_population"]].sum(
            min_count=1)
        rows = []
        for (year, age), row in sums.iterrows():
            if year in national.index and pd.notna(row["female_population"]):
                official = float(national.loc[year, f"rate_{age.replace('-', '_')}"])
                mine_rate = float(1000 * row["births"] / row["female_population"])
                rows.append({"year": int(year), "age_group": age,
                             "recalculated": round(mine_rate, 3), "nvsr": official,
                             "difference": round(mine_rate - official, 3),
                             "within_published_precision":
                                 abs(mine_rate - official) <= PUBLISHED_HALF_UNIT,
                             "note": DENOMINATOR_DIFFERENCE_YEARS.get(int(year), "")})
        results["national_table2"] = {"report": NVSR_REPORTS[latest].name, "rows": rows}
    return results


BENCHMARK_PATH = PROCESSED_DIR / "nvsr_state_rate_benchmark.csv"


def state_benchmark_details(detail: pd.DataFrame) -> pd.DataFrame:
    """Every exported state rate next to the published NVSR value, one row per state-age-year."""
    names = detail.drop_duplicates("state_fips").set_index("state_name")["state_fips"]
    rows = []
    for year, path in NVSR_REPORTS.items():
        if not path.exists():
            continue
        table = parse_nvsr_state_table(path.read_text(encoding="utf-8", errors="replace"))
        table = table[table["area"].isin(names.index)]
        mine = detail[detail["year"].eq(year)].set_index(["state_fips", "age_group"])
        for row in table.itertuples():
            for age in AGE_GROUPS:
                exported = float(mine.loc[(names[row.area], age), "rate_exported"])
                published = getattr(row, f"rate_{age.replace('-', '_')}")
                rows.append({"year": year, "report": path.stem, "state_fips": names[row.area],
                             "state_name": row.area, "age_group": age,
                             "exported_rate": exported, "published_rate": published,
                             "difference": exported - published,
                             "within_published_precision":
                                 abs(exported - published) <= PUBLISHED_HALF_UNIT})
    return pd.DataFrame(rows)


def reconcile(original: pd.DataFrame, expanded: pd.DataFrame) -> dict:
    """Exact agreement of the two exports on every shared year-state-age key."""
    keys = ["year", "state_fips", "age_group"]
    merged = original.merge(expanded, on=keys, suffixes=("_original", "_expanded"),
                            how="inner", validate="one_to_one")
    shared = {"births": merged.index == merged.index}
    result = {"shared_keys": len(merged), "comparisons": {}}
    both_rates = merged["rate_exported_original"].notna()
    for column, mask in (("births", shared["births"]),
                         ("female_population", both_rates.to_numpy()),
                         ("rate_exported", both_rates.to_numpy())):
        a = merged.loc[mask, f"{column}_original"]
        b = merged.loc[mask, f"{column}_expanded"]
        disagree = merged.loc[mask][a.ne(b).to_numpy()]
        result["comparisons"][column] = {
            "compared": int(mask.sum()),
            "years": sorted(merged.loc[mask, "year"].unique().tolist()),
            "disagreements": int(len(disagree)),
            "examples": disagree[keys].head(5).to_dict("records")}
    result["state_names_disagree"] = int(
        merged["state_name_original"].ne(merged["state_name_expanded"]).sum())
    result["expanded_fills_original_gaps"] = int(
        (merged["rate_exported_original"].isna() & merged["rate_exported_expanded"].notna())
        .sum())
    result["agree"] = (all(c["disagreements"] == 0 for c in result["comparisons"].values())
                       and result["state_names_disagree"] == 0)
    return result


def combine(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """2014-2015 from the original export and 2016-2024 from the expanded export."""
    parts = [sources[name][sources[name]["year"].eq(year)].assign(source=name)
             for year, name in ANALYTIC_SOURCE.items()]
    combined = pd.concat(parts, ignore_index=True)
    if combined.duplicated(["year", "state_fips", "age_group"]).any():
        raise ValueError("Duplicate keys in the combined natality series")
    return combined


def hard_failures(report: dict) -> bool:
    return bool(report["duplicate_keys"] or report["missing_combinations"]
                or report["unexpected_combinations"] or report["unexpected_age_labels"]
                or report["unexpected_special_values"] or report["zero_or_negative_births"]
                or report["rate_mismatches"] or report["inconsistent_state_names"]
                or any(report["totals"][k] for k in ("state_year_birth_mismatches",
                                                     "year_birth_mismatches",
                                                     "state_year_population_mismatches"))
                or not report["totals"]["grand_total_matches"])


def status(report: dict) -> str:
    official = report["official_comparison"]
    national = (official.get("national_table2") or {}).get("rows", [])
    unexplained = [r for r in national if not r["within_published_precision"] and not r["note"]]
    hard = (any(hard_failures(r) for r in report["sources"].values())
            or not report["reconciliation"]["agree"]
            or report["combined"]["duplicate_keys"] or report["combined"]["missing_combinations"]
            or any(r.get("outside_published_precision")
                   for r in official["state_table8"].values()) or unexplained)
    if hard:
        return "FAIL"
    combined = report["combined"]
    return ("WARN" if combined["rows_without_rate"] or combined["suppressed_cells"]
            else "PASS")


def build(sources: dict = SOURCES) -> tuple[pd.DataFrame, dict]:
    details, report = {}, {"sources": {}}
    for name, spec in sources.items():
        frame, metadata = parse_export(spec["path"])
        detail, totals = tidy(frame)
        source_report = validate(detail, totals, metadata, spec["years"])
        if source_report["dataset"] != spec["dataset"]:
            source_report["dataset_mismatch"] = spec["dataset"]
        source_report["sha256"] = hashlib.sha256(
            Path(spec["path"]).read_bytes()).hexdigest()
        source_report["file"] = Path(spec["path"]).name
        details[name], report["sources"][name] = detail, source_report
    report["reconciliation"] = reconcile(details["original"], details["expanded"])
    combined = combine(details)
    keys = combined[["year", "state_fips", "age_group"]]
    expected = pd.MultiIndex.from_product([YEARS, STATE_FIPS, list(AGE_GROUPS)])
    report["combined"] = {
        "rows": len(combined), "expected": len(expected),
        "rows_by_source": combined["source"].value_counts().to_dict(),
        "duplicate_keys": int(keys.duplicated().sum()),
        "missing_combinations": len(expected.difference(pd.MultiIndex.from_frame(keys))),
        "rows_without_rate": int(combined["rate_exported"].isna().sum()),
        "suppressed_cells": int(combined[[c for c in combined if c.endswith("_status")]]
                                .eq("Suppressed").sum().sum()),
        "rate_available_by_year": combined.groupby("year")["rate_exported"].apply(
            lambda s: int(s.notna().sum())).to_dict()}
    report["official_comparison"] = compare_official(combined)
    report["status"] = status(report)
    combined["rate_recalculated"] = 1000 * combined["births"] / combined["female_population"]
    return combined.sort_values(["year", "state_fips", "age_group"]).reset_index(drop=True), \
        report


PROVENANCE_PATH = CDC_DIR / "provenance.json"
QUERY_FIELDS = ["Dataset", "Age of Mother 9", "Year", "Group By", "Show Totals",
                "Show Zero Values", "Show Suppressed", "Calculate Rates Per", "Query Date"]


def provenance(sources: dict = SOURCES) -> dict:
    """Per-file provenance from each export's own footer (files are not modified)."""
    files = {}
    for name, spec in sources.items():
        path = Path(spec["path"])
        _, metadata = parse_export(path)
        fields = metadata.get("fields", {})
        files[path.name] = {
            "role": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "format": metadata["format"],
            "state_column": metadata["state_header"],
            "query": {k: fields.get(k) for k in QUERY_FIELDS},
            "citation": " ".join(line for line in metadata["footer"]
                                 if line.startswith(("Suggested Citation", "System,", "the 57",
                                                     "http://wonder"))),
            "obtained_by": "manual export from CDC WONDER by the project owner",
            "analytic_years": [y for y, s in ANALYTIC_SOURCE.items() if s == name]}
    return {"source": "CDC/NCHS National Vital Statistics System, Natality on CDC WONDER",
            "residence": "mother's legal residence (CDC WONDER natality help)", "files": files}


def main() -> int:
    detail, report = build()
    PROVENANCE_PATH.write_text(json.dumps(provenance(), indent=1) + "\n", encoding="utf-8")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    detail.drop(columns="age_label").to_csv(OUTPUT_PATH, index=False, float_format="%.10g")
    state_benchmark_details(detail).to_csv(BENCHMARK_PATH, index=False, float_format="%.10g")
    (PROCESSED_DIR / "cdc_natality_validation.json").write_text(
        json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    for name, source in report["sources"].items():
        print(f"CDC WONDER {name} | {source['dataset']} | column '{source['state_header']}' | "
              f"{source['detail_rows']} rows (expected {source['expected_combinations']}); "
              f"duplicates {source['duplicate_keys']}; missing "
              f"{len(source['missing_combinations'])}; rates recalculated "
              f"{source['rates_recalculated']}, mismatches {source['rate_mismatches']}; "
              f"total rows {source['total_rows']} (state-year/year mismatches "
              f"{source['totals']['state_year_birth_mismatches']}/"
              f"{source['totals']['year_birth_mismatches']})")
    rec = report["reconciliation"]
    print(f"Reconciliation | shared keys {rec['shared_keys']}; " + "; ".join(
        f"{k} {v['compared']} compared ({v['years'][0]}-{v['years'][-1]}), "
        f"{v['disagreements']} disagree" for k, v in rec["comparisons"].items())
          + f"; agree: {rec['agree']}")
    combined = report["combined"]
    print(f"Combined | {combined['rows']} rows (expected {combined['expected']}), by source "
          f"{combined['rows_by_source']}; without rate {combined['rows_without_rate']}")
    official = report["official_comparison"]
    for year, result in official["state_table8"].items():
        print(f"  NVSR Table 8, {year}: {result}")
    for row in official["national_table2"]["rows"]:
        print(f"  NVSR Table 2, {row['year']} {row['age_group']}: recalculated "
              f"{row['recalculated']} vs {row['nvsr']} ({row['difference']:+.3f}) {row['note']}")
    print(f"Status: {report['status']}")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
