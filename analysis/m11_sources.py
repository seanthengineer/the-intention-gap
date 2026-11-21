"""M11 source acquisition, provenance and parsing (NCHS, Census estimates, Census projections).

M11 is a data-acquisition and feasibility stage: nothing here fits a model or
produces a forecast. The Human Fertility Database (HFD) files are handled in
analysis/hfd.py; this module covers the other official sources.

Sources (all saved locally in data/raw/, never modified):

- nchs_2025/: NCHS Data Brief 571 "Births in the United States, 2025" (final
  2025 data, 21 Oct 2026), VSRR 43 "Births: Provisional Data for 2025" (Apr 2026)
  and NCHS index pages saved as evidence of publication status.
- nchs_natality_puf/: the 2024 and 2025 natality public-use files (one
  fixed-width record per birth, no personal identifiers) and their user guides.
  They are only ever tabulated into aggregate counts by year, single year of
  mother's age, residence status and live-birth order.
- nchs_nvsr/ (saved in M10, read only): "Births: Final Data" for 2019, 2023 and
  2024, whose Table 2 gives national birth rates and the TFR for 2010 onward.
- census_popest/: national population estimates by single year of age and sex,
  vintages 2024 and 2025 (the NCHS rate denominators), with method statements.
- census_np2023/: the 2023 National Population Projections (main series and
  high, low and zero immigration scenarios), file layouts and method statement.

    python -m analysis.m11_sources --provenance   # hash and describe every raw file
    python -m analysis.m11_sources --tabulate     # stream the public-use files (slow)
    python -m analysis.m11_sources                # parse and validate everything else
"""

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.nlsy97 import PROJECT_ROOT

RAW = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "m11"
PUBLIC_DIR = PROJECT_ROOT / "data" / "public" / "m11"
RETRIEVED = "2026-11-20"

NCHS_DIR = RAW / "nchs_2025"
PUF_DIR = RAW / "nchs_natality_puf"
NVSR_DIR = RAW / "nchs_nvsr"
POPEST_DIR = RAW / "census_popest"
NP_DIR = RAW / "census_np2023"
HFD_DIR = RAW / "hfd_usa"
HFD_DOCS_DIR = RAW / "hfd_docs"

CDC = "https://www.cdc.gov/nchs"
FTP = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS"
POPEST = "https://www2.census.gov/programs-surveys/popest"
POPPROJ = "https://www2.census.gov/programs-surveys/popproj"
HFD = "https://www.humanfertility.org"

