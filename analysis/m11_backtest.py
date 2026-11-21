"""M11 rolling-origin backtests, evaluation metrics, model selection and interval calibration.

Implements sections 4, 7, 8 and 9 of the locked protocol
(docs/m11_forecast_protocol.md). At each origin T the forecasting functions
receive only training years <= T (and >= the window start); every backtest
record stores the training span, so leakage can be audited afterwards.
"""

import numpy as np
import pandas as pd
from scipy import stats

from analysis import hfd
from analysis import m11_models as models
from analysis.m11_protocol import load_config

CONFIG = load_config()
BT = CONFIG["backtest"]
AGES = list(range(CONFIG["data"]["ages"][0], CONFIG["data"]["ages"][1] + 1))
PRIMARY_H = tuple(BT["primary_horizons"])
LEVELS = tuple(CONFIG["intervals"]["levels"])
MIN_CAL = CONFIG["intervals"]["min_calibration_errors"]


# ------------------------------------------------------------------- data

def rate_matrix(table: pd.DataFrame) -> pd.DataFrame:
    """Year x age ASFR matrix (ages 12-55) with checks for gaps, invalid ages and negative rates."""
    ages = set(table["Age"].astype(int))
    if ages - set(AGES):
        raise ValueError(f"ages outside {AGES[0]}-{AGES[-1]}: {sorted(ages - set(AGES))}")
    wide = table.pivot(index="Year", columns="Age", values="ASFR").reindex(columns=AGES)
    wide.index = wide.index.astype(int)
    years = list(wide.index)
    if years != list(range(years[0], years[-1] + 1)):
        raise ValueError("calendar years are not contiguous")
    if wide.isna().any().any():
        raise ValueError(f"{int(wide.isna().sum().sum())} missing age-year rates")
    if (wide < 0).any().any():
        raise ValueError("negative fertility rates")
    return wide.astype(float)


def hfd_rates() -> pd.DataFrame:
    rates = rate_matrix(hfd.read_hfd("USAasfrRR"))
    first, last = CONFIG["data"]["first_year"], CONFIG["data"]["last_year"]
    if (rates.index[0], rates.index[-1]) != (first, last):
        raise ValueError(f"HFD years {rates.index[0]}-{rates.index[-1]} differ from protocol {first}-{last}")
    return rates


def tfr_series(rates: pd.DataFrame) -> pd.Series:
    return rates.sum(axis=1).rename("tfr")


def era_of(origin: int) -> str:
    for name, (start, end) in BT["eras"].items():
        if start <= origin <= end:
            return name
    return "none"


# --------------------------------------------------------------- TFR backtest

def training_slice(series: pd.Series, origin: int, start: int | None = None, window: int | None = None) -> pd.Series:
    train = series[series.index <= origin]
    if start is not None:
        train = train[train.index >= start]
    if window is not None:
        train = train.iloc[-window:]
    return train


def tfr_backtest(tfr: pd.Series, origins, methods=models.TFR_METHODS, max_h: int = BT["max_horizon"],
                 start: int | None = None, window: int | None = None, last_target: int | None = None) -> pd.DataFrame:
    """One record per (method, origin, horizon) with target year <= last_target.

    Forecasts use only years <= origin; observed values are attached afterwards.
    """
    last_target = int(tfr.index.max()) if last_target is None else last_target
    log_tfr = np.log(tfr)
    rows = []
    for origin in origins:
        train = training_slice(log_tfr, origin, start, window)
        if len(train) < BT["min_train"]:
            continue
        horizon = min(max_h, last_target - origin)
        if horizon < 1:
            continue
        for method in methods:
            out = models.forecast_tfr(method, train.to_numpy(), horizon)
            for h in range(1, horizon + 1):
                rows.append({"method": method, "origin": int(origin), "h": h, "target": int(origin + h),
                             "train_first": int(train.index[0]), "train_last": int(train.index[-1]),
                             "train_years": len(train), "log_forecast": float(out["log_mean"][h - 1]),
                             "log_sd_model": (np.nan if out["log_sd_model"] is None
                                              else float(out["log_sd_model"][h - 1])),
                             "scale": float(np.mean(np.abs(np.diff(np.exp(train.to_numpy()))))),
                             "params": _params_text(out["params"])})
    records = pd.DataFrame(rows)
    if records.empty:
        return records
    if (records["train_last"] > records["origin"]).any() or (records["target"] <= records["train_last"]).any():
        raise AssertionError("training data extend beyond the forecast origin")
    records["forecast"] = np.exp(records["log_forecast"])
    observed = tfr.reindex(records["target"]).to_numpy()
    records["observed"] = observed
    records["error"] = records["observed"] - records["forecast"]
    records["log_error"] = np.log(records["observed"]) - records["log_forecast"]
    records["era"] = records["origin"].map(era_of)
    lo, hi = CONFIG["forecast"]["plausible_range"]
    records["implausible"] = ~records["forecast"].between(lo, hi)
    return records


