"""NSFG 2022-2023 Stage 3 validation: 19 registered checks.

Each check states its objective, variables and calculation, reports
aggregate results, compares them with the recorded Stage 3 values or the
CDC documentation, and returns PASS, FAIL, WARN or SKIP:

    PASS  every executable expectation is met
    FAIL  an expectation is not met
    WARN  expectations are met, but a stated assumption or exception needs review
    SKIP  the check could not run (data or a dependency is missing)

A missing dataset never produces PASS. With --require-data, a missing
dataset is an error instead of SKIP. Definitions live in analysis/nsfg.py
and the design-based variance in analysis/survey_design.py. See
docs/nsfg_stage3_validation.md.

Run from the project root:
    python audit/nsfg_stage3_checks.py                 all checks
    python audit/nsfg_stage3_checks.py --check 17      one check (repeatable)
    python -m audit.nsfg_stage3_checks --require-data  fail if data are missing
"""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from analysis import nsfg  # noqa: E402
from analysis import survey_design as sd  # noqa: E402

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"

# Stage 3 values recorded before consolidation (regression expectations).
EXPECTED = {
    "dimensions": {"female": (5586, 1912), "male": (4371, 1157)},
    "divergence_all_ages": {"female": 581, "male": 420, "total": 1001},
    "cohorts": {
        "conservative": {"female": 1349, "male": 1080, "total": 2429, "divergence": 193,
                         "explicit": 116, "sterility": 77},
        "inclusive": {"total": 2726, "divergence": 220, "explicit": 134, "sterility": 86},
    },
    "primary_breakdown": {nsfg.POSITIVE: 1491, nsfg.EXPLICIT_NEGATIVE: 116,
                          nsfg.STERILITY_LINKED: 77, nsfg.UNKNOWN: 15,
                          nsfg.NOT_PROVIDED_OR_OTHER: 4, nsfg.UNEXPLAINED: 0},
    "primary_denominator": 1703,
    "weighted_pct": {"divergence": (11.24, 0.98), "explicit": (6.56, 0.74),
                     "sterility": (4.68, 0.81)},
    "sex_contrast": {"female": 12.27, "male": 10.37, "difference": 1.90, "se": 2.09,
                     "ci": (-2.29, 6.08), "p": 0.3676},
    "contrast_p": {"conservative": {"divergence": 0.3676, "explicit": 0.1504,
                                    "sterility": 0.7703},
                   "inclusive": {"divergence": 0.2794, "explicit": 0.0701,
                                 "sterility": 0.6832}},
}

# Published CDC values (codebooks; variance estimation example 1, SURVEYFREQ output).
CODEBOOK = {
    "female": {"RWANT": {1: 2474, 5: 2945, 8: 34, 9: 132, "missing": 1},
               "INTENT": {1: 1888, 2: 3593, 3: 88, 4: 17},
               "YEAR": {1: 1579, 2: 4007}},
    "male": {"RWANT": {1: 2380, 5: 1852, 8: 31, 9: 108, "missing": 0},
             "YEAR": {1: 1454, 2: 2917}},
}
CDC_BENCHMARK = {  # women using the pill (CONSTAT1 = 6), by AGER group
    (15, 19): {"n": 730, "pct": 14.2348, "se": 1.6792},
    (20, 24): {"n": 606, "pct": 18.9586, "se": 2.0226},
    (25, 29): {"n": 803, "pct": 14.6057, "se": 1.8889},
}
CDC_DESIGN = {"strata": 20, "clusters": 80, "df": 60, "female_weight_sum": 74_936_917.9}
POPULATION_MILLIONS = {"female": 74.9, "male": 75.7}  # User's Guide, household population 15-49
AGE_GROUPS = [(15, 19), (20, 24), (25, 29), (30, 34), (35, 39), (40, 50)]
MEASURES = {"divergence": "INTENT = 2", "explicit": nsfg.EXPLICIT_NEGATIVE,
            "sterility": nsfg.STERILITY_LINKED}
SE_RATIO_LIMITS = (0.8, 1.25)


class DataUnavailable(Exception):
    pass


class DependencyUnavailable(Exception):
    pass


@dataclass
class CheckResult:
    check_id: str
    title: str
    objective: str
    variables: list[str]
    calculation: str
    status: str
    results: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class AuditData:
    """Lazily loaded respondent files; raises DataUnavailable if a file is missing."""

    def __init__(self, paths: dict[str, Path] | None = None):
        self.paths = dict(nsfg.DATA_PATHS if paths is None else paths)

    def available(self) -> bool:
        return all(Path(path).exists() for path in self.paths.values())

    def missing(self) -> list[str]:
        return [str(path) for path in self.paths.values() if not Path(path).exists()]

    def _load(self, sex: str) -> pd.DataFrame:
        if not Path(self.paths[sex]).exists():
            raise DataUnavailable(f"NSFG {sex} file not found: {self.paths[sex]}")
        frame = nsfg.load_respondents(sex, path=self.paths[sex])
        frame["category"] = nsfg.classify_intention(frame, sex)
        return frame

    @cached_property
    def female(self) -> pd.DataFrame:
        return self._load("female")

    @cached_property
    def male(self) -> pd.DataFrame:
        return self._load("male")

    def frame(self, sex: str) -> pd.DataFrame:
        return self.female if sex == "female" else self.male

    @cached_property
    def pooled(self) -> pd.DataFrame:
        pooled = nsfg.pooled_respondents(self.female, self.male)
        pooled["divergence"] = pooled["RWANT"].eq(nsfg.YES) & pooled["INTENT"].eq(
            nsfg.DOES_NOT_INTEND)
        pooled["explicit"] = pooled["category"].eq(nsfg.EXPLICIT_NEGATIVE)
        pooled["sterility"] = pooled["category"].eq(nsfg.STERILITY_LINKED)
        return pooled


