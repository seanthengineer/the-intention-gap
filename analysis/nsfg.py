"""NSFG 2022-2023 desire, intention and sterility measures for the Stage 3 validation.

Definitions follow the CDC 2022-2023 NSFG public-use documentation
(data/raw/nsfg_2022_2023/documentation/):

- RWANT (female GA-1, male HA-2): wants a(nother) baby some time.
  1 yes, 5 no, 8 refused, 9 don't know.
- JINTEND (GB-1 / HB-2): joint intention, asked of married or cohabiting
  respondents when neither partner is sterile. 1 yes, 5 no.
- INTEND (GC-1 / HC-2): individual intention, asked of other respondents who
  are not sterile and want, or do not know whether they want, a(nother) baby.
  Women: 1 yes, 5 no. Men: 1-2 yes (definitely, probably), 3-4 no.
- INTENT: CDC recode. 1 intends, 2 does not intend, 3 does not know,
  4 did not provide. INTENT = 2 is assigned to respondents who, or whose
  current partner, are sterile (RSTRSTAT, PSTRSTAT), without asking the
  intention question.

Desire-intention divergence is RWANT = 1 with INTENT = 2. Divergent cases are
split into explicit negatives (the respondent answered the intention
question "no") and sterility-linked cases (the question was not asked
because of sterility), which are not voluntary choices.

The Gen Z proxies use age at interview and interview year. Neither
identifies birth year exactly. Estimation uses WGT2022_2023 with VEST
strata and VECL clusters (Taylor linearization). Only aggregates are
produced.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from analysis import survey_design as sd
from analysis.nlsy97 import PROJECT_ROOT

NSFG_DIR = PROJECT_ROOT / "data" / "raw" / "nsfg_2022_2023"
DATA_PATHS = {
    "female": NSFG_DIR / "female" / "NSFG_2022_2023_FemRespPUFData.csv",
    "male": NSFG_DIR / "male" / "NSFG_2022_2023_MaleRespPUFData.csv",
}
SEXES = ("female", "male")

WEIGHT, STRATUM, CLUSTER = "WGT2022_2023", "VEST", "VECL"
DESIGN_COLUMNS = [WEIGHT, STRATUM, CLUSTER]
INTENTION_COLUMNS = ["RWANT", "JINTEND", "INTEND", "INTENT"]
STATUS_COLUMNS = ["RMARIT", "RSTRSTAT", "PSTRSTAT"]
AGE_COLUMNS = ["AGER", "YEAR", "CMINTVW"]
FEMALE_ONLY_COLUMNS = ["FECUND", "STRLOPER", "CONSTAT1"]
COMMON_COLUMNS = [*AGE_COLUMNS, *INTENTION_COLUMNS, *STATUS_COLUMNS, *DESIGN_COLUMNS]

YES, NO, REFUSED, DONT_KNOW = 1, 5, 8, 9
INTENDS, DOES_NOT_INTEND, DOES_NOT_KNOW, NOT_PROVIDED = 1, 2, 3, 4
MARRIED_OR_COHABITING = (1, 2)
INTEND_YES = {"female": (1,), "male": (1, 2)}
INTEND_NO = {"female": (5,), "male": (3, 4)}

# YEAR codes and the century-month range of interviews in each year (codebook).
INTERVIEW_YEARS = {1: 2022, 2: 2023}
CMINTVW_RANGES = {2022: (1465, 1476), 2023: (1477, 1488)}

# Inclusive age ranges at interview, by interview year.
COHORTS = {
    "conservative": {2022: (18, 26), 2023: (18, 27)},
    "inclusive": {2022: (18, 27), 2023: (18, 28)},
}

# Additional M09 measures (CDC codebooks and recode specifications, 2022-2023).
# PARITY (women) and ADDEXP (both sexes) are imputed recodes; EVBIOKID and
# NUMBIOKID (men, FA-1 / FA-2) are raw items; the remaining columns are recodes.
SHARED_ANALYSIS_COLUMNS = ["MARSTAT", "EVRMARRY", "ADDEXP", "ADDEXP_I", "INTENDN", "JINTENDN",
                           "PROBWANT", "CURRPREG", "HIEDUC", "HISPRACE2", "POVERTY",
                           "LABORFOR", "METRO", "RELIGION", "CURR_INS", "NUMKDHH"]
SEX_ANALYSIS_COLUMNS = {"female": ["PARITY"], "male": ["HADSEX", "EVBIOKID", "NUMBIOKID"]}
NUMBER_NOT_GIVEN = (97, 98, 99)  # INTENDN / JINTENDN / NUMBIOKID refused or don't know

VALID_CODES = {
    "RWANT": {1, 5, 8, 9}, "INTENT": {1, 2, 3, 4}, "RMARIT": {0, 1, 2}, "YEAR": {1, 2},
    "HIEDUC": set(range(1, 12)), "HISPRACE2": {1, 2, 3, 4}, "LABORFOR": set(range(1, 8)),
    "METRO": {1, 2, 3}, "RELIGION": {1, 2, 3, 4}, "CURR_INS": {1, 2, 3, 4},
    "EVRMARRY": {0, 1}, "ADDEXP_I": {0, 1, 2}, "HADSEX": {1, 2}, "EVBIOKID": {1, 5, 8, 9},
}

PARTNERSHIP = {0: "neither", 1: "married", 2: "cohabiting"}
EDUCATION = [((1, 2), "less than high school"), ((3, 4), "high school or GED"),
             ((5, 7), "some college or associate"), ((8, 11), "bachelor's or higher")]
RACE_ETHNICITY = {1: "Hispanic", 2: "non-Hispanic White", 3: "non-Hispanic Black",
                  4: "non-Hispanic other or multiple"}
POVERTY_GROUPS = [((0, 99), "below 100% of poverty"), ((100, 199), "100-199%"),
                  ((200, 399), "200-399%"), ((400, 700), "400% or more")]
LABOR_FORCE = {1: "working", 2: "working", 3: "working", 4: "looking for work",
               5: "in school", 6: "caring for home or family", 7: "other"}
METRO_LABELS = {1: "principal city", 2: "other metropolitan", 3: "nonmetropolitan"}
RELIGION_LABELS = {1: "no religion", 2: "Catholic", 3: "Protestant", 4: "other religion"}
INSURANCE = {1: "private", 2: "Medicaid or state plan", 3: "other government",
             4: "uninsured or single-service"}
AGE_GROUPS = [((18, 21), "18-21"), ((22, 24), "22-24"), ((25, 28), "25 or older")]
CHILDREN_GROUPS = ["no children", "one child", "two or more"]

POSITIVE = "positive intention"
EXPLICIT_NEGATIVE = "explicit negative"
STERILITY_LINKED = "sterility-linked"
UNKNOWN = "unknown intention"
NOT_PROVIDED_OR_OTHER = "not provided or other"
UNEXPLAINED = "unexplained INTENT=2"
CATEGORIES = (POSITIVE, EXPLICIT_NEGATIVE, STERILITY_LINKED, UNKNOWN, NOT_PROVIDED_OR_OTHER,
              UNEXPLAINED)


# ------------------------------------------------------------------ data

def data_available() -> bool:
    return all(path.exists() for path in DATA_PATHS.values())


def file_dimensions(path: Path) -> tuple[int, int]:
    """Rows (excluding the header) and columns of a CSV file, read as text."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        columns = len(next(reader))
        rows = sum(1 for _ in reader)
    return rows, columns


