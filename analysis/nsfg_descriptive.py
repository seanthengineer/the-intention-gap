"""NSFG 2022-2023 survey-weighted descriptive analysis for M09.

Extends the Stage 3 desire-intention audit to the prevalence of wanting and
intending children, the decomposition of desire-intention discordance,
expected additional births, observed fertility, and differences by sex, age,
partnership, education and other characteristics. Every estimate uses
WGT2022_2023 with VEST/VECL Taylor linearization on the full stacked sample
(subpopulations as domains), reports its unweighted denominator and applies
the NCHS reliability standard for proportions. All results are cross-sectional
associations at interview; none is causal or longitudinal.

Run from the project root:
    python -m analysis.nsfg_descriptive

Writes aggregate tables to data/public/nsfg_m09/ and figures to
assets/figures/nsfg_*.png. Estimates that fail the NCHS standard ("suppress: ...")
are blanked in the public tables and never drawn; the complete tables are kept
locally in data/processed/nsfg_m09_internal/ for validation. No respondent-level
rows are written.
"""

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from analysis import nsfg  # noqa: E402
from analysis import survey_design as sd  # noqa: E402
from analysis.analyze_calibration import INK, apply_figure_style  # noqa: E402
from analysis.nlsy97 import PROJECT_ROOT  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "data" / "public" / "nsfg_m09"
INTERNAL_DIR = PROJECT_ROOT / "data" / "processed" / "nsfg_m09_internal"
SUPPRESSED_COLUMNS = ["events", "estimate", "se", "ci_low", "ci_high", "effective_n"]
FIGURE_DIR = PROJECT_ROOT / "assets" / "figures"
PRIMARY_COHORT, SENSITIVITY_COHORT = "conservative", "inclusive"
ALPHA = 0.05
SERIES = {"female": "#2a78d6", "male": "#eb6834"}
CATEGORY_COLORS = {nsfg.POSITIVE: "#2a78d6", nsfg.EXPLICIT_NEGATIVE: "#eb6834",
                   nsfg.STERILITY_LINKED: "#1baf7a", nsfg.UNKNOWN: "#eda100",
                   nsfg.NOT_PROVIDED_OR_OTHER: "#e87ba4"}
POPULATIONS = ("all", "female", "male")

# Proportion measures: (indicator column, extra domain restriction, description).
SHARES = {
    "wants": ("wants", None, "wants a(nother) child (RWANT = 1), all respondents"),
    "intends": ("intends", None, "intends a(nother) birth (INTENT = 1), all respondents"),
    "divergence_among_wanters": ("divergence", "wants",
                                 "INTENT = 2 among those who want a child"),
    "explicit_among_wanters": ("explicit", "wants",
                               "answered the intention question 'no', among those who want"),
    "sterility_among_wanters": ("sterility", "wants",
                                "sterility-linked INTENT = 2, among those who want"),
    "explicit_among_direct": ("explicit", "direct",
                              "explicit 'no' among wanters with a yes/no intention answer"),
    "any_children": ("any_children", "children_known", "has had at least one child"),
}
# Mean measures: (value column, extra domain restriction, description).
MEANS = {
    "children": ("children", None, "live births (women) or children fathered (men)"),
    "expected_additional": ("expected_additional", None,
                            "central number of additional births expected (ADDEXP / 10)"),
    "intended_number": ("intended_number", "intends",
                        "number of (more) children intended, among intenders"),
    "expected_total": ("expected_total", "female",
                       "births to date plus additional expected (women only)"),
}
GROUPINGS = ["sex", "age_group", "interview_year", "partnership", "intention_branch",
             "education", "race_ethnicity", "poverty_group", "labor_force", "metro",
             "religion", "insurance", "children_group"]
SUBGROUP_MEASURES = ["wants", "intends", "divergence_among_wanters", "explicit_among_wanters"]
LEVEL_ORDER = {
    "sex": list(nsfg.SEXES),
    "age_group": [label for _, label in nsfg.AGE_GROUPS],
    "partnership": ["married", "cohabiting", "neither"],
    "children_group": nsfg.CHILDREN_GROUPS,
    "education": [label for _, label in nsfg.EDUCATION],
    "race_ethnicity": list(nsfg.RACE_ETHNICITY.values()),
    "poverty_group": [label for _, label in nsfg.POVERTY_GROUPS],
}
# Planned comparisons, Holm-adjusted as one family. They were named before the first run,
# but no time-stamped protocol records that, so they are not presented as pre-registered.
PLANNED_TESTS = [("explicit_among_wanters", "children_group"),
                   ("explicit_among_wanters", "age_group")]