# ------------------------------------------------------------- helpers

def close(observed: float, expected: float, decimals: int) -> bool:
    """Observed rounds to the recorded value at its reported precision."""
    return abs(observed - expected) <= 0.5 * 10 ** -decimals + 1e-12


class Expectations:
    """Collects comparisons; any mismatch makes the check FAIL."""

    def __init__(self):
        self.failures: list[str] = []

    def equal(self, label: str, observed, expected) -> None:
        if observed != expected:
            self.failures.append(f"{label}: observed {observed}, expected {expected}")

    def near(self, label: str, observed: float, expected: float, decimals: int) -> None:
        if not close(observed, expected, decimals):
            self.failures.append(f"{label}: observed {observed:.{decimals + 2}f}, "
                                 f"expected {expected}")

    def status(self, warn: bool = False) -> str:
        return FAIL if self.failures else WARN if warn else PASS


def divergent(frame: pd.DataFrame) -> pd.Series:
    return frame["RWANT"].eq(nsfg.YES) & frame["INTENT"].eq(nsfg.DOES_NOT_INTEND)


def counts(series: pd.Series) -> dict:
    """Frequencies by code, with blanks last as 'missing'."""
    table = {int(k): int(v) for k, v in series.dropna().value_counts().sort_index().items()}
    if series.isna().any():
        table["missing"] = int(series.isna().sum())
    return table


def cohort_domain(frame: pd.DataFrame, cohort: str) -> pd.Series:
    return nsfg.in_cohort(frame, cohort) & frame["RWANT"].eq(nsfg.YES)


def pct(estimate: nsfg.DesignEstimate) -> str:
    return f"{100 * estimate.estimate:.2f}% (SE {100 * estimate.se:.2f} pp, n {estimate.n:,})"


# ------------------------------------------------------------ registry

CHECKS: dict[str, tuple[str, str, list[str], str, Callable]] = {}


def check(check_id: str, title: str, objective: str, variables: list[str], calculation: str):
    def register(function: Callable) -> Callable:
        CHECKS[check_id] = (title, objective, variables, calculation, function)
        return function
    return register


@check("01", "Dataset integrity", "Validate the female and male CSV dimensions.",
       ["female and male public-use CSV files"],
       "Rows (excluding the header) and columns counted from the raw CSV text.")
def check_01(data: AuditData):
    expect, results = Expectations(), {}
    for sex in nsfg.SEXES:
        if not Path(data.paths[sex]).exists():
            raise DataUnavailable(f"NSFG {sex} file not found: {data.paths[sex]}")
        rows, columns = nsfg.file_dimensions(data.paths[sex])
        results[f"{sex} rows x columns"] = f"{rows:,} x {columns:,}"
        expect.equal(f"{sex} dimensions", (rows, columns), EXPECTED["dimensions"][sex])
    return expect, results, []


@check("02", "Variable availability",
       "Audit the demographic, fertility, sterility and design fields the analysis needs.",
       [*nsfg.COMMON_COLUMNS, *nsfg.FEMALE_ONLY_COLUMNS],
       "Column presence in each file; missing values in age, year, INTENT and design fields; "
       "positive weights.")
