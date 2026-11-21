"""M10 observational panel models: rental cost burden and age-specific fertility.

Implements docs/m10_analysis_protocol.md exactly; the protocol's SHA-256 must
match docs/m10_protocol_lock.json or no model is fitted. Coefficients are
reported as births per 1,000 women per 10-percentage-point higher burden.
These are ecological associations; fixed effects and lags do not establish
causality.

    python -m analysis.m10_models

Writes aggregate results to data/public/m10/ and assets/figures/m10_*.png.
"""

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from analysis.analyze_calibration import INK, apply_figure_style  # noqa: E402
from analysis.m10_covariates import OUTPUT_PATH as COVARIATES_PATH  # noqa: E402
from analysis.m10_panel import PANEL_PATH  # noqa: E402
from analysis.nlsy97 import PROJECT_ROOT  # noqa: E402

PROTOCOL_PATH = PROJECT_ROOT / "docs" / "m10_analysis_protocol.md"
LOCK_PATH = PROJECT_ROOT / "docs" / "m10_protocol_lock.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "public" / "m10"
FIGURE_DIR = PROJECT_ROOT / "assets" / "figures"
AGES = ("20-24", "25-29")
YOUNG_EXPOSURE = {"20-24": "young15_24_burden30_pct", "25-29": "young25_34_burden30_pct"}
SCALE = 10.0           # coefficient reported per 10 percentage points
SEED = 2026
BOOTSTRAP = 9999
NOISE_DRAWS = 1000
SIMEX_LAMBDAS = (0.0, 0.5, 1.0, 1.5, 2.0)
SIMEX_DRAWS = 200
Z90 = 1.645


# ------------------------------------------------------------------ protocol

def verify_protocol() -> dict:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
    if digest != lock["sha256"]:
        raise SystemExit("docs/m10_analysis_protocol.md does not match its lock; record an "
                         "amendment before fitting models.")
    return lock


# ------------------------------------------------------------------ data

