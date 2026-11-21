"""NSFG 2022-2023 classification experiment for desire-intention discordance (M09).

Target: among respondents in the conservative Gen Z age proxy who want a(nother)
child (RWANT = 1) and gave a yes/no intention answer, 1 = explicit negative
intention (joint or individual item answered 'no'), 0 = positive intention
(INTENT = 1). Sterility-linked INTENT = 2, unknown and not-provided intentions
are excluded and reported separately. The label is survey-reported discordance
at interview, not future childlessness or realized fertility.

Predictors are demographic and socioeconomic recodes measured at the same
interview. Every variable that constructs the target, belongs to the
intention questionnaire block, determines its routing, or identifies the
sample design is excluded (FEATURE_DICTIONARY; assert_no_leakage).

Evaluation: the final holdout is one quarter of the 80 VEST/VECL clusters
(StratifiedGroupKFold), isolated from model selection. Hyperparameters are
chosen by repeated cluster-grouped cross-validation inside the development
clusters; the decision threshold is chosen on development out-of-fold
predictions. Models are fitted without survey weights; weighted metrics are
reported as a sensitivity and are not design-corrected inference.
Uncertainty on the holdout uses a cluster bootstrap.

Run from the project root:
    python -m analysis.nsfg_models

Writes aggregate results to data/public/nsfg_m09/ (model_*.csv,
model_results.json, feature_dictionary.csv) and assets/figures/
nsfg_model_evaluation.png. Respondent-level holdout predictions are kept
locally in data/processed/ for the independent audit.
"""

import json
from copy import deepcopy
from itertools import product
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import optimize  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.dummy import DummyClassifier  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score, balanced_accuracy_score, brier_score_loss, confusion_matrix,
    f1_score, log_loss, precision_recall_curve, precision_score, recall_score, roc_auc_score,
    roc_curve)
from sklearn.model_selection import StratifiedGroupKFold  # noqa: E402
from sklearn.pipeline import Pipeline, make_pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

from analysis import nsfg  # noqa: E402
from analysis.analyze_calibration import INK, apply_figure_style  # noqa: E402
from analysis.nlsy97 import PROJECT_ROOT  # noqa: E402
from analysis.nsfg_descriptive import FIGURE_DIR, OUTPUT_DIR  # noqa: E402

RESULTS_PATH = OUTPUT_DIR / "model_results.json"
PREDICTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "nsfg_m09_holdout_predictions.csv"
SERIES = {"dummy": INK["muted"], "logistic": "#2a78d6", "boosting": "#eb6834"}

NUMERIC = ["AGER", "children", "HIEDUC", "POVERTY", "NUMKDHH"]
CATEGORICAL = ["sex", "interview_year", "race_ethnicity", "labor_force", "metro", "religion",
               "insurance"]
FEATURE_SETS = {
    "primary": NUMERIC + CATEGORICAL,
    "demographic only": ["AGER", "sex", "interview_year", "race_ethnicity"],
    "primary without parity": [f for f in NUMERIC + CATEGORICAL
                               if f not in ("children", "NUMKDHH")],
    "primary + partnership (routing-related)": NUMERIC + CATEGORICAL
    + ["partnership", "EVRMARRY"],
}
# Source variables behind each derived feature (checked by assert_no_leakage).
FEATURE_SOURCES = {
    "children": ["PARITY", "HADSEX", "EVBIOKID", "NUMBIOKID"], "sex": ["file"],
    "interview_year": ["YEAR"], "race_ethnicity": ["HISPRACE2"], "labor_force": ["LABORFOR"],
    "metro": ["METRO"], "religion": ["RELIGION"], "insurance": ["CURR_INS"],
    "partnership": ["RMARIT"],
}

CONFIG = {
    "cohort": "conservative",
    "eligibility": "RWANT = 1 with a yes/no intention answer",
    "feature_set": "primary",
    "seed": 2023,
    "holdout": {"folds": 4, "fold": 0, "grouping": "VEST x VECL cluster"},
    "selection": {"folds": 5, "repeats": 5, "metric": "pr_auc"},
    "threshold_rule": "maximum F1 on development out-of-fold predictions",
    "bootstrap_replicates": 2000,
    "stability": {"seeds": 20, "folds": 5},
    "robustness": {"seeds": 5, "folds": 5},
    "permutation_repeats": 50,
    "grids": {
        "logistic": {"C": [0.01, 0.03, 0.1, 0.3, 1.0, 3.0], "class_weight": [None, "balanced"]},
        "boosting": {"max_iter": [50, 100, 200], "min_samples_leaf": [20, 40],
                     "class_weight": [None, "balanced"]},
    },
    "boosting_fixed": {"max_depth": 2, "learning_rate": 0.05, "l2_regularization": 1.0},
}

