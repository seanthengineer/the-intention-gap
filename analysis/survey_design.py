"""Survey-design checks, weighted baseline descriptions and selection sensitivity.

Design: NLSY97 variance strata (VSTRAT) and primary sampling units (VPSU),
two PSUs in each of 117 strata, with the round's cross-sectional weight
(SAMPLING_WEIGHT_CC, two implied decimals; 0 = not interviewed).

Variance methods:
- Stratified delete-one-PSU jackknife (JKn): for each PSU, its weights are
  set to 0 and the other PSUs in its stratum are scaled by n_h / (n_h - 1);
  v = sum_h (n_h - 1) / n_h * sum_j (theta_hj - theta)^2. Every statistic,
  including any weight adjustment, is recomputed in each replicate. This
  is the primary method.
- Taylor linearization for weighted means, as a cross-check.
Both treat PSUs as sampled with replacement within strata, use the full
design (a PSU without members of a subgroup still counts), and ignore the
finite-population correction.

DEFT is the jackknife standard error of the weighted estimate divided by
the standard error of a simple random sample of the same size, computed
from the weighted variance of the item. It therefore combines the effects
of unequal weighting, stratification and clustering.

Cross-sectional weights describe that round's respondents (the population
represented by the 1997 sample). They are not longitudinal weights: the
outcome-based results below are sensitivity analyses under stated
assumptions, not design-based population estimates.

Only aggregate results are printed. Nothing is written to disk.

Run from the project root:  python -m analysis.survey_design
"""

from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy import stats

from analysis import analyze_calibration as ac
from analysis import temporal_validation as tv
from analysis.nlsy97 import (
    CHILD_BIRTH_MONTH, EXPECTATION, FEMALE, HOUSEHOLD_ID, INTERVIEW_MONTH, RACE_ETHNICITY,
    RESPONDENT_ID, SEX, WEIGHT_2009, assess_roster,
)

RACE_GROUPS = {1: "Black", 2: "Hispanic", 3: "Other", 4: "Other"}
MIN_CELL = 20
WEIGHT_SUM = 19_378_453     # Table 1, NLSY97 sample weights page (two implied decimals removed)


# ---------------------------------------------------------------- variance

def design_table(strata: np.ndarray, psu: np.ndarray) -> pd.DataFrame:
    """Every (stratum, PSU) pair in the full sample, with the stratum's PSU count."""
    table = pd.DataFrame({"stratum": strata, "psu": psu}).drop_duplicates()
    table["n_h"] = table.groupby("stratum")["psu"].transform("size")
    if (table["n_h"] < 2).any():
        raise ValueError("Every stratum needs at least two PSUs")
    return table.sort_values(["stratum", "psu"]).reset_index(drop=True)


def replicate_factors(strata: np.ndarray, psu: np.ndarray, design: pd.DataFrame):
    """Yield (stratum, n_h, factor array) for each delete-one-PSU replicate."""
    for stratum, psu_id, n_h in design[["stratum", "psu", "n_h"]].itertuples(index=False):
        factor = np.ones(len(strata))
        in_stratum = strata == stratum
        factor[in_stratum] = n_h / (n_h - 1)
        factor[in_stratum & (psu == psu_id)] = 0.0
        yield stratum, n_h, factor


def jackknife(estimator: Callable[[np.ndarray], dict], weights: np.ndarray,
              strata: np.ndarray, psu: np.ndarray, design: pd.DataFrame) -> pd.DataFrame:
    """Point estimates and JKn standard errors for every statistic the estimator returns."""
    point = estimator(weights)
    sums = dict.fromkeys(point, 0.0)
    for _, n_h, factor in replicate_factors(strata, psu, design):
        replicate = estimator(weights * factor)
        for key, value in point.items():
            sums[key] += (n_h - 1) / n_h * (replicate[key] - value) ** 2
    return pd.DataFrame({"estimate": point, "se": {k: np.sqrt(v) for k, v in sums.items()}})


