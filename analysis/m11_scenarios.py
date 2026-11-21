"""M11 external inputs: the 2025 HFD-compatible reconstruction and Census population scenarios.

Protocol sections 6 and 11. Nothing here enters the primary HFD fit. The 2025
reconstruction combines NCHS final 2025 resident births (public-use file) with
Census vintage 2025 female population estimates. The Census 2023 projections
(NP2023) supply female population by scenario for scenario-conditional births;
their fertility assumption is only compared, never used.
"""

import numpy as np
import pandas as pd

from analysis import hfd
from analysis import m11_sources as src
from analysis.m11_backtest import AGES
from analysis.m11_protocol import load_config

CONFIG = load_config()
REC = CONFIG["reconstruction_2025"]
CEN = CONFIG["census"]


def hfd_births(year: int) -> pd.Series:
    births = hfd.read_hfd("USAbirthsRR")
    row = births[births["Year"] == year].set_index("Age")["Total"]
    return row.reindex(AGES).astype(float)


def hfd_exposure(year: int) -> pd.Series:
    expos = hfd.read_hfd("USAexposRR")
    return expos[expos["Year"] == year].set_index("Age")["Exposure"].reindex(AGES).astype(float)


def female_population(vintage: int, year: int) -> pd.Series:
    pop = src.load_popest(vintage)
    row = pop[pop["year"] == year].set_index("age")["population"].reindex(AGES).astype(float)
    if row.isna().any():
        raise ValueError(f"vintage {vintage} lacks female population for {year} at some ages 12-55")
    return row


def births_2025_hfd_ages() -> pd.Series:
    """2025 resident births on HFD single ages 12-55.

    NCHS public-use ages: 12 = 10-12 (HFD 12-), 50 = 50-54 (no older group).
    The 50-54 count is split over HFD ages 50..55+ in proportion to HFD 2024 births.
    """
    puf = src.puf_births_by_age(2025).astype(float)
    if list(puf.index) != list(range(12, 51)):
        raise ValueError("unexpected public-use age coding")
    out = pd.Series(0.0, index=AGES)
    out.loc[12:49] = puf.loc[12:49].to_numpy()
    shares = hfd_births(2024).loc[50:55]
    out.loc[50:55] = puf.loc[50] * (shares / shares.sum()).to_numpy()
    if abs(out.sum() - puf.sum()) > 1e-6:
        raise AssertionError("birth total changed while mapping ages")
    return out


def ratio_backtest() -> pd.DataFrame:
    """Reconstruct HFD TFR(Y) from births(Y), population(Y) and the HFD/Census exposure ratio of Y-1."""
    rows = []
    first, last = REC["ratio_backtest_years"]
    for vintage in (2025, 2024):
        for year in range(first, last + 1):
            ratio = hfd_exposure(year - 1) / female_population(vintage, year - 1)
            exposure = female_population(vintage, year) * ratio
            estimate = float((hfd_births(year) / exposure).sum())
            actual = float((hfd_births(year) / hfd_exposure(year)).sum())
            rows.append({"vintage": vintage, "year": year, "reconstructed_tfr": estimate, "hfd_tfr": actual,
                         "error": actual - estimate})
    return pd.DataFrame(rows)


def reconstruct_2025() -> dict:
    """2025 TFR under three exposure definitions (E2 primary) with the backtest-based band."""
    births = births_2025_hfd_ages()
    pop = female_population(2025, 2025)
    ratio_2024 = hfd_exposure(2024) / female_population(2025, 2024)
    mean_ratio = pd.concat([hfd_exposure(y) / female_population(2025, y) for y in range(2021, 2025)], axis=1).mean(axis=1)
    exposures = {"E1_vintage2025_july1": pop, "E2_ratio_2024": pop * ratio_2024, "E3_ratio_2021_2024": pop * mean_ratio}
    rates = {k: births / v for k, v in exposures.items()}
    backtest = ratio_backtest()
    rmse = float(np.sqrt(np.mean(backtest.loc[backtest["vintage"] == 2025, "error"] ** 2)))
    primary = float(rates["E2_ratio_2024"].sum())
    return {"births": births, "rates": rates, "tfr": {k: float(v.sum()) for k, v in rates.items()},
            "primary": primary, "rmse": rmse, "band": (primary - REC["band_multiplier"] * rmse,
                                                       primary + REC["band_multiplier"] * rmse),
            "backtest": backtest}


# ------------------------------------------------------------------- Census

def np_female(scenario: str) -> pd.DataFrame:
    """NP2023 female population, year x single age (0-100)."""
    table = src.load_np_female(scenario)
    return table.pivot(index="year", columns="age", values="population").astype(float)


def popest_matrix(vintage: int = 2025) -> pd.DataFrame:
    table = src.load_popest(vintage)
    return table.pivot(index="year", columns="age", values="population").astype(float)