# ------------------------------------------------------------- reliability

def korn_graubard_interval(p: float, se: float, n: int, df: int,
                           alpha: float = ALPHA) -> tuple[float, float, float]:
    """Korn-Graubard interval and the df-adjusted effective sample size (NCHS standard)."""
    if n == 0:
        return np.nan, np.nan, 0.0
    if 0 < p < 1 and se > 0:
        effective = p * (1 - p) / se ** 2
    else:
        effective = float(n)
    adjust = (stats.t.ppf(1 - alpha / 2, n - 1) / stats.t.ppf(1 - alpha / 2, df)) ** 2 \
        if n > 1 else 1.0
    effective = min(float(n), effective * adjust)
    events = p * effective
    lower = stats.beta.ppf(alpha / 2, events, effective - events + 1) if events > 0 else 0.0
    upper = (stats.beta.ppf(1 - alpha / 2, events + 1, effective - events)
             if events < effective else 1.0)
    return float(lower), float(upper), effective


def proportion_reliability(p: float, lower: float, upper: float, effective: float,
                           df: int) -> str:
    """NCHS Data Presentation Standards for Proportions (Parker et al., 2017)."""
    if effective < 30:
        return "suppress: effective n < 30"
    width = upper - lower
    if width >= 0.30:
        return "suppress: CI width >= 30 pp"
    if width > 0.05 and p > 0 and width / p > 1.30:
        return "suppress: relative CI width > 130%"
    if df < 8:
        return "flag: design df < 8"
    return "reliable"


def mean_reliability(estimate: float, se: float, n: int) -> str:
    if n < 30:
        return "suppress: n < 30"
    if estimate != 0 and se / abs(estimate) > 0.30:
        return "flag: relative SE > 30%"
    return "reliable"


# --------------------------------------------------------------- estimator

@dataclass
class Survey:
    """The stacked sample with its design; every estimate is a domain of the full design."""

    sample: pd.DataFrame

    def __post_init__(self):
        if self.sample.empty:
            raise ValueError("Empty sample")
        self.design = nsfg.survey_design_table(self.sample)
        self.df = sd.design_degrees_of_freedom(self.design)
        self.weights = self.sample[nsfg.WEIGHT].to_numpy(dtype=float)
        self.strata = self.sample[nsfg.STRATUM].to_numpy()
        self.psu = self.sample[nsfg.CLUSTER].to_numpy()

    def _values(self, column: str) -> tuple[np.ndarray, np.ndarray]:
        values = self.sample[column].astype(float)
        return values.fillna(0.0).to_numpy(), values.notna().to_numpy()

    def share(self, column: str, domain: np.ndarray) -> dict:
        y, known = self._values(column)
        domain = np.asarray(domain, dtype=bool) & known
        n = int(domain.sum())
        if n == 0:
            return {"n": 0, "events": 0, "estimate": np.nan, "se": np.nan, "ci_low": np.nan,
                    "ci_high": np.nan, "reliability": "suppress: empty domain"}
        estimate, se = sd.linearized_mean(y, self.weights, self.strata, self.psu, self.design,
                                          domain)
        lower, upper, effective = korn_graubard_interval(estimate, se, n, self.df)
        return {"n": n, "events": int(y[domain].sum()), "estimate": estimate, "se": se,
                "ci_low": lower, "ci_high": upper, "effective_n": effective,
                "reliability": proportion_reliability(estimate, lower, upper, effective,
                                                      self.df)}

    def mean(self, column: str, domain: np.ndarray) -> dict:
        y, known = self._values(column)
        domain = np.asarray(domain, dtype=bool) & known
        n = int(domain.sum())
        if n == 0:
            return {"n": 0, "estimate": np.nan, "se": np.nan, "ci_low": np.nan,
                    "ci_high": np.nan, "reliability": "suppress: empty domain"}
        estimate, se = sd.linearized_mean(y, self.weights, self.strata, self.psu, self.design,
                                          domain)
        half = stats.t.ppf(1 - ALPHA / 2, self.df) * se
        return {"n": n, "estimate": estimate, "se": se, "ci_low": estimate - half,
                "ci_high": estimate + half, "reliability": mean_reliability(estimate, se, n)}

    def difference(self, column: str, domain_a: np.ndarray, domain_b: np.ndarray) -> dict:
        y, known = self._values(column)
        a, b = (np.asarray(d, dtype=bool) & known for d in (domain_a, domain_b))
        if not a.any() or not b.any():
            raise ValueError("Both domains need at least one respondent")
        difference, se = sd.linearized_domain_difference(y, self.weights, self.strata,
                                                         self.psu, self.design, a, b)
        half = stats.t.ppf(1 - ALPHA / 2, self.df) * se
        return {"difference": difference, "se": se, "ci_low": difference - half,
                "ci_high": difference + half,
                "p_value": float(2 * stats.t.sf(abs(difference / se), self.df))}

    def wald(self, column: str, domains: list[np.ndarray]) -> dict:
        y, known = self._values(column)
        domains = [np.asarray(d, dtype=bool) & known for d in domains]
        means, covariance = sd.linearized_domain_covariance(
            y, self.weights, self.strata, self.psu, self.design, domains)
        statistic, df1, df2, p_value = sd.adjusted_wald_test(means, covariance, self.df)
        return {"F": statistic, "df1": df1, "df2": df2, "p_value": p_value}