def load_respondents(sex: str, columns: list[str] | None = None,
                     path: Path | None = None) -> pd.DataFrame:
    """One respondent file, restricted to the requested columns."""
    path = DATA_PATHS[sex] if path is None else Path(path)
    if not path.exists():
        raise FileNotFoundError(f"NSFG {sex} file not found: {path}")
    wanted = COMMON_COLUMNS + (FEMALE_ONLY_COLUMNS if sex == "female" else [])
    columns = wanted if columns is None else columns
    available = set(pd.read_csv(path, nrows=0).columns)
    missing = [c for c in columns if c not in available]
    if missing:
        raise KeyError(f"NSFG {sex} file lacks columns: {missing}")
    return pd.read_csv(path, usecols=columns)


def pooled_respondents(female: pd.DataFrame, male: pd.DataFrame) -> pd.DataFrame:
    """Both files stacked with a sex column; the design codes must coincide."""
    pairs = [set(map(tuple, frame[[STRATUM, CLUSTER]].drop_duplicates().to_numpy()))
             for frame in (female, male)]
    if pairs[0] != pairs[1]:
        raise ValueError("Female and male files use different VEST/VECL codes")
    return pd.concat([female.assign(sex="female"), male.assign(sex="male")],
                     ignore_index=True, sort=False)


