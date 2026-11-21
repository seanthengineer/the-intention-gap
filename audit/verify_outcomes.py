"""Independent verification of the five-year outcome labels.

Rebuilds the variable map from the extract's codebook and reclassifies every
eligible woman from the raw CSV using the rules written in
docs/methodology.md, section 3. Nothing is imported from the analysis
package. The processed cohort is read only to compare labels. Output is
aggregate; no identifiers or respondent rows are printed.

Run from the project root:  python -m audit.verify_outcomes
"""

import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw" / "intention_gap_nlsy97_v2.csv"
CODEBOOK = ROOT / "data" / "raw" / "intention_gap_nlsy97_v2.cdb"
COHORT = ROOT / "data" / "processed" / "intention_gap_cohort.csv"

WINDOW = 60
CLASSIFIED = {"positive": 1, "negative": 0}


def codebook_variables() -> pd.DataFrame:
    """Reference number, variable name and survey year for every extract column."""
    pattern = re.compile(r"^([A-Z]\d{5})\.(\d{2})\s+\[(.+?)\]\s+Survey Year:\s*(\d{4})", re.M)
    text = CODEBOOK.read_text(encoding="utf-8", errors="replace")
    rows = [(f"{a}{b}", name, int(year)) for a, b, name, year in pattern.findall(text)]
    return pd.DataFrame(rows, columns=["column", "name", "year"])


def column(variables: pd.DataFrame, name: str, year: int) -> str:
    match = variables[(variables["name"] == name) & (variables["year"] == year)]
    if len(match) != 1:
        raise ValueError(f"{name} {year}: {len(match)} codebook matches")
    return match["column"].iloc[0]


def roster_columns(variables: pd.DataFrame, year: int) -> list[str]:
    rows = variables[variables["name"].str.startswith("CV_CHILD_BIRTH_MONTH.")
                     & (variables["year"] == year)].copy()
    rows["slot"] = rows["name"].str.split(".").str[1].astype(int)
    return rows.sort_values("slot")["column"].tolist()


def read_roster(values: list[int], interview: int) -> tuple[str, list[int]]:
    """Return (state, births). States: not_interviewed, incomplete, usable."""
    if interview < 0:
        return "not_interviewed", []
    births = []
    seen_skip = False
    for value in values:
        if value > 0:
            if seen_skip:
                return "incomplete", []
            births.append(value)
        elif value == -4:
            seen_skip = True
        else:
            return "incomplete", []
    if any(b > interview for b in births):
        return "incomplete", []
    return "usable", sorted(births)


def judge_followup(births: list[int], baseline: list[int], b0: int,
                   strict_dates: bool = False) -> tuple[str, dict]:
    """Status of one follow-up roster.

    Rule 4 of the methodology compares pre-baseline births with the 2009 roster
    by count: a changed date with an unchanged count is not a conflict. With
    strict_dates, every unmatched date counts as both missing and extra.
    """
    qualifying = sum(b0 < b < b0 + WINDOW for b in births)
    anniversary = sum(b == b0 + WINDOW for b in births)
    at_baseline = [b for b in births if b == b0]
    matched = min(len(at_baseline), sum(b == b0 for b in baseline))
    unmatched_baseline_month = len(at_baseline) - matched
    pre = Counter([b for b in births if b < b0] + [b0] * matched)
    reference = Counter(baseline)
    if strict_dates:
        missing = sum((reference - pre).values())
        extra = sum((pre - reference).values())
    else:
        missing = max(0, sum(reference.values()) - sum(pre.values()))
        extra = max(0, sum(pre.values()) - sum(reference.values()))
    detail = {"qualifying": qualifying, "anniversary": anniversary,
              "unmatched_baseline_month": unmatched_baseline_month,
              "missing": missing, "extra": extra}
    if qualifying > missing:
        return "positive", detail
    if qualifying > 0 or extra > 0:
        return "conflict", detail
    if unmatched_baseline_month or anniversary:
        return "ambiguous", detail
    return "negative", detail