FEATURE_DICTIONARY = [
    # variable, description, role, justification
    ("AGER", "Age at interview", "primary feature",
     "Demographic; measured at interview; also defines the cohort range (18-26/27)."),
    ("children", "Live births (women, PARITY) or biological children fathered (men, "
     "FA-1/FA-2)", "primary feature",
     "Fertility history up to interview; PARITY is imputed by CDC, men's refusals are "
     "missing and imputed inside the pipeline."),
    ("HIEDUC", "Highest completed schooling (recode, 1-11)", "primary feature",
     "Socioeconomic; CDC-imputed recode; treated as ordinal."),
    ("POVERTY", "Family income as % of poverty threshold (recode, 50-700)", "primary feature",
     "Socioeconomic; CDC-imputed, top- and bottom-coded."),
    ("NUMKDHH", "Children under 18 in the household (recode, top-coded)", "primary feature",
     "Household composition at interview."),
    ("sex", "Respondent file (female or male)", "primary feature",
     "Questionnaire differs by sex; Stage 3 contrast not significant."),
    ("interview_year", "Interview year (YEAR)", "primary feature",
     "Period of interview; cohort bounds differ by year."),
    ("race_ethnicity", "HISPRACE2 (recode)", "primary feature", "Demographic."),
    ("labor_force", "LABORFOR grouped (recode)", "primary feature", "Socioeconomic status."),
    ("metro", "METRO (recode)", "primary feature", "Place of residence."),
    ("religion", "RELIGION (recode)", "primary feature", "Religious affiliation."),
    ("insurance", "CURR_INS (recode)", "primary feature", "Socioeconomic status."),
    ("partnership", "RMARIT: married, cohabiting, neither", "sensitivity feature only",
     "Determines whether the joint (JINTEND) or individual (INTEND) item was asked, so it "
     "encodes questionnaire routing of the target item; excluded from the primary model."),
    ("EVRMARRY", "Ever married (recode)", "sensitivity feature only",
     "Partnership history correlated with current partnership (routing); sensitivity only."),
    ("RWANT", "Wants a(nother) child (GA-1/HA-2)", "excluded: target construction",
     "Defines eligibility (constant = 1 in the sample)."),
    ("JINTEND", "Joint intention (GB-1/HB-2)", "excluded: target construction",
     "Answer defines the label."),
    ("INTEND", "Individual intention (GC-1/HC-2)", "excluded: target construction",
     "Answer defines the label."),
    ("INTENT", "CDC intention recode", "excluded: target construction",
     "Direct recode of the label."),
    ("ADDEXP", "Expected additional births (recode)", "excluded: deterministic function",
     "Set to 0 when the intention answer is 'no' (CDC specification)."),
    ("ADDEXP_I", "ADDEXP imputation flag", "excluded: deterministic function",
     "Depends on the intention answers."),
    ("JSUREINT / SUREINT", "Certainty of intention", "excluded: intention block",
     "Asked only after the intention answer; conditional on the label."),
    ("JINTENDN / INTENDN / EXPECTL / EXPECTS / JEXPECTL / JEXPECTS",
     "Number intended or expected", "excluded: intention block",
     "Asked conditional on the intention answer."),
    ("JINTNEXT / INTNEXT", "Timing of next birth", "excluded: intention block",
     "Asked only of intenders."),
    ("PROBWANT", "Probably wants (follow-up to RWANT = don't know)",
     "excluded: target construction", "Desire item; constant (missing) in the sample."),
    ("PWANT", "Partner wants a(nother) baby (women, GA-2)", "excluded: intention block",
     "Same questionnaire block, asked immediately before the joint intention; partner "
     "desire is a near-equivalent of the joint answer."),
    ("RSTRSTAT / PSTRSTAT", "Respondent / partner sterility status",
     "excluded: routing determinant",
     "Decide whether the intention question is asked and whether INTENT = 2 is assigned."),
    ("FECUND / INFERT", "Fecundity and infertility recodes (women)",
     "excluded: routing determinant",
     "Built from the sterility status that routes the intention items; female-only."),
    ("MARSTAT / RMARIT / RMARITAL / FMARITAL", "Marital and cohabiting status",
     "excluded from primary (routing)", "Choose the joint or individual item."),
    ("CURRPREG", "Current pregnancy (women) / partner's pregnancy (men)",
     "excluded: not comparable", "Different meaning by sex; added to ADDEXP by CDC."),
    ("WGT2022_2023 / VEST / VECL", "Survey weight and design codes",
     "excluded: design", "Used for grouping and weighted evaluation, never as predictors."),
    ("CaseID", "Respondent identifier", "excluded: identifier", "Not read."),
    ("CMINTVW", "Interview century month", "excluded: redundant timing",
     "Interview year is used; month adds no defensible signal."),
]
EXCLUDED = {"RWANT", "JINTEND", "INTEND", "INTENT", "ADDEXP", "ADDEXP_I", "JSUREINT", "SUREINT",
            "JINTENDN", "INTENDN", "EXPECTL", "EXPECTS", "JEXPECTL", "JEXPECTS", "JINTNEXT",
            "INTNEXT", "PROBWANT", "PWANT", "RSTRSTAT", "PSTRSTAT", "FECUND", "INFERT",
            "CURRPREG", nsfg.WEIGHT, nsfg.STRATUM, nsfg.CLUSTER, "CaseID", "category",
            "divergence", "explicit", "sterility", "wants", "intends", "expected_additional",
            "intended_number", "cluster"}
