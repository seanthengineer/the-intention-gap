"""Calibration of stated fertility expectations and simple predictive baselines.

Treats the 2009-10 stated five-year probability of having a child as a
forecast, then compares it with a constant baseline and two logistic
regressions on a fixed household-grouped train/test split. Inputs come from
data/processed/intention_gap_cohort.csv (built by analysis.build_outcomes). Only
labelled respondents are evaluated. All estimates are unweighted. Only
aggregate results are printed or plotted; figures are written to
assets/figures/.
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from analysis.build_outcomes import EXPECTED_ELIGIBLE
from analysis.build_outcomes import OUTPUT_PATH as COHORT_PATH
from analysis.nlsy97 import PROJECT_ROOT

FIGURE_DIR = PROJECT_ROOT / "assets" / "figures"

EXPECTED_OUTCOME_COUNTS = {"positive": 1234, "negative": 2170, "unknown": 256}

# Fixed once, before any results were inspected; not tuned.
SPLIT_SEED = 1997
BOOTSTRAP_SEED = 2009
TEST_SIZE = 0.25
N_BOOTSTRAP = 2000

# Exact 0 and 1 forecasts make log loss infinite for any miss, so log loss
# is reported at two clipping levels. Brier score and AUC use the original,
# unclipped probabilities.
LOG_LOSS_EPSILONS = (0.01, 0.001)

# Calibration ranges (percent, inclusive). The 0, 50 and 100 heaps are kept
# as their own groups; ranges were fixed before results were inspected.
CALIBRATION_BINS = [
    ("0", 0, 0), ("1-19", 1, 19), ("20-39", 20, 39), ("40-49", 40, 49),
    ("50", 50, 50), ("51-69", 51, 69), ("70-89", 70, 89), ("90-99", 90, 99),
    ("100", 100, 100),
]
SMALL_GROUP = 50

# Columns describing the respondent at or before the 2009-10 interview.
# Every predictive feature must come from this list.
BASELINE_COLUMNS = {
    "expectation_prob", "expectation_pct", "age_at_baseline", "parity_at_baseline",
    "race_ethnicity", "cross_sectional_sample", "highest_grade_2009",
    "family_income_2009", "marital_status_2009", "baseline_interview_cmonth",
}
STATED = "expectation_prob"
COVARIATES_NUMERIC = ["age_at_baseline", "parity_at_baseline", "highest_grade_2009"]
COVARIATES_CATEGORICAL = ["marital_status_2009"]
MODEL_D_FEATURES = [STATED, *COVARIATES_NUMERIC, *COVARIATES_CATEGORICAL]

MODEL_LABELS = {
    "A": "A. Constant (training prevalence)",
    "B": "B. Stated probability (no fitting)",
    "C": "C. Logistic: stated probability",
    "D": "D. Logistic: stated + baseline covariates",
}

INK = {
    "surface": "#fcfcfb", "primary": "#0b0b0b", "secondary": "#52514e",
    "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7", "series": "#2a78d6",
}


def load_cohort(path=COHORT_PATH) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Cohort file not found: {path}. "
                         "Run python -m analysis.build_outcomes first.")
    return pd.read_csv(path)


def validate_cohort(cohort: pd.DataFrame) -> None:
    """Raise if the cohort does not match the approved outcome file."""
    if len(cohort) != EXPECTED_ELIGIBLE:
        raise ValueError(f"Expected {EXPECTED_ELIGIBLE} rows, found {len(cohort)}")
    counts = {
        "positive": int((cohort["outcome"] == 1).sum()),
        "negative": int((cohort["outcome"] == 0).sum()),
        "unknown": int(cohort["outcome"].isna().sum()),
    }
    if counts != EXPECTED_OUTCOME_COUNTS:
        raise ValueError(f"Outcome counts {counts} differ from {EXPECTED_OUTCOME_COUNTS}")
    if not (cohort["outcome"].isna() == cohort["unknown_reason"].notna()).all():
        raise ValueError("Unknown outcomes and unknown reasons are inconsistent")
    if not np.allclose(cohort["expectation_prob"], cohort["expectation_pct"] / 100):
        raise ValueError("expectation_prob is not expectation_pct / 100")
    if not cohort["expectation_prob"].between(0, 1).all():
        raise ValueError("expectation_prob outside [0, 1]")
    if cohort["household_id"].isna().any():
        raise ValueError("Missing household identifiers")
    non_baseline = set(MODEL_D_FEATURES) - BASELINE_COLUMNS
    if non_baseline:
        raise ValueError(f"Features not known at baseline: {sorted(non_baseline)}")


def labelled_sample(cohort: pd.DataFrame) -> pd.DataFrame:
    """Respondents with a confirmed outcome; unknown outcomes are excluded."""
    sample = cohort[cohort["outcome"].notna()].copy()
    sample["outcome"] = sample["outcome"].astype(int)
    return sample.reset_index(drop=True)


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = successes / n
    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominator
    half_width = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return (centre - half_width, centre + half_width)


def clipped_log_loss(y, p, epsilon: float) -> float:
    return log_loss(y, np.clip(p, epsilon, 1 - epsilon), labels=[0, 1])


def forecast_metrics(y, p) -> dict:
    y, p = np.asarray(y), np.asarray(p, dtype=float)
    metrics = {
        "n": len(y),
        "births": int(y.sum()),
        "mean_forecast": p.mean(),
        "observed_rate": y.mean(),
        "brier": brier_score_loss(y, p),
        "auc": roc_auc_score(y, p) if np.unique(p).size > 1 else np.nan,
    }
    for epsilon in LOG_LOSS_EPSILONS:
        metrics[f"log_loss_clip_{epsilon}"] = clipped_log_loss(y, p, epsilon)
    return metrics


def expectation_distribution(pct: pd.Series) -> pd.DataFrame:
    n = len(pct)
    rows = {
        "Exactly 0%": (pct == 0).sum(),
        "Exactly 50%": (pct == 50).sum(),
        "Exactly 100%": (pct == 100).sum(),
        "0%, 50% or 100%": pct.isin([0, 50, 100]).sum(),
        "Any multiple of 10%": (pct % 10 == 0).sum(),
        "Any multiple of 5%": (pct % 5 == 0).sum(),
    }
    return pd.DataFrame({
        "respondents": pd.Series(rows, dtype=int),
        "share_pct": pd.Series(rows) / n * 100,
    })


def calibration_table(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, low, high in CALIBRATION_BINS:
        group = sample[sample["expectation_pct"].between(low, high)]
        n, births = len(group), int(group["outcome"].sum())
        ci_low, ci_high = wilson_interval(births, n)
        rows.append({
            "range_pct": label,
            "n": n,
            "births": births,
            "mean_stated_pct": group["expectation_pct"].mean(),
            "observed_pct": 100 * births / n if n else np.nan,
            "ci_low_pct": 100 * ci_low,
            "ci_high_pct": 100 * ci_high,
            "small_group": n < SMALL_GROUP,
        })
    table = pd.DataFrame(rows)
    if table["n"].sum() != len(sample):
        raise ValueError("Calibration ranges do not cover every respondent exactly once")
    return table


def household_split(sample: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Single fixed train/test split with no household on both sides."""
    splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=SPLIT_SEED)
    train_index, test_index = next(splitter.split(sample, groups=sample["household_id"]))
    train, test = sample.iloc[train_index], sample.iloc[test_index]
    shared = set(train["household_id"]) & set(test["household_id"])
    if shared:
        raise ValueError(f"{len(shared)} households appear in both train and test")
    return train.reset_index(drop=True), test.reset_index(drop=True)


