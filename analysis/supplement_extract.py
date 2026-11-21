"""Validate and join a supplementary NLSY97 extract to the original extract.

The supplementary extract is downloaded separately from NLS Investigator and
saved beside the original under data/raw/, which is excluded from version
control. Nothing here modifies either extract or writes a joined file:
joins happen in memory, and the report prints aggregate code counts only.

Run from the project root:  python -m analysis.supplement_extract
"""

import re
from pathlib import Path

import pandas as pd

from analysis.nlsy97 import (
    EXPECTATION, FEMALE, PROJECT_ROOT, RAW_DATA_PATH, RESPONDENT_ID, SEX,
)

MANIFEST_PATH = PROJECT_ROOT / "docs" / "extract_manifest.csv"
SUPPLEMENT_PATH = PROJECT_ROOT / "data" / "raw" / "intention_gap_nlsy97_supplement.csv"
SUPPLEMENT_CODEBOOK = SUPPLEMENT_PATH.with_suffix(".cdb")

CODE_LABELS = {-1: "refusal", -2: "don't know", -3: "invalid skip", -4: "valid skip",
               -5: "non-interview"}


def reference_range(first: str, n: int) -> list[str]:
    """Consecutive reference numbers, e.g. T5203300, T5203400, ..."""
    prefix, number = first[0], int(first[1:])
    return [f"{prefix}{number + 100 * k:07d}" for k in range(n)]


# Verified against data/raw/intention_gap_nlsy97_supplement.cdb (release of
# 23 January 2026).
EVER_PREGNANT = "T4531100"           # YSAQ2-314, asked if no earlier valid answer
PREGNANT_SINCE_LAST = "T4531200"     # YSAQ2-314C, includes a pregnancy current at last interview
PREGNANT_NOW = "T4531300"            # YSAQ2-315
WEEKS_PREGNANT = "T4531400"          # YSAQ2-316, 1-40
LAST_PERIOD_MONTH = "T4531500"       # YSAQ2-317, asked only if weeks not given

SUPPLEMENT_INTERVIEW_MONTH = {       # CV_INTERVIEW_CMONTH
    2010: "T5210300",
    2011: "T6661300",
    2013: "T8132800",
    2019: "U3450100",
}
SUPPLEMENT_CHILD_BIRTH_MONTH = {     # CV_CHILD_BIRTH_MONTH.01 onward
    2010: reference_range("T5203300", 9),
    2011: reference_range("T6653100", 9),
    2013: reference_range("T8124900", 11),
    2019: reference_range("U3439400", 13),
}
BIO_CHILD_COUNTS = {                 # (CV_BIO_CHILD_HH, CV_BIO_CHILD_NR); -4 = no children
    2009: ("T3611600", "T3611700"),
    2010: ("T5211700", "T5211800"),
    2011: ("T6663100", "T6663200"),
    2013: ("T8134300", "T8134400"),
    2015: ("U0014800", "U0014900"),
    2017: ("U1852600", "U1852700"),
}
TOTAL_BIO_CHILD = "Z9085400"         # CVC_TTL_BIO_CHILD, cumulative to the latest interview


def load_manifest(path: Path = MANIFEST_PATH) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"reference_number": str, "survey_year": str, "round": str})


def codebook_index(path: Path) -> pd.DataFrame:
    """Reference number, question name and survey year for each variable in a codebook."""
    pattern = re.compile(r"^([A-Z]\d{5})\.(\d{2})\s+\[(.+?)\]\s+Survey Year:\s*(\d{4}|XRND)", re.M)
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    rows = [(f"{a}{b}", name, year) for a, b, name, year in pattern.findall(text)]
    return pd.DataFrame(rows, columns=["reference_number", "question_name", "survey_year"])


def check_supplement(columns, codebook: pd.DataFrame, manifest: pd.DataFrame) -> list[str]:
    """Problems with a downloaded supplement, compared with the manifest's required rows."""
    problems = []
    if RESPONDENT_ID not in columns:
        problems.append(f"{RESPONDENT_ID} (PUBID) is missing; it is the only join key")
    expected = manifest[(manifest["extract"] == "supplement")
                        & (manifest["priority"] == "required")
                        & manifest["reference_number"].notna()]
    named = codebook.set_index("reference_number")
    for _, row in expected.iterrows():
        ref = row["reference_number"]
        if ref not in columns:
            problems.append(f"{ref} ({row['question_name']}) is not in the supplement")
        elif ref in named.index and named.loc[ref, "question_name"] != row["question_name"]:
            problems.append(f"{ref}: codebook names it {named.loc[ref, 'question_name']}, "
                            f"manifest expects {row['question_name']}")
    return problems