ROUTING = {"MARSTAT", "RMARIT", "RMARITAL", "FMARITAL", "partnership", "EVRMARRY",
           "intention_branch"}


# ------------------------------------------------------------- leakage

def assert_no_leakage(features: list[str], allow_routing: bool = False) -> None:
    """Raise if a feature, or a variable it is built from, is excluded."""
    used = set(features)
    for feature in features:
        used.update(FEATURE_SOURCES.get(feature, []))
    forbidden = sorted(used & EXCLUDED)
    if forbidden:
        raise ValueError(f"Leakage: excluded variables used as features: {forbidden}")
    if not allow_routing and used & ROUTING:
        raise ValueError(f"Routing-related features need allow_routing: "
                         f"{sorted(used & ROUTING)}")


# -------------------------------------------------------------- dataset

def eligible(sample: pd.DataFrame, cohort: str = "conservative",
             eligibility: str = CONFIG["eligibility"]) -> pd.DataFrame:
    """Respondents with a defensible direct yes/no intention label (reset index)."""
    in_scope = (pd.Series(True, index=sample.index) if cohort == "all ages"
                else nsfg.in_cohort(sample, cohort))
    wants = sample["wants"]
    if eligibility == "RWANT = 1 or 'probably want', yes/no answer":
        wants = wants | (sample["RWANT"].eq(nsfg.DONT_KNOW) & sample["PROBWANT"].eq(1))
    elif eligibility != CONFIG["eligibility"]:
        raise ValueError(f"Unknown eligibility rule: {eligibility}")
    labelled = sample["category"].isin([nsfg.POSITIVE, nsfg.EXPLICIT_NEGATIVE])
    frame = sample[in_scope & wants & labelled].reset_index(drop=True)
    if frame.empty:
        raise ValueError("No eligible respondents")
    frame["label"] = frame["category"].eq(nsfg.EXPLICIT_NEGATIVE).astype(int)
    return frame


def class_counts(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, part in [("all", frame), *frame.groupby("sex"),
                       *[(f"{b} item", p) for b, p in frame.groupby("intention_branch")]]:
        positives = int(part["label"].sum())
        rows.append({"group": name, "n": len(part), "explicit negative": positives,
                     "positive intention": len(part) - positives,
                     "prevalence": positives / len(part)})
    return pd.DataFrame(rows)


def preprocessor(features: list[str]) -> ColumnTransformer:
    numeric = [f for f in features if f not in CATEGORICAL + ["partnership"]]
    categorical = [f for f in features if f in CATEGORICAL + ["partnership"]]
    return ColumnTransformer([
        ("numeric", make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                                  StandardScaler()), numeric),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
         categorical)])


def make_model(family: str, params: dict, features: list[str], seed: int) -> Pipeline:
    if family == "dummy":
        estimator = DummyClassifier(strategy="prior")
    elif family == "logistic":
        estimator = LogisticRegression(C=params["C"], class_weight=params["class_weight"],
                                       max_iter=5000)
    elif family == "boosting":
        estimator = HistGradientBoostingClassifier(
            **CONFIG["boosting_fixed"], max_iter=params["max_iter"],
            min_samples_leaf=params["min_samples_leaf"], class_weight=params["class_weight"],
            early_stopping=False, random_state=seed)
    else:
        raise ValueError(f"Unknown model family: {family}")
    return Pipeline([("prepare", preprocessor(features)), ("model", estimator)])


def holdout_split(frame: pd.DataFrame, folds: int, fold: int,
                  seed: int) -> tuple[np.ndarray, np.ndarray]:
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    train, test = list(splitter.split(frame, frame["label"], frame["cluster"]))[fold]
    if set(frame["cluster"].iloc[train]) & set(frame["cluster"].iloc[test]):
        raise AssertionError("A cluster appears in both partitions")
    return train, test