def exposure_alignment() -> pd.DataFrame:
    """HFD ASFR(Y) x vintage 2025 female population(Y) against HFD births(Y)."""
    rows = []
    rates = hfd.read_hfd("USAasfrRR")
    first, last = CEN["alignment_years"]
    for year in range(first, last + 1):
        asfr = rates[rates["Year"] == year].set_index("Age")["ASFR"].reindex(AGES)
        implied = float((asfr * female_population(2025, year)).sum())
        actual = float(hfd_births(year).sum())
        rows.append({"year": year, "hfd_births": actual, "asfr_x_v2025_population": implied,
                     "relative_difference": implied / actual - 1})
    out = pd.DataFrame(rows)
    out["within_tolerance"] = out["relative_difference"].abs() <= CEN["alignment_tolerance"]
    return out


def rebase(np_table: pd.DataFrame, reference: pd.Series, base_year: int, years, method: str) -> pd.DataFrame:
    """Rebase NP2023 to a newer estimate at base_year: by cohort (ratio follows birth year) or by age."""
    ratio_by_age = reference / np_table.loc[base_year]
    out = {}
    for year in years:
        if method == "none":
            out[year] = np_table.loc[year]
        elif method == "age":
            out[year] = np_table.loc[year] * ratio_by_age
        elif method == "cohort":
            ages = np_table.columns
            base_ages = ages - (year - base_year)          # age of the same cohort in base_year
            factors = ratio_by_age.reindex(np.maximum(base_ages, 0)).to_numpy()
            out[year] = np_table.loc[year] * factors
        else:
            raise ValueError(f"unknown rebasing method {method!r}")
    return pd.DataFrame(out).T


def rebasing_test() -> pd.DataFrame:
    """Rebase NP2023 (mid) at 2022 with vintage 2025 and predict vintage 2025 for 2023-2025, ages 12-55."""
    base = CEN["rebase_test_base"]
    years = CEN["rebase_test_years"]
    projection = np_female("mid")
    estimates = popest_matrix(2025)
    rows = []
    for method in ("none", "age", "cohort"):
        rebased = rebase(projection, estimates.loc[base], base, years, method)
        for year in years:
            truth = estimates.loc[year, AGES]
            pred = rebased.loc[year, AGES]
            rows.append({"method": method, "year": year, "h": year - base,
                         "mape_ages_12_55": float((pred / truth - 1).abs().mean()),
                         "women_15_49_error": float(pred.loc[15:49].sum() / truth.loc[15:49].sum() - 1)})
    out = pd.DataFrame(rows)
    raw = out[out["method"] == "none"].set_index("year")["mape_ages_12_55"]
    out["beats_unrebased"] = [m != "none" and v < raw[y] for m, v, y in
                              zip(out["method"], out["mape_ages_12_55"], out["year"])]
    return out


def valid_rebasing(test: pd.DataFrame) -> str | None:
    for method in ("cohort", "age"):
        if test[test["method"] == method]["beats_unrebased"].all():
            return method
    return None


def scenario_population(method: str, years, scenario: str) -> pd.DataFrame:
    year0 = CEN["rebase_year"]
    projection = np_female(scenario)
    if method == "none":
        return projection.loc[list(years), AGES]
    rebased = rebase(projection, popest_matrix(2025).loc[year0], year0, years, method)
    return rebased.loc[list(years), AGES]


def scenario_births(asfr: pd.DataFrame, method: str) -> pd.DataFrame:
    """Calendar-year births = sum over ages of ASFR(t, x) x female population(t, x), each scenario."""
    if asfr.isna().any().any() or (asfr < 0).any().any():
        raise ValueError("ASFR must be complete and non-negative")
    rows = []
    for scenario in CEN["scenarios"]:
        pop = scenario_population(method, asfr.index, scenario)
        if pop.isna().any().any():
            raise ValueError(f"missing population exposure for scenario {scenario}")
        births = (asfr[AGES] * pop[AGES]).sum(axis=1)
        for year, value in births.items():
            rows.append({"scenario": scenario, "year": int(year), "births": float(value),
                         "women_15_49": float(pop.loc[year, 15:49].sum()), "rebasing": method})
    return pd.DataFrame(rows)


def census_births_comparison(our: pd.DataFrame) -> pd.DataFrame:
    """Census projection-year births (July t-1 to June t) against 0.5 B(t-1) + 0.5 B(t)."""
    rows = []
    for scenario in CEN["scenarios"]:
        census = src.load_np_births(scenario).set_index("year")["births"]
        ours = our[our["scenario"] == scenario].set_index("year")["births"]
        for year in ours.index:
            if year - 1 in ours.index and year in census.index:
                rows.append({"scenario": scenario, "census_year": int(year),
                             "census_births": float(census.loc[year]),
                             "ours_july_june_equivalent": float(0.5 * ours[year - 1] + 0.5 * ours[year])})
    out = pd.DataFrame(rows)
    out["ratio"] = out["ours_july_june_equivalent"] / out["census_births"]
    return out