def _params_text(params: dict) -> str:
    parts = []
    for key, value in params.items():
        if isinstance(value, list):
            parts.append(f"{key}=[" + ",".join(f"{v:.12g}" for v in value) + "]")
        else:
            parts.append(f"{key}={value:.12g}" if isinstance(value, float) else f"{key}={value}")
    return ";".join(parts)


# ------------------------------------------------------------------ metrics

def windows(n: int, h: int) -> int:
    return -(-n // h)


def point_metrics(records: pd.DataFrame, by=("method", "h")) -> pd.DataFrame:
    by = list(by)
    grouped = records.groupby(by)
    table = grouped.agg(origins=("origin", "nunique"), first_origin=("origin", "min"), last_origin=("origin", "max"),
                        bias=("error", "mean"), mae=("error", lambda e: e.abs().mean()),
                        rmse=("error", lambda e: np.sqrt(np.mean(e ** 2))),
                        rms_log_error=("log_error", lambda e: np.sqrt(np.mean(e ** 2)))).reset_index()
    scaled = records.assign(scaled=records["error"].abs() / records["scale"])
    table = table.merge(scaled.groupby(by)["scaled"].mean().rename("mase").reset_index(), on=by)
    naive = records[records["method"] == "naive"].set_index(["origin", "h"])["error"].abs()
    aligned = records.join(naive.rename("naive_abs"), on=["origin", "h"])
    ratio = aligned.groupby(by).apply(lambda g: g["error"].abs().mean() / g["naive_abs"].mean(),
                                      include_groups=False).rename("relative_mae").reset_index()
    table = table.merge(ratio, on=by)
    if "h" in by:
        table["non_overlapping_windows"] = [windows(n, h) for n, h in zip(table["origins"], table["h"])]
    return table


def _abs_errors(records: pd.DataFrame, method: str, h: int, col: str = "error") -> pd.Series:
    sub = records[(records["method"] == method) & (records["h"] == h)]
    return sub.set_index("origin")[col].abs().sort_index()


def block_indices(n: int, block: int, reps: int, rng) -> np.ndarray:
    """Circular moving-block bootstrap indices (reps x n)."""
    blocks = -(-n // block)
    starts = rng.integers(0, n, size=(reps, blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    return idx.reshape(reps, -1)[:, :n]


def bootstrap_ratio(records: pd.DataFrame, methods, baseline: str = "naive", horizons=PRIMARY_H,
                    reps: int = BT["bootstrap_reps"], seed: int = BT["seed"], col: str = "error") -> dict:
    """Replicates of the mean (over horizons) MAE ratio method / baseline, common resamples across methods."""
    rng = np.random.default_rng(seed)
    out = {m: np.zeros(reps) for m in methods}
    for h in horizons:
        base = _abs_errors(records, baseline, h, col)
        idx = block_indices(len(base), h, reps, rng)
        base_mean = base.to_numpy()[idx].mean(axis=1)
        for m in methods:
            errs = _abs_errors(records, m, h, col).reindex(base.index).to_numpy()
            out[m] += errs[idx].mean(axis=1) / base_mean / len(horizons)
    return out


def dm_test(records: pd.DataFrame, method: str, h: int, baseline: str = "naive") -> dict:
    """Diebold-Mariano on absolute loss, Bartlett HAC lag h-1, Harvey-Leybourne-Newbold correction."""
    a = _abs_errors(records, method, h)
    b = _abs_errors(records, baseline, h).reindex(a.index)
    d = (a - b).to_numpy()
    n = len(d)
    if n < 3 or np.allclose(d, 0):
        return {"dm_stat": np.nan, "dm_p": np.nan}
    dc = d - d.mean()
    var = dc @ dc / n
    for k in range(1, h):
        if k < n:
            var += 2 * (1 - k / h) * (dc[k:] @ dc[:-k]) / n
    if var <= 0:
        return {"dm_stat": np.nan, "dm_p": np.nan}
    stat = d.mean() / np.sqrt(var / n)
    correction = np.sqrt(max(n + 1 - 2 * h + h * (h - 1) / n, 1e-12) / n)
    stat *= correction
    return {"dm_stat": float(stat), "dm_p": float(2 * stats.t.sf(abs(stat), df=n - 1))}


def selection_table(records: pd.DataFrame, candidates, baseline: str, loss_col: str = "error",
                    split: int = BT["selection_split"], complexity: dict | None = None) -> pd.DataFrame:
    """Criteria of the locked selection rule (protocol section 7) for every candidate."""
    sel = CONFIG["selection"]
    boot = bootstrap_ratio(records, candidates, baseline, col=loss_col)
    rows = []
    for m in candidates:
        ratios, early, late = {}, {}, {}
        for h in PRIMARY_H:
            sub = records[records["h"] == h]
            own = sub[sub["method"] == m].set_index("origin")[loss_col].abs()
            base = sub[sub["method"] == baseline].set_index("origin")[loss_col].abs().reindex(own.index)
            ratios[h] = own.mean() / base.mean()
            early[h] = own[own.index < split].mean() / base[base.index < split].mean()
            late[h] = own[own.index >= split].mean() / base[base.index >= split].mean()
        r = float(np.mean(list(ratios.values())))
        upper = float(np.quantile(boot[m], sel["bootstrap_upper"]))
        c1 = r <= sel["max_ratio"]
        c2 = all(v < 1 for v in early.values()) and all(v < 1 for v in late.values())
        c3 = upper < 1
        row = {"method": m, "R": r, "bootstrap_p90": upper,
               **{f"ratio_h{h}": ratios[h] for h in PRIMARY_H},
               **{f"ratio_h{h}_before_{split}": early[h] for h in PRIMARY_H},
               **{f"ratio_h{h}_from_{split}": late[h] for h in PRIMARY_H},
               "c1_ratio_le_0.90": c1, "c2_both_eras": c2, "c3_bootstrap": c3,
               "qualifies": bool(c1 and c2 and c3) and m != baseline}
        if loss_col == "error":
            for h in PRIMARY_H:
                row.update({f"dm_p_h{h}": dm_test(records, m, h, baseline)["dm_p"]})
        rows.append(row)
    table = pd.DataFrame(rows)
    if complexity is not None:
        table["complexity"] = table["method"].map(complexity)
    return table


def choose(table: pd.DataFrame, baseline: str, order) -> str:
    """Apply the selection and simplicity rules to a selection table."""
    qualified = table[table["qualifies"]]
    if qualified.empty:
        return baseline
    best = qualified["R"].min()
    near = qualified[qualified["R"] <= best + CONFIG["selection"]["simplicity_margin"]]
    if "complexity" in near:
        near = near.assign(position=near["method"].map({m: i for i, m in enumerate(order)}))
        near = near.sort_values(["complexity", "position"])
        return str(near.iloc[0]["method"])
    return str(near.sort_values("R").iloc[0]["method"])


# ---------------------------------------------------------------- intervals

def lognormal_crps(mu, sigma, y):
    """CRPS of a log-normal(mu, sigma) forecast at y (Baran and Lerch, 2015)."""
    mu, sigma, y = (np.asarray(v, dtype=float) for v in (mu, sigma, y))
    w = (np.log(y) - mu) / sigma
    return (y * (2 * stats.norm.cdf(w) - 1)
            - 2 * np.exp(mu + sigma ** 2 / 2) * (stats.norm.cdf(w - sigma) + stats.norm.cdf(sigma / np.sqrt(2)) - 1))


def interval_score(lower, upper, y, level):
    alpha = 1 - level
    return (upper - lower) + (2 / alpha) * np.maximum(lower - y, 0) + (2 / alpha) * np.maximum(y - upper, 0)


def score_intervals(frame: pd.DataFrame, sigma_col: str) -> pd.DataFrame:
    """Add coverage, width, interval score and CRPS for a log-normal with sd in sigma_col."""
    out = frame.copy()
    valid = out[sigma_col].notna() & (out[sigma_col] > 0)
    out = out[valid].copy()
    for level in LEVELS:
        z = stats.norm.ppf(0.5 + level / 2)
        tag = int(round(level * 100))
        lower = np.exp(out["log_forecast"] - z * out[sigma_col])
        upper = np.exp(out["log_forecast"] + z * out[sigma_col])
        out[f"lower{tag}"], out[f"upper{tag}"] = lower, upper
        out[f"covered{tag}"] = (out["observed"] >= lower) & (out["observed"] <= upper)
        out[f"width{tag}"] = upper - lower
        out[f"iscore{tag}"] = interval_score(lower, upper, out["observed"], level)
    out["crps"] = lognormal_crps(out["log_forecast"], out[sigma_col], out["observed"])
    return out


def calibrated_sigma(records: pd.DataFrame, method: str, first_origin: int | None = None) -> pd.Series:
    """sigma_h = RMS of the method's log errors at horizon h over all (or later) backtest origins."""
    sub = records[records["method"] == method]
    if first_origin is not None:
        sub = sub[sub["origin"] >= first_origin]
    return sub.groupby("h")["log_error"].apply(lambda e: float(np.sqrt(np.mean(e ** 2))))


def real_time_sigma(records: pd.DataFrame) -> pd.DataFrame:
    """sigma_h(T) from errors with origin t and t + h <= T (same method and horizon); NaN if < 10 errors."""
    out = records.copy()
    out["sigma_rt"] = np.nan
    out["n_cal"] = 0
    for (method, h), group in records.groupby(["method", "h"]):
        group = group.sort_values("origin")
        targets = group["target"].to_numpy()
        sq = group["log_error"].to_numpy() ** 2
        origins = group["origin"].to_numpy()
        for idx, origin in zip(group.index, origins):
            usable = targets <= origin
            n = int(usable.sum())
            out.loc[idx, "n_cal"] = n
            if n >= MIN_CAL:
                out.loc[idx, "sigma_rt"] = float(np.sqrt(sq[usable].mean()))
    return out


def coverage_summary(scored: pd.DataFrame, by=("method", "h")) -> pd.DataFrame:
    by = list(by)
    agg = {"origins": ("origin", "nunique"), "crps": ("crps", "mean")}
    for level in LEVELS:
        tag = int(round(level * 100))
        agg |= {f"coverage{tag}": (f"covered{tag}", "mean"), f"width{tag}": (f"width{tag}", "mean"),
                f"iscore{tag}": (f"iscore{tag}", "mean")}
    return scored.groupby(by).agg(**agg).reset_index()


def coverage_bootstrap(scored: pd.DataFrame, method: str, level_tag: int = 80, horizons=PRIMARY_H,
                       reps: int = BT["bootstrap_reps"], seed: int = BT["seed"]) -> tuple[float, float, float]:
    """Mean coverage over horizons with a 90% circular-block-bootstrap interval."""
    rng = np.random.default_rng(seed)
    total, reps_total = 0.0, np.zeros(reps)
    for h in horizons:
        sub = scored[(scored["method"] == method) & (scored["h"] == h)].sort_values("origin")
        hits = sub[f"covered{level_tag}"].to_numpy(dtype=float)
        if len(hits) == 0:
            return (np.nan, np.nan, np.nan)
        total += hits.mean() / len(horizons)
        reps_total += hits[block_indices(len(hits), h, reps, rng)].mean(axis=1) / len(horizons)
    lo, hi = np.quantile(reps_total, [0.05, 0.95])
    return float(total), float(lo), float(hi)


# ------------------------------------------------- pseudo-real-time selection

def real_time_selection(records: pd.DataFrame, origins) -> pd.DataFrame:
    """The method the selection rule (conditions 1 and 3) would choose using errors observable at T."""
    sel = CONFIG["selection"]
    methods = list(models.TFR_METHODS)
    rows = []
    for origin in origins:
        known = records[records["target"] <= origin]
        counts = known[known["method"] == "naive"].groupby("h").size()
        if any(counts.get(h, 0) < MIN_CAL for h in PRIMARY_H):
            rows.append({"origin": origin, "chosen": "naive", "reason": "fewer than 10 errors per horizon"})
            continue
        candidates = [m for m in methods if m != "naive"]
        boot = bootstrap_ratio(known, candidates, "naive")
        scores = {}
        for m in candidates:
            r = np.mean([_abs_errors(known, m, h).mean() / _abs_errors(known, "naive", h).mean() for h in PRIMARY_H])
            if r <= sel["max_ratio"] and np.quantile(boot[m], sel["bootstrap_upper"]) < 1:
                scores[m] = r
        if not scores:
            rows.append({"origin": origin, "chosen": "naive", "reason": "no method qualified"})
            continue
        best = min(scores.values())
        near = [m for m in candidates if m in scores and scores[m] <= best + sel["simplicity_margin"]]
        near.sort(key=lambda m: (CONFIG["parameters"][m], methods.index(m)))
        rows.append({"origin": origin, "chosen": near[0], "reason": f"R={scores[near[0]]:.3f}"})
    return pd.DataFrame(rows)


# ----------------------------------------------------------- age profiles

def shape_backtest(rates: pd.DataFrame, origins, tfr_forecasts: pd.DataFrame, methods=models.SHAPE_METHODS,
                   max_h: int = BT["max_horizon"], keep_paths: bool = True):
    """Age-profile backtest. tfr_forecasts: selected TFR method records (origin, h, forecast).

    Returns (metrics per method x origin x h, dict of forecast paths) where paths
    hold coherent ASFR (TFR_selected x shape) and, for direct methods, own rates.
    """
    shape_cfg = CONFIG["shape"]
    ages = np.array(AGES) + 0.5
    level = tfr_forecasts.set_index(["origin", "h"])["forecast"]
    observed = rates.to_numpy()
    year_index = {int(y): i for i, y in enumerate(rates.index)}
    last_year = int(rates.index.max())
    rows, paths = [], {}
    for origin in origins:
        hist = rates[rates.index <= origin]
        if len(hist) < shape_cfg["min_window"]:
            continue
        window = hist.iloc[-shape_cfg["window"]:].to_numpy()
        horizon = min(max_h, last_year - origin) if last_year > origin else max_h
        tfr_path = np.array([level.get((origin, h), np.nan) for h in range(1, horizon + 1)])
        for method in methods:
            out = models.forecast_shape(method, window, horizon)
            coherent = models.coherent_rates(out["shape"], tfr_path) if np.all(np.isfinite(tfr_path)) else None
            if keep_paths:
                paths[(method, int(origin))] = {"shape": out["shape"], "coherent": coherent, "own": out["rates"]}
            for h in range(1, horizon + 1):
                target = origin + h
                if target not in year_index:
                    continue
                actual = observed[year_index[target]]
                actual_shape = actual / actual.sum()
                f_hat = out["shape"][h - 1]
                row = {"method": method, "origin": int(origin), "h": h, "target": int(target),
                       "window_first": int(hist.index[-len(window)]), "window_last": int(hist.index[-1]),
                       "shape_l1": float(np.abs(f_hat - actual_shape).sum()),
                       "mab_error": float((f_hat * ages).sum() - (actual_shape * ages).sum()),
                       "asfr_mae_coherent": (float(np.abs(coherent[h - 1] - actual).mean() * 1000)
                                             if coherent is not None else np.nan)}
                if out["rates"] is not None:
                    own = out["rates"][h - 1]
                    row["implied_tfr_error"] = float(actual.sum() - own.sum())
                    row["asfr_mae_unreconciled"] = float(np.abs(own - actual).mean() * 1000)
                rows.append(row)
    metrics = pd.DataFrame(rows)
    if not metrics.empty and (metrics["window_last"] > metrics["origin"]).any():
        raise AssertionError("age-profile training window extends beyond the origin")
    metrics["era"] = metrics["origin"].map(era_of)
    return metrics, paths


def shape_summary(metrics: pd.DataFrame, by=("method", "h")) -> pd.DataFrame:
    by = list(by)
    cols = {"origins": ("origin", "nunique"), "shape_l1": ("shape_l1", "mean"),
            "mab_mean_abs_error": ("mab_error", lambda e: e.abs().mean()), "mab_bias": ("mab_error", "mean"),
            "asfr_mae_coherent": ("asfr_mae_coherent", "mean")}
    if "implied_tfr_error" in metrics:
        cols |= {"implied_tfr_mae": ("implied_tfr_error", lambda e: e.abs().mean()),
                 "asfr_mae_unreconciled": ("asfr_mae_unreconciled", "mean")}
    return metrics.groupby(by).agg(**cols).reset_index()
