"""Verification of the M09 NSFG results, with each check labelled by kind.

INDEPENDENT checks share no coding or estimation logic with analysis/nsfg*.py:
they read the raw public-use CSV files with polars, recode the constructs they
check directly from the CDC codes, estimate with the svy library (Taylor
linearization) and compare with data/public/nsfg_m09/. Covered: the
conservative-cohort estimates and SEs of nine measures for all respondents,
women and men; the three female-male differences (point estimates); the
explicit-negative share by age group and wanting by race and ethnicity (point
estimates); the sample-flow counts; the model sample size and positives; and
holdout ROC-AUC, PR-AUC and Brier score recomputed from the stored predictions
with rank and step formulas (no scikit-learn; the predictions themselves come
from the pipeline).
REPRODUCIBILITY checks re-run the pipeline's own code from the stored model
configuration and seeds; they show determinism, not correctness.
RECONCILIATION checks compare reported or configured values with generated
ones: suppression in the public tables, the primary feature list against an
independently written list of intention-block variables, the holdout size, and
headline numbers in docs/nsfg_m09.md.
Not covered here: Korn-Graubard intervals, reliability flags, Wald tests,
other subgroups, sensitivity, parity and expected-birth tables, and the model
stability, robustness, bootstrap and interpretation outputs (these rest on the
unit tests and on the shared linearization validated against the CDC benchmark).

Run from the project root:
    python audit/verify_nsfg_m09.py                 SKIP if the data are missing
    python audit/verify_nsfg_m09.py --require-data  exit 2 if the data are missing
"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import rankdata  # noqa: E402

from analysis import nsfg  # noqa: E402  (file locations only)
from analysis.nlsy97 import PROJECT_ROOT  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "data" / "public" / "nsfg_m09"
CHAPTER = PROJECT_ROOT / "docs" / "nsfg_m09.md"
PREDICTIONS = PROJECT_ROOT / "data" / "processed" / "nsfg_m09_holdout_predictions.csv"
TOLERANCE = 2e-5  # stored CSVs keep six significant digits
INTENTION_BLOCK = {"RWANT", "PROBWANT", "PWANT", "JINTEND", "JSUREINT", "JINTENDN",
                   "JEXPECTL", "JEXPECTS", "JINTNEXT", "INTEND", "SUREINT", "INTENDN",
                   "EXPECTL", "EXPECTS", "INTNEXT", "INTENT", "ADDEXP", "ADDEXP_I",
                   "RSTRSTAT", "PSTRSTAT"}
COLUMNS = ["AGER", "YEAR", "RWANT", "JINTEND", "INTEND", "INTENT", "RSTRSTAT", "PSTRSTAT",
           "RMARIT", "ADDEXP", "HISPRACE2", "WGT2022_2023", "VEST", "VECL"]


INDEPENDENT, REPRODUCIBILITY, RECONCILIATION = "independent", "reproducibility", "reconciliation"


class Results:
    def __init__(self):
        self.rows: list[tuple[str, str, str, str]] = []
        self.kind = INDEPENDENT

    def check(self, label: str, ok: bool, detail: str) -> None:
        self.rows.append(("PASS" if ok else "FAIL", self.kind, label, detail))

    def near(self, label: str, observed: float, expected: float,
             tolerance: float = TOLERANCE) -> None:
        ok = bool(np.isclose(observed, expected, rtol=tolerance, atol=1e-9))
        self.check(label, ok, f"independent {observed:.6f} vs stored {expected:.6f}")


def load_raw():
    import polars as pl

    frames = []
    for sex in ("female", "male"):
        path = Path(nsfg.DATA_PATHS[sex])
        extra = ["PARITY"] if sex == "female" else ["HADSEX", "EVBIOKID", "NUMBIOKID"]
        frame = pl.read_csv(path, columns=COLUMNS + extra, infer_schema_length=0)
        frame = frame.with_columns(pl.all().cast(pl.Float64, strict=False))
        no_codes = [5.0] if sex == "female" else [3.0, 4.0]
        if sex == "female":
            children = pl.col("PARITY")
        else:
            children = (pl.when((pl.col("HADSEX") == 2) | (pl.col("EVBIOKID") == 5)).then(0.0)
                        .when((pl.col("EVBIOKID") == 1) & (pl.col("NUMBIOKID") < 97))
                        .then(pl.col("NUMBIOKID")).otherwise(None))
        frame = frame.with_columns(
            pl.lit(sex).alias("sex"),
            children.alias("kids"),
            (((pl.col("YEAR") == 1) & pl.col("AGER").is_between(18, 26))
             | ((pl.col("YEAR") == 2) & pl.col("AGER").is_between(18, 27))).alias("cohort"),
            (pl.col("RWANT") == 1).fill_null(False).alias("want"),
            (pl.col("INTENT") == 1).cast(pl.Float64).alias("intend"),
            ((pl.col("INTENT") == 2) & ((pl.col("JINTEND") == 5)
                                        | pl.col("INTEND").is_in(no_codes)).fill_null(False))
            .alias("no_answer"),
            ((pl.col("INTENT") == 2) & pl.col("JINTEND").is_null() & pl.col("INTEND").is_null()
             & ((pl.col("RSTRSTAT").fill_null(0) != 0) | pl.col("PSTRSTAT").is_in([1.0, 2.0])
                .fill_null(False))).alias("sterile_link"),
            (pl.col("ADDEXP") / 10).alias("addexp"))
        frames.append(frame.drop(extra))
    data = pl.concat(frames, how="vertical")
    return data.with_columns(
        (pl.col("want") & (pl.col("INTENT") == 2)).cast(pl.Float64).alias("div"),
        pl.col("no_answer").cast(pl.Float64).alias("expl"),
        pl.col("sterile_link").cast(pl.Float64).alias("ster"),
        pl.col("want").cast(pl.Float64).alias("want_f"),
        (pl.col("kids") > 0).cast(pl.Float64).alias("parent"),
        (pl.col("want") & ((pl.col("INTENT") == 1) | pl.col("no_answer"))).alias("direct"))


def svy_mean(data, column: str, where):
    import polars as pl
    import svy

    frame = data.with_columns((where & pl.col(column).is_not_null()).alias("_domain"),
                              pl.col(column).fill_null(0.0))
    sample = svy.Sample(frame, svy.Design(stratum="VEST", psu="VECL", wgt="WGT2022_2023"))
    row = sample.estimation.mean(column, where=pl.col("_domain")).to_dicts()[0]
    return row["est"], row["se"]


def verify_descriptive(data, results: Results) -> dict:
    import polars as pl

    stored = pd.read_csv(OUTPUT_DIR / "estimates.csv").set_index(
        ["cohort", "population", "measure"])
    measures = {"wants": ("want_f", None), "intends": ("intend", None),
                "divergence_among_wanters": ("div", pl.col("want")),
                "explicit_among_wanters": ("expl", pl.col("want")),
                "sterility_among_wanters": ("ster", pl.col("want")),
                "explicit_among_direct": ("expl", pl.col("direct")),
                "any_children": ("parent", None), "children": ("kids", None),
                "expected_additional": ("addexp", None)}
    headline = {}
    for population in ("all", "female", "male"):
        base = pl.col("cohort") & (pl.lit(True) if population == "all"
                                   else pl.col("sex") == population)
        for name, (column, restriction) in measures.items():
            where = base if restriction is None else base & restriction
            estimate, se = svy_mean(data, column, where)
            reference = stored.loc[("conservative", population, name)]
            results.near(f"{population} {name} estimate", estimate, reference["estimate"])
            results.near(f"{population} {name} SE", se, reference["se"])
            headline[(population, name)] = (estimate, se)

    differences = pd.read_csv(OUTPUT_DIR / "sex_differences.csv").set_index(["cohort",
                                                                             "measure"])
    for name in ("divergence_among_wanters", "explicit_among_wanters",
                 "sterility_among_wanters"):
        difference = headline[("female", name)][0] - headline[("male", name)][0]
        results.near(f"female - male {name}", difference,
                     differences.loc[("conservative", name), "difference"])

    subgroups = pd.read_csv(OUTPUT_DIR / "subgroups.csv")
    ages = {"18-21": (18, 21), "22-24": (22, 24), "25 or older": (25, 28)}
    for label, (low, high) in ages.items():
        where = pl.col("cohort") & pl.col("want") & pl.col("AGER").is_between(low, high)
        estimate, _ = svy_mean(data, "expl", where)
        stored_row = subgroups[subgroups["population"].eq("all")
                               & subgroups["grouping"].eq("age_group")
                               & subgroups["level"].eq(label)
                               & subgroups["measure"].eq("explicit_among_wanters")]
        results.near(f"explicit among wanters, ages {label}", estimate,
                     float(stored_row["estimate"].iloc[0]))
    races = {1: "Hispanic", 2: "non-Hispanic White", 3: "non-Hispanic Black",
             4: "non-Hispanic other or multiple"}
    for code, label in races.items():
        where = pl.col("cohort") & (pl.col("HISPRACE2") == code)
        estimate, _ = svy_mean(data, "want_f", where)
        stored_row = subgroups[subgroups["population"].eq("all")
                               & subgroups["grouping"].eq("race_ethnicity")
                               & subgroups["level"].eq(label) & subgroups["measure"].eq("wants")]
        results.near(f"wants, {label}", estimate, float(stored_row["estimate"].iloc[0]))

    flow = pd.read_csv(OUTPUT_DIR / "sample_flow.csv").set_index(["population", "cohort"])
    cohort = data.filter(pl.col("cohort"))
    wanters = cohort.filter(pl.col("want"))
    for label, observed, column in [
            ("respondents", cohort.height, "respondents"),
            ("wanters", wanters.height, "want a child"),
            ("explicit negative", int(wanters["no_answer"].sum()), "explicit negative"),
            ("sterility-linked", int(wanters["sterile_link"].sum()), "sterility-linked")]:
        expected = int(flow.loc[("all", "conservative"), column])
        results.check(f"count: {label}", observed == expected,
                      f"independent {observed} vs stored {expected}")
    return headline


def roc_auc(y: np.ndarray, p: np.ndarray) -> float:
    ranks = rankdata(p)
    positives = y == 1
    n1, n0 = positives.sum(), (~positives).sum()
    return float((ranks[positives].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def average_precision(y: np.ndarray, p: np.ndarray) -> float:
    order = np.argsort(-p, kind="mergesort")
    y, p = y[order], p[order]
    distinct = np.r_[np.flatnonzero(np.diff(p)), len(p) - 1]
    tp = np.cumsum(y)[distinct]
    precision = tp / (distinct + 1)
    recall = tp / y.sum()
    return float(np.sum(np.diff(np.r_[0, recall]) * precision))


def verify_models(data, results: Results) -> None:
    import polars as pl

    eligible = data.filter(pl.col("cohort") & pl.col("direct"))
    counts = pd.read_csv(OUTPUT_DIR / "model_class_counts.csv").set_index("group")
    results.check("model sample size", eligible.height == counts.loc["all", "n"],
                  f"independent {eligible.height} vs stored {counts.loc['all', 'n']}")
    positives = int(eligible["no_answer"].sum())
    results.check("model positives", positives == counts.loc["all", "explicit negative"],
                  f"independent {positives} vs stored {counts.loc['all', 'explicit negative']}")

    from analysis import nsfg_models as nm

    results.kind = RECONCILIATION
    features = set(nm.FEATURE_SETS["primary"])
    sources = features.union(*[nm.FEATURE_SOURCES.get(f, []) for f in features])
    overlap = sorted(sources & INTENTION_BLOCK)
    results.check("primary features exclude the intention block", not overlap,
                  f"overlap {overlap}")

    stored = json.loads((OUTPUT_DIR / "model_results.json").read_text(encoding="utf-8"))
    holdout = pd.DataFrame(stored["holdout"]).set_index("model")  # full precision
    if not PREDICTIONS.exists():
        results.check("holdout predictions available", False, f"missing {PREDICTIONS}")
        return
    predictions = pd.read_csv(PREDICTIONS)
    y = predictions["label"].to_numpy()
    results.check("holdout size", len(y) == int(pd.read_csv(
        OUTPUT_DIR / "model_partitions.csv").set_index("partition").loc["holdout",
                                                                        "respondents"]),
        f"{len(y)} holdout predictions")
    results.kind = INDEPENDENT
    for model in holdout.index:
        p = predictions[f"p_{model}"].to_numpy()
        results.near(f"{model} holdout ROC-AUC (rank formula)", roc_auc(y, p),
                     holdout.loc[model, "roc_auc"], 1e-9)
        results.near(f"{model} holdout PR-AUC (step formula)", average_precision(y, p),
                     holdout.loc[model, "pr_auc"], 1e-9)
        results.near(f"{model} holdout Brier", float(np.mean((p - y) ** 2)),
                     holdout.loc[model, "brier"], 1e-9)

    results.kind = REPRODUCIBILITY
    rerun = nm.run_experiment(nsfg.analysis_sample(), stored["config"])["holdout"]
    rerun = rerun.set_index("model")
    for row in stored["holdout"]:
        for key in ("roc_auc", "pr_auc", "brier", "f1", "calibration_slope"):
            if row[key] is None:
                continue
            results.near(f"rerun {row['model']} {key} (same code, stored config)",
                         float(rerun.loc[row["model"], key]), row[key], 1e-9)


def verify_suppression(results: Results) -> None:
    """Public tables carry no estimate, interval or event count for suppressed rows."""
    results.kind = RECONCILIATION
    blanked = ["events", "estimate", "se", "ci_low", "ci_high", "effective_n"]
    for path in sorted(OUTPUT_DIR.glob("*.csv")):
        table = pd.read_csv(path)
        if "reliability" not in table:
            continue
        hide = table["reliability"].astype(str).str.startswith("suppress")
        left = int(table.loc[hide, [c for c in blanked if c in table]].notna().sum().sum())
        results.check(f"suppression honored in {path.name}", left == 0,
                      f"{int(hide.sum())} suppressed rows, {left} values left")


def verify_chapter(headline: dict, results: Results) -> None:
    results.kind = RECONCILIATION
    if not CHAPTER.exists():
        results.check("chapter present", False, f"missing {CHAPTER}")
        return
    text = CHAPTER.read_text(encoding="utf-8")
    for key in [("all", "wants"), ("all", "intends"), ("all", "divergence_among_wanters"),
                ("all", "explicit_among_wanters"), ("all", "sterility_among_wanters"),
                ("female", "explicit_among_wanters"), ("male", "explicit_among_wanters")]:
        value = f"{100 * headline[key][0]:.1f}%"
        results.check(f"chapter reports {key[0]} {key[1]} = {value}", value in text,
                      "found" if value in text else "not found")
    holdout = pd.read_csv(OUTPUT_DIR / "model_holdout.csv").set_index("model")
    for model in ("logistic", "boosting"):
        value = f"{holdout.loc[model, 'roc_auc']:.2f}"
        results.check(f"chapter reports {model} holdout ROC-AUC {value}", value in text,
                      "found" if value in text else "not found")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent verification of M09 results.")
    parser.add_argument("--require-data", action="store_true")
    args = parser.parse_args(argv)
    missing = [str(p) for p in nsfg.DATA_PATHS.values() if not Path(p).exists()]
    if missing:
        print("SKIP: NSFG data missing: " + "; ".join(missing))
        return 2 if args.require_data else 0
    try:
        import svy  # noqa: F401
    except ImportError:
        print("SKIP: svy is not installed (pip install -r requirements-research.txt)")
        return 2 if args.require_data else 0
    outputs = [OUTPUT_DIR / name for name in ("estimates.csv", "model_holdout.csv")]
    if not all(path.exists() for path in outputs):
        print("FAIL: run python -m analysis.nsfg_descriptive and python -m analysis.nsfg_models")
        return 1

    results = Results()
    data = load_raw()
    headline = verify_descriptive(data, results)
    verify_models(data, results)
    verify_suppression(results)
    verify_chapter(headline, results)
    print("NSFG 2022-2023 | M09 VERIFICATION")
    for status, kind, label, detail in results.rows:
        print(f"  {status}  [{kind}] {label}: {detail}")
    for kind in (INDEPENDENT, REPRODUCIBILITY, RECONCILIATION):
        rows = [r for r in results.rows if r[1] == kind]
        print(f"  {kind}: {sum(r[0] == 'PASS' for r in rows)} PASS, "
              f"{sum(r[0] == 'FAIL' for r in rows)} FAIL")
    failures = sum(row[0] == "FAIL" for row in results.rows)
    print(f"\nSummary: {len(results.rows) - failures} PASS, {failures} FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
