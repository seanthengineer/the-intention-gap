"""M10 descriptive analysis of rental cost burden and age-specific fertility, by state.

Summaries are descriptive: correlations are not tested and national trends
moving together are not evidence that housing affordability explains
fertility change. Bands in figures are the interquartile range across states,
not confidence intervals.

    python -m analysis.m10_descriptive

Writes data/public/m10/m10_desc_*.csv and assets/figures/m10_trends.png,
assets/figures/m10_between_within.png.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis.analyze_calibration import INK, apply_figure_style  # noqa: E402
from analysis.cdc_natality import OUTPUT_PATH as NATALITY_PATH  # noqa: E402
from analysis.m10_models import (AGES, FIGURE_DIR, OUTPUT_DIR,  # noqa: E402
                                 load_analysis_frame, two_way_demean)

SERIES = {"20-24": "#2a78d6", "25-29": "#eb6834"}
VARIABLES = {"burden30_pct": "Renter households paying 30%+ (B25070), %",
             "severe50_pct": "Renter households paying 50%+ (B25070), %",
             "young15_24_burden30_pct": "Renter householders 15-24 paying 30%+ (B25072), %",
             "young25_34_burden30_pct": "Renter householders 25-34 paying 30%+ (B25072), %",
             "unemployment_pct": "Unemployment rate, 16+ (B23025), %"}
SOURCES = ("Sources: U.S. Census Bureau ACS 1-year B25070/B25072; CDC WONDER Natality "
           "(mother's residence). 2020 has no standard ACS 1-year release.")


def state_year(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per state-year for housing variables (shared by both age groups)."""
    return frame[frame["age_group"].eq("20-24")].reset_index(drop=True)


def by_year(frame: pd.DataFrame, natality: pd.DataFrame) -> pd.DataFrame:
    rows = []
    housing = state_year(frame)
    for year, part in housing.groupby("year"):
        for column in VARIABLES:
            values = part[column]
            rows.append({"year": year, "variable": column, "states": len(values),
                         "mean": values.mean(), "median": values.median(),
                         "p25": values.quantile(0.25), "p75": values.quantile(0.75),
                         "min": values.min(), "max": values.max()})
    for (year, age), part in natality.groupby(["year", "age_group"]):
        rates = part["rate_exported"]
        rows.append({"year": year, "variable": f"rate_{age}", "states": len(rates),
                     "mean": rates.mean(), "median": rates.median(),
                     "p25": rates.quantile(0.25), "p75": rates.quantile(0.75),
                     "min": rates.min(), "max": rates.max(),
                     "national_rate": 1000 * part["births"].sum()
                     / part["female_population"].sum()})
    return pd.DataFrame(rows)