def holm(p_values: pd.Series) -> pd.Series:
    """Holm step-down adjusted p-values."""
    order = p_values.sort_values()
    m = len(order)
    adjusted = np.maximum.accumulate([(m - i) * p for i, p in enumerate(order)])
    return pd.Series(np.minimum(adjusted, 1.0), index=order.index).reindex(p_values.index)


# ---------------------------------------------------------------- domains

def prepare(sample: pd.DataFrame) -> pd.DataFrame:
    """Add the domain indicators used by the tables (no rows are dropped)."""
    sample = sample.copy()
    sample["in_all"] = True
    for cohort in nsfg.COHORTS:
        sample[f"in_{cohort}"] = nsfg.in_cohort(sample, cohort)
    sample["direct"] = sample["wants"] & sample["category"].isin(
        [nsfg.POSITIVE, nsfg.EXPLICIT_NEGATIVE])
    sample["children_known"] = sample["children"].notna()
    sample["female"] = sample["sex"].eq("female")
    sample["expected_total"] = (sample["children"] + sample["expected_additional"]).where(
        sample["female"])
    sample["any_children"] = sample["any_children"].astype(float)
    return sample


def base_domain(sample: pd.DataFrame, cohort: str, population: str) -> np.ndarray:
    domain = sample["in_all"] if cohort == "all ages" else sample[f"in_{cohort}"]
    if population != "all":
        domain = domain & sample["sex"].eq(population)
    return domain.to_numpy(dtype=bool)


def measure_domain(sample: pd.DataFrame, restriction: str | None) -> np.ndarray:
    if restriction is None:
        return np.ones(len(sample), dtype=bool)
    return sample[restriction].fillna(False).to_numpy(dtype=bool)


def estimate_row(survey: Survey, name: str, domain: np.ndarray) -> dict:
    if name in SHARES:
        column, restriction, _ = SHARES[name]
        result = survey.share(column, domain & measure_domain(survey.sample, restriction))
        return {"measure": name, "kind": "proportion", **result}
    column, restriction, _ = MEANS[name]
    result = survey.mean(column, domain & measure_domain(survey.sample, restriction))
    return {"measure": name, "kind": "mean", **result}


# ----------------------------------------------------------------- tables

