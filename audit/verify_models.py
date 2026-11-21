"""Independent recomputation of the calibration and model-comparison results.

Reads the processed cohort (whose labels audit.verify_outcomes reproduces
from the raw extract) and recomputes the main statistics without the
analysis package: hand-written Brier, rank AUC, Wilson intervals,
unpenalised logistic regression by Newton-Raphson, a household bootstrap
with a different seed, and repeated grouped cross-validation with three
interval methods. Output is aggregate only.

Run from the project root:  python -m audit.verify_models
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold

ROOT = Path(__file__).resolve().parent.parent
COHORT = ROOT / "data" / "processed" / "intention_gap_cohort.csv"

AUDIT_SEED = 777
N_BOOT = 2000


def brier(y, p) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def rank_auc(y, p) -> float:
    y = np.asarray(y)
    ranks = stats.rankdata(p)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def logistic_fit(X: np.ndarray, y: np.ndarray, iterations: int = 50) -> np.ndarray:
    """Unpenalised maximum likelihood by Newton-Raphson; X includes an intercept column."""
    beta = np.zeros(X.shape[1])
    for _ in range(iterations):
        p = predict(X, beta)
        gradient = X.T @ (y - p)
        hessian = (X * (p * (1 - p))[:, None]).T @ X
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return beta


def predict(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(X @ beta, -35, 35)))


def design_c(frame: pd.DataFrame) -> np.ndarray:
    return np.column_stack([np.ones(len(frame)), frame["expectation_prob"]])


def design_d(train: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    """Training-only median imputation with indicator; marital status one-hot, missing as a level."""
    grade_median = train["highest_grade_2009"].median()
    grade = frame["highest_grade_2009"]
    columns = [np.ones(len(frame)), frame["expectation_prob"], frame["age_at_baseline"],
               frame["parity_at_baseline"], grade.fillna(grade_median),
               grade.isna().astype(float)]
    levels = sorted(train["marital_status_2009"].fillna(-1).unique())
    marital = frame["marital_status_2009"].fillna(-1)
    columns += [(marital == level).astype(float) for level in levels[1:]]
    X = np.column_stack(columns).astype(float)
    reference = np.column_stack([np.ones(len(train)), train["expectation_prob"],
                                 train["age_at_baseline"], train["parity_at_baseline"],
                                 train["highest_grade_2009"].fillna(grade_median)]).astype(float)
    mean, sd = reference[:, 1:].mean(axis=0), reference[:, 1:].std(axis=0)
    X[:, 1:5] = (X[:, 1:5] - mean) / sd
    return X


def fit_predict(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    y = train["outcome"].to_numpy()
    beta_c = logistic_fit(design_c(train), y)
    beta_d = logistic_fit(design_d(train, train), y)
    return {
        "A": np.full(len(test), y.mean()),
        "B": test["expectation_prob"].to_numpy(),
        "C": predict(design_c(test), beta_c),
        "D": predict(design_d(train, test), beta_d),
    }


def household_bootstrap(groups: pd.Series, seed: int, n: int):
    rng = np.random.default_rng(seed)
    members = list(groups.groupby(groups).indices.values())
    for _ in range(n):
        picks = rng.integers(0, len(members), len(members))
        yield np.concatenate([members[i] for i in picks])


def section(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def main() -> None:
    cohort = pd.read_csv(COHORT)
    sample = cohort[cohort["outcome"].notna()].reset_index(drop=True)
    sample["outcome"] = sample["outcome"].astype(int)
    y, p = sample["outcome"].to_numpy(), sample["expectation_prob"].to_numpy()
    pct = sample["expectation_pct"].to_numpy()

    section("Stated probabilities, all labelled women")
    print(f"  n={len(y):,} births={y.sum():,} Brier={brier(y, p):.4f} AUC={rank_auc(y, p):.4f}")
    print(f"  Probability scale: max |prob - pct/100| = {np.abs(p - pct / 100).max():.2e}")
    for value in (0, 50, 100):
        k, n = int(y[pct == value].sum()), int((pct == value).sum())
        ci = stats.binomtest(k, n).proportion_ci(method="wilson")
        print(f"  Stated {value:>3}%: {k}/{n} = {k / n:.3f}, Wilson 95% [{ci.low:.3f}, {ci.high:.3f}]")
    slope = np.polyfit(p, y, 1)
    print(f"  Linear calibration (OLS of y on p): intercept {slope[1]:.3f}, slope {slope[0]:.3f}")
    for eps in (0.01, 0.001):
        logit = np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps)))
        beta = logistic_fit(np.column_stack([np.ones(len(y)), logit]), y)
        print(f"  Logistic calibration slope, logit(p) clipped at {eps}: {beta[1]:.3f} "
              f"(intercept {beta[0]:.3f})")
    category = pd.cut(pct, [-1, 0, 49, 50, 99, 100], labels=["0", "1-49", "50", "51-99", "100"])
    X = np.column_stack([np.ones(len(y))] + [(category == c).astype(float)
                                             for c in ["1-49", "50", "51-99", "100"]])
    print(f"  AUC using only five answer categories (0, 1-49, 50, 51-99, 100): "
          f"{rank_auc(y, predict(X, logistic_fit(X, y))):.3f}")

    section("Held-out split (GroupShuffleSplit, seed 1997, 25% of households)")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=1997)
    train_idx, test_idx = next(splitter.split(sample, groups=sample["household_id"]))
    train, test = sample.iloc[train_idx].reset_index(drop=True), sample.iloc[test_idx].reset_index(drop=True)
    shared = set(train["household_id"]) & set(test["household_id"])
    print(f"  Train {len(train):,} women / {train['household_id'].nunique():,} households; "
          f"test {len(test):,} / {test['household_id'].nunique():,}; shared households {len(shared)}")
    predictions = fit_predict(train, test)
    yt = test["outcome"].to_numpy()
    for name, q in predictions.items():
        auc = "n/a" if name == "A" else f"{rank_auc(yt, q):.4f}"
        print(f"  {name}: Brier {brier(yt, q):.4f}  AUC {auc}  mean forecast {q.mean():.3f}")

    section(f"Household bootstrap of held-out differences (seed {AUDIT_SEED}, {N_BOOT} resamples)")
    draws = {"B-A brier": [], "C-B brier": [], "D-C brier": [], "D-C auc": []}
    for rows in household_bootstrap(test["household_id"], AUDIT_SEED, N_BOOT):
        yb = yt[rows]
        s = {k: brier(yb, v[rows]) for k, v in predictions.items()}
        draws["B-A brier"].append(s["B"] - s["A"])
        draws["C-B brier"].append(s["C"] - s["B"])
        draws["D-C brier"].append(s["D"] - s["C"])
        draws["D-C auc"].append(rank_auc(yb, predictions["D"][rows]) - rank_auc(yb, predictions["C"][rows]))
    for key, values in draws.items():
        low, high = np.percentile(values, [2.5, 97.5])
        print(f"  {key}: 95% percentile interval [{low:+.4f}, {high:+.4f}]")

    section("Repeated grouped cross-validation inside the training split (seeds 101-110, 5 folds)")
    records = []
    for seed in range(101, 111):
        folds = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for fit_rows, val_rows in folds.split(train, train["outcome"], groups=train["household_id"]):
            fit, val = train.iloc[fit_rows], train.iloc[val_rows]
            q = fit_predict(fit, val)
            yv = val["outcome"].to_numpy()
            records.append({"seed": seed, "n_fit": len(fit), "n_val": len(val),
                            "brier": brier(yv, q["D"]) - brier(yv, q["C"]),
                            "auc": rank_auc(yv, q["D"]) - rank_auc(yv, q["C"])})
    cv = pd.DataFrame(records)
    ratio = cv["n_val"].mean() / cv["n_fit"].mean()
    k = len(cv)
    for metric in ("brier", "auc"):
        d = cv[metric]
        improved = (d < 0).sum() if metric == "brier" else (d > 0).sum()
        t = stats.t.ppf(0.975, k - 1)
        naive = t * d.std(ddof=1) / np.sqrt(k)
        corrected = t * np.sqrt((1 / k + ratio) * d.var(ddof=1))
        repeat_means = d.groupby(cv["seed"]).mean()
        per_repeat = stats.t.ppf(0.975, 9) * repeat_means.std(ddof=1) / np.sqrt(10)
        print(f"  D-C {metric}: mean {d.mean():+.4f}; folds favouring D {improved}/{k}")
        print(f"    naive t (folds independent)       [{d.mean() - naive:+.4f}, {d.mean() + naive:+.4f}]")
        print(f"    Nadeau-Bengio corrected (k={k})    [{d.mean() - corrected:+.4f}, {d.mean() + corrected:+.4f}]")
        print(f"    t on 10 repeat means               [{d.mean() - per_repeat:+.4f}, {d.mean() + per_repeat:+.4f}]")
    print(f"  Validation/fit size ratio used by the correction: {ratio:.3f}")


if __name__ == "__main__":
    main()