def load_analysis_frame(panel_path: Path = PANEL_PATH,
                        covariates_path: Path = COVARIATES_PATH) -> pd.DataFrame:
    for path in (panel_path, covariates_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing input: {path}")
    panel = pd.read_csv(panel_path, dtype={"state_fips": str, "age_group": str})
    covariates = pd.read_csv(covariates_path, dtype={"state_fips": str})
    frame = panel.merge(covariates, on=["state_fips", "year"], how="left",
                        validate="many_to_one")
    if frame[["unemployment_pct", "young15_24_burden30_pct"]].isna().any().any():
        raise ValueError("Covariates do not cover every panel row")
    frame["burden30_pct_se"] = frame["burden30_pct_moe90"] / Z90
    frame["young_burden30_pct"] = np.where(frame["age_group"].eq("20-24"),
                                           frame["young15_24_burden30_pct"],
                                           frame["young25_34_burden30_pct"])
    frame["young_burden30_pct_se"] = np.where(frame["age_group"].eq("20-24"),
                                              frame["young15_24_burden30_pct_se"],
                                              frame["young25_34_burden30_pct_se"])
    frame["log_rate"] = np.log(frame["outcome_rate"])
    frame["trend"] = frame["year"] - 2014
    return frame


# ------------------------------------------------------------------ estimator

@dataclass
class Fit:
    names: list[str]
    coef: np.ndarray
    vcov: np.ndarray
    n: int
    clusters: int
    k: int
    residuals: np.ndarray = field(repr=False)
    design: np.ndarray = field(repr=False)
    weights: np.ndarray = field(repr=False)

    @property
    def df(self) -> int:
        return self.clusters - 1

    def row(self, name: str, scale: float = SCALE) -> dict:
        i = self.names.index(name)
        estimate, se = self.coef[i] * scale, np.sqrt(self.vcov[i, i]) * scale
        t = estimate / se
        half = stats.t.ppf(0.975, self.df) * se
        return {"estimate_per10": estimate, "se": se, "ci_low": estimate - half,
                "ci_high": estimate + half, "t": t,
                "p_value": float(2 * stats.t.sf(abs(t), self.df)), "n": self.n,
                "clusters": self.clusters, "k": self.k}

    def contrast(self, weights_by_name: dict[str, float], scale: float = SCALE) -> dict:
        vector = np.zeros(len(self.names))
        for name, w in weights_by_name.items():
            vector[self.names.index(name)] = w
        estimate = float(vector @ self.coef) * scale
        se = float(np.sqrt(vector @ self.vcov @ vector)) * scale
        half = stats.t.ppf(0.975, self.df) * se
        return {"estimate_per10": estimate, "se": se, "ci_low": estimate - half,
                "ci_high": estimate + half,
                "p_value": float(2 * stats.t.sf(abs(estimate / se), self.df)),
                "n": self.n, "clusters": self.clusters, "k": self.k}


def build_design(frame: pd.DataFrame, regressors: list[str], absorb: list[str],
                 trends: str | None = None,
                 nuisance: list[str] = ()) -> tuple[np.ndarray, list[str]]:
    """Regressors first, then a constant, nuisance columns, fixed-effect dummies and trends."""
    blocks = [frame[regressors].to_numpy(float), np.ones((len(frame), 1))]
    names = [*regressors, "const"]
    if nuisance:
        blocks.append(frame[list(nuisance)].to_numpy(float))
        names += list(nuisance)
    for column in absorb:
        dummies = pd.get_dummies(frame[column].astype(str), drop_first=True, dtype=float)
        blocks.append(dummies.to_numpy())
        names += [f"{column}={c}" for c in dummies.columns]
    if trends:
        units = sorted(frame[trends].unique())[1:]
        centred = frame["trend"] - frame["trend"].mean()
        for unit in units:
            blocks.append((centred * frame[trends].eq(unit)).to_numpy(float)[:, None])
            names.append(f"trend:{unit}")
    return np.hstack(blocks), names


def fit(frame: pd.DataFrame, outcome: str, regressors: list[str],
        absorb: list[str] = ("state_fips", "year"), trends: str | None = None,
        weight: str | None = None, cluster: str = "state_fips",
        nuisance: list[str] = ()) -> Fit:
    """OLS with dummy fixed effects and CR1 state-clustered variance."""
    data = frame.dropna(subset=[outcome, *regressors]).reset_index(drop=True)
    if data.empty:
        raise ValueError("No observations")
    X, names = build_design(data, list(regressors), list(absorb), trends, nuisance)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise ValueError("Rank-deficient design: a regressor is not identified")
    y = data[outcome].to_numpy(float)
    w = data[weight].to_numpy(float) if weight else np.ones(len(data))
    w = w / w.mean()
    xw = X * w[:, None]
    bread = np.linalg.inv(X.T @ xw)
    beta = bread @ (xw.T @ y)
    residuals = y - X @ beta
    groups = pd.factorize(data[cluster])[0]
    clusters = groups.max() + 1
    if clusters < 2:
        raise ValueError("Need at least two clusters")
    scores = np.zeros((clusters, X.shape[1]))
    np.add.at(scores, groups, X * (w * residuals)[:, None])
    n, k = X.shape
    factor = clusters / (clusters - 1) * (n - 1) / (n - k)
    vcov = factor * bread @ (scores.T @ scores) @ bread
    keep = len(regressors)
    return Fit(names[:keep], beta[:keep], vcov[:keep, :keep], n, int(clusters), k,
               residuals, X, w)


def wild_cluster_p(frame: pd.DataFrame, outcome: str, regressors: list[str], target: str,
                   absorb=("state_fips", "year"), cluster: str = "state_fips",
                   replicates: int = BOOTSTRAP, seed: int = SEED,
                   contrast: dict[str, float] | None = None,
                   nuisance: list[str] = ()) -> float:
    """Restricted wild cluster bootstrap (Rademacher) p-value for a coefficient or contrast."""
    data = frame.dropna(subset=[outcome, *regressors]).reset_index(drop=True)
    X, _ = build_design(data, list(regressors), list(absorb), nuisance=nuisance)
    y = data[outcome].to_numpy(float)
    vector = np.zeros(X.shape[1])
    for name, w in (contrast or {target: 1.0}).items():
        vector[regressors.index(name)] = w
    # restricted fit: impose vector @ beta = 0 by reparameterizing with the constraint
    bread = np.linalg.inv(X.T @ X)
    beta = bread @ X.T @ y
    adjust = bread @ vector / (vector @ bread @ vector)
    beta_r = beta - adjust * (vector @ beta)
    fitted_r, resid_r = X @ beta_r, y - X @ beta_r
    groups = pd.factorize(data[cluster])[0]
    clusters = groups.max() + 1
    n, k = X.shape
    factor = clusters / (clusters - 1) * (n - 1) / (n - k)
    z = X @ (bread @ vector)

    def t_stat(y_star: np.ndarray) -> float:
        b = bread @ (X.T @ y_star)
        u = y_star - X @ b
        s = np.zeros(clusters)
        np.add.at(s, groups, z * u)
        return float(vector @ b / np.sqrt(factor * (s @ s)))

    observed = t_stat(y)
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(replicates):
        signs = rng.choice((-1.0, 1.0), size=clusters)[groups]
        exceed += abs(t_stat(fitted_r + resid_r * signs)) >= abs(observed)
    return (exceed + 1) / (replicates + 1)


# ------------------------------------------------------------------ models

def age_frame(frame: pd.DataFrame, age: str) -> pd.DataFrame:
    return frame[frame["age_group"].eq(age)].reset_index(drop=True)


def main_models(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    specs = [
        ("A pooled", "burden30_pct", [], []),
        ("B state FE", "burden30_pct", [], ["state_fips"]),
        ("C state + year FE (primary)", "burden30_pct", [], ["state_fips", "year"]),
        ("D + unemployment", "burden30_pct", ["unemployment_pct"], ["state_fips", "year"]),
        ("E one-year lag", "burden30_pct_lag1", [], ["state_fips", "year"]),
    ]
    for age in AGES:
        data = age_frame(frame, age)
        for model, exposure, controls, absorb in specs:
            result = fit(data, "outcome_rate", [exposure, *controls], absorb)
            rows.append({"age_group": age, "model": model, "exposure": exposure,
                         **result.row(exposure)})
    return pd.DataFrame(rows)


def stacked_model(frame: pd.DataFrame) -> tuple[dict, Fit]:
    """Both age groups with state x age effects and age-specific year effects.

    Year effects for ages 25-29 enter as common year dummies plus explicit
    year x (age 25-29) dummies, which avoids a redundant age intercept.
    """
    data = frame.copy()
    data["state_age"] = data["state_fips"] + "_" + data["age_group"]
    older = data["age_group"].eq("25-29")
    years = sorted(data["year"].unique())[1:]
    nuisance = []
    for year in years:
        data[f"year{year}_x_25_29"] = (data["year"].eq(year) & older).astype(float)
        nuisance.append(f"year{year}_x_25_29")
    for age in AGES:
        data[f"burden_{age}"] = data["burden30_pct"] * data["age_group"].eq(age)
    regressors = [f"burden_{a}" for a in AGES]
    absorb = ("state_age", "year")
    result = fit(data, "outcome_rate", regressors, absorb, nuisance=nuisance)
    contrast = result.contrast({"burden_20-24": 1.0, "burden_25-29": -1.0})
    contrast["wild_bootstrap_p"] = wild_cluster_p(
        data, "outcome_rate", regressors, "burden_20-24", absorb=absorb,
        contrast={"burden_20-24": 1.0, "burden_25-29": -1.0}, nuisance=nuisance)
    return contrast, result


def robustness(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(age, analysis, variant, result, name, note=""):
        rows.append({"age_group": age, "analysis": analysis, "variant": variant,
                     **result.row(name), "note": note})

    for age in AGES:
        data = age_frame(frame, age)
        fe = ["state_fips", "year"]
        for label, years in (("2014-2019", range(2014, 2020)), ("2021-2024", range(2021, 2025))):
            subset = data[data["year"].isin(list(years))]
            note = ("Gen Z-relevant period; 4 years, possibly underpowered"
                    if age == "20-24" and label == "2021-2024" else "")
            add(age, "period", label, fit(subset, "outcome_rate", ["burden30_pct"], fe),
                "burden30_pct", note)
        add(age, "weighting", "female-population weighted",
            fit(data, "outcome_rate", ["burden30_pct"], fe, weight="female_population"),
            "burden30_pct", "population-weighted average of within-state associations")
        add(age, "sample", "excluding DC",
            fit(data[data["state_fips"].ne("11")], "outcome_rate", ["burden30_pct"], fe),
            "burden30_pct")
        add(age, "lag", "contemporaneous + lag (lag coefficient)",
            fit(data, "outcome_rate", ["burden30_pct", "burden30_pct_lag1"], fe),
            "burden30_pct_lag1")
        add(age, "lag", "contemporaneous + lag (contemporaneous coefficient)",
            fit(data, "outcome_rate", ["burden30_pct", "burden30_pct_lag1"], fe),
            "burden30_pct")
        add(age, "exposure", "severe burden 50%+",
            fit(data, "outcome_rate", ["severe50_pct"], fe), "severe50_pct")
        add(age, "exposure", "B25072 age-matched renter householders 30%+",
            fit(data, "outcome_rate", ["young_burden30_pct"], fe), "young_burden30_pct",
            "householders 15-24 (for 20-24) or 25-34 (for 25-29); not the mothers")
        add(age, "trends", "state-specific linear trends",
            fit(data, "outcome_rate", ["burden30_pct"], fe, trends="state_fips"),
            "burden30_pct")
        add(age, "controls", "unemployment + log median household income",
            fit(data, "outcome_rate", ["burden30_pct", "unemployment_pct",
                                       "log_median_household_income"], fe),
            "burden30_pct", "income is the burden denominator: possible overadjustment")
        add(age, "outcome", "log rate (x100 = approx. percent per 10 pp)",
            fit(data, "log_rate", ["burden30_pct"], fe), "burden30_pct")
    table = pd.DataFrame(rows)
    table.loc[table["analysis"].eq("outcome"), ["estimate_per10", "se", "ci_low",
                                                 "ci_high"]] *= 100
    table["bh_q_exploratory"] = benjamini_hochberg(table["p_value"])
    return table


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    order = p.sort_values()
    m = len(order)
    q = (order * m / np.arange(1, m + 1))[::-1].cummin()[::-1].clip(upper=1)
    return q.reindex(p.index)


def holm(p: pd.Series) -> pd.Series:
    order = p.sort_values()
    m = len(order)
    adjusted = np.maximum.accumulate([(m - i) * v for i, v in enumerate(order)])
    return pd.Series(np.minimum(adjusted, 1), index=order.index).reindex(p.index)


def leave_one_state_out(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for age in AGES:
        data = age_frame(frame, age)
        full = fit(data, "outcome_rate", ["burden30_pct"]).row("burden30_pct")["estimate_per10"]
        for state, name in data.groupby("state_fips")["state_name"].first().items():
            result = fit(data[data["state_fips"].ne(state)], "outcome_rate", ["burden30_pct"])
            row = result.row("burden30_pct")
            rows.append({"age_group": age, "dropped_state": name, "state_fips": state,
                         "estimate_per10": row["estimate_per10"], "se": row["se"],
                         "p_value": row["p_value"],
                         "change_from_full": row["estimate_per10"] - full})
    return pd.DataFrame(rows)


def measurement_error(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(i) added-noise stability; (ii) exploratory SIMEX under classical-error assumptions."""
    rng = np.random.default_rng(SEED)
    stability, simex = [], []
    for age in AGES:
        data = age_frame(frame, age)
        X, _ = build_design(data, ["burden30_pct"], ["state_fips", "year"])
        y = data["outcome_rate"].to_numpy(float)
        x = data["burden30_pct"].to_numpy(float)
        se = data["burden30_pct_se"].to_numpy(float)

        def slope(values: np.ndarray) -> float:
            X[:, 0] = values
            return float(np.linalg.lstsq(X, y, rcond=None)[0][0]) * SCALE

        base = slope(x)
        draws = np.array([slope(x + rng.normal(0, se)) for _ in range(NOISE_DRAWS)])
        stability.append({"age_group": age, "estimate_per10": base,
                          "noise_added_mean": draws.mean(), "noise_added_sd": draws.std(),
                          "noise_added_p2_5": np.quantile(draws, 0.025),
                          "noise_added_p97_5": np.quantile(draws, 0.975),
                          "share_same_sign": float((np.sign(draws) == np.sign(base)).mean())})
        means = []
        for lam in SIMEX_LAMBDAS:
            values = [slope(x + rng.normal(0, np.sqrt(lam) * se)) for _ in range(
                SIMEX_DRAWS if lam else 1)]
            means.append(float(np.mean(values)))
        quadratic = np.polyfit(SIMEX_LAMBDAS, means, 2)
        simex.append({"age_group": age, **{f"lambda_{lam}": m for lam, m in
                                           zip(SIMEX_LAMBDAS, means)},
                      "simex_extrapolated_lambda_minus1": float(np.polyval(quadratic, -1.0)),
                      "status": "exploratory; assumes classical independent normal errors "
                                "with approximate ACS SEs as true error SDs"})
        X[:, 0] = x
    return pd.DataFrame(stability), pd.DataFrame(simex)


# ------------------------------------------------------------------ diagnostics

def two_way_demean(frame: pd.DataFrame, column: str) -> pd.Series:
    values = frame[column]
    return (values - frame.groupby("state_fips")[column].transform("mean")
            - frame.groupby("year")[column].transform("mean") + values.mean())


def diagnostics(frame: pd.DataFrame) -> dict:
    out = {}
    for age in AGES:
        data = age_frame(frame, age)
        result = fit(data, "outcome_rate", ["burden30_pct"])
        u = result.residuals
        within_x = two_way_demean(data, "burden30_pct")
        # Breusch-Pagan on within residuals and exposure
        e2 = u ** 2
        slope, intercept, r, *_ = stats.linregress(within_x, e2)
        bp = len(u) * r ** 2
        # VIF of within-transformed regressors (model D2)
        within = pd.DataFrame({c: two_way_demean(data, c) for c in
                               ("burden30_pct", "unemployment_pct",
                                "log_median_household_income")})
        corr = np.linalg.inv(np.corrcoef(within.to_numpy().T))
        vif = dict(zip(within.columns, np.diag(corr)))
        # Wooldridge serial-correlation test using consecutive calendar years only
        ordered = data.sort_values(["state_fips", "year"]).copy()
        diff = ordered.groupby("state_fips")[["outcome_rate", "burden30_pct", "year"]].diff()
        ordered["dy"] = diff["outcome_rate"]
        ordered["dx"] = diff["burden30_pct"]
        ordered["gap"] = diff["year"]
        fd = ordered[ordered["gap"].eq(1)].copy()
        fd_fit = fit(fd, "dy", ["dx"], ["year"])
        fd["e"] = fd_fit.residuals
        fd["e_lag"] = fd.groupby("state_fips")["e"].shift()
        fd["year_gap"] = fd.groupby("state_fips")["year"].diff()
        pairs = fd[fd["year_gap"].eq(1)].dropna(subset=["e_lag"]).copy()
        ar = fit(pairs, "e", ["e_lag"], [])
        ar_row = ar.row("e_lag", scale=1.0)
        wooldridge_t = (ar_row["estimate_per10"] + 0.5) / ar_row["se"]
        # Pesaran CD on two-way residuals (balanced states x years)
        wide = pd.Series(u, index=pd.MultiIndex.from_frame(data[["state_fips", "year"]])) \
            .unstack("year")
        rho = np.corrcoef(wide.to_numpy())
        n_states, n_years = wide.shape
        cd = np.sqrt(2 * n_years / (n_states * (n_states - 1))) * \
            rho[np.triu_indices(n_states, 1)].sum()
        # cluster influence (dfbeta by state)
        out[age] = {
            "observations": result.n, "clusters": result.clusters,
            "within_state_sd_exposure": float(data.groupby("state_fips")["burden30_pct"]
                                              .std().mean()),
            "two_way_residual_sd_exposure": float(within_x.std()),
            "breusch_pagan_lm": float(bp), "breusch_pagan_p": float(stats.chi2.sf(bp, 1)),
            "vif_within": {k: float(v) for k, v in vif.items()},
            "wooldridge_ar_coefficient": ar_row["estimate_per10"],
            "wooldridge_t_vs_minus_half": float(wooldridge_t),
            "wooldridge_p": float(2 * stats.t.sf(abs(wooldridge_t), ar.df)),
            "wooldridge_pairs": ar.n,
            "pesaran_cd": float(cd),
            "pesaran_cd_p": float(2 * stats.norm.sf(abs(cd))),
            "max_leverage": float(np.max(np.sum(result.design @ np.linalg.inv(
                result.design.T @ result.design) * result.design, axis=1))),
        }
    return out


# ------------------------------------------------------------------ assembly

def primary_tests(frame: pd.DataFrame, models: pd.DataFrame, stacked: dict) -> pd.DataFrame:
    rows = []
    for age, role in (("20-24", "primary"), ("25-29", "secondary")):
        row = models[models["age_group"].eq(age)
                     & models["model"].str.startswith("C ")].iloc[0].to_dict()
        row["wild_bootstrap_p"] = wild_cluster_p(age_frame(frame, age), "outcome_rate",
                                                 ["burden30_pct"], "burden30_pct")
        rows.append({"test": f"beta {age} = 0 (model C)", "role": role, **row})
    rows.append({"test": "beta 20-24 - beta 25-29 = 0 (stacked)", "role": "secondary",
                 "age_group": "both", "model": "stacked", **stacked})
    table = pd.DataFrame(rows)
    secondary = table["role"].eq("secondary")
    table.loc[secondary, "holm_p"] = holm(table.loc[secondary, "p_value"])
    return table


# Shorter row text where the bracketed measure already names the exposure.
DISPLAY_VARIANT = {"B25072 age-matched renter householders 30%+": "age-matched householders",
                   "severe burden 50%+": "severe burden",
                   "contemporaneous + lag (lag coefficient)": "with contemporaneous term, lag",
                   "contemporaneous + lag (contemporaneous coefficient)":
                       "with lag term, contemporaneous",
                   "unemployment + log median household income":
                       "unemployment + log median income"}
MODEL_EXPOSURE = {"burden30_pct": "30%+ burden, B25070",
                  "burden30_pct_lag1": "30%+ burden in year t-1, B25070"}


def robustness_exposure(row) -> str:
    """Housing measure behind each robustness estimate, for its figure label."""
    if "50%" in row.variant:
        return "50%+ burden, B25070"
    if "B25072" in row.variant:
        return "30%+ burden, B25072"
    if "lag coefficient" in row.variant:
        return "30%+ burden in year t-1, B25070"
    return "30%+ burden, B25070"


def coefficient_rows(models: pd.DataFrame, robust: pd.DataFrame, age: str) -> pd.DataFrame:
    """The estimates the coefficient figure draws for one age group, in plotting order."""
    main = models[models["age_group"].eq(age) & ~models["model"].str.startswith("A ")]
    extra = robust[robust["age_group"].eq(age) & robust["analysis"].ne("outcome")]
    rows = [{"label": f"{r.model} [{MODEL_EXPOSURE[r.exposure]}]", "source": "models",
             "key": r.model, "estimate_per10": r.estimate_per10, "ci_low": r.ci_low,
             "ci_high": r.ci_high, "protocol_model": True} for r in main.itertuples()]
    rows += [{"label": f"{r.analysis}: {DISPLAY_VARIANT.get(r.variant, r.variant)} "
                       f"[{robustness_exposure(r)}]",
              "source": "robustness", "key": r.variant, "estimate_per10": r.estimate_per10,
              "ci_low": r.ci_low, "ci_high": r.ci_high, "protocol_model": False}
             for r in extra.itertuples()]
    return pd.DataFrame(rows).assign(age_group=age)


def figure_coefficients(models: pd.DataFrame, robust: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Draw the coefficient figure and return exactly the values plotted."""
    apply_figure_style()
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.6), sharex=True, sharey=True)
    plotted = []
    for ax, age in zip(axes, AGES):
        rows = coefficient_rows(models, robust, age)
        y = np.arange(len(rows))[::-1]
        for yi, row in zip(y, rows.itertuples()):
            color = INK["series"] if row.protocol_model else INK["secondary"]
            ax.plot([row.ci_low, row.ci_high], [yi, yi], color=color, linewidth=2)
            ax.plot(row.estimate_per10, yi, "o", color=color, markersize=6)
        ax.axvline(0, color=INK["muted"], linewidth=1, linestyle="--")
        ax.set_yticks(y, rows["label"], fontsize=7.5)
        ax.set_title(f"Ages {age}", fontsize=11)
        ax.grid(axis="y", visible=False)
        plotted.append(rows)
    fig.supxlabel("Change in births per 1,000 women per 10-percentage-point increase in the "
                  "housing-burden measure named in brackets (95% CI, state-clustered)\n"
                  "Blue: protocol models B-E (C primary). Grey: exploratory robustness "
                  "checks. Pooled model A omitted.", fontsize=9)
    fig.suptitle("Within-state association of rental housing burden with fertility "
                 "(51 state clusters)", x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.subplots_adjust(left=0.29, wspace=0.06)  # room for the longest shared row label
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return pd.concat(plotted, ignore_index=True)


def run() -> dict:
    lock = verify_protocol()
    frame = load_analysis_frame()
    models = main_models(frame)
    stacked, _ = stacked_model(frame)
    primary = primary_tests(frame, models, stacked)
    robust = robustness(frame)
    loso = leave_one_state_out(frame)
    stability, simex = measurement_error(frame)
    diagnostic = diagnostics(frame)
    return {"lock": lock, "frame": frame, "models": models, "primary": primary,
            "robustness": robust, "loso": loso, "noise_stability": stability,
            "simex": simex, "diagnostics": diagnostic}


def main() -> int:
    results = run()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("models", "primary", "robustness", "loso", "noise_stability", "simex"):
        results[name].to_csv(OUTPUT_DIR / f"m10_{name}.csv", index=False, float_format="%.10g")
    summary = {"protocol_sha256": results["lock"]["sha256"],
               "diagnostics": results["diagnostics"],
               "sample": {"rows_per_age_group": int(len(age_frame(results["frame"], "20-24"))),
                          "stacked_rows": len(results["frame"]),
                          "clusters": int(results["frame"]["state_fips"].nunique())}}
    (OUTPUT_DIR / "m10_model_summary.json").write_text(
        json.dumps(summary, indent=1, default=float) + "\n", encoding="utf-8")
    figure_coefficients(results["models"], results["robustness"],
                        FIGURE_DIR / "m10_coefficients.png")
    pd.set_option("display.width", 200)
    columns = ["age_group", "model", "estimate_per10", "se", "ci_low", "ci_high", "p_value", "n",
               "clusters"]
    print(results["models"][columns].round(3).to_string(index=False))
    print(results["primary"][["test", "role", "estimate_per10", "ci_low", "ci_high", "p_value",
                              "wild_bootstrap_p", "holm_p"]].round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