def _mean_scores(y: np.ndarray, weights: np.ndarray,
                 domain: np.ndarray | None) -> tuple[float, np.ndarray]:
    """Weighted domain mean and each unit's linearized score (zero outside the domain)."""
    d = np.ones(len(y), dtype=bool) if domain is None else np.asarray(domain, dtype=bool)
    w = np.where(d, weights, 0.0)
    total = w.sum()
    mean = np.sum(w * np.where(d, y, 0.0)) / total
    return float(mean), w * (np.where(d, y, mean) - mean) / total


def _psu_variance(z: np.ndarray, strata: np.ndarray, psu: np.ndarray,
                  design: pd.DataFrame) -> float:
    """With-replacement variance of summed scores, PSUs within strata, full design."""
    totals = (pd.DataFrame({"stratum": strata, "psu": psu, "z": z})
              .groupby(["stratum", "psu"])["z"].sum())
    totals = design.set_index(["stratum", "psu"]).join(totals.rename("z")).fillna({"z": 0.0})
    centred = totals["z"] - totals.groupby(level="stratum")["z"].transform("mean")
    return float((totals["n_h"] / (totals["n_h"] - 1) * centred ** 2).sum())


def linearized_mean(y: np.ndarray, weights: np.ndarray, strata: np.ndarray, psu: np.ndarray,
                    design: pd.DataFrame, domain: np.ndarray | None = None) -> tuple[float, float]:
    """Weighted domain mean and its Taylor-linearization standard error."""
    mean, z = _mean_scores(y, weights, domain)
    return mean, float(np.sqrt(_psu_variance(z, strata, psu, design)))


def linearized_domain_difference(y: np.ndarray, weights: np.ndarray, strata: np.ndarray,
                                 psu: np.ndarray, design: pd.DataFrame, domain_a: np.ndarray,
                                 domain_b: np.ndarray) -> tuple[float, float]:
    """Difference of two weighted domain means (a - b) and its linearization SE.

    Both domains are scored within one design, so any covariance between
    them through shared PSUs enters the variance.
    """
    mean_a, z_a = _mean_scores(y, weights, domain_a)
    mean_b, z_b = _mean_scores(y, weights, domain_b)
    return mean_a - mean_b, float(np.sqrt(_psu_variance(z_a - z_b, strata, psu, design)))