# Every raw M11 file with its origin. "manual" marks files the owner obtained.
SOURCE_URLS = {
    "hfd_usa": {
        "USA.zip": f"{HFD}/Data/ZippedDataFiles (country archive; login required; downloaded by the owner)",
        "*.txt": "extracted from USA.zip (byte-identical to the archive members)",
    },
    "hfd_docs": {
        "USAnote.pdf": f"{HFD}/File/GetDocument/Docs/USA%5CUSAnote.pdf",
        "USAref.pdf": f"{HFD}/File/GetDocument/Docs/USA%5CUSAref.pdf",
        "USA_indb-map.pdf": f"{HFD}/File/GetDocument/Docs/USA%5CUSA_indb-map.pdf",
        "methods.pdf": f"{HFD}/File/GetDocumentFree/Docs/methods.pdf",
        "formats.pdf": f"{HFD}/File/GetDocumentFree/Docs/formats.pdf",
        "country_usa.html": f"{HFD}/Country/Country?cntr=USA",
    },
    "nchs_2025": {
        "db571.pdf": f"{CDC}/data/databriefs/db571.pdf",
        "db571.htm": f"{CDC}/products/databriefs/db571.htm",
        "vsrr043.pdf": f"{CDC}/data/vsrr/vsrr043.pdf",
        "nvsr.htm": f"{CDC}/products/nvsr.htm",
        "births.htm": f"{CDC}/nvss/births.htm",
        "upcoming.htm": f"{CDC}/pressroom/upcoming.htm",
    },
    "nchs_natality_puf": {
        "Nat2025us.zip": f"{FTP}/Datasets/DVS/natality/Nat2025us.zip",
        "Nat2024us.zip": f"{FTP}/Datasets/DVS/natality/Nat2024us.zip",
        "UserGuide2025.pdf": f"{FTP}/Dataset_Documentation/DVS/natality/UserGuide2025.pdf",
        "UserGuide2024.pdf": f"{FTP}/Dataset_Documentation/DVS/natality/UserGuide2024.pdf",
    },
    "census_popest": {
        "nc-est2025-agesex-res.csv": f"{POPEST}/datasets/2020-2025/national/asrh/nc-est2025-agesex-res.csv",
        "nc-est2024-agesex-res.csv": f"{POPEST}/datasets/2020-2024/national/asrh/nc-est2024-agesex-res.csv",
        "NC-EST2025-AGESEX-RES.pdf": f"{POPEST}/technical-documentation/file-layouts/2020-2025/NC-EST2025-AGESEX-RES.pdf",
        "methods-statement-v2025.pdf": f"{POPEST}/technical-documentation/methodology/2020-2025/methods-statement-v2025.pdf",
        "2025-est-relnotes.pdf": f"{POPEST}/technical-documentation/methodology/2020-2025/2025-est-relnotes.pdf",
        "methods-statement-v2024.pdf": f"{POPEST}/technical-documentation/methodology/2020-2024/methods-statement-v2024.pdf",
        "2024-est-relnotes.pdf": f"{POPEST}/technical-documentation/methodology/2020-2024/2024-est-relnotes.pdf",
    },
    "census_np2023": {
        "np2023_*.csv": f"{POPPROJ}/datasets/2023/2023-popproj/",
        "np2023_*_layout.pdf": f"{POPPROJ}/technical-documentation/file-layouts/2023/np2023_*.pdf",
        "methodstatement23.pdf": f"{POPPROJ}/technical-documentation/methodology/methodstatement23.pdf",
    },
}

PUBLICATION_STATUS = {
    "final_2025_births_data_file": "Nat2025us.zip, last modified 2026-10-15 (2025 natality public-use file)",
    "final_2025_data_brief": "NCHS Data Brief 571, Births in the United States, 2025, 2026-10-21",
    "provisional_2025_report": "VSRR 43, Births: Provisional Data for 2025, 2026-04-09",
    "final_2025_nvsr": ("not published as of 2026-11-20: nvsr.htm and births.htm list Births: Final "
                        "Data for 2024 (2026-06-09) as the latest final report"),
    "official_2025_tfr": "not published in DB571 or VSRR 43 (both give GFR and 5-year age rates only)",
}


# --------------------------------------------------------------- provenance

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_url(directory: str, name: str) -> str:
    urls = SOURCE_URLS.get(directory, {})
    if name in urls:
        return urls[name]
    if name.endswith(".txt") and (Path(name).stem + ".pdf") in urls:
        return "pdftotext -layout of " + Path(name).stem + ".pdf"
    for pattern, url in urls.items():
        if "*" in pattern and Path(name).match(pattern):
            return url.replace("*", Path(name).stem.split("_layout")[0].replace("np2023_", "")) \
                if pattern.endswith("_layout.pdf") else url + (name if url.endswith("/") else "")
    return "unknown"