# -------------------------------------------------------------- metrics

def calibration_fit(y: np.ndarray, p: np.ndarray) -> tuple[float, float, float]:
    """Calibration slope and intercept (logistic recalibration) and calibration-in-the-large.

    Assessed on predictions only; nothing is refitted for use.
    """
    logit = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))

    def loss(theta, offset=None):
        eta = theta[0] + (theta[1] * logit if offset is None else logit)
        return np.sum(np.logaddexp(0, eta) - y * eta)

    slope_fit = optimize.minimize(loss, x0=[0.0, 1.0], method="BFGS")
    large_fit = optimize.minimize(lambda t: loss([t[0], 1.0], offset=True), x0=[0.0],
                                  method="BFGS")
    return float(slope_fit.x[1]), float(slope_fit.x[0]), float(large_fit.x[0])


def threshold_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    predicted = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    return {"threshold": threshold, "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
            "precision": float(precision_score(y, predicted, zero_division=0)),
            "recall": float(recall_score(y, predicted, zero_division=0)),
            "f1": float(f1_score(y, predicted, zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
            "accuracy": float((predicted == y).mean())}


def ranking_metrics(y: np.ndarray, p: np.ndarray, prior: float,
                    weights: np.ndarray | None = None) -> dict:
    brier = brier_score_loss(y, p, sample_weight=weights)
    reference = brier_score_loss(y, np.full(len(y), prior), sample_weight=weights)
    single = len(np.unique(p)) == 1
    return {"roc_auc": float(roc_auc_score(y, p, sample_weight=weights)),
            "pr_auc": float(average_precision_score(y, p, sample_weight=weights)),
            "prevalence": float(np.average(y, weights=weights)),
            "brier": float(brier), "brier_skill": float(1 - brier / reference),
            "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), sample_weight=weights,
                                       labels=[0, 1])),
            "constant_prediction": bool(single)}


