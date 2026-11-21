"""NLSY97 variable definitions and birth-roster checks for The Intention Gap.

Reference numbers, value labels and missing-value codes were verified against
the local NLS Investigator codebook (data/raw/intention_gap_nlsy97_v2.cdb).

Dates use the NLSY97 continuous-month scheme, in which January 1980 = 1.
"""

from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "intention_gap_nlsy97_v2.csv"

# Respondent characteristics (1997 unless noted)
RESPONDENT_ID = "R0000100"       # PUBID
HOUSEHOLD_ID = "R1193000"        # SIDCODE, household identification code
SEX = "R0536300"                 # KEY!SEX: 1 = male, 2 = female
FEMALE = 2
BIRTH_MONTH = "R0536401"         # KEY!BDATE_M (1-12)
BIRTH_YEAR = "R0536402"          # KEY!BDATE_Y (1980-1984)
SAMPLE_TYPE = "R1235800"         # CV_SAMPLE_TYPE: 1 = cross-sectional, 0 = oversample
RACE_ETHNICITY = "R1482600"      # 1 Black, 2 Hispanic, 3 Mixed (non-Hispanic), 4 Non-Black/Non-Hispanic

# Round 13 (2009-2010) baseline
HIGHEST_GRADE_2009 = "T3606400"  # CV_HGC_0910: secondary-school grade (5-12); 95 = ungraded
FAMILY_INCOME_2009 = "T3606500"  # CV_INCOME_FAMILY; top-coded at the 2% level
MARITAL_STATUS_2009 = "T3611100" # CV_MARSTAT_COLLAPSED: 0 never married ... 4 widowed
WEIGHT_2009 = "T3613300"         # SAMPLING_WEIGHT_CC, two implied decimals
EXPECTATION = "T4356900"         # YFER-4861: percent chance of a(nother) child in 5 years

INTERVIEW_MONTH = {               # CV_INTERVIEW_CMONTH
    2009: "T3609900",
    2015: "U0013100",
    2017: "U1850600",
}

# CV_CHILD_BIRTH_MONTH.01 onward. The 2009 extract has 9 slots; later rounds
# have 12, so children are matched across rounds by date, never by slot number.
CHILD_BIRTH_MONTH = {
    2009: ["T3603100", "T3603200", "T3603300", "T3603400", "T3603500",
           "T3603600", "T3603700", "T3603800", "T3603900"],
    2015: ["U0003200", "U0003300", "U0003400", "U0003500", "U0003600",
           "U0003700", "U0003800", "U0003900", "U0004000", "U0004100",
           "U0004200", "U0004300"],
    2017: ["U1839900", "U1840000", "U1840100", "U1840200", "U1840300",
           "U1840400", "U1840500", "U1840600", "U1840700", "U1840800",
           "U1840900", "U1841000"],
}

BASELINE_ROUND = 2009
FOLLOWUP_ROUNDS = (2015, 2017)

MISSING_CODES = {
    -1: "Refusal",
    -2: "Don't know",
    -3: "Invalid skip",
    -4: "Valid skip",
    -5: "Non-interview",
}
NONRESPONSE_CODES = {-1, -2, -3}
VALID_SKIP = -4
NON_INTERVIEW = -5


def cmonth_from_date(year, month):
    """Convert a calendar year and month (1-12) to a continuous month."""
    return (year - 1980) * 12 + month


def cmonth_to_text(cmonth: int) -> str:
    """Format a continuous month as YYYY-MM."""
    year = 1980 + (cmonth - 1) // 12
    month = (cmonth - 1) % 12 + 1
    return f"{year}-{month:02d}"


def assess_roster(slots: Sequence[int], interview_month: int) -> dict:
    """Describe one respondent's biological-child roster for one round.

    A roster is usable when the respondent was interviewed, every slot holds
    a birth month or a valid skip (-4), birth months fill the leading slots
    without gaps, and no birth is dated after the interview month. For an
    interviewed respondent, -4 in the first slot denotes no reported children.
    """
    slots = [int(value) for value in slots]
    interview_month = int(interview_month)
    interviewed = interview_month > 0
    reported = [value for value in slots if value > 0]
    trailing = slots[len(reported):]

    assessment = {
        "interviewed": interviewed,
        "births": sorted(reported),
        "n_births": len(reported),
        "has_missing_code": any(value in NONRESPONSE_CODES for value in slots),
        "has_noninterview_code": interviewed and NON_INTERVIEW in slots,
        "has_unexpected_value": any(
            value <= 0 and value not in MISSING_CODES for value in slots
        ),
        "has_gap": any(value > 0 for value in trailing),
        "out_of_order": reported != sorted(reported),
        "birth_after_interview": interviewed
        and any(value > interview_month for value in reported),
        "all_slots_full": len(reported) == len(slots),
    }
    assessment["usable"] = interviewed and not (
        assessment["has_missing_code"]
        or assessment["has_noninterview_code"]
        or assessment["has_unexpected_value"]
        or assessment["has_gap"]
        or assessment["birth_after_interview"]
    )
    return assessment
