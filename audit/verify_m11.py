"""Verification of the M11 data-acquisition and feasibility outputs, with each check labelled.

INDEPENDENT checks share no code with analysis/hfd.py, analysis/m11_sources.py or
analysis/m11_feasibility.py. They read the raw HFD text files, Census CSV files,
NCHS report text and the natality public-use archives directly (with the
standard library, numpy and pandas only), recompute the reported quantities and
compare them with the stored tables in data/public/m11/.
RECONCILIATION checks compare stored hashes and files: provenance records,
the HFD archive against its extracted files, the frozen M09/M10 manifests,
and headline numbers quoted in docs/m11_data_feasibility.md.

The public-use recount streams about 9.8 GB through Info-ZIP unzip and takes
one to two minutes; --skip-puf skips it.

    python audit/verify_m11.py [--skip-puf]
"""

import argparse
import csv
import hashlib
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

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PUBLIC = ROOT / "data" / "public" / "m11"
REPORT = ROOT / "docs" / "m11_data_feasibility.md"
INDEPENDENT, RECONCILIATION = "independent", "reconciliation"


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, kind, label, ok, detail):
        self.rows.append((kind, "PASS" if ok else "FAIL", label, detail))

    def close(self, kind, label, observed, expected, tol):
        ok = bool(abs(observed - expected) <= tol)
        self.add(kind, label, ok, f"recomputed {observed:.6f} vs stored {expected:.6f} (tol {tol:g})")


def stored(name: str) -> pd.DataFrame:
    return pd.read_csv(PUBLIC / f"m11_{name}.csv")


# ------------------------------------------------------------------ HFD raw text

def hfd_rows(name: str) -> list[list[str]]:
    lines = (RAW / "hfd_usa" / f"{name}.txt").read_text(encoding="utf-8").splitlines()
    return [line.split() for line in lines[3:] if line.strip()]


def hfd_period(name: str, column: int) -> dict:
    """{(year, age): value} from an RR file, open ages '12-'/'55+' mapped to 12/55."""
    return {(int(r[0]), int(r[1].rstrip("+-"))): float(r[column]) for r in hfd_rows(name)}