def best_threshold(y: np.ndarray, p: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(y, p)
    total = precision + recall
    f1 = np.divide(2 * precision * recall, total, out=np.zeros_like(total), where=total > 0)[:-1]
    return float(thresholds[int(np.argmax(f1))]) if len(thresholds) else 0.5


def calibration_bins(y: np.ndarray, p: np.ndarray, bins: int = 5) -> pd.DataFrame:
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    groups = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    rows = []
    for g in range(len(edges) - 1):
        mask = groups == g
        if mask.any():
            rows.append({"bin": g + 1, "n": int(mask.sum()), "events": int(y[mask].sum()),
                         "mean_predicted": float(p[mask].mean()),
                         "observed": float(y[mask].mean())})
    return pd.DataFrame(rows)


# ------------------------------------------------------- cross-validation

def grouped_cv_predictions(frame: pd.DataFrame, features: list[str], family: str,
                           params: dict, folds: int, seed: int,
                           weighted: bool = False) -> np.ndarray:
    """Out-of-fold predictions with whole clusters held out together."""
    predictions = np.full(len(frame), np.nan)
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train, test in splitter.split(frame, frame["label"], frame["cluster"]):
        model = make_model(family, params, features, seed)
        fit_args = ({"model__sample_weight": frame[nsfg.WEIGHT].iloc[train].to_numpy()}
                    if weighted else {})
        model.fit(frame[features].iloc[train], frame["label"].iloc[train], **fit_args)
        predictions[test] = model.predict_proba(frame[features].iloc[test])[:, 1]
    return predictions


def fold_scores(frame: pd.DataFrame, predictions: np.ndarray, folds: int,
                seed: int) -> list[dict]:
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    scores = []
    for _, test in splitter.split(frame, frame["label"], frame["cluster"]):
        y, p = frame["label"].iloc[test].to_numpy(), predictions[test]
        if 0 < y.sum() < len(y):
            scores.append({"roc_auc": roc_auc_score(y, p),
                           "pr_auc": average_precision_score(y, p),
                           "brier": brier_score_loss(y, p), "prevalence": y.mean()})
    return scores


def grid(family: str) -> list[dict]:
    if family == "dummy":
        return [{}]
    space = CONFIG["grids"][family]
    return [dict(zip(space, values)) for values in product(*space.values())]


def select_models(development: pd.DataFrame, features: list[str], config: dict) -> tuple[
        pd.DataFrame, dict]:
    """Repeated grouped CV within development clusters; best configuration per family."""
    rows, chosen = [], {}
    selection = config["selection"]
    for family in ("dummy", "logistic", "boosting"):
        for params in grid(family):
            scores = []
            for repeat in range(selection["repeats"]):
                seed = config["seed"] + repeat
                predictions = grouped_cv_predictions(development, features, family, params,
                                                     selection["folds"], seed)
                scores += fold_scores(development, predictions, selection["folds"], seed)
            table = pd.DataFrame(scores)
            rows.append({"family": family, "params": json.dumps(params),
                         **{f"cv_{k}_mean": table[k].mean() for k in table},
                         **{f"cv_{k}_sd": table[k].std(ddof=1) for k in table},
                         "folds_scored": len(table)})
        family_rows = [r for r in rows if r["family"] == family]
        best = max(family_rows, key=lambda r: r[f"cv_{selection['metric']}_mean"])
        chosen[family] = json.loads(best["params"])
    return pd.DataFrame(rows), chosen


# ----------------------------------------------------------- bootstrap

def cluster_bootstrap(holdout: pd.DataFrame, predictions: dict[str, np.ndarray],
                      replicates: int, seed: int) -> pd.DataFrame:
    """Percentile intervals for holdout metrics and model differences, resampling clusters."""
    rng = np.random.default_rng(seed)
    clusters = holdout["cluster"].to_numpy()
    unique = np.unique(clusters)
    members = {c: np.flatnonzero(clusters == c) for c in unique}
    y = holdout["label"].to_numpy()
    draws = {f"{m}_{k}": [] for m in predictions for k in ("roc_auc", "pr_auc", "brier")}
    pairs = [("logistic", "dummy"), ("boosting", "dummy"), ("boosting", "logistic")]
    for a, b in pairs:
        for k in ("roc_auc", "pr_auc", "brier"):
            draws[f"{a}-{b}_{k}"] = []
    for _ in range(replicates):
        index = np.concatenate([members[c] for c in rng.choice(unique, len(unique))])
        yb = y[index]
        if yb.sum() in (0, len(yb)):
            continue
        values = {}
        for model, p in predictions.items():
            pb = p[index]
            values[model] = {"roc_auc": roc_auc_score(yb, pb),
                             "pr_auc": average_precision_score(yb, pb),
                             "brier": brier_score_loss(yb, pb)}
            for k, v in values[model].items():
                draws[f"{model}_{k}"].append(v)
        for a, b in pairs:
            for k in ("roc_auc", "pr_auc", "brier"):
                draws[f"{a}-{b}_{k}"].append(values[a][k] - values[b][k])
    rows = []
    for key, values in draws.items():
        values = np.array(values)
        rows.append({"quantity": key, "replicates": len(values),
                     "ci_low": float(np.quantile(values, 0.025)),
                     "ci_high": float(np.quantile(values, 0.975)),
                     "share_above_zero": float((values > 0).mean())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------- experiment

def run_experiment(sample: pd.DataFrame, config: dict = CONFIG) -> dict:
    """Primary experiment: selection, threshold, single holdout evaluation."""
    config = deepcopy(config)
    features = FEATURE_SETS[config["feature_set"]]
    assert_no_leakage(features)
    frame = eligible(sample, config["cohort"], config["eligibility"])
    train, test = holdout_split(frame, config["holdout"]["folds"], config["holdout"]["fold"],
                                config["seed"])
    development, holdout = frame.iloc[train].reset_index(drop=True), frame.iloc[test].reset_index(
        drop=True)
    selection, chosen = select_models(development, features, config)
    prior = float(development["label"].mean())

    thresholds, predictions, fitted = {}, {}, {}
    for family, params in chosen.items():
        oof = grouped_cv_predictions(development, features, family, params,
                                     config["selection"]["folds"], config["seed"])
        thresholds[family] = best_threshold(development["label"].to_numpy(), oof)
        model = make_model(family, params, features, config["seed"])
        model.fit(development[features], development["label"])
        fitted[family] = model
        predictions[family] = model.predict_proba(holdout[features])[:, 1]

    y = holdout["label"].to_numpy()
    weights = holdout[nsfg.WEIGHT].to_numpy()
    evaluation, bins = [], []
    for family, p in predictions.items():
        slope, intercept, in_large = (calibration_fit(y, p) if family != "dummy"
                                      else (np.nan, np.nan, np.nan))
        evaluation.append({
            "model": family, "params": json.dumps(chosen[family]),
            **ranking_metrics(y, p, prior),
            **{f"weighted_{k}": v for k, v in ranking_metrics(y, p, prior, weights).items()
               if k in ("roc_auc", "pr_auc", "prevalence", "brier", "brier_skill")},
            **threshold_metrics(y, p, thresholds[family]),
            "calibration_slope": slope, "calibration_intercept": intercept,
            "calibration_in_the_large": in_large, "mean_predicted": float(p.mean())})
        bins.append(calibration_bins(y, p).assign(model=family))

    subgroup = []
    for column in ("sex", "intention_branch"):
        for level, part in holdout.groupby(column):
            positives = int(part["label"].sum())
            row = {"grouping": column, "level": level, "n": len(part), "positives": positives}
            for family in ("logistic", "boosting"):
                p = predictions[family][part.index]
                row[f"{family}_roc_auc"] = (float(roc_auc_score(part["label"], p))
                                            if positives >= 10 and positives < len(part)
                                            else np.nan)
            row["note"] = "estimated" if positives >= 10 else "fewer than 10 positives"
            subgroup.append(row)

    importance = permutation_importance(
        fitted["logistic"], holdout[features], y, scoring="roc_auc",
        n_repeats=config["permutation_repeats"], random_state=config["seed"])
    importance = pd.DataFrame({"feature": features, "auc_drop_mean": importance.importances_mean,
                               "auc_drop_sd": importance.importances_std}).sort_values(
        "auc_drop_mean", ascending=False)

    logistic = fitted["logistic"]
    names = logistic.named_steps["prepare"].get_feature_names_out()
    coefficients = pd.DataFrame({"term": names,
                                 "coefficient": logistic.named_steps["model"].coef_[0]})
    coefficients["odds_ratio"] = np.exp(coefficients["coefficient"])
    coefficients = coefficients.merge(
        coefficient_stability(development, features, chosen["logistic"], config),
        on="term", how="left")

    return {
        "config": config,
        "class_counts": class_counts(frame),
        "partition_counts": pd.DataFrame([
            {"partition": name, "respondents": len(part), "clusters": part["cluster"].nunique(),
             "explicit negative": int(part["label"].sum()),
             "prevalence": float(part["label"].mean())}
            for name, part in (("development", development), ("holdout", holdout))]),
        "selection": selection, "chosen": chosen, "thresholds": thresholds,
        "holdout": pd.DataFrame(evaluation), "calibration_bins": pd.concat(bins),
        "bootstrap": cluster_bootstrap(holdout, predictions, config["bootstrap_replicates"],
                                       config["seed"]),
        "subgroup": pd.DataFrame(subgroup), "importance": importance,
        "coefficients": coefficients,
        "predictions": pd.DataFrame({"label": y, "cluster": holdout["cluster"],
                                     **{f"p_{k}": v for k, v in predictions.items()}}),
    }


def coefficient_stability(development: pd.DataFrame, features: list[str], params: dict,
                          config: dict, replicates: int = 200) -> pd.DataFrame:
    """Share of cluster-bootstrap refits in which each coefficient keeps the full-fit sign."""
    rng = np.random.default_rng(config["seed"])
    base = make_model("logistic", params, features, config["seed"]).fit(
        development[features], development["label"])
    names = base.named_steps["prepare"].get_feature_names_out()
    signs = np.sign(base.named_steps["model"].coef_[0])
    clusters = development["cluster"].to_numpy()
    unique = np.unique(clusters)
    members = {c: np.flatnonzero(clusters == c) for c in unique}
    agree = []
    for _ in range(replicates):
        index = np.concatenate([members[c] for c in rng.choice(unique, len(unique))])
        part = development.iloc[index]
        model = make_model("logistic", params, features, config["seed"]).fit(
            part[features], part["label"])
        refit = dict(zip(model.named_steps["prepare"].get_feature_names_out(),
                         np.sign(model.named_steps["model"].coef_[0])))
        agree.append([refit.get(name, 0) == sign for name, sign in zip(names, signs)])
    return pd.DataFrame({"term": names, "sign_stability": np.mean(agree, axis=0)})


def repeated_cv_summary(frame: pd.DataFrame, features: list[str], chosen: dict, seeds: int,
                        folds: int, base_seed: int, weighted: bool = False,
                        families=("dummy", "logistic", "boosting")) -> pd.DataFrame:
    """Grouped CV over all clusters, repeated over seeds, with fixed hyperparameters."""
    rows = []
    for offset in range(seeds):
        seed = base_seed + 100 + offset
        for family in families:
            p = grouped_cv_predictions(frame, features, family, chosen[family], folds, seed,
                                       weighted)
            y = frame["label"].to_numpy()
            w = frame[nsfg.WEIGHT].to_numpy() if weighted else None
            rows.append({"seed": seed, "model": family,
                         **ranking_metrics(y, p, float(y.mean()), w)})
    return pd.DataFrame(rows)


def stability_and_robustness(sample: pd.DataFrame, chosen: dict,
                             config: dict = CONFIG) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = FEATURE_SETS[config["feature_set"]]
    primary = eligible(sample, config["cohort"], config["eligibility"])
    stability = repeated_cv_summary(primary, features, chosen, config["stability"]["seeds"],
                                    config["stability"]["folds"], config["seed"])
    robust = config["robustness"]
    experiments = [
        ("primary specification", primary, features, {}),
        ("inclusive age proxy", eligible(sample, "inclusive"), features, {}),
        ("all ages 15-49", eligible(sample, "all ages"), features, {}),
        ("RWANT = 1 or 'probably want'", eligible(
            sample, config["cohort"], "RWANT = 1 or 'probably want', yes/no answer"),
         features, {}),
        ("women only", primary[primary["sex"].eq("female")].reset_index(drop=True),
         [f for f in features if f != "sex"], {}),
        ("men only", primary[primary["sex"].eq("male")].reset_index(drop=True),
         [f for f in features if f != "sex"], {}),
        ("joint item only", primary[primary["intention_branch"].eq("joint")].reset_index(
            drop=True), features, {}),
        ("individual item only", primary[primary["intention_branch"].eq("individual")]
         .reset_index(drop=True), features, {}),
        ("complete cases (no imputation)", primary[primary[features].notna().all(axis=1)]
         .reset_index(drop=True), features, {}),
        ("survey-weighted fit and metrics", primary, features, {"weighted": True}),
    ] + [(f"feature set: {name}", primary, fs, {})
         for name, fs in FEATURE_SETS.items() if name != "primary"]
    rows = []
    for name, frame, fs, options in experiments:
        assert_no_leakage(fs, allow_routing="routing" in name)
        summary = repeated_cv_summary(frame, fs, chosen, robust["seeds"], robust["folds"],
                                      config["seed"], **options)
        positives = int(frame["label"].sum())
        for family, part in summary.groupby("model", sort=False):
            rows.append({"experiment": name, "model": family, "n": len(frame),
                         "positives": positives, "prevalence": positives / len(frame),
                         "roc_auc_mean": part["roc_auc"].mean(),
                         "roc_auc_sd": part["roc_auc"].std(ddof=1),
                         "pr_auc_mean": part["pr_auc"].mean(),
                         "pr_auc_sd": part["pr_auc"].std(ddof=1),
                         "brier_skill_mean": part["brier_skill"].mean(),
                         "reliability": ("insufficient positives (<50)" if positives < 50
                                         else "adequate")})
    balanced = {**chosen, "logistic": {**chosen["logistic"], "class_weight": "balanced"
                                       if chosen["logistic"]["class_weight"] is None
                                       else None}}
    summary = repeated_cv_summary(primary, features, balanced, robust["seeds"], robust["folds"],
                                  config["seed"], families=("logistic",))
    rows.append({"experiment": "class weighting switched", "model": "logistic",
                 "n": len(primary), "positives": int(primary["label"].sum()),
                 "prevalence": float(primary["label"].mean()),
                 "roc_auc_mean": summary["roc_auc"].mean(),
                 "roc_auc_sd": summary["roc_auc"].std(ddof=1),
                 "pr_auc_mean": summary["pr_auc"].mean(),
                 "pr_auc_sd": summary["pr_auc"].std(ddof=1),
                 "brier_skill_mean": summary["brier_skill"].mean(), "reliability": "adequate"})
    return stability, pd.DataFrame(rows)


def leakage_screen(sample: pd.DataFrame, config: dict = CONFIG) -> pd.DataFrame:
    """Univariate AUC of each candidate feature on development clusters only."""
    frame = eligible(sample, config["cohort"], config["eligibility"])
    train, _ = holdout_split(frame, config["holdout"]["folds"], config["holdout"]["fold"],
                             config["seed"])
    development = frame.iloc[train]
    rows = []
    for feature in sorted(set(sum(FEATURE_SETS.values(), []))):
        values = development[feature]
        if feature in CATEGORICAL + ["partnership"]:
            rates = development.groupby(feature)["label"].mean()
            score = values.map(rates).astype(float)
        else:
            score = values.astype(float)
        known = score.notna()
        auc = roc_auc_score(development.loc[known, "label"], score[known])
        rows.append({"feature": feature, "missing": int(values.isna().sum()),
                     "univariate_auc": max(auc, 1 - auc),
                     "flag": "possible leakage" if max(auc, 1 - auc) > 0.9 else "none"})
    return pd.DataFrame(rows)


def feature_dictionary(sample: pd.DataFrame) -> pd.DataFrame:
    frame = eligible(sample)
    table = pd.DataFrame(FEATURE_DICTIONARY,
                         columns=["variable", "description", "role", "justification"])
    table["missing_in_model_sample"] = [
        int(frame[v].isna().sum()) if v in frame else np.nan for v in table["variable"]]
    return table


# ------------------------------------------------------------- outputs

def figure_evaluation(result: dict, path: Path) -> None:
    predictions = result["predictions"]
    y = predictions["label"].to_numpy()
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.9))
    for family in ("dummy", "logistic", "boosting"):
        p = predictions[f"p_{family}"].to_numpy()
        fpr, tpr, _ = roc_curve(y, p)
        precision, recall, _ = precision_recall_curve(y, p)
        label = f"{family} (AUC {roc_auc_score(y, p):.2f})"
        axes[0].plot(fpr, tpr, color=SERIES[family], linewidth=2, label=label)
        axes[1].step(recall, precision, where="post", color=SERIES[family], linewidth=2,
                     label=f"{family} (AP {average_precision_score(y, p):.2f})")
    axes[0].plot([0, 1], [0, 1], color=INK["axis"], linewidth=1, linestyle="--")
    axes[1].axhline(y.mean(), color=INK["axis"], linewidth=1, linestyle="--")
    axes[0].set(xlabel="False positive rate", ylabel="True positive rate", title="ROC")
    axes[1].set(xlabel="Recall", ylabel="Precision",
                title=f"Precision-recall (prevalence {y.mean():.3f})")
    bins = result["calibration_bins"]
    for family in ("logistic", "boosting"):
        part = bins[bins["model"].eq(family)]
        axes[2].plot(part["mean_predicted"], part["observed"], marker="o", markersize=6,
                     linewidth=2, color=SERIES[family], label=family)
    top = min(1.0, max(0.3, float(bins[["mean_predicted", "observed"]].max().max()) + 0.05))
    axes[2].plot([0, top], [0, top], color=INK["axis"], linewidth=1, linestyle="--")
    axes[2].set(xlim=(0, top), ylim=(0, top), xlabel="Mean predicted probability",
                ylabel="Observed share", title="Calibration (holdout quintiles)")
    for ax in axes:
        ax.legend(frameon=False, fontsize=8, loc="best")
    clusters = result["partition_counts"].set_index("partition").loc["holdout", "clusters"]
    fig.suptitle(f"Holdout evaluation: explicit 'no' vs positive intention among wanters "
                 f"(n {len(y)}, {int(y.sum())} positives, {clusters} clusters)", x=0.01,
                 ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _json_ready(value):
    if isinstance(value, pd.DataFrame):
        return json.loads(value.to_json(orient="records", double_precision=10))
    if isinstance(value, dict):
        return {k: _json_ready(v) for k, v in value.items()}
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def write_outputs(sample: pd.DataFrame, result: dict, stability: pd.DataFrame,
                  robustness: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tables = {"model_class_counts": result["class_counts"],
              "model_partitions": result["partition_counts"],
              "model_selection": result["selection"], "model_holdout": result["holdout"],
              "model_bootstrap": result["bootstrap"], "model_calibration": result[
                  "calibration_bins"], "model_subgroups": result["subgroup"],
              "model_importance": result["importance"],
              "model_coefficients": result["coefficients"], "model_stability": stability,
              "model_robustness": robustness, "feature_dictionary": feature_dictionary(sample),
              "model_leakage_screen": leakage_screen(sample)}
    for name, table in tables.items():
        table.to_csv(OUTPUT_DIR / f"{name}.csv", index=False, float_format="%.6g")
    summary = {key: result[key] for key in ("config", "chosen", "thresholds")}
    summary["holdout"] = result["holdout"]
    summary["partition_counts"] = result["partition_counts"]
    RESULTS_PATH.write_text(json.dumps(_json_ready(summary), indent=1) + "\n", encoding="utf-8")
    PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    result["predictions"].to_csv(PREDICTIONS_PATH, index=False)
    apply_figure_style()
    figure_evaluation(result, FIGURE_DIR / "nsfg_model_evaluation.png")


def main() -> None:
    if not nsfg.data_available():
        raise SystemExit("NSFG 2022-2023 files not found; see docs/nsfg_m09.md.")
    sample = nsfg.analysis_sample()
    result = run_experiment(sample)
    stability, robustness = stability_and_robustness(sample, result["chosen"])
    write_outputs(sample, result, stability, robustness)
    print("NSFG 2022-2023 | M09 CLASSIFICATION EXPERIMENT")
    print(result["partition_counts"].to_string(index=False))
    print(f"Chosen: {result['chosen']}")
    columns = ["model", "roc_auc", "pr_auc", "prevalence", "brier", "brier_skill", "precision",
               "recall", "f1", "balanced_accuracy", "calibration_slope"]
    print(result["holdout"][columns].round(3).to_string(index=False))
    print(f"\nResults written to {OUTPUT_DIR.relative_to(PROJECT_ROOT).as_posix()}/model_*.csv")


if __name__ == "__main__":
    main()