def check_02(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    for sex in nsfg.SEXES:
        if not Path(data.paths[sex]).exists():
            raise DataUnavailable(f"NSFG {sex} file not found: {data.paths[sex]}")
        header = set(pd.read_csv(data.paths[sex], nrows=0).columns)
        needed = nsfg.COMMON_COLUMNS + (nsfg.FEMALE_ONLY_COLUMNS if sex == "female" else [])
        absent = [c for c in needed if c not in header]
        expect.equal(f"{sex} missing required columns", absent, [])
        frame = data.frame(sex)
        complete = ["AGER", "YEAR", "INTENT", *nsfg.DESIGN_COLUMNS]
        blanks = {c: int(frame[c].isna().sum()) for c in complete if frame[c].isna().any()}
        expect.equal(f"{sex} blanks in {complete}", blanks, {})
        expect.equal(f"{sex} non-positive weights", int((frame[nsfg.WEIGHT] <= 0).sum()), 0)
        results[f"{sex} required columns present"] = f"{len(needed) - len(absent)}/{len(needed)}"
        if sex == "male":
            present = [c for c in nsfg.FEMALE_ONLY_COLUMNS if c in header]
            results["male FECUND / STRLOPER / CONSTAT1"] = (
                f"present: {present}" if present else "not in the male file (female recodes)")
    notes.append("FECUND, STRLOPER and CONSTAT1 are female-file recodes; male sterility "
                 "is described by RSTRSTAT and PSTRSTAT only.")
    return expect, results, notes


@check("03", "Intention schema",
       "Verify the individual, joint and derived intention variables and their routing.",
       ["RWANT", "JINTEND", "INTEND", "INTENT", "RMARIT", "RSTRSTAT", "PSTRSTAT"],
       "Observed codes against the codebook domains; answers outside, and blanks inside, each "
       "question's documented universe.")
def check_03(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    domains = {"RWANT": {1, 5, 8, 9}, "JINTEND": {1, 5, 8, 9}, "INTENT": {1, 2, 3, 4}}
    exceptions = 0
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        intend_codes = {1, 5, 8, 9} if sex == "female" else {1, 2, 3, 4, 8, 9}
        for column, codes in {**domains, "INTEND": intend_codes}.items():
            extra = sorted(set(frame[column].dropna().astype(int)) - codes)
            expect.equal(f"{sex} {column} codes outside the codebook", extra, [])
        expect.equal(f"{sex} INTENT missing", int(frame["INTENT"].isna().sum()), 0)
        married = frame["RMARIT"].isin(nsfg.MARRIED_OR_COHABITING)
        joint_universe = married & frame["RSTRSTAT"].eq(0) & frame["PSTRSTAT"].eq(0)
        single_universe = (~married & frame["RSTRSTAT"].eq(0)
                           & frame["RWANT"].isin([nsfg.YES, nsfg.DONT_KNOW]))
        routing = {
            "JINTEND answered outside universe": int((frame["JINTEND"].notna()
                                                      & ~joint_universe).sum()),
            "JINTEND blank inside universe": int((frame["JINTEND"].isna()
                                                  & joint_universe).sum()),
            "INTEND answered outside universe": int((frame["INTEND"].notna()
                                                     & ~single_universe).sum()),
            "INTEND blank inside universe": int((frame["INTEND"].isna()
                                                 & single_universe).sum()),
            "both intention items answered": int((frame["JINTEND"].notna()
                                                  & frame["INTEND"].notna()).sum()),
        }
        outside = frame["INTEND"].notna() & ~single_universe
        if outside.any():
            routing["INTEND outside universe, by RMARIT"] = counts(frame.loc[outside, "RMARIT"])
        results[f"{sex} routing"] = routing
        exceptions += sum(v for k, v in routing.items()
                          if isinstance(v, int) and k != "both intention items answered")
        expect.equal(f"{sex} respondents with both intention items",
                     routing["both intention items answered"], 0)
        traced = trace_routing_exceptions(data.paths[sex], sex, joint_universe, single_universe,
                                          frame)
        results[f"{sex} exception trace"] = traced["summary"]
        expect.equal(f"{sex} exceptions with INTENT other than 4 (not provided)",
                     traced["intent_not_4"], 0)
        expect.equal(f"{sex} exceptions among RWANT = 1 & INTENT = 2", traced["divergent"], 0)
        expect.equal(f"{sex} exceptions explained by MARSTAT instead of RMARIT",
                     traced["explained_by_marstat"], 0)
    notes.append("All exceptions keep INTENT = 4 (not provided), so none enters the "
                 "divergence, explicit-negative or sterility-linked counts; at most they move "
                 "between 'not provided' and 'positive' in the decomposition.")
    notes.append("Trace (CDC codebooks, recode specifications): (a) three cohabiting men (RMARIT "
                 "= 2, MARSTAT = 2) have no partner-sterility status (PSTRSTAT blank; it is "
                 "computed in the partner section, FC C-13), were asked the individual item "
                 "INTEND, and CDC recodes them INTENT = 4 with ADDEXP imputed (ADDEXP_I = 1), "
                 "i.e. CDC treats their intention as not provided; (b) one woman has the whole "
                 "Section G blank, including RWANT (section nonresponse); (c) one married man "
                 "answered RWANT = 5 but has no JINTEND (item nonresponse, unexplained). "
                 "Questionnaire marital status (MARSTAT, in both public files) explains none of "
                 "them. WARN is kept because (a) is inferred from the data, not stated by CDC, "
                 "and (c) has no documented explanation.")
    return expect, results, notes, bool(exceptions)


def trace_routing_exceptions(path: Path, sex: str, joint_universe: pd.Series,
                             single_universe: pd.Series, frame: pd.DataFrame) -> dict:
    """Classify each routing exception using MARSTAT, PSTRSTAT and the ADDEXP imputation flag."""
    extra = nsfg.load_respondents(sex, ["MARSTAT", "ADDEXP_I"], path=path)
    married_q = extra["MARSTAT"].isin(nsfg.MARRIED_OR_COHABITING)
    joint_q = married_q & frame["RSTRSTAT"].eq(0) & frame["PSTRSTAT"].eq(0)
    single_q = (~married_q & frame["RSTRSTAT"].eq(0)
                & frame["RWANT"].isin([nsfg.YES, nsfg.DONT_KNOW]))
    exception = ((frame["JINTEND"].notna() & ~joint_universe)
                 | (frame["JINTEND"].isna() & joint_universe)
                 | (frame["INTEND"].notna() & ~single_universe)
                 | (frame["INTEND"].isna() & single_universe))
    exception_q = ((frame["JINTEND"].notna() & ~joint_q) | (frame["JINTEND"].isna() & joint_q)
                   | (frame["INTEND"].notna() & ~single_q & ~frame["RMARIT"].eq(0))
                   | (frame["INTEND"].isna() & single_q))
    no_partner_status = (exception & frame["RMARIT"].isin(nsfg.MARRIED_OR_COHABITING)
                         & frame["PSTRSTAT"].isna() & frame["INTEND"].notna())
    section_blank = exception & frame["RWANT"].isna()
    item_blank = exception & ~no_partner_status & ~section_blank
    summary = {
        "partnered, partner sterility missing, routed to INTEND": int(no_partner_status.sum()),
        "  of which ADDEXP imputed (ADDEXP_I = 1)": int(
            (no_partner_status & extra["ADDEXP_I"].eq(1)).sum()),
        "intention section blank (RWANT missing)": int(section_blank.sum()),
        "joint item blank after RWANT answered (unexplained)": int(item_blank.sum()),
    }
    return {"summary": summary,
            "intent_not_4": int((exception & frame["INTENT"].ne(nsfg.NOT_PROVIDED)).sum()),
            "divergent": int((exception & divergent(frame)).sum()),
            "explained_by_marstat": int((exception & ~exception_q).sum())}


@check("04", "Distribution analysis", "Examine RWANT and INTENT frequencies.",
       ["RWANT", "INTENT"],
       "Unweighted frequencies compared with the CDC codebook distributions where printed.")
def check_04(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        for column in ("RWANT", "INTENT"):
            observed = counts(frame[column])
            results[f"{sex} {column}"] = observed
            published = CODEBOOK[sex].get(column)
            if published is not None:
                expect.equal(f"{sex} {column} vs codebook",
                             {k: v for k, v in observed.items() if v or k != "missing"},
                             {k: v for k, v in published.items() if v or k != "missing"})
    notes.append("The male codebook's INTENT frequencies could not be read from the PDF "
                 "text, so male INTENT is reported without an external comparison.")
    return expect, results, notes


@check("05", "Cross-tabulation", "Analyse RWANT x INTENT.", ["RWANT", "INTENT"],
       "Unweighted cross-tabulation by sex; divergence is the RWANT = 1, INTENT = 2 cell.")
def check_05(data: AuditData):
    expect, results = Expectations(), {}
    total = 0
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        table = pd.crosstab(frame["RWANT"].fillna(-1).astype(int), frame["INTENT"])
        results[f"{sex} RWANT x INTENT"] = {
            f"RWANT={'missing' if r == -1 else r}": {f"INTENT={c}": int(v)
                                                     for c, v in row.items()}
            for r, row in table.iterrows()}
        cell = int(divergent(frame).sum())
        total += cell
        results[f"{sex} divergence (RWANT=1, INTENT=2)"] = cell
        expect.equal(f"{sex} divergence", cell, EXPECTED["divergence_all_ages"][sex])
    results["combined divergence"] = total
    expect.equal("combined divergence", total, EXPECTED["divergence_all_ages"]["total"])
    return expect, results, []


@check("06", "Age stratification", "Investigate divergence across age groups.",
       ["AGER", "RWANT", "INTENT"],
       "Unweighted divergence among RWANT = 1 by age group and sex; group totals must equal "
       "the all-age totals.")
def check_06(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        rows, divergent_total = {}, 0
        for low, high in AGE_GROUPS:
            group = frame[frame["AGER"].between(low, high) & frame["RWANT"].eq(nsfg.YES)]
            cases = int(group["INTENT"].eq(nsfg.DOES_NOT_INTEND).sum())
            divergent_total += cases
            rows[f"{low}-{high}"] = (f"{cases}/{len(group)} = "
                                     f"{100 * cases / len(group):.1f}%" if len(group) else "0/0")
        results[sex] = rows
        expect.equal(f"{sex} age groups sum to all-age divergence", divergent_total,
                     EXPECTED["divergence_all_ages"][sex])
    notes.append("Descriptive and unweighted; no Stage 3 age-specific values were recorded, "
                 "so only internal consistency is tested. AGER reaches 50 for respondents "
                 "who turned 50 after screening; they are in the 40-50 group.")
    return expect, results, notes


@check("07", "Interview-year decoding", "Verify YEAR = 1 for 2022 and YEAR = 2 for 2023.",
       ["YEAR", "CMINTVW"],
       "YEAR decoded by analysis.nsfg.interview_year; interview century months must fall "
       "within the decoded calendar year; counts compared with the codebook.")
def check_07(data: AuditData):
    expect, results = Expectations(), {}
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        years = nsfg.interview_year(frame["YEAR"])
        for year, (first, last) in nsfg.CMINTVW_RANGES.items():
            months = frame.loc[years == year, "CMINTVW"]
            results[f"{sex} {year} interview months"] = (f"{months.min()}-{months.max()} "
                                                          f"(n {len(months):,})")
            expect.equal(f"{sex} {year} months outside {first}-{last}",
                         int((~months.between(first, last)).sum()), 0)
        expect.equal(f"{sex} YEAR vs codebook", counts(frame["YEAR"]), CODEBOOK[sex]["YEAR"])
    return expect, results, []


@check("08", "CDC recode interpretation", "Validate the official INTENT construction rules.",
       ["INTENT", "RMARIT", "RSTRSTAT", "PSTRSTAT", "JINTEND", "INTEND", "RWANT"],
       "INTENT rebuilt by analysis.nsfg.reconstruct_intent from the female (Section G) and "
       "male (Section H) recode specifications and compared respondent by respondent.")
def check_08(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        rebuilt = nsfg.reconstruct_intent(frame, sex)
        agree = int((rebuilt == frame["INTENT"]).sum())
        results[f"{sex} INTENT reproduced"] = f"{agree:,} of {len(frame):,}"
        expect.equal(f"{sex} INTENT mismatches", len(frame) - agree, 0)
    notes.append("Executable verification covers the implemented rules only. Reading the "
                 "specification text (female recode specs pp. 93-94, male pp. 52-53) is a "
                 "manual review step and is not counted as an automated test.")
    return expect, results, notes


@check("09", "All-age classification",
       "Analyse the original 1,001 divergence cases.",
       ["RWANT", "INTENT", "JINTEND", "INTEND", "RSTRSTAT", "PSTRSTAT"],
       "Divergent respondents of all ages classified as explicit negatives, sterility-linked "
       "or unexplained (analysis.nsfg.classify_intention).")
def check_09(data: AuditData):
    expect, results = Expectations(), {}
    total, unexplained = 0, 0
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        categories = frame.loc[divergent(frame), "category"].value_counts().to_dict()
        results[sex] = {k: int(v) for k, v in categories.items()}
        total += sum(categories.values())
        unexplained += categories.get(nsfg.UNEXPLAINED, 0)
    results["combined"] = total
    expect.equal("combined divergence", total, EXPECTED["divergence_all_ages"]["total"])
    expect.equal("unexplained INTENT=2", unexplained, 0)
    return expect, results, []


@check("10", "Conservative Gen Z proxy", "Reproduce the 2,429-respondent cohort.",
       ["YEAR", "AGER", "RWANT", "INTENT"],
       "Ages 18-26 if interviewed in 2022 (YEAR = 1) and 18-27 in 2023 (YEAR = 2).")
def check_10(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    expected = EXPECTED["cohorts"]["conservative"]
    total, cases = 0, 0
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        members = nsfg.in_cohort(frame, "conservative")
        total += int(members.sum())
        cases += int((members & divergent(frame)).sum())
        results[f"{sex} respondents"] = int(members.sum())
        results[f"{sex} by interview year"] = {
            int(y): int(n) for y, n in nsfg.interview_year(frame.loc[members, "YEAR"])
            .value_counts().sort_index().items()}
        expect.equal(f"{sex} respondents", int(members.sum()), expected[sex])
    results.update({"combined respondents": total, "divergence cases": cases})
    expect.equal("combined respondents", total, expected["total"])
    expect.equal("divergence cases", cases, expected["divergence"])
    notes.append("Age and interview year do not identify birth year; the proxy is "
                 "conservative, not exact.")
    return expect, results, notes


@check("11", "Blank-response audit", "Investigate the 77 blank intention responses.",
       ["RWANT", "INTENT", "JINTEND", "INTEND", "RMARIT"],
       "Conservative cohort, RWANT = 1, INTENT = 2, with neither intention item answered.")
def check_11(data: AuditData):
    expect, results = Expectations(), {}
    total = 0
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        blank = (cohort_domain(frame, "conservative") & frame["INTENT"].eq(nsfg.DOES_NOT_INTEND)
                 & nsfg.intention_item_blank(frame))
        positive_blank = (cohort_domain(frame, "conservative") & frame["INTENT"].eq(nsfg.INTENDS)
                          & nsfg.intention_item_blank(frame))
        total += int(blank.sum())
        results[sex] = {"blank with INTENT=2": int(blank.sum()),
                        "by RMARIT (0 neither, 1 married, 2 cohabiting)":
                            counts(frame.loc[blank, "RMARIT"]),
                        "blank with INTENT=1": int(positive_blank.sum())}
        expect.equal(f"{sex} blank with INTENT=1", int(positive_blank.sum()), 0)
    results["combined"] = total
    expect.equal("blank intention responses", total,
                 EXPECTED["cohorts"]["conservative"]["sterility"])
    return expect, results, []


@check("12", "Reproductive status", "Analyse RSTRSTAT, PSTRSTAT, FECUND and STRLOPER.",
       ["RSTRSTAT", "PSTRSTAT", "FECUND", "STRLOPER"],
       "Distributions among the blank-response cases; every female case must have a sterile "
       "FECUND status (codes 1-3).")
def check_12(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        blank = (cohort_domain(frame, "conservative") & frame["INTENT"].eq(nsfg.DOES_NOT_INTEND)
                 & nsfg.intention_item_blank(frame))
        cases = frame[blank]
        summary = {"RSTRSTAT": counts(cases["RSTRSTAT"]), "PSTRSTAT": counts(cases["PSTRSTAT"])}
        if sex == "female":
            summary.update({"FECUND": counts(cases["FECUND"]),
                            "STRLOPER": counts(cases["STRLOPER"])})
            expect.equal("female cases without a sterile FECUND status",
                         int((~cases["FECUND"].isin([1, 2, 3])).sum()), 0)
        results[sex] = summary
    notes.append("RSTRSTAT/PSTRSTAT: 0 not sterile, 1 surgically, 2 nonsurgically sterile. "
                 "FECUND: 1-2 surgically sterile, 3 nonsurgically sterile. STRLOPER: 1 tubal, "
                 "2 hysterectomy, 3 vasectomy, 4 other female operation, 5 none. FECUND and "
                 "STRLOPER exist only in the female file.")
    return expect, results, notes


@check("13", "Sterility verification", "Confirm all 77 cases have a sterility link.",
       ["RSTRSTAT", "PSTRSTAT"],
       "Each blank-response case must have RSTRSTAT != 0 or PSTRSTAT in {1, 2}.")
def check_13(data: AuditData):
    expect, results = Expectations(), {}
    linked_total, total = 0, 0
    for sex in nsfg.SEXES:
        frame = data.frame(sex)
        blank = (cohort_domain(frame, "conservative") & frame["INTENT"].eq(nsfg.DOES_NOT_INTEND)
                 & nsfg.intention_item_blank(frame))
        linked = blank & nsfg.sterility_link(frame)
        own = blank & frame["RSTRSTAT"].ne(0)
        results[sex] = {"cases": int(blank.sum()), "sterility-linked": int(linked.sum()),
                        "own sterility": int(own.sum()),
                        "partner sterility only": int((linked & ~own).sum())}
        linked_total += int(linked.sum())
        total += int(blank.sum())
    results["combined"] = f"{linked_total}/{total}"
    expect.equal("cases with a sterility link", linked_total, total)
    expect.equal("cases", total, EXPECTED["cohorts"]["conservative"]["sterility"])
    return expect, results, []


@check("14", "Boundary sensitivity", "Compare the conservative and inclusive cohorts.",
       ["YEAR", "AGER", "RWANT", "INTENT"],
       "Inclusive cohort: ages 18-27 in 2022 and 18-28 in 2023. Counts compared, and the "
       "conservative cohort must be a subset.")
def check_14(data: AuditData):
    expect, results = Expectations(), {}
    for cohort in nsfg.COHORTS:
        tally = {"respondents": 0, "RWANT=1": 0, "divergence": 0, "explicit": 0, "sterility": 0}
        for sex in nsfg.SEXES:
            frame = data.frame(sex)
            members = nsfg.in_cohort(frame, cohort)
            domain = members & frame["RWANT"].eq(nsfg.YES)
            tally["respondents"] += int(members.sum())
            tally["RWANT=1"] += int(domain.sum())
            tally["divergence"] += int((domain & frame["INTENT"].eq(2)).sum())
            tally["explicit"] += int((domain & frame["category"].eq(nsfg.EXPLICIT_NEGATIVE)).sum())
            tally["sterility"] += int((domain & frame["category"].eq(nsfg.STERILITY_LINKED)).sum())
            if cohort == "inclusive":
                outside = nsfg.in_cohort(frame, "conservative") & ~members
                expect.equal(f"{sex} conservative members outside inclusive", int(outside.sum()), 0)
        results[cohort] = tally
        expected = EXPECTED["cohorts"][cohort]
        expect.equal(f"{cohort} respondents", tally["respondents"], expected["total"])
        for key in ("divergence", "explicit", "sterility"):
            expect.equal(f"{cohort} {key}", tally[key], expected[key])
    return expect, results, []


@check("15", "Survey weighting", "Calculate weighted descriptive estimates.",
       [nsfg.WEIGHT, nsfg.STRATUM, nsfg.CLUSTER, "RWANT", "INTENT"],
       "Weighted share with INTENT = 2 among RWANT = 1 in each cohort, both sexes pooled, "
       "Taylor-linearization SE over the full design (domain estimation).")
def check_15(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    pooled = data.pooled
    for sex in nsfg.SEXES:
        total = data.frame(sex)[nsfg.WEIGHT].sum()
        results[f"{sex} weight total"] = f"{total:,.1f}"
        expect.near(f"{sex} weight total (millions)", total / 1e6, POPULATION_MILLIONS[sex], 1)
    for cohort in nsfg.COHORTS:
        estimate = nsfg.weighted_share(pooled, pooled["divergence"], cohort_domain(pooled, cohort))
        results[f"{cohort} divergence"] = pct(estimate)
        if cohort == "conservative":
            point, se = EXPECTED["weighted_pct"]["divergence"]
            expect.near("divergence %", 100 * estimate.estimate, point, 2)
            expect.near("divergence SE", 100 * estimate.se, se, 2)
    notes.append("Weighted to the household population aged 15-49 represented by each file; "
                 "the pooled estimate covers women and men together. See Check 19 for the "
                 "pooled-design assumption.")
    return expect, results, notes


@check("16", "Outcome decomposition",
       "Separate explicit negatives from sterility-linked cases.",
       ["RWANT", "INTENT", "JINTEND", "INTEND", "RSTRSTAT", "PSTRSTAT", nsfg.WEIGHT],
       "Conservative cohort, RWANT = 1: unweighted category counts and weighted shares of "
       "explicit and sterility-linked divergence (linearization SEs).")
def check_16(data: AuditData):
    expect, results = Expectations(), {}
    pooled = data.pooled
    domain = cohort_domain(pooled, "conservative")
    breakdown = pooled.loc[domain, "category"].value_counts()
    observed = {category: int(breakdown.get(category, 0)) for category in nsfg.CATEGORIES}
    results["unweighted, RWANT=1"] = observed
    results["denominator"] = int(domain.sum())
    expect.equal("denominator", int(domain.sum()), EXPECTED["primary_denominator"])
    expect.equal("category counts", observed, EXPECTED["primary_breakdown"])
    shares = {}
    for key in ("divergence", "explicit", "sterility"):
        shares[key] = nsfg.weighted_share(pooled, pooled[key], domain)
        results[f"weighted {key}"] = pct(shares[key])
        point, se = EXPECTED["weighted_pct"][key]
        expect.near(f"{key} %", 100 * shares[key].estimate, point, 2)
        expect.near(f"{key} SE", 100 * shares[key].se, se, 2)
    gap = shares["divergence"].estimate - shares["explicit"].estimate - shares["sterility"].estimate
    expect.near("explicit + sterility - divergence", gap, 0.0, 12)
    return expect, results, []


@check("17", "Taylor linearization",
       "Reproduce the CDC benchmark and design-adjusted standard errors.",
       ["AGER", "CONSTAT1", nsfg.WEIGHT, nsfg.STRATUM, nsfg.CLUSTER],
       "Project linearization (analysis.survey_design.linearized_mean) for women using the "
       "pill (CONSTAT1 = 6) by AGER group, compared with CDC variance estimation example 1.")
def check_17(data: AuditData):
    expect, results = Expectations(), {}
    female = data.female
    design = nsfg.survey_design_table(female)
    results["design"] = (f"{design['stratum'].nunique()} strata, {len(design)} clusters, "
                         f"df {sd.design_degrees_of_freedom(design)}")
    expect.equal("strata", design["stratum"].nunique(), CDC_DESIGN["strata"])
    expect.equal("clusters", len(design), CDC_DESIGN["clusters"])
    expect.equal("design df", sd.design_degrees_of_freedom(design), CDC_DESIGN["df"])
    expect.near("female weight sum", female[nsfg.WEIGHT].sum(), CDC_DESIGN["female_weight_sum"], 1)
    pill = female["CONSTAT1"].eq(6)
    for (low, high), published in CDC_BENCHMARK.items():
        estimate = nsfg.weighted_share(female, pill, female["AGER"].between(low, high), design)
        results[f"ages {low}-{high}"] = (f"{100 * estimate.estimate:.4f}% (SE "
                                         f"{100 * estimate.se:.4f} pp, n {estimate.n})")
        expect.equal(f"{low}-{high} n", estimate.n, published["n"])
        expect.near(f"{low}-{high} %", 100 * estimate.estimate, published["pct"], 4)
        expect.near(f"{low}-{high} SE", 100 * estimate.se, published["se"], 4)
    return expect, results, []


@check("18", "Independent verification",
       "Validate the estimates with Python's svy library.",
       [nsfg.WEIGHT, nsfg.STRATUM, nsfg.CLUSTER],
       "svy Taylor estimates of the CDC benchmark, the Check 15-16 shares and the Check 19 "
       "contrasts, compared with the project implementation (tolerance 1e-9).")
def check_18(data: AuditData):
    try:
        import polars as pl
        import svy
    except ImportError as error:
        raise DependencyUnavailable(f"svy is not installed ({error})") from error
    expect, results = Expectations(), {}
    tolerance = 1e-9

    def sample(frame: pd.DataFrame, columns: list[str]):
        return svy.Sample(pl.from_pandas(frame[columns]),
                          svy.Design(stratum=nsfg.STRATUM, psu=nsfg.CLUSTER, wgt=nsfg.WEIGHT))

    female = data.female.assign(pill=data.female["CONSTAT1"].eq(6).astype(float),
                                age20_24=data.female["AGER"].between(20, 24))
    row = sample(female, ["pill", "age20_24", *nsfg.DESIGN_COLUMNS]).estimation.mean(
        "pill", where=pl.col("age20_24")).to_dicts()[0]
    ours = nsfg.weighted_share(female, female["pill"].astype(bool), female["age20_24"])
    results["CDC benchmark (svy)"] = (f"{100 * row['est']:.4f}% (SE {100 * row['se']:.4f} pp, "
                                      f"df {row['df']})")
    expect.near("benchmark estimate, svy vs project", row["est"], ours.estimate, 9)
    expect.near("benchmark SE, svy vs project", row["se"], ours.se, 9)

    pooled = data.pooled
    largest = 0.0
    for cohort in nsfg.COHORTS:
        domain = cohort_domain(pooled, cohort)
        frame = pooled.assign(domain=domain, **{k: pooled[k].astype(float) for k in MEASURES})
        design_sample = sample(frame, [*MEASURES, "domain", "sex", *nsfg.DESIGN_COLUMNS])
        for key in MEASURES:
            overall = design_sample.estimation.mean(key, where=pl.col("domain")).to_dicts()[0]
            ours = nsfg.weighted_share(pooled, pooled[key], domain)
            by_sex = design_sample.estimation.mean(key, by="sex", where=pl.col("domain"))
            contrast = by_sex.contrast({"female": 1, "male": -1}).to_dicts()[0]
            mine = nsfg.sex_contrast(pooled, pooled[key], domain)
            differences = [abs(overall["est"] - ours.estimate), abs(overall["se"] - ours.se),
                           abs(contrast["est"] - mine.difference), abs(contrast["se"] - mine.se),
                           abs(contrast["p_value"] - mine.p_value)]
            largest = max(largest, *differences)
            results[f"{cohort} {key}"] = (f"share {100 * overall['est']:.2f}% (SE "
                                          f"{100 * overall['se']:.2f}); female - male "
                                          f"{100 * contrast['est']:+.2f} (SE "
                                          f"{100 * contrast['se']:.2f}, p "
                                          f"{contrast['p_value']:.4f})")
    results["largest absolute difference, svy vs project"] = f"{largest:.2e}"
    if largest > tolerance:
        expect.failures.append(f"svy and project differ by {largest:.2e}")
    return expect, results, []


@check("19", "Sex comparisons",
       "Calculate survey-design-aware female-male contrasts.",
       ["sex", "RWANT", "INTENT", nsfg.WEIGHT, nsfg.STRATUM, nsfg.CLUSTER],
       "Female minus male weighted shares in a pooled design (shared VEST/VECL), "
       "linearization SE of the difference, t interval and p-value on the design df; the "
       "independent-samples SE is computed as a sensitivity analysis; the shared design is "
       "established from the CDC sample-design documentation.")
def check_19(data: AuditData):
    expect, results, notes = Expectations(), {}, []
    pooled = data.pooled
    design = nsfg.survey_design_table(pooled)
    df = sd.design_degrees_of_freedom(design)
    results["pooled design"] = (f"{design['stratum'].nunique()} strata, {len(design)} "
                                f"clusters, df {df}; identical VEST/VECL pairs in both files")
    expect.equal("pooled design df", df, CDC_DESIGN["df"])
    ratios, decisions_agree = [], True
    for cohort in nsfg.COHORTS:
        domain = cohort_domain(pooled, cohort)
        for key in MEASURES:
            result = nsfg.sex_contrast(pooled, pooled[key], domain)
            ratio = result.se / result.independent_se
            ratios.append(ratio)
            independent_p = 2 * stats.t.sf(abs(result.difference / result.independent_se), df)
            decisions_agree &= (result.p_value < 0.05) == (independent_p < 0.05)
            results[f"{cohort} {key}"] = (
                f"female {100 * result.female.estimate:.2f}%, male "
                f"{100 * result.male.estimate:.2f}%, difference "
                f"{100 * result.difference:+.2f} pp (SE {100 * result.se:.2f}; "
                f"95% CI [{100 * result.ci[0]:.2f}, {100 * result.ci[1]:.2f}]; "
                f"p {result.p_value:.4f}); independent SE {100 * result.independent_se:.2f}")
            expect.near(f"{cohort} {key} p", result.p_value, EXPECTED["contrast_p"][cohort][key], 4)
            if cohort == "conservative" and key == "divergence":
                primary = EXPECTED["sex_contrast"]
                expect.near("female %", 100 * result.female.estimate, primary["female"], 2)
                expect.near("male %", 100 * result.male.estimate, primary["male"], 2)
                expect.near("difference", 100 * result.difference, primary["difference"], 2)
                expect.near("difference SE", 100 * result.se, primary["se"], 2)
                expect.near("CI lower", 100 * result.ci[0], primary["ci"][0], 2)
                expect.near("CI upper", 100 * result.ci[1], primary["ci"][1], 2)
    results["pooled / independent SE ratio"] = f"{min(ratios):.3f}-{max(ratios):.3f}"
    results["same conclusions at 0.05 with independent SEs"] = decisions_agree
    within = SE_RATIO_LIMITS[0] <= min(ratios) and max(ratios) <= SE_RATIO_LIMITS[1]
    if not (within and decisions_agree):
        expect.failures.append("pooled and independent-sample inference disagree")
    for sex in nsfg.SEXES:
        own = nsfg.survey_design_table(data.frame(sex))
        expect.equal(f"{sex} file strata / clusters",
                     (own["stratum"].nunique(), len(own)),
                     (CDC_DESIGN["strata"], CDC_DESIGN["clusters"]))
    notes.append("Design basis (documentation, not numerical agreement): the 2022-2023 NSFG is "
                 "one area probability sample in which one eligible person, female or male, "
                 "was selected per screened household within the same sampled segments "
                 "(User's Guide, Survey and Sample Design, pp. 13-14); WGT2022_2023 is the "
                 "weight for 'the 2022-2023 NSFG sample of 4,371 male and 5,586 female "
                 "respondents', to be used with VEST and VECL (FAQ 7; User's Guide p. 17); the "
                 "sampling variance is defined for the 9,957 respondents representing 150.6 "
                 "million women and men (User's Guide p. 18); and VEST/VECL were formed once "
                 "from PSUs and segments, not by sex (Variance Estimation Report, section 2). "
                 "Both files carry the same 20 strata and 80 clusters, so the stacked file is "
                 "the full sample and each sex is a domain of it.")
    notes.append("CDC publishes no worked female-male pooled example; the separate-file "
                 "(independent samples) SEs are kept as a sensitivity analysis and give the "
                 "same conclusions.")
    return expect, results, notes, False


# --------------------------------------------------------------- runner

def run_check(check_id: str, data: AuditData) -> CheckResult:
    title, objective, variables, calculation, function = CHECKS[check_id]
    base = {"check_id": check_id, "title": title, "objective": objective,
            "variables": variables, "calculation": calculation}
    try:
        outcome = function(data)
    except (DataUnavailable, FileNotFoundError, DependencyUnavailable) as error:
        return CheckResult(**base, status=SKIP, notes=[str(error)])
    expect, results, notes, *warn = outcome
    status = expect.status(warn=bool(warn and warn[0]))
    return CheckResult(**base, status=status, results=results,
                       notes=[*expect.failures, *notes])


def format_value(value, indent: int) -> list[str]:
    pad = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, dict):
                lines += [f"{pad}{key}:", *format_value(item, indent + 2)]
            else:
                lines.append(f"{pad}{key}: {item}")
        return lines
    return [f"{pad}{value}"]


def format_result(result: CheckResult) -> str:
    header = f"[{result.check_id}] {result.title} "
    lines = [header + "." * max(3, 70 - len(header)) + f" {result.status}",
             f"  Objective: {result.objective}",
             f"  Variables: {', '.join(result.variables)}",
             f"  Calculation: {result.calculation}"]
    if result.results:
        lines += ["  Results:", *format_value(result.results, 4)]
    lines += [f"  Note: {note}" for note in result.notes]
    return "\n".join(lines)


def run(check_ids: list[str], data: AuditData) -> list[CheckResult]:
    return [run_check(check_id, data) for check_id in check_ids]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NSFG 2022-2023 Stage 3 validation checks.")
    parser.add_argument("--check", action="append", metavar="ID",
                        help="run one check, e.g. 17 (repeatable)")
    parser.add_argument("--require-data", action="store_true",
                        help="exit with an error instead of SKIP if a dataset is missing")
    parser.add_argument("--list", action="store_true", help="list the registered checks")
    args = parser.parse_args(argv)

    if args.list:
        for check_id, (title, objective, *_rest) in CHECKS.items():
            print(f"{check_id}  {title}: {objective}")
        return 0
    ids = sorted(CHECKS) if not args.check else [c.zfill(2) for c in args.check]
    unknown = [c for c in ids if c not in CHECKS]
    if unknown:
        parser.error(f"unknown check id(s): {', '.join(unknown)}")
    data = AuditData()
    if args.require_data and not data.available():
        print("NSFG data required but missing: " + "; ".join(data.missing()), file=sys.stderr)
        return 2

    results = run(ids, data)
    print("NSFG 2022-2023 | STAGE 3 VALIDATION")
    print("=" * 74)
    for result in results:
        print(format_result(result) + "\n")
    tally = {status: sum(r.status == status for r in results) for status in (PASS, WARN, FAIL,
                                                                             SKIP)}
    print("Summary: " + ", ".join(f"{k} {v}" for k, v in tally.items()))
    if tally[FAIL] or (args.require_data and tally[SKIP]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