# ---------------------------------------------------------- definitions

def interview_year(year_code: pd.Series) -> pd.Series:
    """Calendar year of interview from YEAR (1 = 2022, 2 = 2023)."""
    unknown = ~year_code.isin(list(INTERVIEW_YEARS))
    if unknown.any():
        raise ValueError(f"Unexpected YEAR codes: {sorted(year_code[unknown].unique())}")
    return year_code.map(INTERVIEW_YEARS)


def in_cohort(frame: pd.DataFrame, cohort: str) -> pd.Series:
    """Respondents inside the age range for their interview year."""
    years = interview_year(frame["YEAR"])
    keep = pd.Series(False, index=frame.index)
    for year, (low, high) in COHORTS[cohort].items():
        keep |= (years == year) & frame["AGER"].between(low, high)
    return keep


def intention_item_blank(frame: pd.DataFrame) -> pd.Series:
    """Neither the joint nor the individual intention question was answered."""
    return frame["JINTEND"].isna() & frame["INTEND"].isna()


def sterility_link(frame: pd.DataFrame) -> pd.Series:
    """Respondent or current partner sterile at interview (RSTRSTAT, PSTRSTAT)."""
    return frame["RSTRSTAT"].fillna(0).ne(0) | frame["PSTRSTAT"].isin([1, 2])


def explicit_negative_answer(frame: pd.DataFrame, sex: pd.Series | str) -> pd.Series:
    """The joint or individual intention question was answered 'no'."""
    sexes = pd.Series(sex, index=frame.index) if isinstance(sex, str) else sex
    individual = pd.Series(False, index=frame.index)
    for name, codes in INTEND_NO.items():
        individual |= (sexes == name) & frame["INTEND"].isin(codes)
    return frame["JINTEND"].eq(NO) | individual


def classify_intention(frame: pd.DataFrame, sex: pd.Series | str) -> pd.Series:
    """Mutually exclusive intention category for every respondent."""
    intent = frame["INTENT"]
    negative = intent.eq(DOES_NOT_INTEND)
    explicit = negative & explicit_negative_answer(frame, sex)
    sterility = negative & ~explicit & intention_item_blank(frame) & sterility_link(frame)
    return pd.Series(np.select(
        [intent.eq(INTENDS), explicit, sterility, negative, intent.eq(DOES_NOT_KNOW)],
        [POSITIVE, EXPLICIT_NEGATIVE, STERILITY_LINKED, UNEXPLAINED, UNKNOWN],
        NOT_PROVIDED_OR_OTHER), index=frame.index)


def reconstruct_intent(frame: pd.DataFrame, sex: str) -> pd.Series:
    """INTENT rebuilt from the CDC 2022-2023 recode specifications.

    Female specification (Section G recodes): INTENT = 2 if the respondent or
    her current partner is sterile. Male specification (Section H): for
    married or cohabiting men, either partner sterile; for other men, his
    own sterility with the intention item missing. Otherwise the joint item
    applies to married or cohabiting respondents and the individual item to
    others; a missing individual item with RWANT = 5 or 8 gives INTENT = 2.
    Don't know gives 3 and refused or not ascertained gives 4.
    """
    married = frame["RMARIT"].isin(MARRIED_OR_COHABITING)
    self_sterile = frame["RSTRSTAT"].fillna(0).ne(0)
    partner_sterile = married & frame["PSTRSTAT"].isin([1, 2])
    fertile = ~self_sterile & ~partner_sterile
    joint, single = frame["JINTEND"], frame["INTEND"]
    if sex == "female":
        sterile = self_sterile | partner_sterile
    else:
        sterile = (married & (self_sterile | partner_sterile)) | (~married & self_sterile
                                                                  & single.isna())
    item = joint.where(married, single)
    yes = np.where(married, joint.eq(YES), single.isin(INTEND_YES[sex]))
    no = np.where(married, joint.eq(NO), single.isin(INTEND_NO[sex])
                  | (single.isna() & frame["RWANT"].isin([NO, REFUSED])))
    return pd.Series(np.select(
        [sterile, fertile & yes, fertile & no, item.eq(DONT_KNOW)],
        [DOES_NOT_INTEND, INTENDS, DOES_NOT_INTEND, DOES_NOT_KNOW], NOT_PROVIDED),
        index=frame.index)