def write_provenance(directory: str, notes: dict | None = None) -> dict:
    folder = RAW / directory
    files = {}
    for path in sorted(p for p in folder.iterdir() if p.is_file() and p.name != "provenance.json"):
        files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path),
                            "source": source_url(directory, path.name)}
    record = {"retrieved": RETRIEVED, "directory": f"data/raw/{directory}", "files": files}
    if notes:
        record.update(notes)
    (folder / "provenance.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return record


PROVENANCE_NOTES = {
    "hfd_usa": {"release": "HFD country page last update 02.07.2026; file headers 'Last modified: 27/06/2026'",
                "obtained_by": "owner download of USA.zip (HFD account required); copy of the archive kept here",
                "terms": "HFD user agreement: data may be used for research with citation; not redistributed"},
    "hfd_docs": {"note": "HFD input-data files (USAbirths.txt, USAmonthly.txt, USAparity.txt) require "
                         "an HFD login and were not retrieved"},
    "nchs_2025": {"publication_status": PUBLICATION_STATUS,
                  "text_extraction": "pdftotext -layout (xpdf 4.06); .txt files beside each PDF"},
    "nchs_natality_puf": {"note": "record-level public-use files without personal identifiers; kept "
                                  "local and tabulated only into aggregate counts"},
    "census_popest": {"note": "July 1 resident population by single year of age and sex; NCHS rate denominators"},
    "census_np2023": {"release": "November 2023; base population July 1, 2022 (vintage 2022 estimates)"},
}


# ------------------------------------------------------- natality public-use file

PUF_DOCUMENTED_LENGTH = 1330   # user guides; the 2024 and 2025 files have 1,345-byte records
PUF_FIELDS = {"year": (9, 12), "month": (13, 14), "age_imputed": (73, 73), "mager": (75, 76),
              "restatus": (104, 104), "lbo_rec": (179, 179)}   # 1-based inclusive positions
PUF_ZIPS = {2024: PUF_DIR / "Nat2024us.zip", 2025: PUF_DIR / "Nat2025us.zip"}


def puf_key(record: bytes) -> tuple:
    return tuple(record[start - 1:end].decode("ascii").strip() for start, end in PUF_FIELDS.values())


def tabulate_puf_stream(handle) -> tuple[Counter, Counter]:
    """Aggregate counts by (year, age_imputed, mager, restatus, lbo_rec) and record-length checks."""
    counts, lengths = Counter(), Counter()
    for line in handle:
        record = line.rstrip(b"\r\n")
        lengths[len(record)] += 1
        counts[puf_key(record)] += 1
    return counts, lengths


DEFLATE64 = 9   # used by the NCHS archives; not supported by Python's zipfile


def tabulate_puf(year: int, path: Path | None = None) -> pd.DataFrame:
    path = path or PUF_ZIPS[year]
    with zipfile.ZipFile(path) as archive:
        (info,) = archive.infolist()
        member = info.filename
        if info.compress_type != DEFLATE64:
            with archive.open(member) as handle:
                counts, lengths = tabulate_puf_stream(handle)
    if info.compress_type == DEFLATE64:
        unzip = shutil.which("unzip")
        if unzip is None:
            raise RuntimeError("Deflate64 archive: Info-ZIP 'unzip' is required to stream it")
        process = subprocess.Popen([unzip, "-p", str(path), member], stdout=subprocess.PIPE,
                                   bufsize=1 << 20)
        counts, lengths = tabulate_puf_stream(process.stdout)
        if process.wait() != 0:
            raise RuntimeError(f"unzip exited with code {process.returncode} for {path.name}")
    rows = [dict(zip(PUF_FIELDS, key), births=n) for key, n in sorted(counts.items())]
    table = pd.DataFrame(rows)
    table.attrs.update(member=member, lengths=dict(lengths))
    return table


def puf_output(year: int) -> Path:
    return PROCESSED_DIR / f"nchs_puf_{year}_age_order.csv"


def write_puf_tabulations() -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    summary = {}
    for year in PUF_ZIPS:
        table = tabulate_puf(year)
        table.to_csv(puf_output(year), index=False)
        summary[year] = {"member": table.attrs["member"], "records": int(table["births"].sum()),
                         "record_lengths": {str(k): v for k, v in table.attrs["lengths"].items()}}
    (PROCESSED_DIR / "nchs_puf_tabulation.json").write_text(json.dumps(summary, indent=1),
                                                             encoding="utf-8")
    return summary


def load_puf_births(year: int, residents_only: bool = True) -> pd.DataFrame:
    """Births by single year of mother's age (MAGER 12 = 10-12, 50 = 50-54) and live-birth order."""
    table = pd.read_csv(puf_output(year), dtype=str, keep_default_na=False)
    table["births"] = table["births"].astype(int)
    if residents_only:
        table = table[table["restatus"] != "4"]      # 4 = foreign resident
    table = table.assign(age=table["mager"].astype(int), year=table["year"].astype(int))
    return table


def puf_births_by_age(year: int) -> pd.Series:
    table = load_puf_births(year)
    return table.groupby("age")["births"].sum()


# ------------------------------------------------------------ NCHS publications

DOT_LEADERS = re.compile(r"(\s*\.\s*){3,}")


def pdf_text(name: str, folder: Path = NCHS_DIR) -> str:
    return (folder / name).read_text(encoding="utf-8", errors="replace")


def number(token: str) -> float:
    return float(token.replace(",", "").rstrip("*"))


def parse_db571() -> dict:
    """Final 2025 births, GFR and 5-year age-specific rates (Data Brief 571 figure tables)."""
    text = pdf_text("db571.txt")
    births = {}
    for year in (2024, 2025):
        match = re.search(rf"^{year}\s+([\d,]+)\*?\s+([\d.]+)\*?\s*$", text, re.M)
        births[year] = {"births": int(number(match.group(1))), "gfr": number(match.group(2))}
    block = text.split("Data table for Figure 2")[1].split("Data table for Figure 3")[0]
    rates = {}
    for match in re.finditer(r"^(\d\d-\d\d)\s+([\d.]+)\s+([\d.]+)\*?\s*$", block, re.M):
        rates[match.group(1)] = {2024: float(match.group(2)), 2025: float(match.group(3))}
    return {"births": births, "rates": rates,
            "release": re.search(r"Number 571 \| (\w+ \d+, \d{4})", text).group(1)}


def parse_vsrr043() -> dict:
    """Provisional 2025 and final 2024 births and rates by age (VSRR 43 Table 1)."""
    text = pdf_text("vsrr043.txt")
    block = text.split("Table 1. Births and birth rate")[1].split("Table 2.")[0]
    rows = {}
    for line in block.splitlines():
        line = DOT_LEADERS.sub("  ", line).strip()
        match = re.match(r"^(All ages|\d\d-\d\d)\d?\s+([\d,]+)\s+([\d.]+)\s+([\d,]+)\s+([\d.]+)$", line)
        if match:
            label = match.group(1)
            rows[label] = {"births_2025p": int(number(match.group(2))), "rate_2025p": float(match.group(3)),
                           "births_2024": int(number(match.group(4))), "rate_2024": float(match.group(5))}
    return rows


NVSR_REPORTS = {2019: "nvsr70-02-508.txt", 2023: "nvsr74-1.txt", 2024: "nvsr75-02.txt"}
NVSR_AGES = ["10-14", "15-19", "15-17", "18-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]


def parse_nvsr_table2(report_year: int) -> pd.DataFrame:
    """National TFR and age-specific rates, all races and origins (NVSR Table 2, first block)."""
    text = pdf_text(NVSR_REPORTS[report_year], NVSR_DIR)
    start = text.index("Table 2. Birth rates, by age of mother")
    block = text[start:start + 6000]
    rows = []
    for line in block.splitlines():
        line = DOT_LEADERS.sub("  ", line).strip()
        match = re.match(r"^(\d{4})\s+([\d,]+\.\d)\s+(.*)$", line)
        if not match:
            if rows and not re.match(r"^\d{4}", line) and "races" not in line and line:
                if any(c.isalpha() for c in line) and "rate" not in line.lower():
                    break
            continue
        values = [float(v) for v in match.group(3).split()]
        if len(values) != len(NVSR_AGES):
            continue
        rows.append({"report": report_year, "year": int(match.group(1)),
                     "tfr": number(match.group(2)), **dict(zip(NVSR_AGES, values))})
        if len(rows) >= report_year - 2010 + 1 and rows[-1]["year"] == 2010:
            break
    table = pd.DataFrame(rows).drop_duplicates("year")
    return table


def parse_nvsr_table1(report_year: int = 2024) -> pd.DataFrame:
    """National births, all races and origins (NVSR Table 1, first block)."""
    text = pdf_text(NVSR_REPORTS[report_year], NVSR_DIR)
    start = text.index("Table 1. Births and birth rates")
    rows = []
    for line in text[start:start + 5000].splitlines():
        line = DOT_LEADERS.sub("  ", line).strip()
        match = re.match(r"^(\d{4})\s+([\d,]{7,})\s+([\d.]+)\s+([\d.]+)$", line)
        if match:
            rows.append({"year": int(match.group(1)), "births": int(number(match.group(2))),
                         "gfr": float(match.group(4))})
        if rows and rows[-1]["year"] == 2010:
            break
    return pd.DataFrame(rows)


# ------------------------------------------------------- Census population estimates

POPEST_FILES = {2024: POPEST_DIR / "nc-est2024-agesex-res.csv",
                2025: POPEST_DIR / "nc-est2025-agesex-res.csv"}


def load_popest(vintage: int) -> pd.DataFrame:
    """Female July 1 resident population by single year of age (85 = 85+), long format."""
    table = pd.read_csv(POPEST_FILES[vintage])
    female = table[(table["SEX"] == 2) & (table["AGE"] < 999)]
    columns = [c for c in table.columns if c.startswith("POPESTIMATE")]
    long = female.melt(id_vars="AGE", value_vars=columns, var_name="column", value_name="population")
    long["year"] = long["column"].str[-4:].astype(int)
    long["vintage"] = vintage
    return long.rename(columns={"AGE": "age"})[["vintage", "year", "age", "population"]]


def popest_checks(vintage: int) -> list[dict]:
    table = pd.read_csv(POPEST_FILES[vintage])
    checks = []
    for column in [c for c in table.columns if c.startswith(("POP", "EST"))]:
        both = table[(table["SEX"] == 0) & (table["AGE"] < 999)][column].sum()
        sexes = table[(table["SEX"] > 0) & (table["AGE"] < 999)][column].sum()
        total = table[(table["SEX"] == 0) & (table["AGE"] == 999)][column].sum()
        checks.append({"vintage": vintage, "column": column, "ok": bool(both == sexes == total),
                       "detail": f"ages sum {both:,}; male+female {sexes:,}; total row {total:,}"})
    return checks


def nchs_style_rates(births: pd.Series, female: pd.Series) -> dict:
    """5-year rates per 1,000 using NCHS conventions (10-14 births / 10-14 women; 45+ / 45-49)."""
    groups = {"10-14": range(10, 15), "15-19": range(15, 20), "20-24": range(20, 25),
              "25-29": range(25, 30), "30-34": range(30, 35), "35-39": range(35, 40),
              "40-44": range(40, 45), "45-49": range(45, 50)}
    rates = {}
    for label, ages in groups.items():
        if label == "10-14":
            numerator = births[births.index <= 14].sum()
        elif label == "45-49":
            numerator = births[births.index >= 45].sum()
        else:
            numerator = births[[a for a in ages]].sum()
        rates[label] = 1000 * numerator / female[list(ages)].sum()
    rates["tfr"] = 5 * sum(rates[label] for label in groups)
    rates["gfr"] = 1000 * births.sum() / female[list(range(15, 45))].sum()
    return rates


def single_year_rates(births: pd.Series, female: pd.Series) -> pd.Series:
    """Rates per woman by single year of age, HFD-style open ends (12 = 12 and under, 50 = 50-54)."""
    ages = range(12, 51)
    return pd.Series({age: births.get(age, 0) / female[age] for age in ages}, name="asfr")


# ------------------------------------------------------- Census 2023 projections

NP_SCENARIOS = {"mid": "main series", "hi": "high immigration", "low": "low immigration",
                "zero": "zero immigration"}
NP_FILES = {
    "a1": "Projected age-specific fertility rates, women 14-54, by nativity/race/Hispanic group, 2023-2100",
    "a2": "Projected age-specific death rates by nativity, sex and group",
    "a3": "Projected life expectancy at birth by nativity, sex and group",
    "a4": "Projected survival ratios by nativity, sex and group",
    "a5": "Projected total fertility rates by nativity/race/Hispanic group, 2023-2100",
    "d1": "Projected population by single year of age, sex, race and Hispanic origin, 2022-2100",
    "d2": "Projected births by sex, race and Hispanic origin, 2023-2100",
    "d3": "Projected deaths by single year of age, sex, race and Hispanic origin",
    "d4": "Projected net international migration by single year of age, sex, race and Hispanic origin",
    "d5": "Projected population by single year of age, sex, race, Hispanic origin and nativity",
}


def np_path(code: str, scenario: str | None = None) -> Path:
    return NP_DIR / (f"np2023_{code}.csv" if scenario is None else f"np2023_{code}_{scenario}.csv")


def load_np_asfr() -> pd.DataFrame:
    """Total-group projected ASFR by single year of age (rates per woman), long format."""
    table = pd.read_csv(np_path("a1"))
    total = table[table["GROUP"] == 0]
    long = total.melt(id_vars="YEAR", value_vars=[c for c in table.columns if c.startswith("ASFR_")],
                      var_name="column", value_name="asfr")
    long["age"] = long["column"].str[5:].astype(int)
    return long.rename(columns={"YEAR": "year"})[["year", "age", "asfr"]]


def load_np_tfr() -> pd.DataFrame:
    return pd.read_csv(np_path("a5")).rename(columns={"YEAR": "year", "TOTAL": "tfr"})


def load_np_female(scenario: str = "mid") -> pd.DataFrame:
    """Projected female July 1 population by single year of age (100 = 100+), all races and origins."""
    table = pd.read_csv(np_path("d1", scenario))
    female = table[(table["SEX"] == 2) & (table["ORIGIN"] == 0) & (table["RACE"] == 0)]
    long = female.melt(id_vars="YEAR", value_vars=[c for c in table.columns if c.startswith("POP_")],
                       var_name="column", value_name="population")
    long["age"] = long["column"].str[4:].astype(int)
    long["scenario"] = scenario
    return long.rename(columns={"YEAR": "year"})[["scenario", "year", "age", "population"]]


def load_np_births(scenario: str = "mid") -> pd.DataFrame:
    table = pd.read_csv(np_path("d2", scenario))
    total = table[(table["RACE_HISP"] == 0) & (table["SEX"] == 0)]
    return total.rename(columns={"YEAR": "year", "BIRTHS": "births"})[["year", "births"]].assign(
        scenario=scenario)


def np_inventory() -> pd.DataFrame:
    rows = []
    for code, description in NP_FILES.items():
        scenarios = [None] if code.startswith("a") else list(NP_SCENARIOS)
        for scenario in scenarios:
            path = np_path(code, scenario)
            table = pd.read_csv(path)
            table.columns = [c.strip('"') for c in table.columns]
            rows.append({"file": path.name, "description": description,
                         "scenario": NP_SCENARIOS[scenario] if scenario else "all (not scenario-specific)",
                         "rows": len(table), "year_min": int(table["YEAR"].min()),
                         "year_max": int(table["YEAR"].max()),
                         "period": ("July 1 of YEAR" if code in ("d1", "d5") else
                                    "July 1 of YEAR-1 to June 30 of YEAR")})
    return pd.DataFrame(rows)


def np_checks() -> list[dict]:
    """Internal consistency of the Census projection files."""
    checks = []
    asfr = load_np_asfr()
    tfr = load_np_tfr().set_index("year")["tfr"]
    summed = asfr.groupby("year")["asfr"].sum()
    gap = (summed - tfr).abs().max()
    # 41 rates rounded to 4 decimals plus a TFR rounded to 4 decimals
    checks.append({"check": "A5 TFR equals the sum of A1 single-year ASFRs (total group)",
                   "ok": bool(gap <= 41 * 5e-5 + 5e-5), "detail": f"max |sum - TFR| = {gap:.5f}"})
    for scenario in NP_SCENARIOS:
        table = pd.read_csv(np_path("d1", scenario))
        pops = table[[c for c in table.columns if c.startswith("POP_")]].sum(axis=1)
        ok_age = bool((pops == table["TOTAL_POP"]).all())
        base = table[(table["ORIGIN"] == 0) & (table["RACE"] == 0)]
        both = base[base["SEX"] == 0].set_index("YEAR")["TOTAL_POP"]
        sexes = base[base["SEX"] > 0].groupby("YEAR")["TOTAL_POP"].sum()
        ok_sex = bool((both == sexes).all())
        births = pd.read_csv(np_path("d2", scenario))
        tot = births[births["RACE_HISP"] == 0]
        b_both = tot[tot["SEX"] == 0].set_index("YEAR")["BIRTHS"]
        b_sex = tot[tot["SEX"] > 0].groupby("YEAR")["BIRTHS"].sum()
        checks.append({"check": f"D1/D2 {scenario}: ages sum to totals, sexes sum to both sexes",
                       "ok": ok_age and ok_sex and bool((b_both == b_sex).all()),
                       "detail": f"ages {ok_age}; population sexes {ok_sex}; births sexes "
                                 f"{bool((b_both == b_sex).all())}"})
    base = {s: load_np_female(s).query("year == 2022").set_index("age")["population"]
            for s in NP_SCENARIOS}
    same = all((base[s] == base["mid"]).all() for s in NP_SCENARIOS)
    checks.append({"check": "All four scenarios share the July 1, 2022 base population",
                   "ok": same, "detail": "female single-year counts identical in 2022" if same else
                   "base populations differ"})
    return checks


def np_births_reproduction(scenario: str = "mid") -> pd.DataFrame:
    """Projected births against total-group ASFR x female population (approximation, see notes).

    Census computes births within six nativity/race groups; the total-group rates
    reproduce them only approximately. Two denominators are tried: the July 1
    population of YEAR and the mean of July 1 of YEAR-1 and YEAR.
    """
    asfr = load_np_asfr().pivot(index="year", columns="age", values="asfr")
    female = load_np_female(scenario).pivot(index="year", columns="age", values="population")
    births = load_np_births(scenario).set_index("year")["births"]
    rows = []
    for year in asfr.index:
        if year not in female.index or year - 1 not in female.index:
            continue
        ages = asfr.columns
        end = float((asfr.loc[year] * female.loc[year, ages]).sum())
        mean = float((asfr.loc[year] * (female.loc[year, ages] + female.loc[year - 1, ages]) / 2).sum())
        rows.append({"scenario": scenario, "year": year, "births": births[year],
                     "ratio_july1": births[year] / end, "ratio_mean": births[year] / mean})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provenance", action="store_true")
    parser.add_argument("--tabulate", action="store_true")
    args = parser.parse_args(argv)
    if args.provenance:
        for directory in ("hfd_usa", "hfd_docs", "nchs_2025", "nchs_natality_puf", "census_popest",
                          "census_np2023"):
            record = write_provenance(directory, PROVENANCE_NOTES.get(directory))
            print(f"{directory}: {len(record['files'])} files")
    if args.tabulate:
        for year, info in write_puf_tabulations().items():
            print(f"PUF {year}: {info['records']:,} records; lengths {info['record_lengths']}")
    if not (args.provenance or args.tabulate):
        print(json.dumps(parse_db571(), indent=1, default=str))
        print(json.dumps(parse_vsrr043(), indent=1))
        for check in np_checks():
            print(("PASS" if check["ok"] else "FAIL"), check["check"], "-", check["detail"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
