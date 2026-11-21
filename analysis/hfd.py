"""Human Fertility Database (HFD), United States: parsing, coverage and validation for M11.

The HFD country archive (USA.zip, HFD release of 2 July 2026; file headers
"Last modified: 27/06/2026") is saved in data/raw/hfd_usa/ with its 51 text
files extracted beside it. Files are read without modification.

HFD file conventions (Methods Protocol, data/raw/hfd_docs/methods.pdf):
- Ages are 12 to 55; "12-" is age 12 and younger, "55+" is 55 and older.
- "." marks a cell that is not observed (cohort cells outside the period
  window, or summary measures for cohorts not yet complete).
- RR = Lexis squares (calendar year x age in completed years), TR = Lexis
  triangles (year x age x cohort), VH = horizontal parallelograms (cohort x
  age), VV = vertical parallelograms (year x age reached during the year).
- Rates are births divided by female person-years of exposure; exposures are
  estimated from Human Mortality Database population data, not taken directly
  from Census July 1 estimates.
- Completed cohort fertility (CCF) is shown only for cohorts observed from age
  15 or younger to age 50 or older; CCF40 for cohorts observed to age 40.

The validation checks recompute HFD quantities from other HFD files (rates from
births and exposures, summary measures from rates, squares from triangles,
cohort cells from triangles). They test internal consistency and calculation
conventions; they cannot test the accuracy of the underlying registrations.

    python -m analysis.hfd
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.m11_sources import HFD_DIR

AGE_COLUMNS = ("Age", "ARDY", "x")
INDEX_COLUMNS = ("Year", "Cohort")
GEN_Z_COHORTS = list(range(1995, 2013))   # owner's definition: births 1995-2012


def header(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    modified = re.search(r"Last modified:\s*(\S+)", lines[1])
    return {"title": lines[0].strip(), "last_modified": modified.group(1) if modified else ""}


def read_hfd(name: str, folder: Path = HFD_DIR) -> pd.DataFrame:
    """One HFD text file as a DataFrame; '.' becomes NaN, open ages are flagged."""
    path = folder / (name if name.endswith(".txt") else name + ".txt")
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.split() and line.split()[0] in INDEX_COLUMNS)
    columns = lines[start].split()
    rows = [line.split() for line in lines[start + 1:] if line.strip()]
    bad = [r for r in rows if len(r) != len(columns)]
    if bad:
        raise ValueError(f"{path.name}: {len(bad)} rows do not have {len(columns)} fields")
    table = pd.DataFrame(rows, columns=columns)
    for column in columns:
        if column in AGE_COLUMNS:
            raw = table[column]
            table["age_open"] = np.where(raw.str.endswith("-"), "lower",
                                         np.where(raw.str.endswith("+"), "upper", ""))
            table[column] = raw.str.rstrip("+-").astype(int)
        elif column == "Cohort":
            # VV files label the open-age cohorts "1921+" (55+) and "1980-" (12-)
            raw = table[column]
            table["cohort_open"] = np.where(raw.str.endswith(("+", "-")), raw.str[-1], "")
            table[column] = pd.to_numeric(raw.str.rstrip("+-").replace(".", np.nan))
        else:
            table[column] = pd.to_numeric(table[column].replace(".", np.nan))
    for column in INDEX_COLUMNS:
        if column in table:
            table[column] = table[column].astype("Int64")   # Cohort can be missing in TR files
    table.attrs.update(header(path), file=path.name)
    return table


def decimals(name: str, column: str) -> int:
    """Number of printed decimals in one column (used to set rounding tolerances)."""
    path = HFD_DIR / f"{name}.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.split() and line.split()[0] in INDEX_COLUMNS)
    position = lines[start].split().index(column)
    places = 0
    for line in lines[start + 1:start + 400]:
        token = line.split()[position] if len(line.split()) > position else "."
        if "." in token and token != ".":
            places = max(places, len(token.split(".")[1]))
    return places


def half_unit(name: str, column: str) -> float:
    return 0.5 * 10 ** -decimals(name, column)


# ------------------------------------------------------------------ coverage

def coverage() -> pd.DataFrame:
    """One row per HFD file: content, index range, ages, birth order and missing cells."""
    rows = []
    for path in sorted(HFD_DIR.glob("USA*.txt")):
        table = read_hfd(path.name)
        index = table.columns[0]
        age = next((c for c in AGE_COLUMNS if c in table.columns), None)
        values = [c for c in table.columns if c not in (index, age, "age_open", "Cohort", "Year")]
        cells = table[values]
        observed = table.dropna(subset=values, how="all")
        rows.append({
            "file": path.name, "title": table.attrs["title"], "last_modified": table.attrs["last_modified"],
            "index": index, "first": int(table[index].min()), "last": int(table[index].max()),
            "first_observed": int(observed[index].min()) if len(observed) else None,
            "last_observed": int(observed[index].max()) if len(observed) else None,
            "ages": f"{table[age].min()}-{table[age].max()}" if age else "",
            "birth_order": any(re.search(r"(1|2|3|4|5p)$", c) for c in values) or "bo" in path.stem[-2:],
            "rows": len(table), "value_cells": int(cells.size),
            "missing_cells": int(cells.isna().sum().sum()),
            "missing_share": float(cells.isna().sum().sum() / cells.size) if cells.size else 0.0,
        })
    return pd.DataFrame(rows)


def period_missing_by_year() -> pd.DataFrame:
    """Missing cells in the period (RR) tables by year, a direct check on gaps."""
    rows = []
    births, expos, asfr = read_hfd("USAbirthsRR"), read_hfd("USAexposRR"), read_hfd("USAasfrRR")
    for year, group in asfr.groupby("Year"):
        rows.append({"year": int(year), "ages": len(group),
                     "missing_asfr": int(group["ASFR"].isna().sum()),
                     "missing_births": int(births.loc[births["Year"] == year, "Total"].isna().sum()),
                     "missing_exposure": int(expos.loc[expos["Year"] == year, "Exposure"].isna().sum())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- validation

def _result(check, ok, detail, tolerance=None, warn=False):
    status = "PASS" if ok else ("WARN" if warn else "FAIL")
    return {"check": check, "status": status, "detail": detail, "tolerance": tolerance}


FLOAT = 1e-6   # floating-point slack when a tolerance is an exact sum of rounding bounds


def period_frame() -> pd.DataFrame:
    births, expos, asfr = read_hfd("USAbirthsRR"), read_hfd("USAexposRR"), read_hfd("USAasfrRR")
    frame = births.merge(expos, on=["Year", "Age"]).merge(asfr, on=["Year", "Age"])
    frame["rate"] = frame["Total"] / frame["Exposure"]
    return frame


def validate() -> list[dict]:
    out = []
    frame = period_frame()

    years = sorted(frame["Year"].unique())
    contiguous = years == list(range(years[0], years[-1] + 1))
    complete = frame.groupby("Year")["Age"].apply(lambda a: sorted(a) == list(range(12, 56))).all()
    nan = int(frame[["Total", "Exposure", "ASFR"]].isna().sum().sum())
    out.append(_result("Period coverage: contiguous years, ages 12-55 every year, no missing cells",
                       contiguous and complete and nan == 0,
                       f"years {years[0]}-{years[-1]} ({len(years)}); missing cells {nan}"))

    tol = half_unit("USAasfrRR", "ASFR") + 1e-9
    gap = (frame["rate"] - frame["ASFR"]).abs().max()
    out.append(_result("ASFR (RR) = births / exposure", gap <= tol, f"max abs diff {gap:.2e}", tol))

    tfr = read_hfd("USAtfrRR").set_index("Year")
    recomputed = frame.groupby("Year")["rate"].sum()
    under40 = frame[frame["Age"] < 40].groupby("Year")["rate"].sum()
    tol = half_unit("USAtfrRR", "TFR") + 1e-9
    gap = max((recomputed - tfr["TFR"]).abs().max(), (under40 - tfr["TFR40"]).abs().max())
    out.append(_result("TFR and TFR40 = sum of single-year rates (all ages / ages under 40)",
                       gap <= tol, f"max abs diff {gap:.2e}", tol))

    total = read_hfd("USAtotbirthsRR").set_index("Year")["Total"]
    summed = frame.groupby("Year")["Total"].sum()
    tol = 44 * half_unit("USAbirthsRR", "Total") + half_unit("USAtotbirthsRR", "Total")
    gap = (summed - total).abs().max()
    out.append(_result("Total births = sum of births by age", gap <= tol, f"max abs diff {gap:.3f}", tol))

    bo = read_hfd("USAbirthsRRbo")
    orders = bo[["B1", "B2", "B3", "B4", "B5p"]].sum(axis=1)
    tol = 6 * half_unit("USAbirthsRRbo", "Total") + FLOAT
    same = bo.merge(frame[["Year", "Age", "Total"]], on=["Year", "Age"], suffixes=("", "_rr"))
    gap = max((orders - bo["Total"]).abs().max(), (same["Total"] - same["Total_rr"]).abs().max())
    out.append(_result("Births by order sum to the total; order file total equals RR births",
                       gap <= tol, f"max abs diff {gap:.3f}", tol))

    abo = read_hfd("USAasfrRRbo")
    tol = 6 * half_unit("USAasfrRRbo", "ASFR")
    gap = (abo[["ASFR1", "ASFR2", "ASFR3", "ASFR4", "ASFR5p"]].sum(axis=1) - abo["ASFR"]).abs().max()
    out.append(_result("Order-specific ASFRs sum to the all-order ASFR", gap <= tol,
                       f"max abs diff {gap:.2e}", tol))

    tbo = read_hfd("USAtfrRRbo")
    tol = 6 * half_unit("USAtfrRRbo", "TFR")
    gap = (tbo[["TFR1", "TFR2", "TFR3", "TFR4", "TFR5p"]].sum(axis=1) - tbo["TFR"]).abs().max()
    out.append(_result("Order-specific TFRs sum to the TFR", gap <= tol, f"max abs diff {gap:.4f}", tol))

    tr_b, tr_e = read_hfd("USAbirthsTR"), read_hfd("USAexposTR")
    squares_b = tr_b.groupby(["Year", "Age"])["Total"].sum()
    squares_e = tr_e.groupby(["Year", "Age"])["Exposure"].sum()
    rr = frame.set_index(["Year", "Age"])
    gap_b = (squares_b - rr["Total"]).abs().max()
    gap_e = (squares_e - rr["Exposure"]).abs().max()
    tol_b, tol_e = 3 * half_unit("USAbirthsTR", "Total"), 3 * half_unit("USAexposTR", "Exposure")
    out.append(_result("Lexis triangles sum to Lexis squares (births and exposures)",
                       gap_b <= tol_b and gap_e <= tol_e,
                       f"births {gap_b:.3f}; exposure {gap_e:.3f}", max(tol_b, tol_e)))

    out.append(cohort_from_triangles(tr_b, tr_e))

    vh = cohort_frame()
    tol = half_unit("USAasfrVH", "ASFR") + 1e-9
    gap = (vh["Total"] / vh["Exposure"] - vh["ASFR"]).abs().max()
    out.append(_result("Cohort ASFR (VH) = cohort births / cohort exposure", gap <= tol,
                       f"max abs diff {gap:.2e} over {len(vh):,} cells", tol))

    out.append(cumulative_cohort_check(vh))
    out.append(completed_cohort_check(vh))
    out.extend(vv_checks(tr_b, tr_e))
    out.append(mean_age_check(frame))
    out.append(token_check())
    return out


def cohort_frame(folder: Path = HFD_DIR) -> pd.DataFrame:
    """Cohort (VH) births, exposures and rates, one row per observed cohort-age cell.

    Exposure files print the open ages as "12" and "55" while birth and rate
    files print "12-" and "55+", so the files are joined on cohort and age only
    and the open-age flag is taken from the births file. (Joining on the flag
    as well silently dropped every open-age cell; corrected in M11 stage 1.)
    """
    births = read_hfd("USAbirthsVH", folder)
    expos = read_hfd("USAexposVH", folder).drop(columns="age_open")
    rates = read_hfd("USAasfrVH", folder).drop(columns="age_open")
    frame = births.merge(expos, on=["Cohort", "Age"], how="inner", validate="one_to_one") \
        .merge(rates, on=["Cohort", "Age"], how="inner", validate="one_to_one")
    return frame.dropna(subset=["ASFR"]).sort_values(["Cohort", "Age"]).reset_index(drop=True)


def cohort_from_triangles(tr_b: pd.DataFrame, tr_e: pd.DataFrame) -> dict:
    """VH cell (cohort c, age x) = lower triangle (year c+x) + upper triangle (year c+x+1).

    Open-age cells are excluded by design: 12- and 55+ are not two triangles.
    """
    tr = tr_b.merge(tr_e.drop(columns="age_open"), on=["Year", "Age", "Cohort"]).dropna(subset=["Cohort"])
    tr = tr[tr["age_open"] == ""]
    grouped = tr.groupby(["Cohort", "Age"]).agg(births=("Total", "sum"), exposure=("Exposure", "sum"),
                                               cells=("Total", "size"))
    complete = grouped[grouped["cells"] == 2]
    vh = cohort_frame()
    vh = vh[vh["age_open"] == ""].set_index(["Cohort", "Age"])
    joined = complete.join(vh, how="inner").dropna(subset=["Total", "Exposure"])
    gap_b = (joined["births"] - joined["Total"]).abs().max()
    gap_e = (joined["exposure"] - joined["Exposure"]).abs().max()
    tol = 3 * max(half_unit("USAbirthsTR", "Total"), half_unit("USAexposTR", "Exposure"))
    return _result("Cohort cells (VH) = two Lexis triangles of the same cohort",
                   gap_b <= tol and gap_e <= tol,
                   f"{len(joined):,} cells; births {gap_b:.3f}; exposure {gap_e:.3f}", tol)


def cumulative_by_exact_age(vh: pd.DataFrame) -> pd.DataFrame:
    """Cohort fertility accumulated before exact age x: the sum of VH rates at ages below x.

    This is the HFD CCFR convention (CCFR at age x excludes births at age x).
    """
    rates = vh.sort_values(["Cohort", "Age"]).copy()
    rates["cumulative"] = rates.groupby("Cohort")["ASFR"].cumsum()
    rates["Age"] = rates["Age"] + 1
    return rates[["Cohort", "Age", "cumulative"]]


def cumulative_cohort_check(vh: pd.DataFrame) -> dict:
    ccfr = read_hfd("USAccfrVH").dropna(subset=["CCFR"])
    joined = ccfr.merge(cumulative_by_exact_age(vh), on=["Cohort", "Age"])
    gaps = (joined["cumulative"] - joined["CCFR"]).abs()
    tol = 44 * half_unit("USAasfrVH", "ASFR") + half_unit("USAccfrVH", "CCFR")
    detail = (f"{len(joined):,} cells; max abs diff {gaps.max():.5f}; "
              f"{int((gaps > half_unit('USAccfrVH', 'CCFR')).sum())} cells beyond print precision")
    return _result("CCFR at age x = sum of cohort ASFRs at ages below x", gaps.max() <= tol,
                   detail, tol, warn=gaps.max() <= 0.001)


def completed_cohort_check(vh: pd.DataFrame) -> dict:
    """CCF (all ages) and CCF40 (ages under 40) against sums of exact cohort rates.

    PASS within the 3-decimal print precision; WARN up to 0.001 child per woman
    (immaterial, cause not identified); FAIL beyond.
    """
    ccf = read_hfd("USAtfrVH")
    rates = vh.assign(rate=vh["Total"] / vh["Exposure"])
    total = rates.groupby("Cohort")["rate"].sum()
    under40 = rates[rates["Age"] < 40].groupby("Cohort")["rate"].sum()
    joined = ccf.set_index("Cohort").join(total.rename("sum_all")).join(under40.rename("sum_40"))
    full, by40 = joined.dropna(subset=["CCF"]), joined.dropna(subset=["CCF40"])
    gaps = pd.concat([(full["sum_all"] - full["CCF"]).abs(), (by40["sum_40"] - by40["CCF40"]).abs()])
    tol = half_unit("USAtfrVH", "CCF") + 1e-9
    beyond = int((gaps > tol).sum())
    detail = (f"CCF cohorts {int(full.index.min())}-{int(full.index.max())}, CCF40 to "
              f"{int(by40.index.max())}; max abs diff {gaps.max():.5f}; {beyond} of {len(gaps)} "
              f"values beyond print precision")
    return _result("CCF and CCF40 = sum of cohort rates over observed ages", gaps.max() <= tol,
                   detail, tol, warn=gaps.max() <= 0.001)


def vv_frame(folder: Path = HFD_DIR) -> pd.DataFrame:
    """Vertical parallelograms: year x age reached during the year (ARDY), one cohort per cell.

    Cohort = Year - ARDY. "12-" (cohorts born in or after Year - 12) and "55+"
    (born in or before Year - 55) are open; exposure files print them as 12 and 55.
    """
    births = read_hfd("USAbirthsVV", folder)
    expos = read_hfd("USAexposVV", folder).drop(columns=["age_open", "Cohort", "cohort_open"], errors="ignore")
    rates = read_hfd("USAasfrVV", folder).drop(columns=["age_open", "Cohort", "cohort_open"], errors="ignore")
    frame = births.merge(expos, on=["Year", "ARDY"], how="inner", validate="one_to_one") \
        .merge(rates, on=["Year", "ARDY"], how="inner", validate="one_to_one")
    if not (frame["Cohort"] == frame["Year"] - frame["ARDY"]).all():
        raise ValueError("VV cohort labels do not equal Year - ARDY")
    return frame.sort_values(["Year", "ARDY"]).reset_index(drop=True)


def vv_checks(tr_b: pd.DataFrame, tr_e: pd.DataFrame) -> list[dict]:
    """VV rates = births / exposure; each closed VV cell = upper triangle (age a-1) + lower (age a)."""
    vv = vv_frame()
    tol = half_unit("USAasfrVV", "ASFR") + 1e-9
    gap = (vv["Total"] / vv["Exposure"] - vv["ASFR"]).abs().max()
    out = [_result("Period-cohort ASFR (VV, age reached during year) = births / exposure", gap <= tol,
                   f"max abs diff {gap:.2e} over {len(vv):,} cells (open ages included)", tol)]

    tr = tr_b.merge(tr_e.drop(columns="age_open"), on=["Year", "Age", "Cohort"]).dropna(subset=["Cohort"])
    tr = tr[tr["age_open"] == ""]
    tr["ARDY"] = tr["Year"] - tr["Cohort"]          # upper triangle of age a-1 and lower of age a share it
    summed = tr.groupby(["Year", "ARDY"]).agg(births=("Total", "sum"), exposure=("Exposure", "sum"),
                                              cells=("Total", "size"))
    # ARDY 13 is excluded: its upper triangle (age 12) lies in HFD's open 12- triangle,
    # which carries no cohort label. Every cell with ARDY 14-54 must be rebuilt.
    closed = vv[vv["ARDY"].between(14, 54)].set_index(["Year", "ARDY"])
    joined = summed[summed["cells"] == 2].join(closed, how="inner")
    gap_b = (joined["births"] - joined["Total"]).abs().max()
    gap_e = (joined["exposure"] - joined["Exposure"]).abs().max()
    tol = 3 * max(half_unit("USAbirthsTR", "Total"), half_unit("USAexposTR", "Exposure"))
    out.append(_result("VV cell (year t, ARDY a) = upper triangle at age a-1 + lower triangle at age a, "
                       "same cohort t-a (ARDY 14-54)", gap_b <= tol and gap_e <= tol and len(joined) == len(closed),
                       f"{len(joined):,} of {len(closed):,} cells; births {gap_b:.3f}; "
                       f"exposure {gap_e:.3f}", tol))
    return out


def cumulative_by_year_end(vv: pd.DataFrame, cohorts, last_year: int) -> pd.DataFrame:
    """Cohort fertility accumulated by 31 December of each year: running sum of VV rates.

    At the end of year t a woman born in year c has exact age between t-c and
    t-c+1, so this is "fertility by the end of year t", not fertility by an
    exact age. The open 12- cell is included (births at ages 12 and younger).
    """
    rows = vv[vv["Cohort"].isin(list(cohorts)) & (vv["Year"] <= last_year)].sort_values(["Cohort", "Year"])
    rows = rows.assign(cumulative=rows.groupby("Cohort")["ASFR"].cumsum())
    return rows[["Cohort", "Year", "ARDY", "ASFR", "cumulative"]].reset_index(drop=True)


def mean_age_check(frame: pd.DataFrame) -> dict:
    """Period mean age at birth with rates weighted at age x + 0.5."""
    mab = read_hfd("USAmabRR").set_index("Year")
    weighted = frame.assign(w=frame["rate"] * (frame["Age"] + 0.5))
    recomputed = weighted.groupby("Year")["w"].sum() / weighted.groupby("Year")["rate"].sum()
    tol = half_unit("USAmabRR", "MAB") + 1e-9
    gap = (recomputed - mab["MAB"]).abs().max()
    return _result("Period mean age at birth = rate-weighted mean of (age + 0.5)", gap <= tol,
                   f"max abs diff {gap:.4f}", tol)


def token_check() -> dict:
    """No provisional, estimated or revision markers: every value is numeric, '.', or an open age."""
    unexpected = 0
    for path in HFD_DIR.glob("USA*.txt"):
        lines = path.read_text(encoding="utf-8").splitlines()
        start = next(i for i, line in enumerate(lines) if line.split() and line.split()[0] in INDEX_COLUMNS)
        for line in lines[start + 1:]:
            for token in line.split():
                if not re.fullmatch(r"-?\d+(\.\d+)?|\.|\d+[-+]", token):
                    unexpected += 1
    return _result("No flagged, provisional or non-numeric values in any file", unexpected == 0,
                   f"{unexpected} unexpected tokens")


# ------------------------------------------------------- cohort observability

def cohort_observability(cohorts=GEN_Z_COHORTS, last_period_year: int = 2024,
                         nchs_year: int = 2025, horizon: int = 2040) -> pd.DataFrame:
    """For each cohort: what HFD observes (cohort cells and triangles) and what lies beyond.

    Age conventions: a cohort born in year c reaches exact age (t - c) during
    calendar year t. A complete HFD cohort cell at age x (completed years) needs
    calendar years c+x and c+x+1. Ages of childbearing are 12-55+.
    """
    asfr = read_hfd("USAasfrVH").dropna(subset=["ASFR"])
    ccfr = read_hfd("USAccfrVH").dropna(subset=["CCFR"])
    tr = read_hfd("USAasfrTR").dropna(subset=["Cohort", "ASFR"])
    rows = []
    for c in cohorts:
        cells = asfr[asfr["Cohort"] == c]
        triangles = tr[tr["Cohort"] == c]
        last_complete = int(cells["Age"].max()) if len(cells) else None
        cum = ccfr[(ccfr["Cohort"] == c) & (ccfr["Age"] == (last_complete or 0) + 1)]
        last_year = triangles[triangles["Year"] == triangles["Year"].max()] if len(triangles) else triangles
        rows.append({
            "cohort": c,
            "age_reached_in_2024": last_period_year - c,
            "hfd_complete_ages": ("none" if last_complete is None else
                                  "12" if last_complete == 12 else f"12-{last_complete}"),
            "hfd_partial_age_2024": (f"{int(last_year['Age'].max())} (lower triangle only)"
                                     if len(last_year) else "none"),
            "hfd_cumulative_fertility": float(cum["CCFR"].iloc[0]) if len(cum) else None,
            "hfd_cumulative_to_exact_age": (last_complete + 1) if last_complete is not None else None,
            "nchs_2025_period_ages": f"{nchs_year - c - 1}-{nchs_year - c}",
            "age_reached_in_2040": horizon - c,
            "ages_to_forecast_2026_2040": f"{nchs_year + 1 - c - 1}-{horizon - c}",
            "ages_unobserved_after_2040": f"{horizon - c + 1}-55+" if horizon - c < 55 else "none",
        })
    return pd.DataFrame(rows)


def completed_share_by_age(reference: range = range(1965, 1975)) -> pd.DataFrame:
    """Share of completed cohort fertility reached by each age, in completed reference cohorts.

    Historical context for how much of lifetime fertility a cohort has had by
    a given age; it is a description of past cohorts, not a projection.
    """
    ccfr = read_hfd("USAccfrVH").dropna(subset=["CCFR"])
    ccf = read_hfd("USAtfrVH").dropna(subset=["CCF"]).set_index("Cohort")["CCF"]
    ref = ccfr[ccfr["Cohort"].isin(list(reference))].copy()
    ref["share"] = ref["CCFR"] / ref["Cohort"].map(ccf)
    return ref.groupby("Age")["share"].agg(["min", "median", "max"]).reset_index()


def main() -> int:
    for result in validate():
        print(f"{result['status']}  {result['check']}: {result['detail']}")
    print(cohort_observability().to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