# -------------------------------------------------------- M09 constructs

def analysis_columns(sex: str) -> list[str]:
    extra = [*SHARED_ANALYSIS_COLUMNS, *SEX_ANALYSIS_COLUMNS[sex]]
    base = COMMON_COLUMNS + (FEMALE_ONLY_COLUMNS if sex == "female" else [])
    return base + [c for c in extra if c not in base]


def validate_codes(frame: pd.DataFrame) -> None:
    """Raise if a coded column holds a value outside its documented domain."""
    problems = {}
    for column, codes in VALID_CODES.items():
        if column in frame:
            extra = sorted(set(frame[column].dropna().astype(int)) - codes)
            if extra:
                problems[column] = extra
    if problems:
        raise ValueError(f"Codes outside the documented domains: {problems}")


def _banded(values: pd.Series, bands: list[tuple[tuple[int, int], str]]) -> pd.Series:
    labels = pd.Series(pd.NA, index=values.index, dtype="object")
    for (low, high), label in bands:
        labels[values.between(low, high)] = label
    return labels


def children_ever_born(frame: pd.DataFrame, sex: str) -> pd.Series:
    """Live births (women, PARITY) or biological children fathered (men, FA-1/FA-2).

    Men who never had sex (HADSEX = 2) or never fathered a child (EVBIOKID = 5)
    have zero; refused or unknown answers are missing.
    """
    if sex == "female":
        return frame["PARITY"].astype(float)
    count = frame["NUMBIOKID"].where(~frame["NUMBIOKID"].isin(NUMBER_NOT_GIVEN))
    none = frame["HADSEX"].eq(2) | frame["EVBIOKID"].eq(NO)
    return count.where(~none, 0.0).where(frame["EVBIOKID"].isin([YES, NO]) | none)


def intended_number(frame: pd.DataFrame) -> pd.Series:
    """Number of (more) children intended, asked of intenders (JINTENDN or INTENDN)."""
    married = frame["RMARIT"].isin(MARRIED_OR_COHABITING)
    number = frame["JINTENDN"].where(married, frame["INTENDN"])
    return number.where(frame["INTENT"].eq(INTENDS) & ~number.isin(NUMBER_NOT_GIVEN))


def derive_constructs(frame: pd.DataFrame, sex: str) -> pd.DataFrame:
    """Harmonized M09 measures for one respondent file (adds columns, keeps rows)."""
    validate_codes(frame)
    out = frame.copy()
    out["sex"] = sex
    out["category"] = classify_intention(out, sex)
    out["wants"] = out["RWANT"].eq(YES)
    out["intends"] = out["INTENT"].eq(INTENDS)
    out["divergence"] = out["wants"] & out["INTENT"].eq(DOES_NOT_INTEND)
    out["explicit"] = out["category"].eq(EXPLICIT_NEGATIVE)
    out["sterility"] = out["category"].eq(STERILITY_LINKED)
    out["intention_branch"] = np.where(out["RMARIT"].isin(MARRIED_OR_COHABITING),
                                       "joint", "individual")
    out["partnership"] = out["RMARIT"].map(PARTNERSHIP)
    out["education"] = _banded(out["HIEDUC"], EDUCATION)
    out["race_ethnicity"] = out["HISPRACE2"].map(RACE_ETHNICITY)
    out["poverty_group"] = _banded(out["POVERTY"], POVERTY_GROUPS)
    out["labor_force"] = out["LABORFOR"].map(LABOR_FORCE)
    out["metro"] = out["METRO"].map(METRO_LABELS)
    out["religion"] = out["RELIGION"].map(RELIGION_LABELS)
    out["insurance"] = out["CURR_INS"].map(INSURANCE)
    out["age_group"] = _banded(out["AGER"], AGE_GROUPS)
    out["interview_year"] = interview_year(out["YEAR"])
    out["children"] = children_ever_born(out, sex)
    out["children_group"] = pd.cut(out["children"], [-0.5, 0.5, 1.5, np.inf],
                                   labels=CHILDREN_GROUPS).astype("object")
    out["any_children"] = out["children"].gt(0).where(out["children"].notna())
    out["expected_additional"] = out["ADDEXP"] / 10
    out["intended_number"] = intended_number(out)
    out["cluster"] = out[STRATUM] * 10 + out[CLUSTER]
    return out