def classify(row: pd.Series, cols: dict, strict_dates: bool = False) -> dict:
    b0 = int(row[cols["interview"][2009]])
    state09, base = read_roster([int(row[c]) for c in cols["roster"][2009]], b0)
    rounds = {}
    for year in (2015, 2017):
        interview = int(row[cols["interview"][year]])
        state, births = read_roster([int(row[c]) for c in cols["roster"][year]], interview)
        if state == "usable" and interview <= b0 + WINDOW:
            state = "too_early"
        rounds[year] = (state, births)

    usable = {y: births for y, (state, births) in rounds.items() if state == "usable"}
    interviewed = any(state != "not_interviewed" for state, _ in rounds.values())
    result = {"label": np.nan, "reason": None, "statuses": None}
    if state09 != "usable":
        result["reason"] = "baseline_roster_unusable"
        return result
    if not interviewed:
        result["reason"] = "no_followup_interview"
        return result
    if not usable:
        result["reason"] = "incomplete_followup"
        return result

    judged = {y: judge_followup(births, base, b0, strict_dates) for y, births in usable.items()}
    statuses = {y: s for y, (s, _) in judged.items()}
    result["statuses"] = tuple(sorted(statuses.items()))
    distinct = set(statuses.values())
    if len(distinct) == 1 and distinct <= set(CLASSIFIED):
        result["label"] = CLASSIFIED[distinct.pop()]
    elif {"positive", "negative"} <= distinct:
        result["reason"] = "rounds_disagree"
    elif "conflict" in distinct:
        result["reason"] = "record_conflict"
    elif "ambiguous" in distinct and len(distinct) == 1:
        details = [d for s, d in judged.values() if s == "ambiguous"]
        baseline_month = any(d["unmatched_baseline_month"] for d in details)
        result["reason"] = "baseline_month_timing" if baseline_month else "anniversary_month_timing"
    else:
        result["reason"] = "rounds_disagree"
    return result


def naive_label(row: pd.Series, cols: dict) -> float:
    """Inclusive window, no reconciliation: any follow-up birth in (B, B + 60]."""
    b0 = int(row[cols["interview"][2009]])
    seen_roster = False
    for year in (2015, 2017):
        state, births = read_roster([int(row[c]) for c in cols["roster"][year]],
                                    int(row[cols["interview"][year]]))
        if state == "usable":
            seen_roster = True
            if any(b0 < b <= b0 + WINDOW for b in births):
                return 1.0
    return 0.0 if seen_roster else np.nan


def rank_auc(y: np.ndarray, p: np.ndarray) -> float:
    """Mann-Whitney AUC with ties counted as one half."""
    ranks = pd.Series(p).rank(method="average").to_numpy()
    n1 = y.sum()
    n0 = len(y) - n1
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def forecast_summary(y: np.ndarray, pct: np.ndarray) -> str:
    p = pct / 100
    slope = np.polyfit(p, y, 1)[0]
    return (f"n={len(y):,} rate={y.mean():.3f} mean stated={p.mean():.3f} "
            f"Brier={np.mean((p - y) ** 2):.4f} AUC={rank_auc(y, p):.3f} slope={slope:.3f} "
            f"birth rate at 0%={y[pct == 0].mean():.3f} at 50%={y[pct == 50].mean():.3f} "
            f"at 100%={y[pct == 100].mean():.3f}")