def variance_decomposition(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    columns = {**{c: state_year(frame) for c in VARIABLES},
               **{f"rate_{a}": frame[frame["age_group"].eq(a)].reset_index(drop=True)
                  for a in AGES}}
    for name, data in columns.items():
        column = "outcome_rate" if name.startswith("rate_") else name
        values = data[column]
        within = values - data.groupby("state_fips")[column].transform("mean")
        rows.append({"variable": name, "total_sd": values.std(),
                     "between_state_sd": data.groupby("state_fips")[column].mean().std(),
                     "within_state_sd": within.std(),
                     "two_way_residual_sd": two_way_demean(data, column).std(),
                     "within_share_of_variance": within.var() / values.var()})
    return pd.DataFrame(rows)


def associations(frame: pd.DataFrame) -> pd.DataFrame:
    """Correlations by level of variation (descriptive; no inference)."""
    rows = []
    for age in AGES:
        data = frame[frame["age_group"].eq(age)].reset_index(drop=True)
        for exposure in ("burden30_pct", "young_burden30_pct"):
            means = data.groupby("state_fips")[[exposure, "outcome_rate"]].mean()
            state_demeaned = data[[exposure, "outcome_rate"]] - data.groupby("state_fips")[
                [exposure, "outcome_rate"]].transform("mean")
            rows.append({
                "age_group": age, "exposure": exposure,
                "cross_section_state_means_r": means.corr().iloc[0, 1],
                "within_state_r": state_demeaned.corr().iloc[0, 1],
                "two_way_demeaned_r": np.corrcoef(two_way_demean(data, exposure),
                                                  two_way_demean(data, "outcome_rate"))[0, 1],
                "states": data["state_fips"].nunique(), "state_years": len(data)})
    return pd.DataFrame(rows)


def pre_post(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    frame = frame.assign(period=np.where(frame["year"] < 2020, "2014-2019", "2021-2024"))
    for (age, period), part in frame.groupby(["age_group", "period"]):
        rows.append({"age_group": age, "period": period,
                     "mean_state_rate": part["outcome_rate"].mean(),
                     "national_rate": 1000 * part["births"].sum()
                     / part["female_population"].sum(),
                     "mean_burden30_pct": part["burden30_pct"].mean(),
                     "mean_young_burden30_pct": part["young_burden30_pct"].mean(),
                     "state_years": len(part)})
    table = pd.DataFrame(rows)
    change = table.pivot(index="age_group", columns="period")
    for column in ("mean_state_rate", "national_rate", "mean_burden30_pct",
                   "mean_young_burden30_pct"):
        table.loc[table["period"].eq("2021-2024"), f"change_{column}"] = (
            change[column]["2021-2024"] - change[column]["2014-2019"]).reindex(
            table.loc[table["period"].eq("2021-2024"), "age_group"]).to_numpy()
    return table


def burden_measures(frame: pd.DataFrame) -> pd.DataFrame:
    housing = state_year(frame)
    rows = []
    for young in ("young15_24_burden30_pct", "young25_34_burden30_pct"):
        rows.append({"general": "burden30_pct", "younger": young,
                     "level_r": housing[["burden30_pct", young]].corr().iloc[0, 1],
                     "two_way_demeaned_r": np.corrcoef(two_way_demean(housing, "burden30_pct"),
                                                       two_way_demean(housing, young))[0, 1],
                     "mean_gap_pp": (housing[young] - housing["burden30_pct"]).mean(),
                     "median_se_younger": housing[young.replace("_pct", "_pct_se")].median()
                     if young.replace("_pct", "_pct_se") in housing else np.nan})
    return pd.DataFrame(rows)


def figure_trends(table: pd.DataFrame, path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    for age in AGES:
        part = table[table["variable"].eq(f"rate_{age}")].sort_values("year")
        ax.fill_between(part["year"], part["p25"], part["p75"], color=SERIES[age], alpha=0.15,
                        linewidth=0)
        ax.plot(part["year"], part["national_rate"], marker="o", markersize=5, linewidth=2,
                color=SERIES[age], label=f"Ages {age}: national rate")
    ax.axvspan(2019.5, 2020.5, color=INK["grid"], alpha=0.6, linewidth=0)
    ax.set_title("Births per 1,000 women, by age group", fontsize=11)
    ax.set_ylabel("Births per 1,000 women")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax = axes[1]
    for column, color, label in (("burden30_pct", INK["series"], "All renter households"),
                                 ("young15_24_burden30_pct", "#1baf7a", "Householders 15-24"),
                                 ("young25_34_burden30_pct", "#eda100", "Householders 25-34")):
        part = table[table["variable"].eq(column)].sort_values("year")
        for segment in (part[part["year"] < 2020], part[part["year"] > 2020]):
            ax.fill_between(segment["year"], segment["p25"], segment["p75"], color=color,
                            alpha=0.12, linewidth=0)
            ax.plot(segment["year"], segment["median"], marker="o", markersize=5, linewidth=2,
                    color=color, label=label if segment["year"].min() < 2020 else None)
    ax.axvspan(2019.5, 2020.5, color=INK["grid"], alpha=0.6, linewidth=0)
    ax.set_title("Renters paying 30%+ of income on gross rent (state median)", fontsize=11)
    ax.set_ylabel("Percent of renter households")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    for ax in axes:
        ax.set_xticks(range(2014, 2025, 2))
    fig.text(0.01, 0.01, "Bands: interquartile range across 51 jurisdictions (not confidence "
             "intervals). Grey: 2020, no ACS 1-year release. " + SOURCES, fontsize=7,
             color=INK["muted"], wrap=True)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def figure_between_within(frame: pd.DataFrame, path) -> None:
    data = frame[frame["age_group"].eq("20-24")].reset_index(drop=True)
    means = data.groupby("state_fips")[["burden30_pct", "outcome_rate"]].mean()
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3))
    axes[0].scatter(means["burden30_pct"], means["outcome_rate"], s=22, color=INK["series"])
    axes[0].set_title("Between states: 10-year state averages", fontsize=11)
    axes[0].set_xlabel("Renters paying 30%+, %")
    axes[0].set_ylabel("Births per 1,000 women aged 20-24")
    axes[1].scatter(two_way_demean(data, "burden30_pct"), two_way_demean(data, "outcome_rate"),
                    s=12, color=INK["series"], alpha=0.6)
    axes[1].set_title("Within states: after removing state and year averages", fontsize=11)
    axes[1].set_xlabel("Renters paying 30%+, deviation (percentage points)")
    axes[1].set_ylabel("Birth rate, deviation")
    fig.text(0.01, 0.01, "Descriptive only; each point is a state (left) or state-year (right), "
             "ages 20-24, 2014-2019 and 2021-2024. " + SOURCES, fontsize=7, color=INK["muted"])
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def build() -> dict[str, pd.DataFrame]:
    frame = load_analysis_frame()
    natality = pd.read_csv(NATALITY_PATH, dtype={"state_fips": str, "age_group": str})
    return {"frame": frame, "by_year": by_year(frame, natality),
            "variance": variance_decomposition(frame), "associations": associations(frame),
            "pre_post": pre_post(frame), "burden_measures": burden_measures(frame)}


def main() -> int:
    tables = build()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("by_year", "variance", "associations", "pre_post", "burden_measures"):
        tables[name].to_csv(OUTPUT_DIR / f"m10_desc_{name}.csv", index=False,
                            float_format="%.10g")
    apply_figure_style()
    figure_trends(tables["by_year"], FIGURE_DIR / "m10_trends.png")
    figure_between_within(tables["frame"], FIGURE_DIR / "m10_between_within.png")
    pd.set_option("display.width", 200)
    for name in ("variance", "associations", "pre_post", "burden_measures"):
        print(f"--- {name}")
        print(tables[name].round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