def load_analysis_frame(sex: str, path: Path | None = None) -> pd.DataFrame:
    return derive_constructs(load_respondents(sex, analysis_columns(sex), path), sex)


def analysis_sample(paths: dict[str, Path] | None = None) -> pd.DataFrame:
    """Both files with the M09 constructs, stacked on the shared design."""
    paths = DATA_PATHS if paths is None else paths
    female, male = (load_analysis_frame(sex, paths[sex]) for sex in SEXES)
    return pooled_respondents(female.drop(columns="sex"), male.drop(columns="sex"))


# ------------------------------------------------------------ estimation

@dataclass(frozen=True)
class DesignEstimate:
    estimate: float
    se: float
    n: int
    df: int


@dataclass(frozen=True)
class Contrast:
    female: DesignEstimate
    male: DesignEstimate
    difference: float
    se: float
    ci: tuple[float, float]
    p_value: float
    df: int
    independent_se: float


def survey_design_table(frame: pd.DataFrame) -> pd.DataFrame:
    return sd.design_table(frame[STRATUM].to_numpy(), frame[CLUSTER].to_numpy())


def weighted_share(frame: pd.DataFrame, indicator: pd.Series, domain: pd.Series,
                   design: pd.DataFrame | None = None) -> DesignEstimate:
    """Weighted share of the indicator within a domain, using the full design."""
    design = survey_design_table(frame) if design is None else design
    estimate, se = sd.linearized_mean(
        indicator.astype(float).to_numpy(), frame[WEIGHT].to_numpy(),
        frame[STRATUM].to_numpy(), frame[CLUSTER].to_numpy(), design,
        domain.to_numpy(dtype=bool))
    return DesignEstimate(estimate, se, int(domain.sum()), sd.design_degrees_of_freedom(design))


def sex_contrast(pooled: pd.DataFrame, indicator: pd.Series, domain: pd.Series,
                 alpha: float = 0.05) -> Contrast:
    """Female minus male weighted share, with a pooled-design t interval.

    The independent-samples standard error, sqrt(SE_f^2 + SE_m^2), is
    reported alongside as a check on the shared-design covariance.
    """
    design = survey_design_table(pooled)
    df = sd.design_degrees_of_freedom(design)
    female, male = domain & pooled["sex"].eq("female"), domain & pooled["sex"].eq("male")
    estimates = [weighted_share(pooled, indicator, mask, design) for mask in (female, male)]
    difference, se = sd.linearized_domain_difference(
        indicator.astype(float).to_numpy(), pooled[WEIGHT].to_numpy(),
        pooled[STRATUM].to_numpy(), pooled[CLUSTER].to_numpy(), design,
        female.to_numpy(dtype=bool), male.to_numpy(dtype=bool))
    quantile = stats.t.ppf(1 - alpha / 2, df)
    return Contrast(
        female=estimates[0], male=estimates[1], difference=difference, se=se,
        ci=(difference - quantile * se, difference + quantile * se),
        p_value=float(2 * stats.t.sf(abs(difference / se), df)), df=df,
        independent_se=float(np.hypot(estimates[0].se, estimates[1].se)))
