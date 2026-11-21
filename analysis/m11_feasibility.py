"""M11 cross-source compatibility, cohort observability and forecasting feasibility.

Builds the M11 feasibility tables and figures from the validated sources:
Human Fertility Database (analysis/hfd.py), NCHS final 2025 data, Census
population estimates and the Census 2023 National Population Projections
(analysis/m11_sources.py).

No forecasting model is fitted and no forecast is produced. The backtesting
design is described (origins, horizons, metrics), not run: forecast errors of
any baseline are deliberately not computed, so that the backtest protocol can
be locked before any forecast error is seen.

Census projected fertility appears only as an external scenario (its stated
assumption), never as an observed value or a predictor.

    python -m analysis.m11_feasibility
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import hfd  # noqa: E402
from analysis import m11_sources as src  # noqa: E402
from analysis.analyze_calibration import INK, apply_figure_style  # noqa: E402
from analysis.nlsy97 import PROJECT_ROOT  # noqa: E402

PUBLIC_DIR = src.PUBLIC_DIR
FIGURE_DIR = PROJECT_ROOT / "assets" / "figures"
GROUPS = {"15-19": (15, 19), "20-24": (20, 24), "25-29": (25, 29), "30-34": (30, 34),
          "35-39": (35, 39), "40-44": (40, 44), "45-49": (45, 49), "15-49": (15, 49)}
NCHS_GROUPS = ["10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"]
GREEN, AMBER = "#1baf7a", "#eda100"
HORIZONS = (5, 10, 15)
FORECAST_END = 2040
LAST_HFD_YEAR = 2024
NCHS_FINAL_YEAR = 2025


# --------------------------------------------------------------- HFD vs NCHS

def hfd_exposure(years) -> pd.DataFrame:
    expos = hfd.read_hfd("USAexposRR")
    return expos[expos["Year"].isin(list(years))].rename(columns={"Year": "year", "Age": "age"})


def five_year_tfr(births: pd.Series, female: pd.Series) -> float:
    """NCHS convention, unrounded: 5 x sum of 5-year rates (10-14 and 45+ conventions).

    HFD exposures start at age 12; for them, ages 10 and 11 are set equal to the
    age-12 exposure (an approximation affecting the TFR by well under 0.001).
    """
    female = female.copy()
    for age in (10, 11):
        if age not in female.index:
            female[age] = female[12]
    return src.nchs_style_rates(births, female.sort_index())["tfr"] / 1000


def reconciliation() -> pd.DataFrame:
    """National TFR and births, 2010-2025, decomposed by source convention.

    Columns: NCHS as published (rounded 5-year rates, denominators of the
    vintage current at each release); NCHS convention recomputed exactly on
    vintage 2024 and vintage 2025 July 1 estimates; NCHS convention on HFD
    exposures; HFD single-year TFR. Births are identical across sources, so
    differences come from denominators and age-grouping conventions.
    """
    published = src.parse_nvsr_table2(2024).set_index("year")
    births_nvsr = src.parse_nvsr_table1(2024).set_index("year")["births"]
    hfd_tfr = hfd.read_hfd("USAtfrRR").set_index("Year")["TFR"]
    hfd_births = hfd.read_hfd("USAbirthsRR")
    hfd_total = hfd.read_hfd("USAtotbirthsRR").set_index("Year")["Total"]
    expos = hfd.read_hfd("USAexposRR")
    pop = {v: src.load_popest(v) for v in (2024, 2025)}
    db571 = src.parse_db571()
    rows = []
    for year in range(2010, NCHS_FINAL_YEAR + 1):
        row = {"year": year}
        if year <= LAST_HFD_YEAR:
            by_age = hfd_births[hfd_births["Year"] == year].set_index("Age")["Total"]
            row.update(nchs_births=int(births_nvsr[year]), hfd_births=float(hfd_total[year]),
                       nchs_tfr_published=published.loc[year, "tfr"] / 1000,
                       hfd_tfr=float(hfd_tfr[year]))
            exposure = expos[expos["Year"] == year].set_index("Age")["Exposure"]
            row["tfr_5yr_on_hfd_exposure"] = five_year_tfr(by_age, exposure)
        else:
            by_age = src.puf_births_by_age(year).astype(float)
            row.update(nchs_births=db571["births"][year]["births"], hfd_births=np.nan,
                       nchs_tfr_published=np.nan, hfd_tfr=np.nan, tfr_5yr_on_hfd_exposure=np.nan)
            row["nchs_tfr_rounded_rates"] = 5 * sum(db571["rates"][g][year] for g in NCHS_GROUPS) / 1000
        for vintage, table in pop.items():
            female = table[table["year"] == year].set_index("age")["population"]
            row[f"tfr_5yr_exact_v{vintage}"] = five_year_tfr(by_age, female) if len(female) else np.nan
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame["hfd_minus_nchs_published"] = frame["hfd_tfr"] - frame["nchs_tfr_published"]
    frame["grouping_effect"] = frame["hfd_tfr"] - frame["tfr_5yr_on_hfd_exposure"]
    frame["denominator_effect_v2025"] = frame["tfr_5yr_on_hfd_exposure"] - frame["tfr_5yr_exact_v2025"]
    return frame


def births_by_age_2024() -> pd.DataFrame:
    births = hfd.read_hfd("USAbirthsRR")
    hfd_2024 = births[births["Year"] == 2024].set_index("Age")["Total"]
    puf = src.puf_births_by_age(2024)
    table = pd.DataFrame({"hfd_births": hfd_2024, "nchs_puf_births": puf}).fillna(0.0)
    table.index.name = "age"
    table["difference"] = table["hfd_births"] - table["nchs_puf_births"]
    table = table.reset_index()
    table["note"] = np.where(table["age"] == 12, "HFD 12- / NCHS 10-12",
                             np.where(table["age"] >= 50, "NCHS 50 = 50-54; HFD splits 50-54 by age", ""))
    return table


def exposure_comparison() -> pd.DataFrame:
    """Female denominators by age group: HFD exposure, Census estimates, Census projection."""
    expos = hfd.read_hfd("USAexposRR")
    sources = {"hfd_exposure": expos.rename(columns={"Year": "year", "Age": "age", "Exposure": "value"})}
    for vintage in (2024, 2025):
        sources[f"census_v{vintage}_july1"] = src.load_popest(vintage).rename(columns={"population": "value"})
    sources["census_np2023_mid_july1"] = src.load_np_female("mid").rename(columns={"population": "value"})
    rows = []
    for year in range(2020, NCHS_FINAL_YEAR + 1):
        for label, (low, high) in GROUPS.items():
            row = {"year": year, "ages": label}
            for name, table in sources.items():
                part = table[(table["year"] == year) & table["age"].between(low, high)]
                row[name] = float(part["value"].sum()) if len(part) == high - low + 1 else np.nan
            rows.append(row)
    frame = pd.DataFrame(rows)
    base = frame["census_v2025_july1"]
    frame["hfd_over_v2025"] = frame["hfd_exposure"] / base
    frame["v2024_over_v2025"] = frame["census_v2024_july1"] / base
    frame["np2023_over_v2025"] = frame["census_np2023_mid_july1"] / base
    return frame


def nchs_2025_rates() -> pd.DataFrame:
    """Published and recomputed 5-year rates, 2024 and 2025, with the denominator revision."""
    db571, provisional = src.parse_db571(), src.parse_vsrr043()
    births = {y: src.puf_births_by_age(y) for y in (2024, 2025)}
    female = {(y, v): src.load_popest(v).query("year == @y").set_index("age")["population"]
              for y, v in ((2024, 2024), (2024, 2025), (2025, 2025))}
    recomputed = {key: src.nchs_style_rates(births[key[0]], female[key]) for key in female}
    rows = []
    for group in NCHS_GROUPS + ["tfr", "gfr"]:
        row = {"measure": group}
        if group in db571["rates"]:
            row.update(published_2024=db571["rates"][group][2024], published_2025=db571["rates"][group][2025],
                       provisional_2025=provisional[group]["rate_2025p"] if group in provisional else np.nan)
        elif group == "gfr":
            row.update(published_2024=db571["births"][2024]["gfr"], published_2025=db571["births"][2025]["gfr"],
                       provisional_2025=provisional["All ages"]["rate_2025p"])
        else:
            row.update(published_2024=1599.5, published_2025=np.nan, provisional_2025=np.nan)
        row.update(exact_2024_v2024=recomputed[(2024, 2024)][group],
                   exact_2024_v2025=recomputed[(2024, 2025)][group],
                   exact_2025_v2025=recomputed[(2025, 2025)][group])
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame["change_published_pct"] = 100 * (frame["published_2025"] / frame["published_2024"] - 1)
    frame["change_same_vintage_pct"] = 100 * (frame["exact_2025_v2025"] / frame["exact_2024_v2025"] - 1)
    return frame


def single_year_2025() -> pd.DataFrame:
    """Project-derived single-year rates for 2024-2025 on vintage 2025 denominators (not official)."""
    rows = []
    hfd_asfr = hfd.read_hfd("USAasfrRR").query("Year == 2024").set_index("Age")["ASFR"]
    v2025 = src.load_popest(2025)
    for year in (2024, 2025):
        births = src.puf_births_by_age(year)
        female = v2025[v2025["year"] == year].set_index("age")["population"]
        rates = src.single_year_rates(births, female)
        for age, rate in rates.items():
            rows.append({"year": year, "age": age, "births": int(births.get(age, 0)),
                         "female_july1_v2025": int(female[age]), "asfr_derived": rate,
                         "hfd_asfr": float(hfd_asfr[age]) if year == 2024 and age < 50 else np.nan})
    frame = pd.DataFrame(rows)
    frame["note"] = np.where(frame["age"] == 12, "births at ages 10-12 over women aged 12",
                             np.where(frame["age"] == 50, "births at ages 50-54 over women aged 50", ""))
    return frame


# --------------------------------------------------------------- Census

def census_scenarios() -> pd.DataFrame:
    tfr = src.load_np_tfr().set_index("year")["tfr"]
    rows = []
    for scenario, label in src.NP_SCENARIOS.items():
        female = src.load_np_female(scenario)
        births = src.load_np_births(scenario).set_index("year")["births"]
        for year in range(2022, FORECAST_END + 1):
            part = female[female["year"] == year]
            rows.append({"scenario": label, "year": year,
                         "assumed_tfr": float(tfr[year]) if year in tfr.index else np.nan,
                         "projected_births_jul_jun": int(births[year]) if year in births.index else np.nan,
                         "female_15_49_july1": int(part[part["age"].between(15, 49)]["population"].sum()),
                         "female_20_34_july1": int(part[part["age"].between(20, 34)]["population"].sum())})
    return pd.DataFrame(rows)


def july_june_births() -> dict:
    """Observed births for July 2024 to June 2025 (residents), from the public-use files."""
    total = 0
    for year, months in ((2024, range(7, 13)), (2025, range(1, 7))):
        table = src.load_puf_births(year)
        if "month" not in table:
            return {}
        table["month"] = table["month"].astype(int)
        total += int(table[table["month"].isin(list(months))]["births"].sum())
    return {2025: total}


def census_vs_observed() -> pd.DataFrame:
    """Census main-series assumptions for already-observed years, beside observed values.

    An external scenario contrast, not a validation: the assumption is shown
    next to what was later observed, with period definitions stated.
    """
    tfr = src.load_np_tfr().set_index("year")["tfr"]
    births = src.load_np_births("mid").set_index("year")["births"]
    observed = reconciliation().set_index("year")
    exact = july_june_births()
    rows = []
    for year in (2023, 2024, 2025):
        calendar = observed.loc[year, "nchs_births"]
        previous = observed.loc[year - 1, "nchs_births"]
        rows.append({"projection_year": year, "period": f"July {year - 1} to June {year}",
                     "census_assumed_tfr": float(tfr[year]),
                     "observed_tfr_nchs_calendar": (observed.loc[year, "nchs_tfr_published"]
                                                    if year <= LAST_HFD_YEAR
                                                    else observed.loc[year, "nchs_tfr_rounded_rates"]),
                     "observed_tfr_hfd_calendar": observed.loc[year, "hfd_tfr"],
                     "census_projected_births": int(births[year]),
                     "observed_births_jul_jun": exact.get(year, np.nan),
                     "observed_births_mean_of_calendar_years": (calendar + previous) / 2})
    return pd.DataFrame(rows)


# ------------------------------------------------------- cohorts and backtesting

def backtest_design(last_year: int = LAST_HFD_YEAR, min_train: int = 20) -> pd.DataFrame:
    """Rolling-origin counts by horizon and training start (design only, nothing fitted)."""
    rows = []
    for start, label in ((1933, "full HFD series (1933-)"), (1977, "after the 1976 TFR trough"),
                         (1990, "post-1990 near-replacement regime")):
        for h in HORIZONS:
            first = start + min_train - 1
            last = last_year - h
            n = max(0, last - first + 1)
            rows.append({"training_start": start, "series": label, "horizon": h,
                         "min_training_years": min_train, "first_origin": first if n else None,
                         "last_origin": last if n else None, "origins": n,
                         # origins spaced h years apart, so forecast windows never overlap
                         "non_overlapping_windows": -(-n // h),
                         "latest_target_year": last_year})
    return pd.DataFrame(rows)


def structural_periods() -> pd.DataFrame:
    """Turning points of the HFD period TFR, found by simple rules (descriptive only)."""
    tfr = hfd.read_hfd("USAtfrRR").set_index("Year")["TFR"]
    mab = hfd.read_hfd("USAmabRR").set_index("Year")["MAB"]
    picks = {
        "series start": 1933,
        "baby-boom peak (max 1933-1970)": int(tfr.loc[1933:1970].idxmax()),
        "post-boom trough (min 1970-1990)": int(tfr.loc[1970:1990].idxmin()),
        "pre-recession peak (max 1990-2015)": int(tfr.loc[1990:2015].idxmax()),
        "pandemic year": 2020,
        "latest HFD year": LAST_HFD_YEAR,
    }
    changes = tfr.diff()
    rows = [{"feature": name, "year": year, "tfr": float(tfr[year]), "mean_age_at_birth": float(mab[year])}
            for name, year in picks.items()]
    rows.append({"feature": "largest one-year fall", "year": int(changes.idxmin()),
                 "tfr": float(tfr[changes.idxmin()]), "mean_age_at_birth": float(mab[changes.idxmin()])})
    rows.append({"feature": "largest one-year rise", "year": int(changes.idxmax()),
                 "tfr": float(tfr[changes.idxmax()]), "mean_age_at_birth": float(mab[changes.idxmax()])})
    return pd.DataFrame(rows)


def observability_with_context() -> pd.DataFrame:
    """Observability matrix plus the share of completed fertility that 1965-1974 cohorts had
    reached by the same ages. By the end of 2040 a woman born in year c is between exact
    ages 2040-c and 2040-c+1, so the share is bracketed by those two exact ages. Later
    cohorts have their children later, so these historical shares likely overstate how
    much of Gen Z lifetime fertility falls before 2041."""
    matrix = hfd.cohort_observability()
    shares = hfd.completed_share_by_age().set_index("Age")["median"]
    matrix["reference_share_low"] = [float(shares.get(age, np.nan)) for age in matrix["age_reached_in_2040"]]
    matrix["reference_share_high"] = [float(shares.get(age + 1, np.nan))
                                      for age in matrix["age_reached_in_2040"]]
    return matrix


# --------------------------------------------------------------- statuses

def source_status(checks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for source, group in checks.groupby("source", sort=False):
        statuses = set(group["status"])
        status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
        rows.append({"source": source, "checks": len(group), "pass": int((group["status"] == "PASS").sum()),
                     "warn": int((group["status"] == "WARN").sum()),
                     "fail": int((group["status"] == "FAIL").sum()), "status": status})
    return pd.DataFrame(rows)


def all_checks(recon: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for result in hfd.validate():
        rows.append({"source": "HFD USA", **result})
    rows.append({"source": "HFD USA", "check": "Latest period year and update",
                 "status": "WARN", "tolerance": None,
                 "detail": "period data end in 2024; 2025 not yet in HFD (release of 2 July 2026)"})
    rows.append({"source": "HFD USA", "check": "HFD input-data files (USAbirths/USAmonthly/USAparity)",
                 "status": "WARN", "tolerance": None,
                 "detail": "require an HFD login; not retrieved, so HFD's own source notes for recent years are not checked"})

    summary = json.loads((src.PROCESSED_DIR / "nchs_puf_tabulation.json").read_text(encoding="utf-8"))
    db571 = src.parse_db571()
    for year in (2024, 2025):
        residents = int(src.puf_births_by_age(year).sum())
        official = db571["births"][year]["births"]
        rows.append({"source": "NCHS 2025", "check": f"{year} public-use file: resident births = official total",
                     "status": "PASS" if residents == official else "FAIL", "tolerance": 0,
                     "detail": f"{residents:,} vs {official:,}"})
        lengths = summary[str(year)]["record_lengths"]
        rows.append({"source": "NCHS 2025", "check": f"{year} public-use file: record layout",
                     "status": "WARN" if list(lengths) != [str(src.PUF_DOCUMENTED_LENGTH)] else "PASS",
                     "tolerance": None,
                     "detail": f"record lengths {lengths}; user guide states {src.PUF_DOCUMENTED_LENGTH}; "
                               "field positions confirmed by the exact totals and rates"})
    for label, column, year in (("2024 published rates reproduced from vintage 2024 denominators",
                                 "exact_2024_v2024", 2024),
                                ("2025 final rates reproduced from vintage 2025 denominators",
                                 "exact_2025_v2025", 2025)):
        part = rates[rates["measure"].isin(NCHS_GROUPS + ["gfr"])]
        published = part[f"published_{year}"]
        ok = bool((part[column].round(1).sub(published).abs() < 1e-9).all())
        rows.append({"source": "NCHS 2025", "check": label, "status": "PASS" if ok else "FAIL",
                     "tolerance": 0.05, "detail": "all 8 age groups and the GFR match to 0.1" if ok else
                     part[["measure", column, f"published_{year}"]].to_string(index=False)})
    tfr_conv = {r: bool(((t[NCHS_GROUPS].sum(axis=1) * 5) - t["tfr"]).abs().max() < 1e-6)
                for r, t in ((r, src.parse_nvsr_table2(r)) for r in src.NVSR_REPORTS)}
    rows.append({"source": "NCHS 2025", "check": "NCHS TFR = 5 x sum of published (rounded) 5-year rates",
                 "status": "PASS" if all(tfr_conv.values()) else "FAIL", "tolerance": 1e-6,
                 "detail": f"reports {sorted(tfr_conv)}: {tfr_conv}"})
    births_match = recon.dropna(subset=["hfd_births"])
    gap = (births_match["hfd_births"] - births_match["nchs_births"]).abs().max()
    rows.append({"source": "NCHS 2025", "check": "HFD annual births = NCHS final births, 2010-2024",
                 "status": "PASS" if gap <= 0.5 else "FAIL", "tolerance": 0.5,
                 "detail": f"max abs diff {gap:.2f} (HFD prints 2 decimals)"})
    by_age = births_by_age_2024()
    core = by_age[by_age["age"].between(12, 49)]
    tail = by_age[by_age["age"] >= 50]
    ok = core["difference"].abs().max() < 0.5 and abs(tail["difference"].sum()) < 0.5
    rows.append({"source": "NCHS 2025", "check": "2024 births by single age: HFD = NCHS public-use file",
                 "status": "PASS" if ok else "FAIL", "tolerance": 0.5,
                 "detail": f"ages 12-49 max abs diff {core['difference'].abs().max():.2f}; ages 50+ total diff "
                           f"{tail['difference'].sum():.2f}"})
    rows.append({"source": "NCHS 2025", "check": "Final 2025 NVSR and official 2025 TFR",
                 "status": "WARN", "tolerance": None,
                 "detail": "not published by 2026-11-20; 2025 TFR here is derived (5 x rounded DB571 rates)"})
    rows.append({"source": "NCHS 2025", "check": "2025 rates comparable with published 2024 rates",
                 "status": "WARN", "tolerance": None,
                 "detail": "no: 2025 uses vintage 2025 denominators (methodology change); see m11_nchs_2025_rates.csv"})

    for vintage in (2024, 2025):
        checks = src.popest_checks(vintage)
        ok = all(c["ok"] for c in checks)
        rows.append({"source": "Census population estimates", "status": "PASS" if ok else "FAIL",
                     "check": f"Vintage {vintage}: single ages sum to totals; male + female = both sexes",
                     "tolerance": 0, "detail": f"{len(checks)} columns checked"})
    for check in src.np_checks():
        rows.append({"source": "Census 2023 projections", "check": check["check"],
                     "status": "PASS" if check["ok"] else "FAIL", "tolerance": None, "detail": check["detail"]})
    repro = src.np_births_reproduction("mid")
    repro = repro[repro["year"] <= FORECAST_END]
    rows.append({"source": "Census 2023 projections",
                 "check": "Projected births approximately = total-group ASFR x female population (2023-2040)",
                 "status": "PASS" if (repro["ratio_mean"].sub(1).abs() < 0.01).all() else "WARN",
                 "tolerance": 0.01,
                 "detail": f"ratio births / (ASFR x mean July 1 female pop) {repro['ratio_mean'].min():.4f}-"
                           f"{repro['ratio_mean'].max():.4f}; Census computes births within six groups"})
    contrast = census_vs_observed()
    above = contrast["census_assumed_tfr"] > contrast["observed_tfr_nchs_calendar"]
    pairs = "; ".join(f"{int(r.projection_year)}: {r.census_assumed_tfr:.3f} vs {r.observed_tfr_nchs_calendar:.3f}"
                      for r in contrast.itertuples())
    rows.append({"source": "Census 2023 projections", "check": "Fertility assumption against later observations",
                 "status": "WARN" if above.any() else "PASS", "tolerance": None,
                 "detail": f"assumed vs observed NCHS TFR (projection year vs calendar year) {pairs}; "
                           "fertility inputs end in 2020; scenarios vary immigration only"})
    return pd.DataFrame(rows)[["source", "check", "status", "detail", "tolerance"]]


def inventory() -> pd.DataFrame:
    rows = []
    descriptions = {
        "hfd_usa": ("Human Fertility Database, United States (USA.zip + 51 extracted files)",
                    "Period 1933-2024 by single age 12-55+, birth order 1-5+; cohorts 1878-2011"),
        "hfd_docs": ("HFD methods protocol, file formats, USA notes, references, input-data map",
                     "Documentation"),
        "nchs_2025": ("NCHS Data Brief 571 (final 2025), VSRR 43 (provisional 2025), NCHS index pages",
                      "2024-2025, 5-year age groups"),
        "nchs_natality_puf": ("NCHS natality public-use files 2024 and 2025 with user guides",
                              "Births by single year of mother's age 10-12 ... 50-54, 2024-2025"),
        "nchs_nvsr": ("Births: Final Data for 2019, 2023, 2024 (saved in M10, read only)",
                      "National TFR and 5-year rates 2010-2024"),
        "census_popest": ("Census national estimates by single age and sex, vintages 2024 and 2025",
                          "July 1 2020-2024 (V2024) and 2020-2025 (V2025), ages 0-85+"),
        "census_np2023": ("Census 2023 National Population Projections, 4 scenarios",
                          "2022-2100 population, 2023-2100 births/ASFR/TFR, single ages"),
    }
    for directory, (content, coverage) in descriptions.items():
        folder = src.RAW / directory
        files = [p for p in folder.iterdir() if p.is_file()]
        provenance = folder / "provenance.json"
        rows.append({"directory": f"data/raw/{directory}", "content": content, "coverage": coverage,
                     "files": len(files), "megabytes": round(sum(p.stat().st_size for p in files) / 1e6, 1),
                     "provenance": "provenance.json" if provenance.exists() else "missing"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------- figures

def figure_tfr(recon: pd.DataFrame, path) -> None:
    tfr = hfd.read_hfd("USAtfrRR")
    census = src.load_np_tfr().query("year <= @FORECAST_END")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(tfr["Year"], tfr["TFR"], color=INK["series"], linewidth=2, label="HFD period TFR, 1933-2024")
    nchs = recon.dropna(subset=["nchs_tfr_published"])
    ax.plot(nchs["year"], nchs["nchs_tfr_published"], linestyle="none", marker="o", markersize=4,
            color=GREEN, label="NCHS published TFR, 2010-2024")
    last = recon[recon["year"] == NCHS_FINAL_YEAR].iloc[0]
    ax.plot([NCHS_FINAL_YEAR], [last["nchs_tfr_rounded_rates"]], linestyle="none", marker="D",
            markersize=6, color=GREEN, markerfacecolor=INK["surface"], markeredgewidth=2,
            label="2025, derived from final NCHS rates (no official TFR yet)")
    ax.plot(census["year"], census["tfr"], color=AMBER, linewidth=2, linestyle="--",
            label="Census 2023 main-series assumption (scenario, not a forecast)")
    ax.axvspan(NCHS_FINAL_YEAR + 0.5, FORECAST_END + 0.5, color=INK["grid"], alpha=0.35, linewidth=0)
    ax.text(2033, 2.35, "2026-2040:\nnot observed", ha="center", va="top", fontsize=8, color=INK["secondary"])
    ax.set_xlim(1930, FORECAST_END + 1)
    ax.set_ylim(1.4, 3.8)
    ax.set_ylabel("Births per woman")
    ax.set_title("U.S. period total fertility rate: observed sources and the Census assumption")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.text(0.01, 0.01, "Sources: Human Fertility Database (release 2 July 2026); NCHS NVSR 75(2) and "
             "Data Brief 571; Census Bureau 2023 National Population Projections (projection years run "
             "July-June).", fontsize=7, color=INK["muted"], wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def figure_observability(matrix: pd.DataFrame, path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.2))
    segments = [("Observed in HFD (complete cohort-age cells)", INK["series"]),
                ("Observed in part (HFD 2024 triangle, NCHS 2025 period data)", GREEN),
                ("Must be forecast, 2026-2040", AMBER),
                ("After 2040: not covered by M11", INK["grid"])]
    for _, row in matrix.iterrows():
        c = row["cohort"]
        complete = 2023 - c                       # last complete cohort-age cell
        parts = [(12, complete + 1, segments[0][1]), (complete + 1, NCHS_FINAL_YEAR - c + 1, segments[1][1]),
                 (NCHS_FINAL_YEAR - c + 1, FORECAST_END - c + 1, segments[2][1]),
                 (FORECAST_END - c + 1, 50, segments[3][1])]
        for start, end, color in parts:
            if end > start:
                ax.barh(c, end - start, left=start, height=0.72, color=color, linewidth=0)
    for label, color in segments:
        ax.barh(np.nan, 0, color=color, label=label)
    ax.set_xlim(12, 50)
    ax.set_ylim(2012.6, 1994.4)
    ax.set_yticks(range(1995, 2013))
    ax.set_xlabel("Age of the woman (years)")
    ax.set_ylabel("Birth cohort")
    ax.grid(axis="y", visible=False)
    ax.set_title("What is observed for the 1995-2012 birth cohorts, and what would have to be forecast")
    ax.legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, -0.32), ncol=2)
    fig.text(0.01, 0.01, "Ages shown to 50; childbearing after 50 is negligible. Each age of a cohort spans "
             "two calendar years, so boundary ages are partly in the neighbouring segment. Reaching an age "
             "by 2040 is not completing childbearing: cohorts born after 1995 are below age 45 in 2040.",
             fontsize=7, color=INK["muted"], wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


# --------------------------------------------------------------- main

def build() -> dict:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    recon = reconciliation()
    rates = nchs_2025_rates()
    checks = all_checks(recon, rates)
    matrix = observability_with_context()
    tables = {
        "source_inventory": inventory(),
        "validation_checks": checks,
        "source_status": source_status(checks),
        "hfd_coverage": hfd.coverage(),
        "hfd_period_missing": hfd.period_missing_by_year(),
        "hfd_nchs_reconciliation": recon,
        "hfd_nchs_births_2024_by_age": births_by_age_2024(),
        "denominator_comparison": exposure_comparison(),
        "nchs_2025_rates": rates,
        "nchs_single_year_2024_2025": single_year_2025(),
        "census_inventory": src.np_inventory(),
        "census_scenarios": census_scenarios(),
        "census_vs_observed": census_vs_observed(),
        "census_births_reproduction": src.np_births_reproduction("mid").query("year <= @FORECAST_END"),
        "cohort_observability": matrix,
        "completed_share_reference": hfd.completed_share_by_age(),
        "backtest_design": backtest_design(),
        "structural_periods": structural_periods(),
    }
    for name, table in tables.items():
        table.to_csv(PUBLIC_DIR / f"m11_{name}.csv", index=False, float_format="%.10g")
    apply_figure_style()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    figure_tfr(recon, FIGURE_DIR / "m11_tfr_sources.png")
    figure_observability(matrix, FIGURE_DIR / "m11_cohort_observability.png")
    return tables


def decision(status: pd.DataFrame) -> str:
    if (status["status"] == "FAIL").any():
        return "BLOCKED"
    return "CONDITIONAL" if (status["status"] == "WARN").any() else "READY"


def main() -> int:
    tables = build()
    print(tables["source_status"].to_string(index=False))
    for _, row in tables["validation_checks"].iterrows():
        print(f"{row['status']:4}  [{row['source']}] {row['check']}: {row['detail']}")
    print("Decision:", decision(tables["source_status"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