def check_hfd(c: Checks):
    births, expos = hfd_period("USAbirthsRR", 2), hfd_period("USAexposRR", 2)
    tfr = {}
    for (year, age), b in births.items():
        tfr[year] = tfr.get(year, 0.0) + b / expos[(year, age)]
    printed = {int(r[0]): float(r[1]) for r in hfd_rows("USAtfrRR")}
    gap = max(abs(tfr[y] - printed[y]) for y in printed)
    c.add(INDEPENDENT, "HFD TFR 1933-2024 recomputed from births / exposures", gap <= 0.0005 + 1e-9,
          f"max abs diff from printed TFR {gap:.6f}")
    recon = stored("hfd_nchs_reconciliation").set_index("year")
    for year in (2010, 2020, 2023, 2024):
        c.close(INDEPENDENT, f"Stored HFD TFR {year}", tfr[year], recon.loc[year, "hfd_tfr"], 0.0005 + 1e-9)

    # 5-year NCHS-convention TFR on HFD exposures (ages 10-11 exposure = age 12), 2024
    year = 2024
    exp = {a: expos[(year, a)] for a in range(12, 56)}
    exp[10] = exp[11] = exp[12]
    b = {a: births[(year, a)] for a in range(12, 56)}
    groups = [(10, 14, range(12, 15)), (15, 19, None), (20, 24, None), (25, 29, None), (30, 34, None),
              (35, 39, None), (40, 44, None), (45, 49, range(45, 56))]
    total = 0.0
    for low, high, numerator_ages in groups:
        ages = numerator_ages or range(low, high + 1)
        total += sum(b[a] for a in ages) / sum(exp[a] for a in range(low, high + 1))
    c.close(INDEPENDENT, "TFR 2024, 5-year convention on HFD exposures", 5 * total,
            recon.loc[year, "tfr_5yr_on_hfd_exposure"], 1e-6)

    # Exposure comparison: HFD 15-49 exposure over vintage 2025 July 1 females, 2024
    v2025 = census_female("nc-est2025-agesex-res.csv")
    hfd_1549 = sum(expos[(2024, a)] for a in range(15, 50))
    census_1549 = sum(v2025[(2024, a)] for a in range(15, 50))
    denominators = stored("denominator_comparison")
    row = denominators[(denominators["year"] == 2024) & (denominators["ages"] == "15-49")].iloc[0]
    c.close(INDEPENDENT, "HFD / V2025 female exposure ratio, ages 15-49, 2024", hfd_1549 / census_1549,
            row["hfd_over_v2025"], 1e-9)

    # Cohort observability: last complete cohort cell and cumulative fertility
    asfr_vh = [(int(r[0]), int(r[1].rstrip("+-")), r[2]) for r in hfd_rows("USAasfrVH")]
    observed = {}
    cumulative = {}
    for cohort, age, value in asfr_vh:
        if value != "." and 1995 <= cohort <= 2012:
            observed[cohort] = max(observed.get(cohort, 0), age)
            cumulative[cohort] = cumulative.get(cohort, 0.0) + float(value)
    matrix = stored("cohort_observability").set_index("cohort")
    expected_last = {k: 2023 - k for k in range(1995, 2012)}   # cohort-age cell needs years c+x and c+x+1
    ok = all(observed.get(k) == v for k, v in expected_last.items()) and 2012 not in observed
    stored_ok = all(str(matrix.loc[k, "hfd_complete_ages"]).endswith(str(v)) for k, v in expected_last.items())
    c.add(INDEPENDENT, "Cohorts 1995-2011 complete to age 2023-c in HFD; 2012 has no complete cell",
          ok and stored_ok, f"raw last ages {observed.get(1995)}..{observed.get(2011)}; stored matrix agrees: {stored_ok}")
    c.close(INDEPENDENT, "Cohort 1995 cumulative fertility to exact age 29", cumulative[1995],
            matrix.loc[1995, "hfd_cumulative_fertility"], 0.001)

    # Reference shares: CCFR / CCF in cohorts 1965-1974 (median), at exact age 45
    ccf = {int(r[0]): float(r[1]) for r in hfd_rows("USAtfrVH") if r[1] != "."}
    shares = [float(r[2]) / ccf[int(r[0])] for r in hfd_rows("USAccfrVH")
              if r[2] != "." and 1965 <= int(r[0]) <= 1974 and int(r[1].rstrip("+-")) == 45]
    c.close(INDEPENDENT, "Median share of completed fertility before exact age 45 (cohorts 1965-1974)",
            float(np.median(shares)), matrix.loc[1995, "reference_share_low"], 1e-9)


# ------------------------------------------------------------ Census raw CSV

