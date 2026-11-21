"""M10 provisional state-year-age panel: CDC WONDER natality joined to ACS B25070.

Feasibility only: no model is fitted. The panel keeps the two maternal age
groups (20-24, 25-29) as separate rows and joins housing measures by FIPS code
and calendar year. 2020 is excluded from the primary panel (no standard ACS
1-year release) but kept in the CDC table. Lagged housing measures are joined
on the actual previous calendar year, so a 2021 row has no lag (2020 does not
exist) instead of borrowing 2019.

    python -m analysis.m10_panel        (after analysis.acs_housing and analysis.cdc_natality)
"""

import json
import sys

import numpy as np
import pandas as pd

from analysis.acs_housing import OUTPUT_PATH as ACS_PATH
from analysis.acs_housing import PROCESSED_DIR, STATE_FIPS
from analysis.cdc_natality import OUTPUT_PATH as CDC_PATH

PANEL_PATH = PROCESSED_DIR / "m10_panel_state_year_age.csv"
EXCLUDED_YEAR = 2020
HOUSING = ["burden30_pct", "burden30_pct_moe90", "severe50_pct", "severe50_pct_moe90",
           "not_computed_pct", "households_computed"]


def load(acs_path=ACS_PATH, cdc_path=CDC_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    for path in (acs_path, cdc_path):
        if not path.exists():
            raise FileNotFoundError(f"Run the acquisition step first: {path}")
    acs = pd.read_csv(acs_path, dtype={"state_fips": str})
    cdc = pd.read_csv(cdc_path, dtype={"state_fips": str, "age_group": str})
    return acs, cdc


def lagged(acs: pd.DataFrame, lag: int = 1) -> pd.DataFrame:
    """Housing measures of calendar year t - lag, keyed to year t (no bridging of gaps)."""
    shifted = acs[["state_fips", "year", *HOUSING]].copy()
    shifted["year"] = shifted["year"] + lag
    return shifted.rename(columns={c: f"{c}_lag{lag}" for c in HOUSING})


def build_panel(acs: pd.DataFrame, cdc: pd.DataFrame) -> pd.DataFrame:
    if acs.duplicated(["state_fips", "year"]).any():
        raise ValueError("Duplicate ACS state-year keys")
    if cdc.duplicated(["state_fips", "year", "age_group"]).any():
        raise ValueError("Duplicate CDC state-year-age keys")
    primary = cdc[cdc["year"].ne(EXCLUDED_YEAR)]
    panel = primary.merge(acs[["state_fips", "year", "state_name", *HOUSING]],
                          on=["state_fips", "year"], how="left", validate="many_to_one",
                          suffixes=("", "_acs"), indicator="acs_match")
    panel = panel.merge(lagged(acs), on=["state_fips", "year"], how="left",
                        validate="many_to_one")
    panel["state_name_agrees"] = panel["state_name"].eq(panel["state_name_acs"])
    panel["outcome_rate"] = panel["rate_exported"]
    return panel.sort_values(["state_fips", "year", "age_group"]).reset_index(drop=True)


NOISE_ASSUMPTIONS = [
    "approximate SEs (Census formulas, covariance between categories ignored) are correct "
    "on average",
    "sampling errors are independent across states and years (separate annual samples; "
    "population controls induce some dependence that is ignored)",
    "sampling errors are uncorrelated with the true burden share",
]


def two_way_demean(values: np.ndarray) -> np.ndarray:
    """Remove state (row) and year (column) means from a balanced state x year array."""
    return (values - values.mean(axis=1, keepdims=True) - values.mean(axis=0, keepdims=True)
            + values.mean())


def sampling_noise_assessment(acs: pd.DataFrame, column: str = "burden30_pct",
                              draws: int = 2000, seed: int = 2026) -> dict:
    """Expected share of the two-way-demeaned variance that ACS sampling error would produce.

    Sampling errors are simulated from each estimate's approximate SE and passed
    through the same state and year demeaning as the observed series. This
    describes the measure only; it says nothing about bias in any regression.
    """
    wide = acs.pivot(index="state_fips", columns="year", values=column)
    se = acs.pivot(index="state_fips", columns="year", values=f"{column}_se")
    if wide.isna().any().any() or se.isna().any().any():
        raise ValueError("Noise assessment needs a balanced state x year panel")
    observed = two_way_demean(wide.to_numpy())
    observed_var = float(observed.var())
    rng = np.random.default_rng(seed)
    result = {"observed_residual_variance": observed_var,
              "raw_mean_sampling_variance": float((se.to_numpy() ** 2).mean())}
    for scale in (0.75, 1.0, 1.25):
        noise = rng.standard_normal((draws, *wide.shape)) * (scale * se.to_numpy())
        demeaned = (noise - noise.mean(axis=2, keepdims=True) - noise.mean(axis=1, keepdims=True)
                    + noise.mean(axis=(1, 2), keepdims=True))
        noise_var = float(demeaned.var(axis=(1, 2)).mean())
        result[f"se_x{scale}"] = {"expected_noise_variance": noise_var,
                                  "noise_share": noise_var / observed_var,
                                  "implied_reliability": 1 - noise_var / observed_var}
    result["assumptions"] = NOISE_ASSUMPTIONS
    return result


def feasibility(panel: pd.DataFrame, acs: pd.DataFrame, cdc: pd.DataFrame) -> dict:
    keys = panel[["state_fips", "year", "age_group"]]
    years = sorted(panel["year"].unique().tolist())
    complete_rate = panel["outcome_rate"].notna() & panel["burden30_pct"].notna()
    lag_rows = panel[["year", "burden30_pct_lag1"]]
    within_state_sd = acs.groupby("state_fips")["burden30_pct"].std()
    within_year_sd = acs.groupby("year")["burden30_pct"].std()
    demeaned = (acs["burden30_pct"] - acs.groupby("state_fips")["burden30_pct"].transform("mean")
                - acs.groupby("year")["burden30_pct"].transform("mean")
                + acs["burden30_pct"].mean())
    rate_panel = panel[complete_rate]
    acs_lookup = acs.set_index(["state_fips", "year"])["burden30_pct"]
    has_lag = panel["burden30_pct_lag1"].notna()
    expected_lag = [acs_lookup.get((s, y - 1), np.nan)
                    for s, y in zip(panel.loc[has_lag, "state_fips"], panel.loc[has_lag, "year"])]
    coverage = panel.groupby("year")["state_fips"].nunique()
    acs_se = (acs.assign(burden30_pct_se=acs["burden30_pct_moe90"] / 1.645)
              if "burden30_pct_se" not in acs else acs)
    return {
        "records": len(panel), "expected_records": len(STATE_FIPS) * 10 * 2,
        "years": years, "jurisdictions": int(panel["state_fips"].nunique()),
        "age_groups": sorted(panel["age_group"].unique().tolist()),
        "duplicate_keys": int(keys.duplicated().sum()),
        "unmatched_to_acs": int(panel["acs_match"].ne("both").sum()),
        "state_name_disagreements": int((~panel["state_name_agrees"]).sum()),
        "cdc_2020_rows_kept_outside_panel": int(cdc["year"].eq(EXCLUDED_YEAR).sum()),
        "acs_state_years_without_cdc": int(len(acs.merge(cdc[["state_fips", "year"]]
                                                         .drop_duplicates(),
                                                         how="left", indicator=True)
                                               .query("_merge == 'left_only'"))),
        "births_and_housing_complete": int((panel["births"].notna()
                                            & panel["burden30_pct"].notna()).sum()),
        "rate_and_housing_complete": int(complete_rate.sum()),
        "rate_complete_by_year": panel.groupby("year")["outcome_rate"].apply(
            lambda s: int(s.notna().sum())).to_dict(),
        "lag1_available_by_year": lag_rows.groupby("year")["burden30_pct_lag1"].apply(
            lambda s: int(s.notna().sum())).to_dict(),
        "lag1_2021_rows_with_value": int(lag_rows.loc[lag_rows["year"].eq(2021),
                                                      "burden30_pct_lag1"].notna().sum()),
        "lag1_values_checked": int(has_lag.sum()),
        "lag1_value_mismatches": int((~np.isclose(panel.loc[has_lag, "burden30_pct_lag1"],
                                                  expected_lag)).sum()),
        "years_with_incomplete_geography": [int(y) for y, n in coverage.items()
                                            if n != len(STATE_FIPS)],
        "rows_per_state_year": sorted(panel.groupby(["state_fips", "year"]).size().unique()
                                      .tolist()),
        "sampling_noise": sampling_noise_assessment(acs_se),
        "fixed_effects": {
            "states": int(panel["state_fips"].nunique()), "years": len(years),
            "balanced_births_panel": bool(panel.groupby("state_fips").size().nunique() == 1),
            "states_with_zero_within_variation": int((within_state_sd == 0).sum()),
            "min_within_state_sd_burden30": float(within_state_sd.min()),
            "min_within_year_sd_burden30": float(within_year_sd.min()),
            "residual_sd_after_two_way_demeaning": float(demeaned.std()),
            "raw_sd_burden30": float(acs["burden30_pct"].std()),
            "rate_panel_years": sorted(rate_panel["year"].unique().tolist()),
            "rate_panel_balanced": bool(rate_panel.groupby("state_fips").size().nunique()
                                        == 1) if len(rate_panel) else False,
        },
    }


def status(report: dict) -> str:
    if (report["duplicate_keys"] or report["unmatched_to_acs"]
            or report["state_name_disagreements"] or report["lag1_2021_rows_with_value"]
            or report["lag1_value_mismatches"] or report["years_with_incomplete_geography"]
            or report["fixed_effects"]["states_with_zero_within_variation"]):
        return "FAIL"
    if (report["records"] != report["expected_records"]
            or report["rate_and_housing_complete"] < report["records"]
            or report["jurisdictions"] != len(STATE_FIPS)):
        return "WARN"
    return "PASS"


def main() -> int:
    acs, cdc = load()
    panel = build_panel(acs, cdc)
    report = feasibility(panel, acs, cdc)
    report["status"] = status(report)
    panel.drop(columns=["acs_match", "state_name_acs"]).to_csv(PANEL_PATH, index=False,
                                                              float_format="%.10g")
    (PROCESSED_DIR / "m10_panel_validation.json").write_text(
        json.dumps(report, indent=1, default=lambda v: v.item() if isinstance(v, np.generic)
                   else str(v)) + "\n", encoding="utf-8")
    print(f"M10 panel | {report['records']} state-year-age records (expected "
          f"{report['expected_records']}); years {report['years']}")
    print(f"  duplicates {report['duplicate_keys']}, unmatched {report['unmatched_to_acs']}, "
          f"name disagreements {report['state_name_disagreements']}")
    print(f"  births + housing complete: {report['births_and_housing_complete']}; "
          f"rate + housing complete: {report['rate_and_housing_complete']}")
    print(f"  rate rows by year: {report['rate_complete_by_year']}")
    print(f"  lag-1 rows by year: {report['lag1_available_by_year']}")
    print(f"  fixed effects: {report['fixed_effects']}")
    print(f"  lag values checked {report['lag1_values_checked']}, mismatches "
          f"{report['lag1_value_mismatches']}; incomplete geography "
          f"{report['years_with_incomplete_geography'] or 'none'}")
    noise = report["sampling_noise"]
    print(f"  sampling noise in two-way-demeaned burden30: " + "; ".join(
        f"SE x{k[4:]}: share {v['noise_share']:.2f}" for k, v in noise.items()
        if k.startswith("se_x")) + f" (observed residual variance "
        f"{noise['observed_residual_variance']:.3f})")
    print(f"Status: {report['status']}")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
