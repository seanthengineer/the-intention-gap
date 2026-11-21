"""M11 forecasting figures, drawn only from the saved tables in data/public/m11/forecast/.

Observed values are solid lines or filled markers; projections are dashed lines
or open markers. Every interval is labelled with its type (prediction interval,
model-dependent projection or scenario).

    python -m analysis.m11_figures
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import hfd  # noqa: E402
from analysis.analyze_calibration import INK, apply_figure_style  # noqa: E402
from analysis.m11_forecast import OUT  # noqa: E402
from analysis.m11_protocol import PROJECT_ROOT  # noqa: E402

FIGURES = PROJECT_ROOT / "assets" / "figures"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"   # reference palette slots 1-4, in order
SOURCE = "Source: Human Fertility Database (USA, release 2 July 2026); M11 analysis."


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / f"{name}.csv")


def note(fig, text: str) -> None:
    fig.text(0.01, 0.01, text, fontsize=7, color=INK["muted"], wrap=True, va="bottom")


def finish(fig, name: str, bottom: float = 0.1) -> None:
    fig.tight_layout(rect=(0, bottom, 1, 1))
    fig.savefig(FIGURES / name, dpi=200)
    plt.close(fig)


def figure_tfr_forecast() -> None:
    tfr = hfd.read_hfd("USAtfrRR")
    fc = table("m11_fc_tfr_forecast")
    check = table("m11_fc_check_2025").set_index("quantity")
    census = table("m11_fc_census_tfr_comparison")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1.5, 1]})
    for ax, start in zip(axes, (1930, 2000)):
        ax.fill_between(fc["year"], fc["lower95"], fc["upper95"], color=BLUE, alpha=0.12, linewidth=0,
                        label="95% historical-error interval (nominal; failed calibration check)")
        ax.fill_between(fc["year"], fc["lower80"], fc["upper80"], color=BLUE, alpha=0.22, linewidth=0,
                        label="80% historical-error interval (nominal; failed calibration check)")
        ax.plot(fc["year"], fc["sens1977_lower80"], color=ORANGE, linewidth=1, linestyle=":")
        ax.plot(fc["year"], fc["sens1977_upper80"], color=ORANGE, linewidth=1, linestyle=":",
                label="80% interval from origins 1977+ errors (sensitivity; under-covers)")
        ax.plot(tfr["Year"], tfr["TFR"], color=BLUE, linewidth=2, label="Observed HFD period TFR, 1933-2024")
        ax.plot(fc["year"], fc["forecast"], color=BLUE, linewidth=2, linestyle="--",
                label="Forecast 2025-2040: no change (baseline retained)")
        ax.plot(census["year"], census["census_assumed_tfr_projection_year"], color=YELLOW, linewidth=1.5,
                linestyle="--", label="Census 2023 assumption (July-June years; comparison only)")
        recon = check.loc["reconstructed 2025, E2_ratio_2024", "value"]
        ax.plot([2025], [recon], marker="D", markersize=6, color=AQUA, markerfacecolor=INK["surface"],
                markeredgewidth=2, linestyle="none", label="2025 reconstructed from NCHS + Census (not HFD)")
        ax.axvline(2024.5, color=INK["axis"], linewidth=0.8)
        ax.set_xlim(start, 2041)
        ax.set_ylabel("Births per woman (period TFR)")
    axes[0].set_ylim(0.7, 3.9)
    axes[1].set_ylim(0.7, 3.2)
    axes[0].set_title("A. U.S. period TFR, observed and forecast")
    axes[1].set_title("B. Detail, 2000-2040")
    axes[0].legend(loc="upper right", fontsize=7, frameon=False)
    note(fig, SOURCE + " No alternative model satisfied the prespecified criteria for replacing the no-change baseline. Intervals use historical forecast errors (origins 1952-2008) and are not "
         "calibrated: in pseudo-real-time tests the 80% intervals covered 96% of outcomes, and the 1977+ version "
         "covered far fewer than 80% at long horizons. They are not validated probability statements.")
    finish(fig, "m11_fc_tfr_forecast.png", 0.08)


def figure_backtest() -> None:
    windows = table("m11_fc_rob_training_windows")
    order = ["naive", "ses", "ari", "converge30", "holt_damped", "drift10_damped", "mean10", "drift10", "ar_level"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, training, title in zip(axes, ["expanding_1933 (primary)", "expanding_1977"],
                                   ["A. Primary backtest: origins 1952-2023, training from 1933",
                                    "B. Sensitivity: training from 1977 (origins: 24, 19, 14)"]):
        sub = windows[windows["training"] == training]
        for offset, (h, color) in zip((-0.2, 0, 0.2), [(5, BLUE), (10, ORANGE), (15, AQUA)]):
            vals = sub[sub["h"] == h].set_index("method").reindex(order)
            ax.plot(vals["relative_mae"], np.arange(len(order)) + offset, marker="o", markersize=6, linestyle="none",
                    color=color, label=f"{h}-year horizon (origins: {int(vals['origins'].iloc[0])})")
        ax.axvline(1.0, color=INK["secondary"], linewidth=1)
        ax.axvline(0.9, color=INK["secondary"], linewidth=0.8, linestyle="--")
        ax.set_xscale("log")
        ax.set_xticks([0.6, 0.8, 1, 1.25, 1.6, 2.0])
        ax.set_xticklabels(["0.6", "0.8", "1", "1.25", "1.6", "2.0"])
        ax.set_xlabel("MAE relative to no change (lower is better; dashed = 0.90 threshold)")
        ax.set_title(title, fontsize=10)
    axes[0].set_yticks(range(len(order)))
    axes[0].set_yticklabels(order)
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=7, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 0.06), ncol=3)
    note(fig, SOURCE + " TFR forecast errors on the TFR scale. Overlapping origins: at 15 years the primary backtest "
         "has 4 non-overlapping windows; panel B has 1. 'ses' coincides with no change (smoothing weight at its bound).")
    finish(fig, "m11_fc_backtest_relative_mae.png", 0.13)


def figure_calibration() -> None:
    calib = table("m11_fc_interval_calibration")
    late = table("m11_fc_rob_interval_calibration_1977")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, level in zip(axes, (80, 95)):
        lines = [(calib[(calib["interval"] == "historical_error") & (calib["method"] == "naive")], BLUE,
                  "Empirical spread, errors from origins since 1952 (primary method)"),
                 (late[late["method"] == "naive"], ORANGE, "Empirical spread, errors from origins since 1977"),
                 (calib[(calib["interval"] == "model_based") & (calib["method"] == "naive")], AQUA,
                  "Model-based random-walk spread")]
        for frame, color, label in lines:
            ax.plot(frame["h"], frame[f"coverage{level}"], color=color, marker="o", markersize=4, linewidth=1.8,
                    label=label)
        ax.axhline(level / 100, color=INK["secondary"], linewidth=1, linestyle="--")
        ax.set_title(f"{'AB'[level == 95]}. {level}% intervals: share of outcomes inside", fontsize=10)
        ax.set_xlabel("Forecast horizon (years)")
        ax.set_ylim(-0.02, 1.05)
    axes[0].set_ylabel("Empirical coverage (pseudo-real time)")
    axes[0].legend(fontsize=7, frameon=False, loc="lower left")
    note(fig, SOURCE + " No-change forecasts; each interval uses only errors observable at its origin (at least 10). "
         "Dashed line = nominal coverage. Points at long horizons rest on few independent windows.")
    finish(fig, "m11_fc_interval_calibration.png", 0.08)


def figure_asfr() -> None:
    obs = table("m11_fc_asfr_observed_1995_2024")
    fc = table("m11_fc_asfr_forecast")
    mab = table("m11_fc_mean_age_by_shape_method")
    mab_obs = hfd.read_hfd("USAmabRR")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    ax = axes[0]
    for year, color in [(1995, INK["muted"]), (2010, ORANGE), (2024, BLUE)]:
        s = obs[obs["year"] == year]
        ax.plot(s["age"], s["asfr"] * 1000, color=color, linewidth=2, label=f"Observed {year}")
    s = fc[fc["year"] == 2040]
    ax.fill_between(s["age"], s["asfr_lower80_tfr_driven"] * 1000, s["asfr_upper80_tfr_driven"] * 1000, color=BLUE,
                    alpha=0.15, linewidth=0, label="2040, at nominal 80% TFR interval bounds (not calibrated)")
    ax.plot(s["age"], s["asfr"] * 1000, color=BLUE, marker="o", markersize=5, markevery=2, linestyle="none",
            markerfacecolor=INK["surface"], markeredgewidth=1.5,
            label="Projected 2040: identical to 2024 (no change x fixed shape)")
    ax.set_xlabel("Age in completed years")
    ax.set_ylabel("Births per 1,000 women")
    ax.set_title("A. Age-specific fertility rates", fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    ax = axes[1]
    ax.plot(mab_obs["Year"], mab_obs["MAB"], color=BLUE, linewidth=2, label="Observed (HFD)")
    styles = [("S0_fixed", BLUE, "Fixed 2024 shape (selected)"), ("S1_shape_drift", ORANGE, "Shape trend, drift"),
              ("S2_shape_damped", AQUA, "Shape trend, damped"), ("S3_direct_ets", YELLOW, "Direct per-age smoothing")]
    for col, color, label in styles:
        ax.plot(mab["year"], mab[col], color=color, linewidth=1.8, linestyle="--", label=label)
    ax.set_xlim(1980, 2041)
    ax.set_ylim(25, 32.5)
    ax.set_ylabel("Mean age at birth (years)")
    ax.set_title("B. Mean age at birth: observed and model-dependent projections", fontsize=10)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    note(fig, SOURCE + " Projected rates = TFR forecast x age shape, so they sum exactly to the TFR. Alternative "
         "shapes are sensitivity projections, not probability intervals (Lee-Carter matches the drift path).")
    finish(fig, "m11_fc_age_profiles.png", 0.08)


def figure_genz() -> None:
    traj = table("m11_fc_genz_trajectories")
    vv = hfd.vv_frame()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    for cohort in (1975, 1985):
        rows = vv[vv["Cohort"] == cohort].sort_values("Year")
        ax.plot(rows["ARDY"], rows["ASFR"].cumsum(), color=INK["axis"], linewidth=1.5)
        ax.text(rows["ARDY"].iloc[-1] + 0.6, rows["ASFR"].cumsum().iloc[-1], f"{cohort}\n(observed)", fontsize=7,
                color=INK["muted"], va="center")
    for cohort, color in [(1995, BLUE), (2000, ORANGE), (2005, AQUA), (2010, YELLOW)]:
        rows = traj[traj["cohort"] == cohort]
        o, p = rows[rows["segment"] == "observed"], rows[rows["segment"] == "projected"]
        ax.plot(o["ardy"], o["cumulative"], color=color, linewidth=2.2, label=f"{cohort}")
        joined = pd.concat([o.tail(1), p])
        ax.plot(joined["ardy"], joined["cumulative"], color=color, linewidth=2, linestyle="--")
        ax.fill_between(p["ardy"], p["lower80"], p["upper80"], color=color, alpha=0.15, linewidth=0)
    ax.set_xlabel("Age reached during the year")
    ax.set_ylabel("Cumulative births per woman, by 31 December")
    ax.set_title("A. Cohort trajectories: solid observed to 2024, dashed projected to 2040", fontsize=10)
    ax.set_xlim(12, 54)
    ax.legend(title="Birth cohort", fontsize=7, title_fontsize=7, frameon=False, loc="upper left")
    ax = axes[1]
    ends = table("m11_fc_genz_endpoints_2040")
    y = ends["cohort"]
    ax.hlines(y, ends["lower95"], ends["upper95"], color=BLUE, alpha=0.35, linewidth=2, label="95% historical-error interval")
    ax.hlines(y, ends["lower80"], ends["upper80"], color=BLUE, linewidth=4, alpha=0.6, label="80% historical-error interval")
    ax.plot(ends["projected_2040"], y, marker="o", markerfacecolor=INK["surface"], markeredgecolor=BLUE,
            markeredgewidth=1.8, linestyle="none", label="Projected by end of 2040")
    ax.plot(ends["observed_2024"], y, marker="o", color=INK["secondary"], markersize=4, linestyle="none",
            label="Observed by end of 2024")
    for _, row in ends.iterrows():
        tag = {"nearly complete by historical standards": "near-complete", "substantial but incomplete": "incomplete",
               "partial": "partial"}[row["completion_label"]]
        ax.text(2.55, row["cohort"], f"age {int(row['age_reached_2040'])}, {tag}", fontsize=6.5,
                color=INK["secondary"], va="center")
    ax.set_xlim(0, 3.4)
    ax.invert_yaxis()
    ax.set_yticks(list(range(1995, 2013)))
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlabel("Cumulative births per woman")
    ax.set_title("B. Gen Z cohorts by the end of 2040", fontsize=10)
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.13), ncol=4)
    note(fig, SOURCE + " Cohort sums of HFD vertical-parallelogram rates; projections convert forecast period rates to "
         "cohorts by Lexis triangles. Bands are nominal intervals from 1952-2008 pseudo-cohort backtest errors, not "
         "calibrated (80% bands covered 78-96% of outcomes by horizon). Fertility by 2040 is not completed fertility "
         "and says nothing about any individual woman.")
    finish(fig, "m11_fc_genz_cohorts.png", 0.09)


def figure_births() -> None:
    births = table("m11_fc_census_births")
    observed = hfd.read_hfd("USAtotbirthsRR")
    observed = observed[observed["Year"] >= 2000]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(observed["Year"], observed["Total"] / 1e6, color=INK["primary"], linewidth=2, label="Observed births (HFD)")
    mid = births[births["scenario"] == "mid"]
    ax.fill_between(mid["year"], mid["fertility_lower80"] / 1e6, mid["fertility_upper80"] / 1e6, color=BLUE,
                    alpha=0.15, linewidth=0, label="Main series: births at nominal 80% TFR interval bounds (fertility only; not calibrated)")
    for scenario, color, label in [("mid", BLUE, "Main immigration series"), ("hi", ORANGE, "High immigration"),
                                   ("low", AQUA, "Low immigration"), ("zero", YELLOW, "Zero immigration")]:
        s = births[births["scenario"] == scenario]
        ax.plot(s["year"], s["births"] / 1e6, color=color, linewidth=2, linestyle="--",
                label=f"{label} (scenario, no-change fertility)")
    ax.set_ylabel("Births per calendar year (millions)")
    ax.set_xlim(2000, 2041)
    ax.set_ylim(1.8, 5.8)
    ax.set_title("Births under Census 2023 immigration scenarios, female population rebased to vintage 2025")
    ax.legend(fontsize=7, frameon=False, loc="upper left", ncol=2)
    note(fig, SOURCE + " Population: Census 2023 projections (July 1), rebased by cohort to vintage 2025 estimates. "
         "Scenario lines are not probabilities; the shaded band shows fertility uncertainty only.")
    finish(fig, "m11_fc_births_scenarios.png", 0.08)


def figure_sensitivity() -> None:
    by_method = table("m11_fc_rob_2040_by_method_and_window")
    origins = table("m11_fc_rob_origin_sensitivity")
    fc = table("m11_fc_tfr_forecast").set_index("year").loc[2040]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.3, 1]})
    ax = axes[0]
    order = list(by_method.groupby("method")["tfr_2040"].mean().sort_values().index)
    ax.axvspan(fc["lower80"], fc["upper80"], color=BLUE, alpha=0.1, linewidth=0, label="Primary nominal 80% interval (not calibrated)")
    for offset, (training, color) in zip((-0.2, 0, 0.2), [("expanding_1933 (primary)", BLUE),
                                                           ("expanding_1977", ORANGE), ("rolling_30", AQUA)]):
        s = by_method[by_method["training"] == training].set_index("method").reindex(order)
        ax.plot(s["tfr_2040"], np.arange(len(order)) + offset, marker="o", linestyle="none", color=color,
                markerfacecolor=INK["surface"], markeredgewidth=1.8, label=f"Training: {training}")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order)
    ax.set_xlabel("Projected TFR in 2040")
    ax.set_title("A. 2040 TFR by method and training window", fontsize=10)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax = axes[1]
    ax.plot(origins["origin"], origins["tfr_2040"], marker="o", markerfacecolor=INK["surface"], color=BLUE,
            linewidth=1.8, label="2040 forecast made at each origin (no change)")
    ax.set_xlabel("Forecast origin (last observed year)")
    ax.set_ylabel("Projected TFR in 2040")
    ax.set_title("B. Sensitivity to the jump-off year", fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    note(fig, SOURCE + " Model-dependent projections, not probability intervals. No alternative model satisfied the prespecified criteria for replacing the no-change baseline.")
    finish(fig, "m11_fc_sensitivity.png", 0.08)


FIGURE_FUNCTIONS = [figure_tfr_forecast, figure_backtest, figure_calibration, figure_asfr, figure_genz,
                    figure_births, figure_sensitivity]


def main() -> int:
    apply_figure_style()
    FIGURES.mkdir(parents=True, exist_ok=True)
    for draw in FIGURE_FUNCTIONS:
        draw()
    print(f"{len(FIGURE_FUNCTIONS)} figures written to {FIGURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