def stated_only_model():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))


def covariate_model():
    """Logistic regression with training-only imputation.

    Missing numeric values are filled with the training median and
    accompanied by a missing indicator; missing marital status becomes its
    own category, so missing codes never masquerade as substantive values.
    """
    numeric = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True), StandardScaler()
    )
    categorical = make_pipeline(
        SimpleImputer(strategy="constant", fill_value=-1),
        OneHotEncoder(handle_unknown="ignore"),
    )
    preprocess = ColumnTransformer([
        ("numeric", numeric, [STATED, *COVARIATES_NUMERIC]),
        ("categorical", categorical, COVARIATES_CATEGORICAL),
    ])
    return make_pipeline(preprocess, LogisticRegression(max_iter=1000))


def fit_and_predict(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    """Test-set probabilities for every approach; parameters use training data only."""
    y_train = train["outcome"]
    prevalence = y_train.mean()
    model_c = stated_only_model().fit(train[[STATED]], y_train)
    model_d = covariate_model().fit(train[MODEL_D_FEATURES], y_train)
    return {
        "A": np.full(len(test), prevalence),
        "B": test[STATED].to_numpy(dtype=float),
        "C": model_c.predict_proba(test[[STATED]])[:, 1],
        "D": model_d.predict_proba(test[MODEL_D_FEATURES])[:, 1],
    }


def household_bootstrap_indices(groups: pd.Series, n_replicates: int, seed: int):
    """Yield row indices for a household (cluster) bootstrap."""
    rng = np.random.default_rng(seed)
    rows_by_household = [np.asarray(rows) for rows in groups.groupby(groups).indices.values()]
    n_households = len(rows_by_household)
    for _ in range(n_replicates):
        chosen = rng.integers(0, n_households, n_households)
        yield np.concatenate([rows_by_household[k] for k in chosen])


def interval(values) -> tuple[float, float]:
    return tuple(np.percentile(values, [2.5, 97.5]))


def stated_forecast_intervals(sample: pd.DataFrame) -> dict:
    y, p = sample["outcome"].to_numpy(), sample[STATED].to_numpy()
    briers, aucs = [], []
    for rows in household_bootstrap_indices(sample["household_id"], N_BOOTSTRAP, BOOTSTRAP_SEED):
        briers.append(brier_score_loss(y[rows], p[rows]))
        aucs.append(roc_auc_score(y[rows], p[rows]))
    return {"brier": interval(briers), "auc": interval(aucs)}


def evaluate_baselines(test: pd.DataFrame, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    """Point estimates plus paired household-bootstrap intervals.

    Every replicate resamples the same households for all approaches, so
    differences between approaches are evaluated on identical respondents.
    AUC is undefined for the constant forecast and is omitted for it.
    """
    y = test["outcome"].to_numpy()
    point = {name: forecast_metrics(y, p) for name, p in predictions.items()}
    ranked = [name for name in predictions if name != "A"]

    boot_brier = {name: [] for name in predictions}
    boot_auc = {name: [] for name in ranked}
    for rows in household_bootstrap_indices(test["household_id"], N_BOOTSTRAP, BOOTSTRAP_SEED):
        for name, p in predictions.items():
            boot_brier[name].append(brier_score_loss(y[rows], p[rows]))
            if name in boot_auc:
                boot_auc[name].append(roc_auc_score(y[rows], p[rows]))
    boot_brier = {name: np.array(values) for name, values in boot_brier.items()}
    boot_auc = {name: np.array(values) for name, values in boot_auc.items()}

    results = []
    for name, metrics in point.items():
        row = {
            "model": MODEL_LABELS[name],
            "n": metrics["n"],
            "births": metrics["births"],
            "mean_forecast": metrics["mean_forecast"],
            "observed_rate": metrics["observed_rate"],
            "brier": metrics["brier"],
            "brier_ci": interval(boot_brier[name]),
            "brier_skill_vs_A": 1 - metrics["brier"] / point["A"]["brier"],
            "auc": metrics["auc"] if name in boot_auc else np.nan,
            "auc_ci": interval(boot_auc[name]) if name in boot_auc else (np.nan, np.nan),
        }
        for reference in ("A", "B", "C"):
            row[f"brier_diff_vs_{reference}"] = metrics["brier"] - point[reference]["brier"]
            row[f"brier_diff_vs_{reference}_ci"] = interval(
                boot_brier[name] - boot_brier[reference])
        for reference in ("B", "C"):
            has_auc = name in boot_auc
            row[f"auc_diff_vs_{reference}"] = (
                metrics["auc"] - point[reference]["auc"] if has_auc else np.nan)
            row[f"auc_diff_vs_{reference}_ci"] = (
                interval(boot_auc[name] - boot_auc[reference]) if has_auc else (np.nan, np.nan))
        for epsilon in LOG_LOSS_EPSILONS:
            row[f"log_loss_clip_{epsilon}"] = metrics[f"log_loss_clip_{epsilon}"]
        results.append(row)
    return pd.DataFrame(results, index=list(point))


def apply_figure_style() -> None:
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"],
        "font.size": 10,
        "figure.facecolor": INK["surface"],
        "axes.facecolor": INK["surface"],
        "savefig.facecolor": INK["surface"],
        "axes.edgecolor": INK["axis"],
        "axes.labelcolor": INK["secondary"],
        "axes.titlecolor": INK["primary"],
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": INK["grid"],
        "grid.linewidth": 0.6,
        "xtick.color": INK["muted"],
        "ytick.color": INK["muted"],
        "xtick.labelcolor": INK["secondary"],
        "ytick.labelcolor": INK["secondary"],
        "text.color": INK["primary"],
    })