def sample_flow(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for population in POPULATIONS:
        frame = sample if population == "all" else sample[sample["sex"].eq(population)]
        for cohort in ["all ages", PRIMARY_COHORT, SENSITIVITY_COHORT]:
            scope = frame if cohort == "all ages" else frame[frame[f"in_{cohort}"]]
            wanters = scope[scope["wants"]]
            rows.append({
                "population": population, "cohort": cohort, "respondents": len(scope),
                "want a child": len(wanters),
                "wanters with yes/no intention": int(wanters["direct"].sum()),
                "explicit negative": int(wanters["explicit"].sum()),
                "sterility-linked": int(wanters["sterility"].sum()),
                "unknown or not provided": int(wanters["category"].isin(
                    [nsfg.UNKNOWN, nsfg.NOT_PROVIDED_OR_OTHER]).sum())})
    return pd.DataFrame(rows)


def response_distributions(survey: Survey, cohort: str) -> pd.DataFrame:
    """Weighted distributions of RWANT, INTENT and the wanters' intention categories."""
    sample = survey.sample
    rwant = sample["RWANT"].map({1: "yes", 5: "no", 8: "refused", 9: "don't know"}).fillna(
        "missing")
    intent = sample["INTENT"].map({1: "intends", 2: "does not intend", 3: "does not know",
                                   4: "not provided"})
    items = {"RWANT": (rwant, np.ones(len(sample), dtype=bool)),
             "INTENT": (intent, np.ones(len(sample), dtype=bool)),
             "intention category among wanters": (sample["category"],
                                                  sample["wants"].to_numpy(dtype=bool))}
    rows = []
    for population in POPULATIONS:
        domain = base_domain(sample, cohort, population)
        for item, (labels, restriction) in items.items():
            for label in labels[domain & restriction].dropna().unique():
                survey.sample["_indicator"] = labels.eq(label).astype(float)
                result = survey.share("_indicator", domain & restriction)
                rows.append({"cohort": cohort, "population": population, "item": item,
                             "response": label, **result})
    del survey.sample["_indicator"]
    return pd.DataFrame(rows).sort_values(["population", "item", "estimate"],
                                          ascending=[True, True, False])


def overall_estimates(survey: Survey, cohorts: list[str]) -> pd.DataFrame:
    rows = []
    for cohort in cohorts:
        for population in POPULATIONS:
            domain = base_domain(survey.sample, cohort, population)
            for name in [*SHARES, *MEANS]:
                if name == "expected_total" and population == "male":
                    continue
                rows.append({"cohort": cohort, "population": population,
                             **estimate_row(survey, name, domain)})
    return pd.DataFrame(rows)


def sex_differences(survey: Survey, cohorts: list[str]) -> pd.DataFrame:
    rows, sample = [], survey.sample
    for cohort in cohorts:
        for name in [*SHARES, *MEANS]:
            if name == "expected_total":
                continue
            column, restriction, _ = SHARES.get(name) or MEANS[name]
            restrict = measure_domain(sample, restriction)
            female = base_domain(sample, cohort, "female") & restrict
            male = base_domain(sample, cohort, "male") & restrict
            rows.append({"cohort": cohort, "measure": name,
                         **survey.difference(column, female, male)})
    return pd.DataFrame(rows)


def subgroup_table(survey: Survey, cohort: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Estimates by subgroup and design-adjusted Wald tests of equality across levels."""
    sample, rows, tests = survey.sample, [], []
    for population in POPULATIONS:
        domain = base_domain(sample, cohort, population)
        for grouping in GROUPINGS:
            if grouping == "sex" and population != "all":
                continue
            levels = [level for level in sample.loc[domain, grouping].dropna().unique()]
            levels = sorted(levels, key=str)
            for name in SUBGROUP_MEASURES:
                column, restriction, _ = SHARES[name]
                restrict = domain & measure_domain(sample, restriction)
                masks = {level: restrict & sample[grouping].eq(level).to_numpy()
                         for level in levels}
                for level, mask in masks.items():
                    rows.append({"cohort": cohort, "population": population,
                                 "grouping": grouping, "level": str(level),
                                 **estimate_row(survey, name, domain
                                                & sample[grouping].eq(level).to_numpy())})
                usable = [mask for mask in masks.values() if mask.sum() > 0]
                if len(usable) >= 2:
                    tests.append({"cohort": cohort, "population": population,
                                  "grouping": grouping, "measure": name,
                                  "levels": len(usable),
                                  "smallest level n": int(min(m.sum() for m in usable)),
                                  **survey.wald(column, usable)})
    tests = pd.DataFrame(tests)
    tests["holm_p_within_measure"] = tests.groupby(["population", "measure"])[
        "p_value"].transform(holm)
    tests["role"] = [
        "planned comparison" if (row.measure, row.grouping) in PLANNED_TESTS
        and row.population == "all" else "exploratory" for row in tests.itertuples()]
    planned = tests["role"].eq("planned comparison")
    tests.loc[planned, "holm_p_planned_family"] = holm(tests.loc[planned, "p_value"])
    return pd.DataFrame(rows), tests


def parity_contrasts(survey: Survey, cohort: str) -> pd.DataFrame:
    """Parents minus non-parents for the intention measures, by population."""
    rows, sample = [], survey.sample
    parent = sample["any_children"].eq(1).to_numpy()
    childless = sample["any_children"].eq(0).to_numpy()
    for population in POPULATIONS:
        domain = base_domain(sample, cohort, population)
        for name in SUBGROUP_MEASURES:
            column, restriction, _ = SHARES[name]
            restrict = domain & measure_domain(sample, restriction)
            rows.append({"cohort": cohort, "population": population, "measure": name,
                         "comparison": "parents - childless",
                         "n parents": int((restrict & parent).sum()),
                         "n childless": int((restrict & childless).sum()),
                         **survey.difference(column, restrict & parent,
                                             restrict & childless)})
    return pd.DataFrame(rows)


def expected_by_category(survey: Survey, cohort: str) -> pd.DataFrame:
    """Expected additional births and observed children by intention category of wanters."""
    rows, sample = [], survey.sample
    for population in POPULATIONS:
        domain = base_domain(sample, cohort, population) & sample["wants"].to_numpy()
        for category in nsfg.CATEGORIES:
            mask = domain & sample["category"].eq(category).to_numpy()
            if not mask.any():
                continue
            for column in ("expected_additional", "children"):
                rows.append({"cohort": cohort, "population": population,
                             "category": category, "measure": column,
                             **survey.mean(column, mask)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------- robustness

def jackknife_shares(survey: Survey, column: str, domain: np.ndarray) -> tuple[float, float]:
    y, known = survey._values(column)
    d = domain & known

    def estimator(weights: np.ndarray) -> dict:
        return {"share": float(np.sum(weights[d] * y[d]) / np.sum(weights[d]))}

    table = sd.jackknife(estimator, survey.weights, survey.strata, survey.psu, survey.design)
    return float(table.loc["share", "estimate"]), float(table.loc["share", "se"])


def separate_design_difference(sample: pd.DataFrame, column: str,
                               restriction: str | None, cohort: str) -> dict:
    """Female - male difference with each file analysed alone (independent samples)."""
    parts = []
    for sex in nsfg.SEXES:
        frame = sample[sample["sex"].eq(sex)].reset_index(drop=True)
        survey = Survey(frame)
        domain = base_domain(frame, cohort, sex) & measure_domain(frame, restriction)
        parts.append(survey.share(column, domain))
    difference = parts[0]["estimate"] - parts[1]["estimate"]
    se = float(np.hypot(parts[0]["se"], parts[1]["se"]))
    half = stats.t.ppf(1 - ALPHA / 2, survey.df) * se
    return {"difference": difference, "se": se, "ci_low": difference - half,
            "ci_high": difference + half,
            "p_value": float(2 * stats.t.sf(abs(difference / se), survey.df))}


def sensitivity_table(survey: Survey) -> pd.DataFrame:
    """Key estimands under alternative populations, eligibility, coding and variance choices."""
    sample, rows = survey.sample, []

    def add(analysis: str, variant: str, measure: str, result: dict) -> None:
        rows.append({"analysis": analysis, "variant": variant, "measure": measure,
                     **{k: result.get(k) for k in ("n", "estimate", "se", "ci_low",
                                                   "ci_high", "difference", "p_value",
                                                   "reliability")}})

    primary = base_domain(sample, PRIMARY_COHORT, "all")
    wanters = primary & sample["wants"].to_numpy()
    for cohort in [PRIMARY_COHORT, SENSITIVITY_COHORT, "all ages"]:
        domain = base_domain(sample, cohort, "all") & sample["wants"].to_numpy()
        for column in ("divergence", "explicit", "sterility"):
            add("age proxy", cohort, f"{column} among wanters", survey.share(column, domain))
        female = base_domain(sample, cohort, "female") & sample["wants"].to_numpy()
        male = base_domain(sample, cohort, "male") & sample["wants"].to_numpy()
        add("age proxy", cohort, "female - male divergence",
            survey.difference("divergence", female, male))

    probable = (sample["wants"] | (sample["RWANT"].eq(nsfg.DONT_KNOW)
                                   & sample["PROBWANT"].eq(1))).to_numpy()
    broad = primary & probable
    for column in ("divergence", "explicit", "sterility"):
        add("eligibility", "RWANT = 1 or 'probably want'", f"{column} among wanters",
            survey.share(column, broad))
    for branch in ("joint", "individual"):
        mask = wanters & sample["intention_branch"].eq(branch).to_numpy()
        for column in ("divergence", "explicit", "sterility"):
            add("intention item", f"{branch} item", f"{column} among wanters",
                survey.share(column, mask))
    joint = wanters & sample["intention_branch"].eq("joint").to_numpy()
    single = wanters & sample["intention_branch"].eq("individual").to_numpy()
    add("intention item", "joint - individual", "explicit among wanters",
        survey.difference("explicit", joint, single))

    fertile = wanters & ~sample["sterility"].to_numpy()
    add("sterility handling", "sterility-linked excluded from denominator",
        "explicit among wanters", survey.share("explicit", fertile))
    add("sterility handling", "sterility-linked counted as discordant (INTENT = 2)",
        "divergence among wanters", survey.share("divergence", wanters))

    unresolved = sample["category"].isin([nsfg.UNKNOWN, nsfg.NOT_PROVIDED_OR_OTHER])
    sample["_upper"] = (sample["explicit"] | unresolved).astype(float)
    add("unknown intentions", "excluded (yes/no answers only)", "explicit share",
        survey.share("explicit", primary & sample["direct"].to_numpy()))
    add("unknown intentions", "kept in denominator as not explicit (lower bound)",
        "explicit share", survey.share("explicit", wanters))
    add("unknown intentions", "counted as explicit negative (upper bound)", "explicit share",
        survey.share("_upper", wanters))
    del sample["_upper"]

    for column in ("divergence", "explicit", "sterility"):
        y = sample[column].astype(float).to_numpy()
        add("weighting", "unweighted", f"{column} among wanters",
            {"n": int(wanters.sum()), "estimate": float(y[wanters].mean()),
             "se": float(y[wanters].std(ddof=1) / np.sqrt(wanters.sum()))})
        estimate, se = jackknife_shares(survey, column, wanters)
        add("variance method", "JKn delete-one-cluster jackknife", f"{column} among wanters",
            {"n": int(wanters.sum()), "estimate": estimate, "se": se})
        add("variance method", "Taylor linearization (primary)", f"{column} among wanters",
            survey.share(column, wanters))
    for column in ("divergence", "explicit", "sterility"):
        add("sex contrast design", "separate files (independent samples)",
            f"female - male {column}",
            separate_design_difference(sample, column, "wants", PRIMARY_COHORT))
        female = base_domain(sample, PRIMARY_COHORT, "female") & sample["wants"].to_numpy()
        male = base_domain(sample, PRIMARY_COHORT, "male") & sample["wants"].to_numpy()
        add("sex contrast design", "pooled design (primary)", f"female - male {column}",
            survey.difference(column, female, male))
    return pd.DataFrame(rows)


def weighted_vs_unweighted(survey: Survey) -> pd.DataFrame:
    rows, sample = [], survey.sample
    for population in POPULATIONS:
        domain = base_domain(sample, PRIMARY_COHORT, population)
        for name in SUBGROUP_MEASURES + ["any_children"]:
            column, restriction, _ = SHARES[name]
            mask = domain & measure_domain(sample, restriction) & sample[column].notna()
            weighted = survey.share(column, mask)
            rows.append({"population": population, "measure": name, "n": weighted["n"],
                         "weighted": weighted["estimate"],
                         "unweighted": float(sample.loc[mask, column].astype(float).mean()),
                         "difference": weighted["estimate"]
                         - float(sample.loc[mask, column].astype(float).mean())})
    return pd.DataFrame(rows)


def build_tables(sample: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sample = prepare(sample)
    survey = Survey(sample.reset_index(drop=True))
    cohorts = [PRIMARY_COHORT, SENSITIVITY_COHORT]
    subgroups, tests = subgroup_table(survey, PRIMARY_COHORT)
    return {
        "sample_flow": sample_flow(survey.sample),
        "response_distributions": pd.concat(
            [response_distributions(survey, cohort) for cohort in cohorts]),
        "estimates": overall_estimates(survey, [*cohorts, "all ages"]),
        "sex_differences": sex_differences(survey, cohorts),
        "subgroups": subgroups,
        "subgroup_tests": tests,
        "parity_contrasts": parity_contrasts(survey, PRIMARY_COHORT),
        "expected_by_category": expected_by_category(survey, PRIMARY_COHORT),
        "sensitivity": sensitivity_table(survey),
        "weighted_vs_unweighted": weighted_vs_unweighted(survey),
    }


# ------------------------------------------------------- public release

def is_suppressed(table: pd.DataFrame) -> pd.Series:
    if "reliability" not in table:
        return pd.Series(False, index=table.index)
    return table["reliability"].astype(str).str.startswith("suppress")


def public_table(table: pd.DataFrame) -> pd.DataFrame:
    """Blank the estimate, interval, SE and event count of every suppressed row."""
    table = table.copy()
    hide = is_suppressed(table)
    for column in SUPPRESSED_COLUMNS:
        if column in table:
            table[column] = table[column].astype(float)
            table.loc[hide, column] = np.nan
    return table


def public_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {name: public_table(table) for name, table in tables.items()}


def plottable(data: pd.DataFrame) -> pd.DataFrame:
    """Rows that may be drawn: an estimate exists and the row is not suppressed."""
    return data[data["estimate"].notna() & ~is_suppressed(data)]


# ---------------------------------------------------------------- figures

def figure_decomposition(tables: dict, path: Path) -> None:
    """Intention categories of respondents who want a child, by sex (100% bars)."""
    data = tables["response_distributions"]
    data = data[data["cohort"].eq(PRIMARY_COHORT)
                & data["item"].eq("intention category among wanters")]
    order = [c for c in CATEGORY_COLORS if c in set(data["response"])]
    populations = ["female", "male", "all"]
    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    for row, population in enumerate(populations):
        left = 0.0
        part = data[data["population"].eq(population)].set_index("response")
        for category in order:
            shown = category in part.index and pd.notna(part.loc[category, "estimate"]) \
                and not str(part.loc[category, "reliability"]).startswith("suppress")
            value = 100 * part.loc[category, "estimate"] if shown else 0.0
            ax.barh(row, value, left=left, color=CATEGORY_COLORS[category], height=0.56,
                    edgecolor=INK["surface"], linewidth=2,
                    label=category if row == 0 else None)
            if value >= 4:
                ax.text(left + value / 2, row, f"{value:.1f}", ha="center", va="center",
                        fontsize=9, color="white" if category != nsfg.UNKNOWN else INK["primary"])
            left += value
    n = {p: int(data[data["population"].eq(p)]["n"].max()) for p in populations}
    ax.set_yticks(range(len(populations)),
                  [f"{p.capitalize()} (n {n[p]:,})" for p in populations])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Weighted percent of respondents who want a(nother) child "
                  "(categories failing the NCHS standard are not drawn)")
    ax.set_title("Intention among respondents who want a child, ages 18-26/27")
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.28), frameon=False,
              fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def figure_age_profile(tables: dict, path: Path) -> None:
    """Wanting and intending by age group and sex, with Korn-Graubard intervals."""
    data = tables["subgroups"]
    data = data[data["grouping"].eq("age_group") & data["population"].isin(nsfg.SEXES)]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6), sharey=False)
    measures = [("wants", "Want a(nother) child"), ("intends", "Intend a(nother) birth"),
                ("explicit_among_wanters", "Explicit 'no' among those who want")]
    for ax, (measure, title) in zip(axes, measures):
        for offset, sex in ((-0.1, "female"), (0.1, "male")):
            part = data[data["measure"].eq(measure) & data["population"].eq(sex)].sort_values(
                "level")
            levels = list(part["level"])
            part = plottable(part)
            x = np.array([levels.index(level) for level in part["level"]]) + offset
            ax.errorbar(x, 100 * part["estimate"],
                        yerr=[100 * (part["estimate"] - part["ci_low"]),
                              100 * (part["ci_high"] - part["estimate"])],
                        fmt="o", color=SERIES[sex], markersize=6, capsize=0, linewidth=2,
                        label=sex.capitalize())
        ax.set_xticks(range(len(levels)), levels)
        ax.set_title(title, fontsize=10.5)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Age at interview")
    axes[0].set_ylabel("Weighted percent (95% CI)")
    axes[0].legend(frameon=False, loc="lower left")
    fig.text(0.01, 0.01, "Estimates failing the NCHS reliability standard for proportions are "
             "not shown.", fontsize=8, color=INK["muted"])
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def figure_subgroups(tables: dict, path: Path) -> None:
    """Explicit negative intention among wanters by subgroup (reliable estimates only)."""
    data = tables["subgroups"]
    groupings = ["sex", "age_group", "partnership", "children_group", "education",
                 "race_ethnicity", "poverty_group"]
    data = data[data["measure"].eq("explicit_among_wanters") & data["population"].eq("all")
                & data["grouping"].isin(groupings)].copy()
    data["order"] = data["grouping"].map({g: i for i, g in enumerate(groupings)})
    data["level_order"] = [LEVEL_ORDER.get(row.grouping, []).index(row.level)
                           if row.level in LEVEL_ORDER.get(row.grouping, []) else 99
                           for row in data.itertuples()]
    data = data.sort_values(["order", "level_order", "level"]).reset_index(drop=True)
    overall = tables["estimates"]
    overall = overall[overall["cohort"].eq(PRIMARY_COHORT) & overall["population"].eq("all")
                      & overall["measure"].eq("explicit_among_wanters")].iloc[0]
    fig, ax = plt.subplots(figsize=(8.2, 0.32 * len(data) + 1.4))
    y = np.arange(len(data))
    shown = data.index.isin(plottable(data).index)
    part = data[shown]
    ax.errorbar(100 * part["estimate"], y[shown],
                xerr=[100 * (part["estimate"] - part["ci_low"]),
                      100 * (part["ci_high"] - part["estimate"])],
                fmt="o", color=INK["series"], markersize=6, linewidth=2, capsize=0)
    ax.axvline(100 * overall["estimate"], color=INK["muted"], linewidth=1, linestyle="--")
    labels = [f"{row.grouping.replace('_', ' ')}: {row.level} (n {row.n})"
              + ("" if keep else " - suppressed") for row, keep in zip(data.itertuples(), shown)]
    ax.set_yticks(y, labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(left=0)
    ax.set_xlabel("Weighted percent (95% Korn-Graubard CI); dashed line: all wanters\n"
                  "Suppressed: fails the NCHS reliability standard for proportions; not shown")
    ax.set_title("Explicit 'no' among those who want a child (ages 18-26/27)", fontsize=11)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


FIGURES = {"nsfg_intention_decomposition.png": figure_decomposition,
           "nsfg_age_profile.png": figure_age_profile,
           "nsfg_explicit_negative_subgroups.png": figure_subgroups}


def write_outputs(tables: dict[str, pd.DataFrame], output_dir: Path = OUTPUT_DIR,
                  figure_dir: Path = FIGURE_DIR, internal_dir: Path = INTERNAL_DIR) -> None:
    """Complete tables to the local internal folder; suppressed public tables and figures."""
    public = public_tables(tables)
    for folder, release in ((internal_dir, tables), (output_dir, public)):
        folder.mkdir(parents=True, exist_ok=True)
        for name, table in release.items():
            table.to_csv(folder / f"{name}.csv", index=False, float_format="%.6g")
    figure_dir.mkdir(parents=True, exist_ok=True)
    apply_figure_style()
    for filename, draw in FIGURES.items():
        draw(public, figure_dir / filename)


def main() -> None:
    if not nsfg.data_available():
        raise SystemExit("NSFG 2022-2023 files not found; see docs/nsfg_m09.md for the data "
                         "locations.")
    tables = build_tables(nsfg.analysis_sample())
    write_outputs(tables)
    estimates = tables["estimates"]
    key = estimates[estimates["cohort"].eq(PRIMARY_COHORT)]
    print("NSFG 2022-2023 | M09 DESCRIPTIVE ANALYSIS (conservative cohort)")
    for row in key.itertuples():
        scale = 100 if row.kind == "proportion" else 1
        unit = "%" if row.kind == "proportion" else ""
        print(f"  {row.population:6} {row.measure:26} {scale * row.estimate:7.2f}{unit} "
              f"(SE {scale * row.se:.2f}; n {row.n:,}; {row.reliability})")
    print(f"\nTables written to {OUTPUT_DIR.relative_to(PROJECT_ROOT).as_posix()}/ and figures "
          f"to {FIGURE_DIR.relative_to(PROJECT_ROOT).as_posix()}/nsfg_*.png")


if __name__ == "__main__":
    main()