def section(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def main() -> None:
    variables = codebook_variables()
    cols = {
        "id": column(variables, "PUBID", 1997),
        "sex": column(variables, "KEY!SEX", 1997),
        "expectation": column(variables, "YFER-4861", 2009),
        "birth_month": column(variables, "KEY!BDATE_M", 1997),
        "birth_year": column(variables, "KEY!BDATE_Y", 1997),
        "race": column(variables, "KEY!RACE_ETHNICITY", 1997),
        "sample": column(variables, "CV_SAMPLE_TYPE", 1997),
        "weight": column(variables, "SAMPLING_WEIGHT_CC", 2009),
        "interview": {y: column(variables, "CV_INTERVIEW_CMONTH", y) for y in (2009, 2015, 2017)},
        "roster": {y: roster_columns(variables, y) for y in (2009, 2015, 2017)},
    }
    raw = pd.read_csv(RAW_CSV)

    section("Variable map rebuilt from the codebook")
    for year in (2009, 2015, 2017):
        roster = cols["roster"][year]
        print(f"  {year}: {len(roster)} roster slots {roster[0]}-{roster[-1]}, "
              f"interview month {cols['interview'][year]}")
    print(f"  Expectation {cols['expectation']}, household id not used here")

    section("Eligibility")
    women = raw[raw[cols["sex"]] == 2]
    interviewed09 = women[women[cols["interview"][2009]] > 0]
    expectation = interviewed09[cols["expectation"]]
    eligible = interviewed09[expectation.between(0, 100)].copy()
    print(f"  Respondents {len(raw):,}; women {len(women):,}; women interviewed 2009 "
          f"{len(interviewed09):,}")
    print(f"  Expectation among interviewed women: valid {expectation.between(0, 100).sum():,}, "
          f"refusal {(expectation == -1).sum()}, don't know {(expectation == -2).sum()}, "
          f"other negative {((expectation < 0) & ~expectation.isin([-1, -2])).sum()}")
    print(f"  Eligible women: {len(eligible):,}")

    section("Independent classification")
    results = pd.DataFrame([classify(row, cols) for _, row in eligible.iterrows()],
                           index=eligible.index)
    eligible = eligible.join(results)
    eligible["naive"] = [naive_label(row, cols) for _, row in eligible.iterrows()]
    eligible["strict"] = [classify(row, cols, strict_dates=True)["label"]
                          for _, row in eligible.iterrows()]
    counts = {"positive": int((eligible["label"] == 1).sum()),
              "negative": int((eligible["label"] == 0).sum()),
              "unknown": int(eligible["label"].isna().sum())}
    print(f"  Positive {counts['positive']:,}  negative {counts['negative']:,}  "
          f"unknown {counts['unknown']:,}")
    print("  Unknown reasons: " + ", ".join(
        f"{k} {v}" for k, v in eligible["reason"].value_counts().items()))
    print(f"  Naive inclusive window, no reconciliation: "
          f"positive {(eligible['naive'] == 1).sum():,}, negative {(eligible['naive'] == 0).sum():,}, "
          f"unknown {eligible['naive'].isna().sum():,}")
    print(f"  Strict date matching of pre-baseline births: "
          f"positive {(eligible['strict'] == 1).sum():,}, negative {(eligible['strict'] == 0).sum():,}, "
          f"unknown {eligible['strict'].isna().sum():,}")
    print(pd.crosstab(eligible["label"].fillna(-9).astype(int), eligible["strict"].fillna(-9).astype(int),
                      rownames=["count rule"], colnames=["strict dates"]).to_string())

    section("Agreement with data/processed/intention_gap_cohort.csv")
    cohort = pd.read_csv(COHORT)[["respondent_id", "outcome", "unknown_reason"]]
    merged = eligible[[cols["id"], "label", "reason"]].merge(
        cohort, left_on=cols["id"], right_on="respondent_id", how="outer", indicator=True)
    print(f"  Row match: {merged['_merge'].value_counts().to_dict()}")
    table = pd.crosstab(merged["label"].fillna(-9).astype(int), merged["outcome"].fillna(-9).astype(int),
                        rownames=["independent (-9 = unknown)"], colnames=["pipeline"])
    print(table.to_string())
    reasons = pd.crosstab(merged["reason"].fillna("labelled"), merged["unknown_reason"].fillna("labelled"))
    print("\n  Unknown reason, independent (rows) vs pipeline (columns):")
    print(reasons.to_string())

    section("Cumulative-roster check (pre-2009 births, women usable in both rounds)")
    for year in (2015, 2017):
        same = total = 0
        for _, row in eligible.iterrows():
            b0 = int(row[cols["interview"][2009]])
            s09, base = read_roster([int(row[c]) for c in cols["roster"][2009]], b0)
            s, births = read_roster([int(row[c]) for c in cols["roster"][year]],
                                    int(row[cols["interview"][year]]))
            if s09 == "usable" and s == "usable":
                total += 1
                same += Counter(b for b in births if b < b0) == Counter(b for b in base if b < b0)
        print(f"  2009 vs {year}: identical pre-baseline births for {same:,} of {total:,} "
              f"({same / total:.1%})")
    same = total = 0
    for _, row in eligible.iterrows():
        i15 = int(row[cols["interview"][2015]])
        s15, b15 = read_roster([int(row[c]) for c in cols["roster"][2015]], i15)
        s17, b17 = read_roster([int(row[c]) for c in cols["roster"][2017]],
                               int(row[cols["interview"][2017]]))
        if s15 == "usable" and s17 == "usable":
            total += 1
            same += Counter(b15) == Counter(b for b in b17 if b <= i15)
    print(f"  2015 vs 2017: identical births up to the 2015 interview for {same:,} of {total:,} "
          f"({same / total:.1%})")

    section("Roster codes and dates among eligible women")
    birth_cmonth = (eligible[cols["birth_year"]] - 1980) * 12 + eligible[cols["birth_month"]]
    for year in (2009, 2015, 2017):
        values = eligible[cols["roster"][year]]
        codes = {code: int((values == code).sum().sum()) for code in (-1, -2, -3, -4, -5)}
        births = values.where(values > 0)
        age_at_birth = births.sub(birth_cmonth, axis=0) / 12
        interview = eligible[cols["interview"][year]]
        print(f"  {year}: codes {codes}; births {int(births.notna().sum().sum()):,}; "
              f"birth before mother aged 13: {int((age_at_birth < 13).sum().sum())} births in "
              f"{int((age_at_birth < 13).any(axis=1).sum())} women; "
              f"interview months {int(interview[interview > 0].min())}-{int(interview.max())}")
    b0 = eligible[cols["interview"][2009]]
    print(f"  Baseline months {int(b0.min())}-{int(b0.max())}; anniversary months "
          f"{int(b0.min()) + WINDOW}-{int(b0.max()) + WINDOW}")

    section("Boundary-month births among eligible women (any usable follow-up roster)")
    for label, offset in (("baseline month", 0), ("anniversary month", WINDOW)):
        hit = np.zeros(len(eligible), dtype=bool)
        for year in (2015, 2017):
            hit |= (eligible[cols["roster"][year]].eq(b0 + offset, axis=0)).any(axis=1).to_numpy()
        print(f"  Women with a {label} birth: {int(hit.sum())}")

    section("Differential follow-up (eligible women; unknown share)")
    eligible["unknown"] = eligible["label"].isna()
    pct = eligible[cols["expectation"]]
    groups = {
        "stated 0%": pct == 0, "stated 1-49%": pct.between(1, 49), "stated 50%": pct == 50,
        "stated 51-99%": pct.between(51, 99), "stated 100%": pct == 100,
    }
    for name, mask in groups.items():
        print(f"  {name:<14} n={int(mask.sum()):>5,}  unknown {eligible.loc[mask, 'unknown'].mean():.1%}")
    race_names = {1: "Black", 2: "Hispanic", 3: "Mixed race (non-Hispanic)", 4: "Non-Black, non-Hispanic"}
    for code, name in race_names.items():
        mask = eligible[cols["race"]] == code
        print(f"  {name:<26} n={int(mask.sum()):>5,}  unknown {eligible.loc[mask, 'unknown'].mean():.1%}")
    for code, name in {1: "Cross-sectional sample", 0: "Oversample"}.items():
        mask = eligible[cols["sample"]] == code
        print(f"  {name:<26} n={int(mask.sum()):>5,}  unknown {eligible.loc[mask, 'unknown'].mean():.1%}")
    weight = eligible[cols["weight"]] / 100
    labelled = ~eligible["unknown"]
    print(f"  Round 13 weighted mean stated %: labelled {np.average(pct[labelled], weights=weight[labelled]):.1f}, "
          f"unknown {np.average(pct[~labelled], weights=weight[~labelled]):.1f}")
    print(f"  Round 13 weighted unknown share: {np.average(eligible['unknown'], weights=weight):.1%} "
          f"(unweighted {eligible['unknown'].mean():.1%})")

    section("Timing of first qualifying birth among confirmed positives (pregnancy proxy)")
    first = []
    for _, row in eligible[eligible["label"] == 1].iterrows():
        b = int(row[cols["interview"][2009]])
        months = []
        for year in (2015, 2017):
            state, births = read_roster([int(row[c]) for c in cols["roster"][year]],
                                        int(row[cols["interview"][year]]))
            if state == "usable":
                months += [x - b for x in births if b < x < b + WINDOW]
        first.append(min(months))
    positives = eligible[eligible["label"] == 1].assign(first_birth=first)
    early = positives["first_birth"] <= 8
    print(f"  Positives with first qualifying birth within 8 months: {int(early.sum())} of "
          f"{len(positives):,} ({early.mean():.1%})")
    ppct = positives[cols["expectation"]]
    for name, mask in {"stated 0%": ppct == 0, "stated 1-99%": ppct.between(1, 99),
                       "stated 100%": ppct == 100}.items():
        print(f"    {name:<13} {int(early[mask].sum()):>4} of {int(mask.sum()):>4} "
              f"({early[mask].mean():.1%})")

    section("Exploratory: excluding women whose first qualifying birth came within 8 months")
    labelled = eligible[eligible["label"].notna()].copy()
    labelled["early"] = False
    labelled.loc[positives.index[early.to_numpy()], "early"] = True
    for name, frame in (("All labelled", labelled), ("Excluding early births", labelled[~labelled["early"]])):
        y = frame["label"].to_numpy(dtype=int)
        print(f"  {name:<24} " + forecast_summary(y, frame[cols["expectation"]].to_numpy(dtype=float)))
    print("  Excluding only women who gave birth biases the outcome downward (pregnant women "
          "whose pregnancy did not end in a live birth stay in); read as a bound, not an estimate.")


if __name__ == "__main__":
    main()
