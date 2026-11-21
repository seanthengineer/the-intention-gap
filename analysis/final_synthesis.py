"""Final synthesis: collated evidence tables and integrated figures.

Reads only the frozen aggregate outputs of M01-M11 in data/public/. Nothing is
re-estimated: every value is copied from a frozen table, with its source file
and locator, so the synthesis can be traced back to the chapter that produced it.

    python -m analysis.final_synthesis
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

from analysis.analyze_calibration import INK, apply_figure_style  # noqa: E402
from analysis.nlsy97 import PROJECT_ROOT  # noqa: E402

PUBLIC = PROJECT_ROOT / "data" / "public"
OUT = PUBLIC / "final"
FIGURES = PROJECT_ROOT / "assets" / "figures"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GENZ = (1995, 2012)

DASHBOARD = "data/public/dashboard_summary.json"
NSFG = "data/public/nsfg_m09/estimates.csv"
M10_PRIMARY = "data/public/m10/m10_primary.csv"
M10_ROBUST = "data/public/m10/m10_robustness.csv"
M11_SUMMARY = "data/public/m11/forecast/m11_fc_summary.json"
M11_GENZ = "data/public/m11/forecast/m11_fc_genz_endpoints_2040.csv"
M11_BIRTHS = "data/public/m11/forecast/m11_fc_census_births.csv"

NLSY = "women in the NLSY97 analytical cohort (born 1980-84), unweighted"
NSFG_POP = "U.S. household population aged 18-26 (2022) / 18-27 (2023), weighted"
NSFG_WANT = "same population, among those who want a(nother) child, weighted"
M10_POP = "51 state jurisdictions x years; state birth rates per 1,000 women"
M11_POP = "U.S. female population (HFD), period and cohort rates"


def birth_cohort_bounds(windows) -> tuple[int, int]:
    """Earliest and latest birth year of people aged low..high (completed years) in each interview year."""
    for year, low, high in windows:
        if low > high:
            raise ValueError(f"age window {low}-{high} in {year} is inverted")
    return (min(year - high - 1 for year, _, high in windows), max(year - low for year, low, _ in windows))


def _cohorts(windows, note: str) -> str:
    first, last = birth_cohort_bounds(windows)
    return f"{first}-{last} ({note})"


def population_map() -> pd.DataFrame:
    """Who each chapter observes, when, and what kind of quantity it estimates."""
    rows = [
        {"chapter": "M01-M08", "data_source": "NLSY97 public-use extracts (BLS)",
         "design": "longitudinal panel; baselines 2009-10 and 2015-16, outcomes to 2017 and 2023",
         "unit": "individual women", "observation_years": "2009-2023", "ages": "24.8-30.2 at 2009-10 baseline",
         "birth_cohorts": "1980-1984 (sample design)", "genz_overlap": "none",
         "measures": "stated percent chance of a birth within five years; observed five-year births",
         "estimand_types": "stated expectation; observed fertility outcome; model prediction (recalibration)",
         "inference": "unweighted sample-level; household bootstrap; design-based SEs for baselines only"},
        {"chapter": "M09", "data_source": "NSFG 2022-2023 public-use files (CDC/NCHS)",
         "design": "cross-sectional household survey, one interview",
         "unit": "individual women and men", "observation_years": "2022-2023",
         "ages": "18-26 (2022) / 18-27 (2023), conservative proxy",
         "birth_cohorts": _cohorts([(2022, 18, 26), (2023, 18, 27)], "bounded by age proxy; no birth year"),
         "genz_overlap": "older Gen Z only",
         "measures": "wanting a(nother) child; intending one; expected additional births; parity",
         "estimand_types": "stated desire (yes/no); stated intention; stated expectation (births); observed parity",
         "inference": "design-based (Taylor linearization, 20 strata, 80 clusters)"},
        {"chapter": "M10", "data_source": "Census ACS 1-year; CDC WONDER natality; NVSR",
         "design": "state-year panel, two-way fixed effects", "unit": "state x year x age group",
         "observation_years": "2014-2019, 2021-2024",
         "ages": "women 20-24 and 25-29",
         "birth_cohorts": _cohorts([(y, 20, 29) for y in (2014, 2024)], "different cohorts each year"),
         "genz_overlap": "ages 20-24 in 2021-2024 were born " + "{}-{}".format(
             *birth_cohort_bounds([(y, 20, 24) for y in range(2021, 2025)])),
         "measures": "renter cost burden (30%+); births per 1,000 women",
         "estimand_types": "ecological association (not causal)",
         "inference": "CR1 clustered by state (51 clusters), t(50); wild cluster bootstrap"},
        {"chapter": "M11", "data_source": "Human Fertility Database (USA); NCHS 2025; Census estimates and NP2023",
         "design": "period and cohort rate series 1933-2024; forecasts to 2040",
         "unit": "national aggregate rates", "observation_years": "1933-2024 observed; 2025-2040 projected",
         "ages": "12-55", "birth_cohorts": "1995-2012 (owner's Gen Z definition)",
         "genz_overlap": "all Gen Z cohorts, partly observed",
         "measures": "period TFR; age-specific rates; cohort cumulative fertility; births",
         "estimand_types": "model prediction (no-change forecast); projected partial cohort fertility; scenario",
         "inference": "historical-error intervals (nominal; failed calibration); scenario ranges"},
    ]
    return pd.DataFrame(rows)


def _json_value(path: str, keys):
    value = json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))
    for key in keys:
        if isinstance(key, tuple):
            value = next(item for item in value if str(item[key[0]]) == key[1])
        else:
            value = value[key]
    return value


def _csv_row(path: str, **filters) -> pd.Series:
    frame = pd.read_csv(PROJECT_ROOT / path)
    mask = np.ones(len(frame), dtype=bool)
    for column, wanted in filters.items():
        mask &= frame[column].astype(str).eq(str(wanted)).to_numpy()
    if mask.sum() != 1:
        raise ValueError(f"{path}: {filters} matched {int(mask.sum())} rows")
    return frame[mask].iloc[0]


def _row(id_, chapter, quantity, estimand, population, period, estimate, lower, upper, utype, source, locator,
         source_scale=1.0):
    return {"id": id_, "chapter": chapter, "quantity": quantity, "estimand_type": estimand,
            "population": population, "period": period, "estimate": estimate, "lower": lower,
            "upper": upper, "uncertainty_type": utype, "source_file": source, "locator": locator,
            "source_scale": source_scale}


def evidence_table() -> pd.DataFrame:
    """Headline estimates of every chapter, copied from frozen outputs with their estimand and uncertainty type."""
    rows = []
    cal = {c["range_pct"]: c for c in _json_value(DASHBOARD, ["calibration"])}
    for pct in ("0", "50", "100"):
        c = cal[pct]
        rows.append(_row(f"M01.observed_at_{pct}", "M01-M08", f"birth within five years after stating {pct}%",
                         "observed fertility outcome", NLSY, "2009-10 baseline, births to 2014-15",
                         c["observed_pct"] / 100, c["ci_low_pct"] / 100, c["ci_high_pct"] / 100,
                         "Wilson 95% CI", DASHBOARD, f"json:calibration[range_pct={pct}].observed_pct", 0.01))
    primary = _json_value(DASHBOARD, ["sensitivity", 0])
    rows.append(_row("M01.slope", "M01-M08", "linear calibration slope of outcome on stated chance",
                     "stated expectation evaluated against observed outcome", NLSY, "2009-10 baseline",
                     primary["slope"], primary["slope_ci"][0], primary["slope_ci"][1], "household bootstrap 95% CI", DASHBOARD,
                     "json:sensitivity[0].slope"))
    stated = _json_value(DASHBOARD, ["stated_forecast"])
    rows.append(_row("M01.auc", "M01-M08", "ROC AUC of stated chance", "stated expectation evaluated against observed outcome",
                     NLSY, "2009-10 baseline", stated["auc"], stated["auc_ci"][0], stated["auc_ci"][1], "household bootstrap 95% CI",
                     DASHBOARD, "json:stated_forecast.auc"))
    diff = next(d for d in _json_value(DASHBOARD, ["held_out", "differences"]) if d["comparison"] == "C - B")
    rows.append(_row("M01.recalibration_gain", "M01-M08", "held-out Brier difference, recalibrated minus stated (C - B)",
                     "model prediction (recalibration)", "852 held-out women in 754 households", "2009-10 baseline",
                     diff["mean"], diff["ci"][0], diff["ci"][1], "paired household bootstrap 95% CI", DASHBOARD,
                     "json:held_out.differences[comparison=C - B].mean"))
    nsfg_rows = [("wants", "wants a(nother) child", "stated desire (yes/no)", NSFG_POP),
                 ("intends", "intends a(nother) birth", "stated intention", NSFG_POP),
                 ("divergence_among_wanters", "does not intend one (INTENT = 2)", "stated intention", NSFG_WANT),
                 ("explicit_among_wanters", "explicit 'no' intention", "stated intention", NSFG_WANT),
                 ("sterility_among_wanters", "not intending because respondent or partner sterile",
                  "stated intention (sterility-linked)", NSFG_WANT)]
    names = {"wants": "M09.wants", "intends": "M09.intends", "divergence_among_wanters": "M09.divergence",
             "explicit_among_wanters": "M09.explicit_no", "sterility_among_wanters": "M09.sterility_linked"}
    for measure, quantity, estimand, population in nsfg_rows:
        r = _csv_row(NSFG, cohort="conservative", population="all", measure=measure)
        rows.append(_row(names[measure], "M09", quantity, estimand, population, "2022-2023", r["estimate"],
                         r["ci_low"], r["ci_high"], "design-based Korn-Graubard 95% CI", NSFG,
                         f"csv:cohort=conservative;population=all;measure={measure}|estimate"))
    r = _csv_row(NSFG, cohort="conservative", population="female", measure="expected_total")
    rows.append(_row("M09.expected_total_women", "M09", "children so far plus expected additional births (women)",
                     "stated expectation (births); not a desire", NSFG_POP.replace("population", "women"),
                     "2022-2023", r["estimate"], r["ci_low"], r["ci_high"], "design-based t 95% CI", NSFG,
                     "csv:cohort=conservative;population=female;measure=expected_total|estimate"))
    for id_, age, label in (("M10.primary_20_24", "20-24", "primary"), ("M10.secondary_25_29", "25-29", "secondary")):
        r = _csv_row(M10_PRIMARY, age_group=age, role=label)
        rows.append(_row(id_, "M10", f"births per 1,000 women {age} per 10-point higher 30%+ rent burden",
                         "ecological association (not causal)", M10_POP, "2014-2019, 2021-2024",
                         r["estimate_per10"], r["ci_low"], r["ci_high"], "CR1 state-clustered 95% CI, t(50)",
                         M10_PRIMARY, f"csv:age_group={age};role={label}|estimate_per10"))
    r = _csv_row(M10_ROBUST, age_group="20-24", analysis="period", variant="2021-2024")
    rows.append(_row("M10.recent_20_24", "M10", "births per 1,000 women 20-24 per 10 points, 2021-2024 only",
                     "ecological association (not causal)", M10_POP, "2021-2024", r["estimate_per10"],
                     r["ci_low"], r["ci_high"], "CR1 state-clustered 95% CI, t(50)", M10_ROBUST,
                     "csv:age_group=20-24;analysis=period;variant=2021-2024|estimate_per10"))
    tfr = _json_value(M11_SUMMARY, ["tfr_2040"])
    for level in ("80", "95"):
        rows.append(_row(f"M11.tfr_2040_{level}" if level == "95" else "M11.tfr_2040", "M11",
                         "period total fertility rate in 2040 (no-change forecast)",
                         "model prediction (no-change forecast)", M11_POP, "2040", tfr["forecast"],
                         tfr[f"lower{level}"], tfr[f"upper{level}"],
                         f"nominal {level}% historical-error interval; failed calibration criterion",
                         M11_SUMMARY, "json:tfr_2040.forecast"))
    for cohort in (1995, 2002, 2008, 2012):
        r = _csv_row(M11_GENZ, cohort=cohort)
        rows.append(_row(f"M11.genz_{cohort}", "M11",
                         f"cumulative births per woman born {cohort} by end-2040 (age {int(r['age_reached_2040'])})",
                         f"projected partial cohort fertility ({r['completion_label']})", M11_POP,
                         "observed to 2024; 2024 period rates held to 2040", r["projected_2040"], r["lower80"],
                         r["upper80"], "nominal 80% historical-error interval; not calibrated", M11_GENZ,
                         f"csv:cohort={cohort}|projected_2040"))
    mid = _csv_row(M11_BIRTHS, scenario="mid", year=2040)
    low = _csv_row(M11_BIRTHS, scenario="zero", year=2040)
    high = _csv_row(M11_BIRTHS, scenario="hi", year=2040)
    rows.append(_row("M11.births_2040", "M11", "births in 2040, main immigration series, no-change fertility",
                     "scenario-conditional projection", M11_POP, "2040", mid["births"], low["births"],
                     high["births"], "scenario range across immigration series (zero to high); not a probability",
                     M11_BIRTHS, "csv:scenario=mid;year=2040|births"))
    return pd.DataFrame(rows)


def _lexis_polygon(years, ages):
    (y0, y1), (a0, a1) = years, ages
    return [(y0, y0 - a1 - 0.5), (y0, y0 - a0 - 0.5), (y1 + 1, y1 + 1 - a0 - 0.5), (y1 + 1, y1 + 1 - a1 - 0.5)]


def figure_evidence_map() -> None:
    """Calendar year by birth cohort: which people each chapter observes or projects."""
    fig, ax = plt.subplots(figsize=(10, 6.2))
    ax.axhspan(GENZ[0] - 0.5, GENZ[1] + 0.5, color=INK["grid"], alpha=0.55, linewidth=0, zorder=0)
    ax.text(1995.3, 2011.6, "Gen Z cohorts 1995-2012 (owner's definition)", fontsize=8.5, color=INK["secondary"],
            va="top")
    for age in (20, 30, 45):
        xs = np.array([1995, 2042])
        ax.plot(xs, xs - age, color=INK["axis"], linewidth=0.8, linestyle=":", zorder=1)
        ax.text(1978.3 + age, 1978.3, f"age {age}", fontsize=7.5, color=INK["muted"], rotation=33)
    ax.add_patch(Rectangle((2009, 1979.5), 15, 5, facecolor=BLUE, alpha=0.35, edgecolor=BLUE, zorder=2))
    ax.text(2016.5, 1982, "M01-M08 NLSY97: women born 1980-84,\nexpectations 2009-10 and 2015-16, births to 2023",
            fontsize=8, color=INK["primary"], ha="center", va="center", zorder=5)
    ax.add_patch(Polygon(_lexis_polygon((2014, 2024), (20, 29)), closed=True, facecolor=ORANGE, alpha=0.22,
                         edgecolor=ORANGE, zorder=2))
    ax.add_patch(Polygon(_lexis_polygon((2021, 2024), (20, 24)), closed=True, facecolor=ORANGE, alpha=0.45,
                         edgecolor=ORANGE, zorder=3))
    ax.text(2013.6, 1990.5, "M10: state birth rates, ages 20-29,\n2014-2024 (darker: ages 20-24, 2021-24)",
            fontsize=8, color=INK["primary"], ha="right", va="center")
    ax.add_patch(Rectangle((2022, 1994.5), 2, 11, facecolor=AQUA, alpha=0.55, edgecolor=AQUA, zorder=4))
    ax.text(2017.0, 2005.9, "M09 NSFG 2022-23: one interview,\nages 18-27 (born 1995-2005)", fontsize=8,
            color=INK["primary"], va="bottom")
    ax.add_patch(Rectangle((2025, 1994.5), 16, 18, facecolor="none", edgecolor=YELLOW, hatch="///",
                           linewidth=1.2, zorder=2))
    ax.text(2025.4, 1993.2, "M11: Gen Z cumulative fertility projected to end-2040\n(2024 rates held; nearly complete, not completed,\n"
                            "for 1995-2002; partial for cohorts born 2003+)", fontsize=8, color=INK["primary"], va="top")
    ax.set_xlim(1995, 2042)
    ax.set_ylim(1977, 2014)
    ax.set_xlabel("Calendar year")
    ax.set_ylabel("Birth cohort")
    ax.set_title("Who each chapter observes: no chapter follows Gen Z from stated desire to completed fertility",
                 fontsize=10.5, loc="left")
    fig.text(0.01, 0.01, "Shaded areas mark observed data; hatching marks projections. Diagonals mark ages. "
                         "Each chapter's people, units and measures differ, so their numbers cannot be combined.",
             fontsize=7.5, color=INK["muted"])
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIGURES / "final_evidence_map.png", dpi=200)
    plt.close(fig)


def figure_headline_panels(table: pd.DataFrame) -> None:
    """One panel per chapter, each on its own scale; values must not be compared across panels."""
    t = table.set_index("id")
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.2))
    ax = axes[0, 0]
    cal = _json_value(DASHBOARD, ["calibration"])
    stated = np.array([c["mean_stated_pct"] for c in cal])
    observed = np.array([c["observed_pct"] for c in cal])
    err = np.array([[c["observed_pct"] - c["ci_low_pct"] for c in cal], [c["ci_high_pct"] - c["observed_pct"] for c in cal]])
    ax.plot([0, 100], [0, 100], color=INK["axis"], linewidth=1, linestyle="--", label="perfect calibration")
    ax.errorbar(stated, observed, yerr=err, fmt="o", color=BLUE, markersize=5, capsize=0, linewidth=1.2,
                label="observed birth rate (Wilson 95% CI)")
    ax.set_xlabel("Stated chance of a birth within five years (%)")
    ax.set_ylabel("Women with a birth within five years (%)")
    ax.set_title("M01-M08 NLSY97, born 1980-84: stated chance vs births\n(observed outcome, unweighted sample)",
                 fontsize=9, loc="left")
    ax.legend(fontsize=7.5, frameon=False, loc="upper left")
    ax = axes[0, 1]
    labels = ["Wants a(nother) child", "Intends a(nother) birth", "Does not intend (of wanters)",
              "  explicit 'no' (of wanters)", "  sterility-linked (of wanters)"]
    ids = ["M09.wants", "M09.intends", "M09.divergence", "M09.explicit_no", "M09.sterility_linked"]
    ys = np.arange(len(ids))[::-1]
    for y, id_ in zip(ys, ids):
        r = t.loc[id_]
        colour = BLUE if y >= 3 else ORANGE
        ax.plot([100 * r["lower"], 100 * r["upper"]], [y, y], color=colour, linewidth=2)
        ax.plot(100 * r["estimate"], y, "o", color=colour, markersize=6)
        ax.text(100 * r["upper"] + 1.5, y, f"{100 * r['estimate']:.1f}%", va="center", fontsize=8,
                color=INK["primary"])
    ax.set_yticks(ys, labels, fontsize=8)
    ax.set_xlim(0, 85)
    ax.set_xlabel("Weighted percent (95% CI)")
    ax.set_title("M09 NSFG 2022-23, ages 18-27: stated desire and intention\n(answers at one interview, not outcomes)",
                 fontsize=9, loc="left")
    ax = axes[1, 0]
    ids = ["M10.primary_20_24", "M10.secondary_25_29", "M10.recent_20_24"]
    labels = ["Ages 20-24, 2014-24 (primary)", "Ages 25-29, 2014-24", "Ages 20-24, 2021-24 only"]
    ys = np.arange(len(ids))[::-1]
    ax.axvline(0, color=INK["axis"], linewidth=1)
    for y, id_ in zip(ys, ids):
        r = t.loc[id_]
        ax.plot([r["lower"], r["upper"]], [y, y], color=ORANGE, linewidth=2)
        ax.plot(r["estimate"], y, "o", color=ORANGE, markersize=6)
        ax.text(r["upper"] + 0.2, y, f"{r['estimate']:.2f}", va="center", fontsize=8, color=INK["primary"])
    ax.set_yticks(ys, labels, fontsize=8)
    ax.set_xlim(-7, 4.5)
    ax.set_xlabel("Births per 1,000 women per 10-point higher rent burden (95% CI)")
    ax.set_title("M10 states 2014-24: rent burden and birth rates\n(ecological association, not causal)",
                 fontsize=9, loc="left")
    ax = axes[1, 1]
    genz = pd.read_csv(PROJECT_ROOT / M11_GENZ)
    styles = {"nearly complete by historical standards": (BLUE, "o"), "substantial but incomplete": (YELLOW, "s"),
              "partial": (ORANGE, "D")}
    for label, (colour, marker) in styles.items():
        sub = genz[genz["completion_label"] == label]
        ax.vlines(sub["cohort"], sub["lower80"], sub["upper80"], color=colour, linewidth=1.6)
        ax.plot(sub["cohort"], sub["projected_2040"], marker, color=colour, markersize=5, linestyle="none",
                markerfacecolor="white", label=f"projected by end-2040: {label}")
    ax.plot(genz["cohort"], genz["observed_2024"], "o", color=INK["secondary"], markersize=3.5,
            label="observed by end-2024")
    ax.set_xticks(range(1995, 2013, 3))
    ax.set_xlabel("Birth cohort")
    ax.set_ylabel("Cumulative births per woman")
    ax.set_ylim(0, 2.6)
    ax.set_title("M11 Gen Z cohorts: births per woman by end-2040 if 2024\nrates persist (projection; bars = nominal 80% "
                 "historical-\nerror interval, not calibrated)", fontsize=9, loc="left")
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    fig.text(0.01, 0.01, "Each panel has its own population, unit and estimand (observed outcome, stated answer, "
                         "ecological association, projection). Values are not comparable across panels and must "
                         "not be differenced.", fontsize=7.5, color=INK["muted"])
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIGURES / "final_headline_panels.png", dpi=200)
    plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    table = evidence_table()
    table.to_csv(OUT / "final_evidence_table.csv", index=False, float_format="%.10g", lineterminator="\n")
    population_map().to_csv(OUT / "final_population_map.csv", index=False, lineterminator="\n")
    apply_figure_style()
    figure_evidence_map()
    figure_headline_panels(table)
    print(f"Wrote {len(table)} evidence rows, the population map and two figures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