def census_female(name: str) -> dict:
    out = {}
    with open(RAW / "census_popest" / name, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["SEX"] == "2" and row["AGE"] != "999":
                for key, value in row.items():
                    if key.startswith("POPESTIMATE"):
                        out[(int(key[-4:]), int(row["AGE"]))] = int(value)
    return out


def np_rows(name: str) -> list[dict]:
    with open(RAW / "census_np2023" / name, newline="", encoding="utf-8") as handle:
        return [{k.strip('"'): v for k, v in row.items()} for row in csv.DictReader(handle)]


def check_census(c: Checks):
    a5 = {int(r["YEAR"]): float(r["TOTAL"]) for r in np_rows("np2023_a5.csv")}
    a1 = {int(r["YEAR"]): sum(float(v) for k, v in r.items() if k.startswith("ASFR_"))
          for r in np_rows("np2023_a1.csv") if r["GROUP"] == "0"}
    gap = max(abs(a1[y] - a5[y]) for y in a5)
    c.add(INDEPENDENT, "Census A5 TFR = sum of A1 total-group ASFRs, 2023-2100", gap <= 0.0021,
          f"max abs diff {gap:.5f} (41 rates and the TFR rounded to 4 decimals)")
    scenarios = stored("census_scenarios")
    labels = {"mid": "main series", "hi": "high immigration", "low": "low immigration", "zero": "zero immigration"}
    for code, label in labels.items():
        rows = np_rows(f"np2023_d1_{code}.csv")
        female = next(r for r in rows if r["SEX"] == "2" and r["ORIGIN"] == "0" and r["RACE"] == "0"
                      and r["YEAR"] == "2040")
        value = sum(int(female[f"POP_{a}"]) for a in range(15, 50))
        births = next(int(r["BIRTHS"]) for r in np_rows(f"np2023_d2_{code}.csv")
                      if r["RACE_HISP"] == "0" and r["SEX"] == "0" and r["YEAR"] == "2040")
        row = scenarios[(scenarios["scenario"] == label) & (scenarios["year"] == 2040)].iloc[0]
        c.add(INDEPENDENT, f"Census {label}, 2040: female 15-49 and projected births",
              value == row["female_15_49_july1"] and births == row["projected_births_jul_jun"],
              f"{value:,} / {births:,} vs stored {int(row['female_15_49_july1']):,} / "
              f"{int(row['projected_births_jul_jun']):,}")
    c.close(INDEPENDENT, "Census assumed TFR 2040", a5[2040],
            scenarios[(scenarios["year"] == 2040)]["assumed_tfr"].iloc[0], 1e-9)


# --------------------------------------------------------- NCHS public-use files

def recount_puf(year: int) -> tuple[Counter, Counter]:
    """Resident births by mother's age (MAGER 75-76) and by month (13-14), plus record count."""
    path = RAW / "nchs_natality_puf" / f"Nat{year}us.zip"
    member = zipfile.ZipFile(path).namelist()[0]
    process = subprocess.Popen([shutil.which("unzip"), "-p", str(path), member], stdout=subprocess.PIPE,
                               bufsize=1 << 20)
    by_age, by_month = Counter(), Counter()
    for line in process.stdout:
        if line[103:104] != b"4":                     # RESTATUS 4 = foreign resident
            by_age[int(line[74:76])] += 1
            by_month[int(line[12:14])] += 1
    process.wait()
    return by_age, by_month


def db571_rates() -> dict:
    text = (RAW / "nchs_2025" / "db571.txt").read_text(encoding="utf-8", errors="replace")
    block = text[text.index("Data table for Figure 2"):text.index("Data table for Figure 3")]
    return {m[0]: float(m[2]) for m in re.findall(r"(\d\d-\d\d)\s+([\d.]+)\s+([\d.]+)", block)}


def check_nchs(c: Checks, skip_puf: bool):
    rates = stored("nchs_2025_rates").set_index("measure")
    published = db571_rates()
    if skip_puf:
        c.add(INDEPENDENT, "Public-use recount", True, "skipped (--skip-puf)")
        return
    counts = {year: recount_puf(year) for year in (2024, 2025)}
    for year, official in ((2024, 3628934), (2025, 3612012)):
        total = sum(counts[year][0].values())
        c.add(INDEPENDENT, f"{year} resident births recounted from the public-use file", total == official,
              f"{total:,} vs official {official:,}")
    female = census_female("nc-est2025-agesex-res.csv")
    births = counts[2025][0]
    groups = {"10-14": (range(10, 15), range(10, 15)), "20-24": (range(20, 25), range(20, 25)),
              "30-34": (range(30, 35), range(30, 35)), "45-49": (range(45, 51), range(45, 50))}
    for label, (b_ages, p_ages) in groups.items():
        rate = 1000 * sum(births[a] for a in b_ages) / sum(female[(2025, a)] for a in p_ages)
        stored_rate = rates.loc[label, "exact_2025_v2025"]          # CSV keeps 10 significant digits
        c.add(INDEPENDENT, f"2025 rate {label} from recount and V2025 = DB571 and stored",
              round(rate, 1) == published[label] and abs(rate - stored_rate) <= 1e-9 * max(1.0, abs(rate)),
              f"{rate:.4f} (published {published[label]}, stored {rates.loc[label, 'exact_2025_v2025']:.4f})")
    jul_jun = sum(counts[2024][1][m] for m in range(7, 13)) + sum(counts[2025][1][m] for m in range(1, 7))
    contrast = stored("census_vs_observed").set_index("projection_year")
    c.add(INDEPENDENT, "Observed births July 2024-June 2025 recounted", jul_jun == contrast.loc[2025, "observed_births_jul_jun"],
          f"{jul_jun:,} vs stored {int(contrast.loc[2025, 'observed_births_jul_jun']):,}")
    hfd_2024 = {int(r[1].rstrip("+-")): float(r[2]) for r in hfd_rows("USAbirthsRR") if r[0] == "2024"}
    gap = max(abs(hfd_2024[a] - counts[2024][0][a]) for a in range(12, 50))
    c.add(INDEPENDENT, "2024 births by single age 12-49: HFD = public-use recount", gap < 0.5, f"max abs diff {gap:.2f}")


# ------------------------------------------------------------ reconciliation

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_reconciliation(c: Checks):
    for directory in ("hfd_usa", "hfd_docs", "nchs_2025", "nchs_natality_puf", "census_popest", "census_np2023"):
        record = json.loads((RAW / directory / "provenance.json").read_text(encoding="utf-8"))
        bad = [name for name, info in record["files"].items() if sha256(RAW / directory / name) != info["sha256"]]
        c.add(RECONCILIATION, f"Provenance hashes, data/raw/{directory}", not bad,
              f"{len(record['files'])} files; mismatches {bad}")
    archive = zipfile.ZipFile(RAW / "hfd_usa" / "USA.zip")
    differ = [i.filename for i in archive.infolist()
              if hashlib.sha256(archive.read(i)).hexdigest() != sha256(RAW / "hfd_usa" / i.filename)]
    c.add(RECONCILIATION, "HFD extracted files are byte-identical to USA.zip members", not differ,
          f"{len(archive.infolist())} members; differing {differ}")
    result = subprocess.run([sys.executable, str(ROOT / "audit" / "verify_freeze.py")], capture_output=True,
                            text=True, cwd=ROOT)
    c.add(RECONCILIATION, "Frozen M09 and M10 manifests unchanged", result.returncode == 0,
          "; ".join(result.stdout.strip().splitlines()) or result.stderr.strip()[-200:])
    if REPORT.exists():
        text = REPORT.read_text(encoding="utf-8")
        recon = stored("hfd_nchs_reconciliation").set_index("year")
        quotes = {"HFD TFR 2024": f"{recon.loc[2024, 'hfd_tfr']:.3f}",
                  "derived 2025 TFR": f"{recon.loc[2025, 'nchs_tfr_rounded_rates']:.3f}",
                  "decision": "CONDITIONAL"}
        missing = [k for k, v in quotes.items() if v not in text]
        c.add(RECONCILIATION, "Headline numbers quoted in docs/m11_data_feasibility.md", not missing,
              f"missing {missing}" if missing else ", ".join(f"{k} {v}" for k, v in quotes.items()))
    else:
        c.add(RECONCILIATION, "Feasibility report present", False, f"{REPORT} not found")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-puf", action="store_true")
    args = parser.parse_args(argv)
    checks = Checks()
    check_hfd(checks)
    check_census(checks)
    check_nchs(checks, args.skip_puf)
    check_reconciliation(checks)
    for kind, status, label, detail in checks.rows:
        print(f"{status}  [{kind}] {label}: {detail}")
    failed = sum(1 for row in checks.rows if row[1] == "FAIL")
    kinds = Counter(row[0] for row in checks.rows)
    print(f"\n{len(checks.rows)} checks ({kinds[INDEPENDENT]} independent, {kinds[RECONCILIATION]} "
          f"reconciliation): {len(checks.rows) - failed} PASS, {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