def join_extracts(original: pd.DataFrame, supplement: pd.DataFrame) -> pd.DataFrame:
    """One-to-one join on PUBID, refusing anything that could misalign respondents."""
    for name, frame in (("original", original), ("supplement", supplement)):
        if RESPONDENT_ID not in frame:
            raise ValueError(f"{name} extract has no {RESPONDENT_ID} column")
        if frame[RESPONDENT_ID].duplicated().any():
            raise ValueError(f"{name} extract has duplicate respondent IDs")
    if set(original[RESPONDENT_ID]) != set(supplement[RESPONDENT_ID]):
        raise ValueError("The extracts cover different respondents")
    shared = (set(original) & set(supplement)) - {RESPONDENT_ID}
    if shared:
        aligned = original.set_index(RESPONDENT_ID)[sorted(shared)].sort_index()
        other = supplement.set_index(RESPONDENT_ID)[sorted(shared)].sort_index()
        differing = [c for c in sorted(shared) if not aligned[c].equals(other[c])]
        if differing:
            raise ValueError(f"Columns present in both extracts disagree: {differing}")
        supplement = supplement.drop(columns=sorted(shared))
    return original.merge(supplement, on=RESPONDENT_ID, how="inner", validate="one_to_one")


def code_availability(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Counts of substantive values and each NLSY97 missing-value code, per column."""
    table = {}
    for column in columns:
        values = frame[column]
        counts = {"substantive (>= 0)": int((values >= 0).sum())}
        counts.update({f"{code} {label}": int((values == code).sum())
                       for code, label in CODE_LABELS.items()})
        counts["other negative"] = int((values.lt(0) & ~values.isin(list(CODE_LABELS))).sum())
        table[column] = counts
    return pd.DataFrame(table).T


def supplement_columns() -> list[str]:
    columns = [EVER_PREGNANT, PREGNANT_SINCE_LAST, PREGNANT_NOW, WEEKS_PREGNANT,
               LAST_PERIOD_MONTH, *SUPPLEMENT_INTERVIEW_MONTH.values(), TOTAL_BIO_CHILD]
    for slots in SUPPLEMENT_CHILD_BIRTH_MONTH.values():
        columns += slots
    for pair in BIO_CHILD_COUNTS.values():
        columns += pair
    return columns


def load_joined_eligible(original_columns: list[str]) -> pd.DataFrame:
    """Eligible women with the requested original columns and the supplement.

    The full supplement is read so that every column shared with the
    original extract is checked for agreement before the join.
    """
    if not SUPPLEMENT_PATH.exists():
        raise SystemExit(f"Supplementary extract not found at "
                         f"{SUPPLEMENT_PATH.relative_to(PROJECT_ROOT).as_posix()}.")
    original = pd.read_csv(RAW_DATA_PATH, usecols=sorted({RESPONDENT_ID, *original_columns}))
    supplement = pd.read_csv(SUPPLEMENT_PATH)
    missing = [c for c in supplement_columns() if c not in supplement]
    if missing:
        raise ValueError(f"Supplement lacks expected columns: {missing}")
    joined = join_extracts(original, supplement)
    eligible = joined[(joined[SEX] == FEMALE) & joined[EXPECTATION].between(0, 100)]
    if eligible[[*original_columns, *supplement_columns()]].isna().any().any():
        raise ValueError("Unexpected blank cells among eligible women")
    return eligible.reset_index(drop=True)


def main() -> None:
    if not SUPPLEMENT_PATH.exists():
        raise SystemExit(f"Supplementary extract not found at "
                         f"{SUPPLEMENT_PATH.relative_to(PROJECT_ROOT).as_posix()}. "
                         "See docs/methodology.md, 'Planned supplementary extract'.")
    manifest = load_manifest()
    supplement = pd.read_csv(SUPPLEMENT_PATH)
    codebook = codebook_index(SUPPLEMENT_CODEBOOK)
    problems = check_supplement(supplement.columns, codebook, manifest)
    for problem in problems:
        print(f"  PROBLEM: {problem}")

    joined = join_extracts(pd.read_csv(RAW_DATA_PATH), supplement)
    eligible = joined[(joined[SEX] == FEMALE) & joined[EXPECTATION].between(0, 100)]
    new_columns = [c for c in supplement.columns if c != RESPONDENT_ID]
    print(f"Joined {len(joined):,} respondents one-to-one; eligible women: {len(eligible):,}")
    names = codebook.set_index("reference_number")["question_name"]
    report = code_availability(eligible, new_columns)
    report.index = [f"{c} {names.get(c, '')}".strip() for c in report.index]
    print(report.to_string())


if __name__ == "__main__":
    main()