def add_note(fig, text: str) -> None:
    fig.text(0.01, 0.01, text, ha="left", va="bottom", fontsize=8, color=INK["muted"], wrap=True)


def plot_distribution(sample: pd.DataFrame, path) -> None:
    pct = sample["expectation_pct"].astype(int)
    counts = np.bincount(pct, minlength=101)
    n = len(pct)

    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(np.arange(101), counts, width=0.8, color=INK["series"], zorder=2)
    ax.grid(axis="x", visible=False)
    ax.set_xlim(-2, 102)
    ax.set_xticks(range(0, 101, 10))
    ax.xaxis.set_major_formatter(PercentFormatter(100))
    ax.set_xlabel("Stated probability of having a(nother) child within five years")
    ax.set_ylabel("Respondents")
    ax.set_title(f"Stated five-year fertility expectations, 2009-10 (n = {n:,})")
    for value in (0, 50, 100):
        share = 100 * counts[value] / n
        ax.annotate(
            f"{value}%: {counts[value]:,} ({share:.0f}%)",
            xy=(value, counts[value]), xytext=(0, 4), textcoords="offset points",
            ha={0: "left", 50: "center", 100: "right"}[value], va="bottom",
            fontsize=9, color=INK["secondary"],
        )
    ax.set_ylim(0, counts.max() * 1.12)
    add_note(fig, "Women with a confirmed five-year outcome. NLSY97 Round 13 item YFER-4861 "
                  "(T4356900); one bar per integer response. Unweighted.")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_calibration(table: pd.DataFrame, n: int, path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 6.6))
    ax.plot([0, 100], [0, 100], color=INK["axis"], linewidth=1.5, zorder=1)
    ax.text(86, 80, "Stated = observed", rotation=45, ha="center", va="center",
            fontsize=8.5, color=INK["muted"])
    for small, group in table.groupby("small_group"):
        ax.errorbar(
            group["mean_stated_pct"], group["observed_pct"],
            yerr=[group["observed_pct"] - group["ci_low_pct"],
                  group["ci_high_pct"] - group["observed_pct"]],
            fmt="o", color=INK["series"], markersize=7,
            markerfacecolor=INK["surface"] if small else INK["series"],
            markeredgecolor=INK["series"] if small else INK["surface"],
            markeredgewidth=1.5, elinewidth=1.5, capsize=0, zorder=3,
        )
    for _, row in table.iterrows():
        ax.annotate(
            f"{row['range_pct']}%\nn={row['n']:,}",
            xy=(row["mean_stated_pct"], row["observed_pct"]), xytext=(7, -2),
            textcoords="offset points", fontsize=7.5, color=INK["secondary"],
            va="top", ha="left",
        )
    ax.set_xlim(-3, 103)
    ax.set_ylim(-3, 103)
    ax.set_aspect("equal")
    ax.xaxis.set_major_formatter(PercentFormatter(100))
    ax.yaxis.set_major_formatter(PercentFormatter(100))
    ax.set_xlabel("Mean stated probability in range")
    ax.set_ylabel("Observed share with a birth within five years")
    ax.set_title("Stated expectations vs. observed births")
    add_note(fig, f"Points: stated-probability ranges (labels: range and respondents); hollow "
                  f"points have fewer than {SMALL_GROUP} respondents and are imprecise. "
                  f"Bars: 95% Wilson intervals. n = {n:,}; unweighted; unknown outcomes excluded.")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_baselines(results: pd.DataFrame, path) -> None:
    order = ["A", "B", "C", "D"]
    positions = np.arange(len(order))[::-1]
    labels = [MODEL_LABELS[name] for name in order]
    n, births = int(results.loc["A", "n"]), int(results.loc["A", "births"])

    fig, (ax_brier, ax_auc) = plt.subplots(1, 2, figsize=(9.5, 3.6), sharey=True)
    for name, y in zip(order, positions):
        row = results.loc[name]
        brier_low, brier_high = row["brier_ci"]
        ax_brier.errorbar(row["brier"], y,
                          xerr=[[row["brier"] - brier_low], [brier_high - row["brier"]]],
                          fmt="o", color=INK["series"], markersize=7,
                          markeredgecolor=INK["surface"], elinewidth=1.5, capsize=0)
        ax_brier.annotate(f"{row['brier']:.3f}", (brier_high, y), xytext=(6, 0),
                          textcoords="offset points", va="center", fontsize=8.5,
                          color=INK["secondary"])
        if name == "A":
            ax_auc.text(0.5, y, "0.50 by construction", va="center", fontsize=8.5,
                        color=INK["muted"])
            continue
        low, high = row["auc_ci"]
        ax_auc.errorbar(row["auc"], y, xerr=[[row["auc"] - low], [high - row["auc"]]],
                        fmt="o", color=INK["series"], markersize=7,
                        markeredgecolor=INK["surface"], elinewidth=1.5, capsize=0)
        ax_auc.annotate(f"{row['auc']:.3f}", (high, y), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=8.5,
                        color=INK["secondary"])

    ax_brier.set_yticks(positions, labels)
    ax_brier.set_xlabel("Brier score (lower is better)")
    ax_auc.set_xlabel("ROC AUC (higher is better)")
    ax_brier.set_title("Held-out Brier score")
    ax_auc.set_title("Held-out discrimination")
    for ax in (ax_brier, ax_auc):
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
    brier_bounds = np.array(results["brier_ci"].tolist())
    ax_brier.set_xlim(brier_bounds.min() - 0.02, brier_bounds.max() + 0.03)
    ax_auc.set_xlim(0.45, 0.95)
    add_note(fig, f"Test set: {n:,} women ({births:,} births) from households not used in "
                  f"training. Whiskers: 95% household-cluster bootstrap intervals for each "
                  f"approach ({N_BOOTSTRAP:,} replicates); comparisons between approaches use "
                  f"paired differences (docs/methodology.md). Unweighted.")
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def print_section(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def format_ci(ci) -> str:
    return f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"


def main() -> None:
    pd.set_option("display.width", 140)
    cohort = load_cohort()
    validate_cohort(cohort)
    sample = labelled_sample(cohort)

    print("THE INTENTION GAP | CALIBRATION AND PREDICTIVE BASELINES (unweighted)")
    print("=" * 72)
    print(f"Eligible women: {len(cohort):,}   Labelled: {len(sample):,}   "
          f"Unknown (excluded): {cohort['outcome'].isna().sum():,}")
    print(f"Households among labelled women: {sample['household_id'].nunique():,}")

    print_section("Distribution of stated expectations (labelled women)")
    print(expectation_distribution(sample["expectation_pct"]).round(1).to_string())
    print(f"  For reference, all eligible women: "
          f"{(cohort['expectation_pct'] == 0).mean():.1%} at 0%, "
          f"{(cohort['expectation_pct'] == 50).mean():.1%} at 50%, "
          f"{(cohort['expectation_pct'] == 100).mean():.1%} at 100%")

    print_section("Stated probabilities as forecasts (all labelled women)")
    stated = forecast_metrics(sample["outcome"], sample[STATED])
    stated_ci = stated_forecast_intervals(sample)
    print(f"  Mean stated probability          {stated['mean_forecast']:.3f}")
    print(f"  Observed birth frequency         {stated['observed_rate']:.3f}")
    print(f"  Brier score                      {stated['brier']:.4f}  "
          f"95% CI [{stated_ci['brier'][0]:.4f}, {stated_ci['brier'][1]:.4f}]")
    print(f"  ROC AUC                          {stated['auc']:.4f}  "
          f"95% CI [{stated_ci['auc'][0]:.4f}, {stated_ci['auc'][1]:.4f}]")
    for epsilon in LOG_LOSS_EPSILONS:
        print(f"  Log loss, clipped to [{epsilon}, {1 - epsilon}]  "
              f"{stated[f'log_loss_clip_{epsilon}']:.4f}")
    stated_zero = sample["expectation_pct"] == 0
    stated_hundred = sample["expectation_pct"] == 100
    print(f"  Stated 0% but had a birth        {int(sample.loc[stated_zero, 'outcome'].sum()):,} "
          f"of {int(stated_zero.sum()):,}")
    print(f"  Stated 100% but no birth         "
          f"{int((1 - sample.loc[stated_hundred, 'outcome']).sum()):,} of {int(stated_hundred.sum()):,}")

    print_section("Calibration by stated-probability range")
    calibration = calibration_table(sample)
    print(calibration.round(1).to_string(index=False))

    print_section("Household-grouped split")
    train, test = household_split(sample)
    print(f"  Train: {len(train):,} women, {train['household_id'].nunique():,} households, "
          f"{int(train['outcome'].sum()):,} births ({train['outcome'].mean():.3f})")
    print(f"  Test:  {len(test):,} women, {test['household_id'].nunique():,} households, "
          f"{int(test['outcome'].sum()):,} births ({test['outcome'].mean():.3f})")
    print("  Households in both: 0 (verified)")
    print(f"  Model D features: {', '.join(MODEL_D_FEATURES)}")
    print("  Training missing values: "
          + ", ".join(f"{c}={int(train[c].isna().sum())}" for c in MODEL_D_FEATURES))

    print_section("Held-out performance")
    predictions = fit_and_predict(train, test)
    results = evaluate_baselines(test, predictions)
    print("  Differences are (row - reference); negative Brier difference = more accurate.")
    for name, row in results.iterrows():
        print(f"\n  {row['model']}")
        print(f"    Mean forecast {row['mean_forecast']:.3f} vs observed {row['observed_rate']:.3f}")
        print(f"    Brier {row['brier']:.4f} [{row['brier_ci'][0]:.4f}, {row['brier_ci'][1]:.4f}]"
              f"   skill vs A {row['brier_skill_vs_A']:+.3f}")
        references = [r for r in ("A", "B", "C") if r != name]
        print("    Brier difference " + "   ".join(
            f"vs {r} {row[f'brier_diff_vs_{r}']:+.4f} {format_ci(row[f'brier_diff_vs_{r}_ci'])}"
            for r in references))
        if name != "A":
            print(f"    AUC {row['auc']:.4f} [{row['auc_ci'][0]:.4f}, {row['auc_ci'][1]:.4f}]")
            auc_references = [r for r in ("B", "C") if r != name]
            print("    AUC difference " + "   ".join(
                f"vs {r} {row[f'auc_diff_vs_{r}']:+.4f} {format_ci(row[f'auc_diff_vs_{r}_ci'])}"
                for r in auc_references))
        print("    Log loss (clipped): " + ", ".join(
            f"eps={e}: {row[f'log_loss_clip_{e}']:.4f}" for e in LOG_LOSS_EPSILONS))

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    apply_figure_style()
    figures = {
        "stated_expectation_distribution.png": lambda p: plot_distribution(sample, p),
        "stated_expectation_calibration.png": lambda p: plot_calibration(calibration, len(sample), p),
        "baseline_comparison.png": lambda p: plot_baselines(results, p),
    }
    for filename, draw in figures.items():
        draw(FIGURE_DIR / filename)
    print("\nFigures written to assets/figures/: " + ", ".join(figures))


if __name__ == "__main__":
    main()
