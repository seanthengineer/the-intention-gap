"""Independent verification of the 2015-16 out-of-period evaluation.

Variables are located from the three NLS Investigator codebooks; outcomes
are reclassified with the audit's own roster rules (audit.verify_outcomes);
model C forecasts are computed from the stored coefficients by formula; and
Brier scores, AUCs and the household bootstrap are recomputed without the
analysis package. The analysis package is imported only in the final
section, to compare labels and forecasts. Output is aggregate; no
identifiers or respondent rows are printed.

Run from the project root:  python -m audit.verify_temporal
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from audit.verify_outcomes import judge_followup, rank_auc, read_roster

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
EXTRACTS = ("intention_gap_nlsy97_v2", "intention_gap_nlsy97_temporal")
COHORT = ROOT / "data" / "processed" / "intention_gap_cohort.csv"
PARAMETERS = ROOT / "docs" / "frozen_model_parameters.json"
SUMMARY = ROOT / "data" / "public" / "dashboard_summary.json"

WINDOW = 60
FOLLOWUP = (2021, 2023)
N_BOOTSTRAP = 2000
CATEGORIES = ([-1, 0, 49, 50, 99, 100], ["0", "1-49", "50", "51-99", "100"])


def codebook(name: str) -> pd.DataFrame:
    pattern = re.compile(r"^([A-Z]\d{5})\.(\d{2})\s+\[(.+?)\]\s+Survey Year:\s*(\d{4}|XRND)", re.M)
    text = (RAW / f"{name}.cdb").read_text(encoding="utf-8", errors="replace")
    return pd.DataFrame([(f"{a}{b}", n, y) for a, b, n, y in pattern.findall(text)],
                        columns=["column", "name", "year"])


def locate(variables: pd.DataFrame, name: str, year: str) -> str:
    match = variables[(variables["name"] == name) & (variables["year"] == year)]
    if len(match) != 1:
        raise ValueError(f"{name} {year}: {len(match)} codebook matches")
    return match["column"].iloc[0]


def rosters(variables: pd.DataFrame, year: str) -> list[str]:
    rows = variables[variables["name"].str.startswith("CV_CHILD_BIRTH_MONTH.")
                     & (variables["year"] == year)].copy()
    rows["slot"] = rows["name"].str.split(".").str[1].astype(int)
    return rows.sort_values("slot")["column"].tolist()


def load() -> tuple[pd.DataFrame, dict]:
    """Merge the original and temporal extracts on PUBID, keeping only needed columns."""
    books = {name: codebook(name) for name in EXTRACTS}
    v2, temporal = books[EXTRACTS[0]], books[EXTRACTS[1]]
    cols = {
        "id": "R0000100", "household": locate(v2, "SIDCODE", "1997"),
        "sex": locate(v2, "KEY!SEX", "1997"), "birth_m": locate(v2, "KEY!BDATE_M", "1997"),
        "birth_y": locate(v2, "KEY!BDATE_Y", "1997"),
        "grade_2009": locate(v2, "CV_HGC_0910", "2009"),
        "interview_2015": locate(v2, "CV_INTERVIEW_CMONTH", "2015"),
        "roster_2015": rosters(v2, "2015"),
        "expectation": locate(temporal, "YFER-4861", "2015"),
        "grade_2015": locate(temporal, "CV_HGC_EVER_EDT", "2015"),
        "marital": locate(temporal, "CV_MARSTAT_COLLAPSED", "2015"),
        "weight": locate(temporal, "SAMPLING_WEIGHT_CC", "2015"),
        "vstrat": locate(temporal, "VSTRAT", "1997"), "vpsu": locate(temporal, "VPSU", "1997"),
        **{f"interview_{y}": locate(temporal, "CV_INTERVIEW_CMONTH", str(y)) for y in FOLLOWUP},
        **{f"roster_{y}": rosters(temporal, str(y)) for y in FOLLOWUP},
    }
    flat = lambda keys: [c for k in keys for c in (cols[k] if isinstance(cols[k], list) else [cols[k]])]
    v2_keys = ["id", "household", "sex", "birth_m", "birth_y", "grade_2009", "interview_2015",
               "roster_2015"]
    left = pd.read_csv(RAW / f"{EXTRACTS[0]}.csv", usecols=flat(v2_keys))
    right = pd.read_csv(RAW / f"{EXTRACTS[1]}.csv",
                        usecols=["R0000100", *flat([k for k in cols if k not in v2_keys])])
    frame = left.merge(right, on="R0000100", how="inner", validate="one_to_one")
    if len(frame) != len(left) or len(frame) != len(right):
        raise ValueError("Extracts cover different respondents")
    return frame, cols


def classify(row: pd.Series, cols: dict) -> dict:
    b0 = int(row[cols["interview_2015"]])
    state, base = read_roster([int(row[c]) for c in cols["roster_2015"]], b0)
    rounds = {}
    for year in FOLLOWUP:
        interview = int(row[cols[f"interview_{year}"]])
        s, births = read_roster([int(row[c]) for c in cols[f"roster_{year}"]], interview)
        if s == "usable" and interview <= b0 + WINDOW:
            s = "too_early"
        rounds[year] = (s, births)
    usable = {y: b for y, (s, b) in rounds.items() if s == "usable"}
    out = {"label": np.nan, "reason": None, "used": "+".join(map(str, usable)),
           "parity": len(base) if state == "usable" else np.nan, "baseline_usable": state == "usable"}
    if state != "usable":
        out["reason"] = "baseline_roster_unusable"
    elif all(s == "not_interviewed" for s, _ in rounds.values()):
        out["reason"] = "no_followup_interview"
    elif not usable:
        out["reason"] = "incomplete_followup"
    else:
        statuses = {judge_followup(b, base, b0)[0] for b in usable.values()}
        if statuses == {"positive"}:
            out["label"] = 1.0
        elif statuses == {"negative"}:
            out["label"] = 0.0
        elif {"positive", "negative"} <= statuses:
            out["reason"] = "rounds_disagree"
        elif "conflict" in statuses:
            out["reason"] = "record_conflict"
        elif statuses == {"ambiguous"}:
            details = [judge_followup(b, base, b0)[1] for b in usable.values()]
            out["reason"] = ("baseline_month_timing"
                             if any(d["unmatched_baseline_month"] for d in details)
                             else "anniversary_month_timing")
        else:
            out["reason"] = "rounds_disagree"
    return out


def model_c(p: np.ndarray, parameters: dict) -> np.ndarray:
    c = parameters["C"]
    z = c["intercept"][0] + c["coef"][0] * (p - c["scaler_mean"][0]) / c["scaler_scale"][0]
    return 1 / (1 + np.exp(-z))


def brier(y, p) -> float:
    return float(np.mean((p - y) ** 2))


def murphy(y: np.ndarray, p: np.ndarray, bins: np.ndarray) -> dict:
    """Reliability, resolution and uncertainty over bins of identical forecasts."""
    frame = pd.DataFrame({"y": y, "p": p, "bin": bins}).groupby("bin")
    n, f, o = frame.size(), frame["p"].mean(), frame["y"].mean()
    if not np.allclose(frame["p"].min(), frame["p"].max()):
        raise ValueError("Forecasts vary within a bin")
    rate = y.mean()
    return {"reliability": float((n * (f - o) ** 2).sum() / len(y)),
            "resolution": float((n * (o - rate) ** 2).sum() / len(y)),
            "uncertainty": rate * (1 - rate), "brier": brier(y, p)}


def bootstrap(y, forecasts: dict, households: np.ndarray, seed: int, n=N_BOOTSTRAP):
    """Household cluster bootstrap with paired resamples; returns replicate tables."""
    rng = np.random.default_rng(seed)
    members = list(pd.Series(households).groupby(households).indices.values())
    rows, skipped = [], 0
    for _ in range(n):
        idx = np.concatenate([members[k] for k in rng.integers(0, len(members), len(members))])
        if y[idx].min() == y[idx].max():
            skipped += 1
            continue
        rows.append({**{f"brier_{m}": brier(y[idx], p[idx]) for m, p in forecasts.items()},
                     "auc_B": rank_auc(y[idx], forecasts["B"][idx])})
    table = pd.DataFrame(rows)
    table["C_minus_B"] = table["brier_C"] - table["brier_B"]
    table["C_minus_A"] = table["brier_C"] - table["brier_A"]
    return table, skipped


def ci(values) -> str:
    low, high = np.percentile(values, [2.5, 97.5])
    return f"[{low:+.4f}, {high:+.4f}]"


def section(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def main() -> None:
    pd.set_option("display.width", 200)
    frame, cols = load()
    parameters = json.loads(PARAMETERS.read_text(encoding="utf-8"))

    section("Eligibility at the 2015-16 interview")
    female = frame[cols["sex"]] == 2
    interviewed = frame[cols["interview_2015"]] > 0
    answer = frame[cols["expectation"]]
    print(f"  Women {int(female.sum()):,}; interviewed in 2015 {int((female & interviewed).sum()):,}; "
          f"YFER-4861 codes among interviewed women: "
          + ", ".join(f"{k}: {int(v)}" for k, v in answer[female & interviewed]
                      .where(answer < 0, "0-100").value_counts().items()))
    eligible = frame[female & interviewed & answer.between(0, 100)].reset_index(drop=True)
    print(f"  Eligible: {len(eligible):,}")

    results = pd.DataFrame([classify(row, cols) for _, row in eligible.iterrows()])
    labels = results["label"]
    section("Outcome reconstruction")
    print(f"  Births {int((labels == 1).sum()):,}; no births {int((labels == 0).sum()):,}; "
          f"unknown {int(labels.isna().sum()):,}; baseline roster usable "
          f"{int(results['baseline_usable'].sum()):,}")
    print("  Unknown reasons: " + ", ".join(f"{k} {v}" for k, v in
                                           results["reason"].value_counts().items()))
    print("  Follow-up rosters used (labelled): " + ", ".join(
        f"{k or 'none'} {v:,}" for k, v in results.loc[labels.notna(), "used"]
        .value_counts().items()))

    section("Follow-up roster dates and completeness (eligible women)")
    b0 = eligible[cols["interview_2015"]].to_numpy()
    own_birth = (eligible[cols["birth_y"]] - 1980) * 12 + eligible[cols["birth_m"]]
    print(f"  Baseline months {b0.min()}-{b0.max()}; anniversaries {b0.min() + WINDOW}-"
          f"{b0.max() + WINDOW}")
    for year in FOLLOWUP:
        month = eligible[cols[f"interview_{year}"]].to_numpy()
        slots = eligible[cols[f"roster_{year}"]].to_numpy()
        seen = month > 0
        states = [read_roster(list(map(int, s)), int(m))[0] if m > 0 else "not_interviewed"
                  for s, m in zip(slots, month)]
        births = np.where(slots > 0, slots, np.nan)
        lag = month[seen] - (b0[seen] + WINDOW)
        print(f"  {year}: interviewed {int(seen.sum()):,}, months {month[seen].min()}-"
              f"{month[seen].max()}, interview minus anniversary {lag.min()} to {lag.max()} "
              f"months (on or before anniversary: {int((lag <= 0).sum())})")
        print(f"    roster states: " + ", ".join(f"{k} {v:,}" for k, v in
                                                pd.Series(states).value_counts().items()))
        print(f"    codes in slots of interviewed women: -1 {int((slots[seen] == -1).sum())}, "
              f"-2 {int((slots[seen] == -2).sum())}, -3 {int((slots[seen] == -3).sum())}, "
              f"-5 {int((slots[seen] == -5).sum())}; all {slots.shape[1]} slots filled: "
              f"{int((slots[seen] > 0).all(axis=1).sum())}")
        after = (births > month[:, None]) & seen[:, None]
        early = births < (own_birth.to_numpy()[:, None] + 12 * 12)
        print(f"    births dated after the interview {int(np.nansum(after))}; "
              f"before the mother's 12th birthday {int(np.nansum(early))}")
    both = [(read_roster(list(map(int, a)), int(ma)), read_roster(list(map(int, b)), int(mb)), ma)
            for a, ma, b, mb in zip(eligible[cols["roster_2021"]].to_numpy(),
                                    eligible[cols["interview_2021"]],
                                    eligible[cols["roster_2023"]].to_numpy(),
                                    eligible[cols["interview_2023"]])]
    pairs = [(r1[1], [b for b in r3[1] if b <= m]) for r1, r3, m in both
             if r1[0] == "usable" and r3[0] == "usable"]
    print(f"  2021 vs 2023 (both usable, births up to the 2021 interview): {len(pairs):,} women; "
          f"identical {sum(a == b for a, b in pairs):,}; same count, dates differ "
          f"{sum(len(a) == len(b) and a != b for a, b in pairs)}; count differs "
          f"{sum(len(a) != len(b) for a, b in pairs)}")
    boundary = {"baseline month": 0, "anniversary month": 0}
    for (r1, r3, _), m0 in zip(both, b0):
        births = set(r1[1] if r1[0] == "usable" else []) | set(r3[1] if r3[0] == "usable" else [])
        boundary["baseline month"] += sum(b == m0 for b in births)
        boundary["anniversary month"] += sum(b == m0 + WINDOW for b in births)
    print("  Distinct follow-up birth months on a boundary: " + ", ".join(
        f"{k} {v}" for k, v in boundary.items()))

    section("Forecast metrics recomputed (labelled women)")
    known = labels.notna().to_numpy()
    sample = eligible[known].reset_index(drop=True)
    y = labels[known].to_numpy()
    p_b = sample[cols["expectation"]].to_numpy() / 100
    forecasts = {"A": np.full(len(y), parameters["A"]["prevalence"]), "B": p_b,
                 "C": model_c(p_b, parameters)}
    cohort = pd.read_csv(COHORT)
    labelled09 = cohort[cohort["outcome"].notna()].reset_index(drop=True)
    split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=1997)
    train_idx, test_idx = next(split.split(labelled09, groups=labelled09["household_id"]))
    train_h = set(labelled09.loc[train_idx, "household_id"])
    test_h = set(labelled09.loc[test_idx, "household_id"])
    in_b = ~sample[cols["household"]].isin(train_h).to_numpy()
    for name, rows in (("A (all)", np.ones(len(y), bool)), ("B (outside training)", in_b)):
        yy = y[rows]
        print(f"  Setting {name}: n {rows.sum():,}, births {int(yy.sum()):,}, households "
              f"{sample.loc[rows, cols['household']].nunique():,}")
        for m, p in forecasts.items():
            auc = "" if m == "A" else f", AUC {rank_auc(yy, p[rows]):.4f}"
            print(f"    {m}: Brier {brier(yy, p[rows]):.4f}{auc}, mean forecast "
                  f"{p[rows].mean():.4f}, mean error {p[rows].mean() - yy.mean():+.4f}")
        print(f"    C - B {brier(yy, forecasts['C'][rows]) - brier(yy, p_b[rows]):+.4f}; "
              f"C - A {brier(yy, forecasts['C'][rows]) - brier(yy, forecasts['A'][rows]):+.4f}")

    section("Why C has a larger mean error than B (setting A, by answer category)")
    category = pd.cut(sample[cols["expectation"]], *CATEGORIES)
    table = pd.DataFrame({"y": y, "B": p_b, "C": forecasts["C"], "cat": category}).groupby(
        "cat", observed=True).agg(n=("y", "size"), observed=("y", "mean"), B=("B", "mean"),
                                  C=("C", "mean"))
    table["share"] = table["n"] / table["n"].sum()
    table["B_error_contribution"] = table["share"] * (table["B"] - table["observed"])
    table["C_error_contribution"] = table["share"] * (table["C"] - table["observed"])
    table["B_sq_error"] = [brier(y[(category == c).to_numpy()], p_b[(category == c).to_numpy()])
                           for c in table.index]
    table["C_sq_error"] = [brier(y[(category == c).to_numpy()],
                                 forecasts["C"][(category == c).to_numpy()]) for c in table.index]
    print(table.round(4).to_string())
    for m in ("B", "C"):
        print(f"  Murphy decomposition {m}: " + ", ".join(
            f"{k} {v:.4f}" for k, v in murphy(y, forecasts[m], p_b).items()))

    section("Household membership of setting B")
    pubid = sample["R0000100"]
    test09 = set(labelled09.loc[test_idx, "respondent_id"])
    train09 = set(labelled09.loc[train_idx, "respondent_id"])
    cohort_ids = set(cohort["respondent_id"])
    household = sample[cols["household"]]
    woman = np.select([pubid.isin(train09), pubid.isin(test09), pubid.isin(cohort_ids)],
                      ["own 2009 outcome in training", "own 2009 outcome in held-out test",
                       "2009 cohort, outcome unknown"], "not in 2009 cohort")
    home = np.select([household.isin(train_h), household.isin(test_h),
                      household.isin(set(cohort["household_id"]))],
                     ["training household", "test household", "cohort household, unlabelled"],
                     "household not in 2009 cohort")
    print(pd.crosstab(pd.Series(woman[in_b], name="woman"),
                      pd.Series(home[in_b], name="household")).to_string())
    print(f"  Setting B households also in training: "
          f"{len(set(household[in_b]) & train_h)}")
    print("  Setting A, women by own 2009 role: " + ", ".join(
        f"{k} {v:,}" for k, v in pd.Series(woman).value_counts().items()))

    section("Bootstrap verification (independent resampling, setting A and B)")
    for name, rows in (("A", np.ones(len(y), bool)), ("B", in_b)):
        sub = {m: p[rows] for m, p in forecasts.items()}
        households = sample.loc[rows, cols["household"]].to_numpy()
        endpoints = []
        for seed in (11, 12, 13, 14, 15):
            table, skipped = bootstrap(y[rows], sub, households, seed)
            endpoints.append(np.percentile(table["C_minus_B"], [2.5, 97.5]))
            if seed == 11:
                print(f"  {name}: C - B {ci(table['C_minus_B'])}, C - A {ci(table['C_minus_A'])}, "
                      f"AUC {ci(table['auc_B'])}, replicates skipped {skipped}, households "
                      f"{len(set(households)):,}")
        endpoints = np.array(endpoints)
        print(f"     C - B endpoints across 5 seeds: lower {endpoints[:, 0].min():+.4f} to "
              f"{endpoints[:, 0].max():+.4f}, upper {endpoints[:, 1].min():+.4f} to "
              f"{endpoints[:, 1].max():+.4f}")

    section("Prevalence and composition (frozen forecasts, no fitting)")
    test09 = labelled09.loc[test_idx].reset_index(drop=True)
    y09, p09 = test09["outcome"].to_numpy(), test09["expectation_prob"].to_numpy()
    c09 = model_c(p09, parameters)
    for name, yy, pb, pc, parity in (
            ("2009 held-out", y09, p09, c09, test09["parity_at_baseline"].to_numpy()),
            ("2015 setting A", y, p_b, forecasts["C"], results.loc[known, "parity"].to_numpy())):
        u = yy.mean() * (1 - yy.mean())
        print(f"  {name}: n {len(yy):,}, birth rate {yy.mean():.3f}, uncertainty {u:.4f}, "
              f"no children {np.mean(parity == 0):.3f}, mean stated {pb.mean():.3f}, "
              f"stated 0% {np.mean(pb == 0):.3f}")
        print(f"    Brier B {brier(yy, pb):.4f} (skill vs uncertainty {1 - brier(yy, pb) / u:+.3f}), "
              f"C {brier(yy, pc):.4f} ({1 - brier(yy, pc) / u:+.3f}), AUC {rank_auc(yy, pb):.3f}")
        for group, mask in (("no children", parity == 0), ("one or more", parity >= 1)):
            print(f"    {group}: n {mask.sum():,}, rate {yy[mask].mean():.3f}, Brier B "
                  f"{brier(yy[mask], pb[mask]):.4f}, C {brier(yy[mask], pc[mask]):.4f}, AUC "
                  f"{rank_auc(yy[mask], pb[mask]):.3f}, mean error B "
                  f"{pb[mask].mean() - yy[mask].mean():+.3f}, C {pc[mask].mean() - yy[mask].mean():+.3f}")
    shares09 = np.mean(test09["parity_at_baseline"].to_numpy() == 0)
    parity15 = results.loc[known, "parity"].to_numpy()
    for m in ("B", "C"):
        groups = [brier(y[parity15 == 0], forecasts[m][parity15 == 0]),
                  brier(y[parity15 >= 1], forecasts[m][parity15 >= 1])]
        print(f"  2015 Brier {m} reweighted to the 2009 held-out parenthood mix: "
              f"{shares09 * groups[0] + (1 - shares09) * groups[1]:.4f}")

    section("Education: CV_HGC_EVER_EDT (2015) against CV_HGC_0910 (2009)")
    g15, g09 = eligible[cols["grade_2015"]], eligible[cols["grade_2009"]]
    band = lambda g: np.select([g < 0, g == 95, g < 12, g == 12], ["missing", "ungraded",
                                                                   "below 12", "12"], "13 or more")
    print(pd.crosstab(pd.Series(band(g09), name="2009 CV_HGC_0910"),
                      pd.Series(band(g15), name="2015 CV_HGC_EVER_EDT")).to_string())
    valid = (g09.between(5, 12)) & (g15.between(0, 20))
    capped = np.minimum(g15[valid], 12)
    print(f"  Both valid {int(valid.sum()):,}: min(2015, 12) equals 2009 value "
          f"{int((capped == g09[valid]).sum()):,}; higher {int((capped > g09[valid]).sum())}; "
          f"lower {int((capped < g09[valid]).sum())}")

    section("Survey design variables")
    strata, psu = frame[cols["vstrat"]], frame[cols["vpsu"]]
    per_stratum = frame.groupby(cols["vstrat"])[cols["vpsu"]].nunique()
    print(f"  All respondents {len(frame):,}: VSTRAT {strata.min()}-{strata.max()} "
          f"({strata.nunique()} strata), VPSU values {sorted(psu.unique())}, negative codes "
          f"{int((strata < 0).sum() + (psu < 0).sum())}, strata with both PSUs "
          f"{int((per_stratum == 2).sum())}")
    labelled_design = sample.groupby(cols["vstrat"])[cols["vpsu"]].nunique()
    print(f"  Labelled 2015 women: {sample[cols['vstrat']].nunique()} strata, "
          f"{int((labelled_design == 1).sum())} with one PSU represented; 2015 weight > 0 for "
          f"{int((sample[cols['weight']] > 0).sum()):,} of {len(sample):,}")

    section("Agreement with analysis.temporal_validation")
    from analysis import temporal_validation as tv
    joined, items, missing = tv.load_temporal()
    if missing:
        raise SystemExit(f"Module cannot load the temporal extract: {missing}")
    later = tv.later_cohort(joined, items)
    if not (later["respondent_id"].to_numpy() == eligible[cols["id"]].to_numpy()).all():
        raise ValueError("Module and audit list eligible women in different orders")
    module = later["outcome"].astype(float).to_numpy()
    same = (np.isnan(module) & np.isnan(labels.to_numpy())) | (module == labels.to_numpy())
    print(f"  Women compared {len(later):,}; labels identical {int(same.sum()):,}")
    models = tv.frozen_models()
    module_c = models.model_c.predict_proba(later.loc[known, [tv.ac.STATED]])[:, 1]
    print(f"  Largest |C forecast difference| (formula vs fitted pipeline) "
          f"{np.abs(module_c - forecasts['C']).max():.2e}")


if __name__ == "__main__":
    main()