def linearized_domain_covariance(y: np.ndarray, weights: np.ndarray, strata: np.ndarray,
                                 psu: np.ndarray, design: pd.DataFrame,
                                 domains: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Weighted means of several domains and their linearization covariance matrix.

    The diagonal equals linearized_mean's variance for each domain, and
    var(a) + var(b) - 2 cov(a, b) equals linearized_domain_difference's.
    """
    means, scores = zip(*(_mean_scores(y, weights, domain) for domain in domains))
    frame = pd.DataFrame(np.column_stack(scores))
    frame["stratum"], frame["psu"] = strata, psu
    totals = frame.groupby(["stratum", "psu"]).sum()
    index = pd.MultiIndex.from_frame(design[["stratum", "psu"]])
    totals = totals.reindex(index, fill_value=0.0)
    centred = totals - totals.groupby(level="stratum").transform("mean")
    factor = (design["n_h"] / (design["n_h"] - 1)).to_numpy()
    matrix = centred.to_numpy()
    return np.array(means), (matrix * factor[:, None]).T @ matrix


def adjusted_wald_test(means: np.ndarray, covariance: np.ndarray,
                       df: int) -> tuple[float, int, int, float]:
    """Design-adjusted Wald F test that all domain means are equal.

    F = (df - q + 1) / (df * q) * W on (q, df - q + 1) degrees of freedom,
    with q = number of domains - 1 (Korn and Graubard, 1990).
    """
    q = len(means) - 1
    if q < 1 or df - q + 1 < 1:
        raise ValueError("Need at least two domains and enough design degrees of freedom")
    contrast = np.hstack([np.eye(q), -np.ones((q, 1))])
    difference = contrast @ means
    wald = float(difference @ np.linalg.pinv(contrast @ covariance @ contrast.T) @ difference)
    statistic = (df - q + 1) / (df * q) * wald
    return statistic, q, df - q + 1, float(stats.f.sf(statistic, q, df - q + 1))


def design_degrees_of_freedom(design: pd.DataFrame) -> int:
    """Number of PSUs minus number of strata."""
    return int(len(design) - design["stratum"].nunique())


def srs_se(y: np.ndarray, weights: np.ndarray | None = None) -> float:
    """Standard error of a (weighted) mean if the sample were a simple random sample."""
    w = np.ones(len(y)) if weights is None else weights
    mean = np.average(y, weights=w)
    return float(np.sqrt(np.average((y - mean) ** 2, weights=w) / len(y)))


# ------------------------------------------------------------------ frames

def answer_category(pct: pd.Series) -> pd.Series:
    return tv.answer_category(pct).astype(str)


def baseline_frames() -> tuple[dict[int, pd.DataFrame], pd.DataFrame]:
    """Female round respondents in 2009 and 2015 with design variables, aggregated later.

    Each frame holds women interviewed in that round. 'answered' marks a
    0-100 answer to YFER-4861; parity comes from that round's roster.
    """
    joined, items, missing = tv.load_temporal()
    if missing:
        raise SystemExit(f"Temporal extract incomplete: {missing}")
    strata, psu = joined[items["vstrat"]].to_numpy(), joined[items["vpsu"]].to_numpy()
    design = design_table(strata, psu)
    frames = {}
    for year, weight, expectation in ((2009, WEIGHT_2009, EXPECTATION),
                                      (2015, items["weight"], items["expectation"])):
        women = joined[(joined[SEX] == FEMALE) & (joined[INTERVIEW_MONTH[year]] > 0)]
        rosters = [assess_roster(slots, month) for slots, month in
                   zip(women[CHILD_BIRTH_MONTH[year]].to_numpy(),
                       women[INTERVIEW_MONTH[year]].to_numpy())]
        frames[year] = pd.DataFrame({
            "respondent_id": women[RESPONDENT_ID].to_numpy(),
            "household_id": women[HOUSEHOLD_ID].to_numpy(),
            "weight": women[weight].to_numpy() / 100,
            "stratum": women[items["vstrat"]].to_numpy(),
            "psu": women[items["vpsu"]].to_numpy(),
            "race": women[RACE_ETHNICITY].map(RACE_GROUPS).to_numpy(),
            "answered": women[expectation].between(0, 100).to_numpy(),
            "expectation_pct": women[expectation].where(women[expectation] >= 0).to_numpy(),
            "parity": [r["n_births"] if r["usable"] else np.nan for r in rosters],
        })
    return frames, design


def design_audit(design_frame: pd.DataFrame) -> dict:
    """Aggregate checks of the weights and design variables over all respondents."""
    out = {}
    for year, column in ((2009, "weight_2009"), (2015, "weight_2015")):
        w, interviewed = design_frame[column], design_frame[f"interviewed_{year}"]
        out[year] = {
            "respondents with positive weight": int((w > 0).sum()),
            "zero weight": int((w == 0).sum()),
            "zero weight but interviewed": int(((w == 0) & interviewed).sum()),
            "positive weight but not interviewed": int(((w > 0) & ~interviewed).sum()),
            "negative codes": int((w < 0).sum()),
            "sum of weights": float(w.sum()),
            "smallest / largest positive weight": f"{w[w > 0].min():.2f} / {w.max():.2f}",
            "fewest round respondents in a PSU": int(design_frame[interviewed].groupby(
                ["stratum", "psu"]).size().min()),
        }
    return out


# ------------------------------------------------------ baseline description

def description_estimator(frame: pd.DataFrame) -> Callable[[np.ndarray], dict]:
    answered = frame["answered"].to_numpy()
    pct = frame["expectation_pct"].fillna(0).to_numpy()
    known_parity = answered & frame["parity"].notna().to_numpy()
    childless = known_parity & (frame["parity"].to_numpy() == 0)
    mothers = known_parity & (frame["parity"].to_numpy() >= 1)
    race = frame["race"].to_numpy()

    def mean(values, mask, w):
        return np.sum(w[mask] * values[mask]) / np.sum(w[mask])

    def estimator(w: np.ndarray) -> dict:
        return {
            "item nonresponse (%)": 100 * mean(~answered, np.ones(len(w), bool), w),
            "mean stated chance (%)": mean(pct, answered, w),
            "answered 0% (%)": 100 * mean(pct == 0, answered, w),
            "answered 50% (%)": 100 * mean(pct == 50, answered, w),
            "answered 100% (%)": 100 * mean(pct == 100, answered, w),
            "no children (%)": 100 * mean(childless, known_parity, w),
            "mean stated, no children (%)": mean(pct, childless, w),
            "mean stated, mothers (%)": mean(pct, mothers, w),
            "mothers minus no children (points)": mean(pct, mothers, w) - mean(pct, childless, w),
            "Black (%)": 100 * mean(race == "Black", answered, w),
            "Hispanic (%)": 100 * mean(race == "Hispanic", answered, w),
        }
    return estimator


def baseline_description(frame: pd.DataFrame, design: pd.DataFrame) -> pd.DataFrame:
    """Unweighted and weighted descriptions with JKn, linearized and SRS standard errors."""
    strata, psu, w = (frame[c].to_numpy() for c in ("stratum", "psu", "weight"))
    estimator = description_estimator(frame)
    unweighted = pd.Series(estimator(np.ones(len(frame))))
    weighted = jackknife(estimator, w, strata, psu, design)
    table = pd.DataFrame({"unweighted": unweighted, "weighted": weighted["estimate"],
                          "jackknife_se": weighted["se"]})
    answered = frame["answered"].to_numpy()
    pct = frame["expectation_pct"].fillna(0).to_numpy()
    parity = frame["parity"].to_numpy()
    linear = {
        "mean stated chance (%)": (pct, answered),
        "answered 0% (%)": (100 * (pct == 0), answered),
        "answered 50% (%)": (100 * (pct == 50), answered),
        "answered 100% (%)": (100 * (pct == 100), answered),
        "no children (%)": (100 * (parity == 0), answered & ~np.isnan(parity)),
        "item nonresponse (%)": (100 * ~answered, np.ones(len(frame), bool)),
    }
    for name, (y, domain) in linear.items():
        _, se = linearized_mean(y.astype(float), w, strata, psu, design, domain)
        table.loc[name, "linearized_se"] = se
        table.loc[name, "srs_se"] = srs_se(y[domain].astype(float), w[domain])
    table["deft"] = table["jackknife_se"] / table["srs_se"]
    return table


# --------------------------------------------------- outcome sensitivity

def outcome_frames(frames: dict[int, pd.DataFrame]) -> dict[int, pd.DataFrame]:
    """Eligible women with frozen labels and frozen forecasts, aligned to the design.

    2009: the primary cohort; recalibration is judged on the M02 held-out
    women only. 2015: the temporal cohort (setting A); every labelled woman
    is out of period.
    """
    models = tv.frozen_models()
    tv.verify_frozen(models)
    cohort = ac.load_cohort()
    _, test = ac.household_split(ac.labelled_sample(cohort))
    first = frames[2009][frames[2009]["answered"]].merge(
        cohort[["respondent_id", "outcome", "parity_at_baseline", ac.STATED]],
        on="respondent_id", how="inner", validate="one_to_one")
    if len(first) != len(cohort):
        raise ValueError("2009 design frame does not cover the cohort")
    first["evaluate"] = first["respondent_id"].isin(test["respondent_id"])
    first["parity"] = first["parity_at_baseline"].astype(float)

    joined, items, _ = tv.load_temporal()
    later = tv.later_cohort(joined, items)
    answered = frames[2015][frames[2015]["answered"]]
    second = answered.merge(
        later[["respondent_id", "household_id", "outcome", "parity_at_baseline", ac.STATED]],
        on="respondent_id", how="inner", validate="one_to_one", suffixes=("", "_cohort"))
    if len(second) != len(answered) or len(second) != len(later):
        raise ValueError("2015 design frame and temporal cohort cover different respondents")
    if not (second["household_id"] == second["household_id_cohort"]).all():
        raise ValueError("2015 design frame and temporal cohort disagree on households")
    second["parity"] = second["parity_at_baseline"].astype(float)
    second["evaluate"] = True

    out = {}
    for year, frame in ((2009, first), (2015, second)):
        frame = frame.reset_index(drop=True)
        frame["forecast_c"] = models.model_c.predict_proba(frame[[ac.STATED]])[:, 1]
        frame["outcome"] = frame["outcome"].astype(float)
        out[year] = frame
    return out


def adjustment_cells(frame: pd.DataFrame, min_cell: int = MIN_CELL) -> np.ndarray:
    """Weighting classes for missing labels: the finest of answer x parenthood x race,
    answer x parenthood, or answer that has at least min_cell labelled women."""
    answer = answer_category(frame["expectation_pct"])
    parenthood = np.select([frame["parity"] == 0, frame["parity"] >= 1],
                           ["none", "mother"], "unknown")
    levels = [answer + "|" + parenthood + "|" + frame["race"], answer + "|" + parenthood, answer]
    known = frame["outcome"].notna()
    cells = levels[-1].copy()
    for level in reversed(levels[:-1]):
        counts = level[known].value_counts()
        fine = level.map(counts).fillna(0) >= min_cell
        cells = cells.where(~fine, level)
    return cells.to_numpy()


def adjusted_weights(weights: np.ndarray, known: np.ndarray, cells: np.ndarray) -> np.ndarray:
    """Weighting-class adjustment: labelled women carry their cell's full weight."""
    frame = pd.DataFrame({"w": weights, "known": known, "cell": cells})
    total = frame.groupby("cell")["w"].transform("sum")
    labelled = frame["w"].where(frame["known"], 0.0).groupby(frame["cell"]).transform("sum")
    factor = np.where(labelled > 0, total / labelled.where(labelled > 0, 1.0), 0.0)
    return np.where(known, weights * factor, 0.0)


def outcome_statistics(y: np.ndarray, p: np.ndarray, c: np.ndarray, parity: np.ndarray,
                       evaluate: np.ndarray, w: np.ndarray) -> dict:
    """Weighted calibration summaries; rows with zero weight are ignored."""
    use = w > 0

    def mean(values, mask):
        return np.sum(w[mask] * values[mask]) / np.sum(w[mask])

    childless, mothers = use & (parity == 0), use & (parity >= 1)
    over_none = mean(p, childless) - mean(y, childless)
    over_mothers = mean(p, mothers) - mean(y, mothers)
    slope = np.polyfit(p[use], y[use], 1, w=np.sqrt(w[use]))[0]
    e = use & evaluate
    brier_b = mean((p - y) ** 2, e)
    brier_c = mean((c - y) ** 2, e)
    return {
        "observed rate": mean(y, use), "mean stated": mean(p, use),
        "overestimate": mean(p, use) - mean(y, use),
        "overestimate, no children": over_none, "overestimate, mothers": over_mothers,
        "mothers minus no children": over_mothers - over_none,
        "birth rate after 0%": mean(y, use & (p == 0)),
        "birth rate after 100%": mean(y, use & (p == 1)),
        "linear slope": slope,
        "Brier B (evaluation set)": brier_b, "Brier C (evaluation set)": brier_c,
        "C - B": brier_c - brier_b,
    }


def selection_scenarios(frame: pd.DataFrame, design: pd.DataFrame) -> pd.DataFrame:
    """Outcome summaries under each weighting and missing-label assumption."""
    known = frame["outcome"].notna().to_numpy()
    y = frame["outcome"].fillna(0).to_numpy()
    p, c = frame[ac.STATED].to_numpy(), frame["forecast_c"].to_numpy()
    parity, evaluate = frame["parity"].to_numpy(), frame["evaluate"].to_numpy()
    strata, psu, w = (frame[col].to_numpy() for col in ("stratum", "psu", "weight"))
    cells = adjustment_cells(frame)

    def stats(weights, outcome=y):
        return outcome_statistics(outcome, p, c, parity, evaluate, weights)

    rows = {
        "Unweighted, labelled (published)":
            (None, jackknife(lambda v: stats(np.where(known, v, 0.0)), np.ones(len(frame)),
                             strata, psu, design)),
        "Cross-sectional weight, labelled":
            (None, jackknife(lambda v: stats(np.where(known, v, 0.0)), w, strata, psu, design)),
        "Cross-sectional weight x missing-label adjustment":
            (None, jackknife(lambda v: stats(adjusted_weights(v, known, cells)), w, strata, psu,
                             design)),
    }
    table = {}
    for name, (_, replicated) in rows.items():
        table[(name, "estimate")] = replicated["estimate"]
        table[(name, "se")] = replicated["se"]
    return pd.DataFrame(table)


RECALIBRATION_ROWS = ["Brier B (evaluation set)", "Brier C (evaluation set)", "C - B"]


def respondent_bounds(statistic: Callable[[np.ndarray], dict], y: np.ndarray,
                      unknown: np.ndarray) -> pd.DataFrame:
    """Smallest and largest value of each statistic over every 0/1 assignment of unknowns.

    Valid for statistics that are sums of per-respondent terms over fixed
    denominators (weighted means within fixed groups, the weighted linear
    slope with forecasts and weights fixed, Brier scores and their
    differences). Each unknown then shifts a statistic by its own amount
    when set to a birth, so the bounds take every unknown whose shift is
    negative (lower) or positive (upper). Additivity is checked against the
    all-births assignment.
    """
    base_y = np.where(unknown, 0.0, y)
    base = pd.Series(statistic(base_y))
    shifts = []
    for i in np.flatnonzero(unknown):
        trial = base_y.copy()
        trial[i] = 1.0
        shifts.append(pd.Series(statistic(trial)) - base)
    shifts = pd.DataFrame(shifts, columns=base.index).fillna(0.0)
    all_births = pd.Series(statistic(np.where(unknown, 1.0, y)))
    if not np.allclose(all_births, base + shifts.sum(), rtol=0, atol=1e-9, equal_nan=True):
        raise ValueError("A statistic is not additive in the unknown outcomes")
    return pd.DataFrame({"lower": base + shifts.clip(upper=0).sum(),
                         "upper": base + shifts.clip(lower=0).sum()})


def outcome_bounds(frame: pd.DataFrame) -> pd.DataFrame:
    """Uniform assignments and respondent-specific bounds over all eligible women.

    Uniform assignments give every unknown the same outcome; they bound a
    statistic only if every unknown moves it in the same direction.
    Respondent-specific bounds choose each unknown's outcome separately and
    are the true worst cases. The cohort, frozen forecasts and weights are
    fixed. Recalibration rows are left blank when the evaluation set was
    defined using outcome labels, because its unknown members cannot be
    identified.
    """
    unknown = frame["outcome"].isna().to_numpy()
    y = frame["outcome"].fillna(0).to_numpy()
    p, c = frame[ac.STATED].to_numpy(), frame["forecast_c"].to_numpy()
    parity, evaluate = frame["parity"].to_numpy(), frame["evaluate"].to_numpy()
    w = frame["weight"].to_numpy()
    columns = {}
    for label, weights in (("weighted", w), ("unweighted", np.ones(len(frame)))):
        def statistic(outcome, weights=weights):
            return outcome_statistics(outcome, p, c, parity, evaluate, weights)
        if label == "weighted":
            columns["uniform: all births (weighted)"] = pd.Series(
                statistic(np.where(unknown, 1.0, y)))
            columns["uniform: no births (weighted)"] = pd.Series(
                statistic(np.where(unknown, 0.0, y)))
        bounds = respondent_bounds(statistic, y, unknown)
        columns[f"lower ({label})"] = bounds["lower"]
        columns[f"upper ({label})"] = bounds["upper"]
    table = pd.DataFrame(columns)
    if not (unknown & evaluate).any():
        table.loc[RECALIBRATION_ROWS] = np.nan
    return table


def held_out_coverage() -> pd.Series:
    """Where unlabelled 2009 women's households sit relative to the M02 split."""
    cohort = ac.load_cohort()
    train, test = ac.household_split(ac.labelled_sample(cohort))
    unlabelled = cohort[cohort["outcome"].isna()]["household_id"]
    return pd.Series(np.select(
        [unlabelled.isin(train["household_id"]), unlabelled.isin(test["household_id"])],
        ["training household", "held-out household"], "no labelled woman in household"),
        index=unlabelled.index).value_counts()


def cell_summary(frame: pd.DataFrame) -> str:
    cells = adjustment_cells(frame)
    known = frame["outcome"].notna()
    labelled = pd.Series(cells[known.to_numpy()]).value_counts()
    return (f"{len(set(cells))} cells; fewest labelled women in a cell {labelled.min()}; "
            f"cells with fewer than {MIN_CELL} labelled women collapsed")


def main() -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    frames, design = baseline_frames()
    joined, items, _ = tv.load_temporal()
    audit_frame = pd.DataFrame({
        "stratum": joined[items["vstrat"]], "psu": joined[items["vpsu"]],
        "weight_2009": joined[WEIGHT_2009] / 100, "weight_2015": joined[items["weight"]] / 100,
        "interviewed_2009": joined[INTERVIEW_MONTH[2009]] > 0,
        "interviewed_2015": joined[INTERVIEW_MONTH[2015]] > 0,
    })
    print("THE INTENTION GAP | SURVEY DESIGN, WEIGHTING AND SELECTION")
    print("=" * 72)
    print(f"\nDesign: {len(audit_frame):,} respondents, {design['stratum'].nunique()} strata, "
          f"{len(design)} PSUs (PSUs per stratum: {sorted(design['n_h'].unique())}); "
          f"PSU sizes {audit_frame.groupby(['stratum', 'psu']).size().min()}-"
          f"{audit_frame.groupby(['stratum', 'psu']).size().max()}")
    for year, checks in design_audit(audit_frame).items():
        print(f"  {year} weight: " + "; ".join(f"{k} {v:,.0f}" if isinstance(v, float) else
                                                f"{k} {v}" for k, v in checks.items()))
    print(f"  Published round total: {WEIGHT_SUM:,}")

    print("\nDESIGN-BASED BASELINE ESTIMATES")
    print("DEFT = jackknife SE of the weighted estimate / SE of a simple random sample of the "
          "same size,\nusing the weighted variance of the item; it includes unequal weighting, "
          "stratification and clustering.")
    for year, frame in frames.items():
        print(f"\nBaseline description, {year} (female round respondents: {len(frame):,}; "
              f"answered: {int(frame['answered'].sum()):,}). Weighted = round cross-sectional "
              "weight; SEs from the delete-one-PSU jackknife and linearization")
        print(baseline_description(frame, design).round(3).to_string())

    print("\nEXPLORATORY LONGITUDINAL SENSITIVITY (not design-based population estimates: "
          "cross-sectional weights\ndo not cover attrition, and the adjustment assumes labels "
          "are missing at random within cells)")
    for year, frame in outcome_frames(frames).items():
        print(f"\nSelection sensitivity, {year} cohort (n {len(frame):,}, labelled "
              f"{int(frame['outcome'].notna().sum()):,}; recalibration judged on "
              f"{int((frame['evaluate'] & frame['outcome'].notna()).sum()):,} women). "
              f"Missing-label adjustment: {cell_summary(frame)}")
        print(selection_scenarios(frame, design).round(4).to_string())
        print(f"\nMissing outcomes, {year}: uniform assignments and respondent-specific bounds "
              "(weights, cohort and frozen forecasts fixed)")
        print(outcome_bounds(frame).round(4).to_string())
        if year == 2009:
            print("  Recalibration bounds not established: the held-out set was drawn from "
                  "labelled women only.\n  Households of the 256 unlabelled women: " + ", ".join(
                      f"{k} {v}" for k, v in held_out_coverage().items()))


if __name__ == "__main__":
    main()
