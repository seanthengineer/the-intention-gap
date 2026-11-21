"""M11 forecasting methods: period TFR (nine methods) and age profiles (five methods).

Every setting comes from the locked protocol (docs/m11_forecast_protocol.md,
section 5 and 9, and its configuration block). Functions take only the training
data they are given, so a caller that passes years <= origin cannot leak the
future into a forecast. All TFR methods work on log TFR; age-profile methods
work on log rates or on the log-ratio of the age shape, so every forecast rate
is positive.
"""

import numpy as np
from scipy.optimize import minimize

from analysis.m11_protocol import load_config

CONFIG = load_config()
ETS = CONFIG["ets"]
SETTINGS = CONFIG["method_settings"]
TFR_METHODS = tuple(CONFIG["methods"])
STOCHASTIC = ("naive", "ses", "holt_damped", "ar_level", "ari")   # methods with model-based intervals
SHAPE_METHODS = tuple(CONFIG["shape"]["methods"])
RATE_FLOOR = CONFIG["data"]["rate_floor"]
# Technical minimum (the 10-year drift needs 11 values); the backtest itself enforces 20 training years.
MIN_TFR_SERIES = max(SETTINGS["drift_years"] + 1, SETTINGS["mean_years"], 12)


def _check_series(y, minimum: int = 3) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    if y.ndim != 1 or len(y) < minimum:
        raise ValueError(f"need a 1-D series of at least {minimum} values")
    if not np.all(np.isfinite(y)):
        raise ValueError("series has missing or infinite values")
    return y


# ------------------------------------------------------------ exponential smoothing

def ses_errors(y: np.ndarray, alpha) -> np.ndarray:
    """One-step errors of ETS(A,N,N) with l0 = y[0]; alpha may be an array (vectorised grid)."""
    alpha = np.asarray(alpha, dtype=float)
    level = np.full(alpha.shape, y[0])
    errors = np.empty((len(y) - 1,) + alpha.shape)
    for t in range(1, len(y)):
        e = y[t] - level
        errors[t - 1] = e
        level = level + alpha * e
    return errors


def ses_state(y: np.ndarray, alpha: float) -> float:
    level = y[0]
    for t in range(1, len(y)):
        level += alpha * (y[t] - level)
    return level


def damped_errors(y, alpha, beta, phi):
    """One-step errors of ETS(A,Ad,N), l0 = y[0], b0 = y[1] - y[0].

    y has shape (n,) or (S, n) for S series; parameters broadcast against the
    leading series axis (vectorised grid search). Returns errors for t >= 2
    (the protocol excludes the first two steps) with time as the first axis.
    """
    y = np.asarray(y, dtype=float)
    series = y[None, :] if y.ndim == 1 else y                       # (S, n)
    alpha, beta, phi = (np.asarray(v, dtype=float) for v in (alpha, beta, phi))
    grid = alpha.ndim > 0
    shape = np.broadcast_shapes((series.shape[0], 1), alpha.shape, beta.shape, phi.shape) if grid \
        else (series.shape[0],)

    def column(values):
        return np.broadcast_to(values[:, None] if grid else values, shape)

    level = column(series[:, 0]).copy()
    trend = column(series[:, 1] - series[:, 0]).copy()
    n = series.shape[1]
    errors = np.empty((n - 2,) + shape)
    for t in range(1, n):
        prediction = level + phi * trend
        e = column(series[:, t]) - prediction
        if t >= 2:
            errors[t - 2] = e
        level = prediction + alpha * e
        trend = phi * trend + beta * e
    return errors[:, 0] if y.ndim == 1 else errors


def damped_state(y: np.ndarray, alpha: float, beta: float, phi: float) -> tuple[float, float]:
    level, trend = y[0], y[1] - y[0]
    for t in range(1, len(y)):
        prediction = level + phi * trend
        e = y[t] - prediction
        level = prediction + alpha * e
        trend = phi * trend + beta * e
    return level, trend


def _damped_sse(y: np.ndarray, params) -> float:
    alpha, beta_star, phi = params
    e = damped_errors(y, alpha, alpha * beta_star, phi)
    return float(np.sum(np.square(e)))


def fit_ses(y) -> dict:
    y = _check_series(y)
    grid = np.array(ETS["alpha_grid"])
    sse = np.sum(np.square(ses_errors(y, grid)), axis=0)
    start = grid[int(np.argmin(sse))]
    bounds = [tuple(ETS["alpha_bounds"])]
    result = minimize(lambda a: float(np.sum(np.square(ses_errors(y, a[0])))), x0=[start],
                      method="L-BFGS-B", bounds=bounds)
    alpha = float(result.x[0])
    errors = ses_errors(y, alpha)
    return {"alpha": alpha, "sse": float(np.sum(errors ** 2)), "n_errors": len(errors),
            "level": float(ses_state(y, alpha))}


def _damped_grid():
    a, b, p = np.meshgrid(ETS["alpha_grid"], ETS["beta_star_grid"], ETS["phi_grid"], indexing="ij")
    return a.ravel(), b.ravel(), p.ravel()


def fit_damped_many(Y) -> list[dict]:
    """Fit ETS(A,Ad,N) to each row of Y (vectorised grid, then L-BFGS-B per series)."""
    Y = np.atleast_2d(np.asarray(Y, dtype=float))
    if Y.shape[1] < 5 or not np.all(np.isfinite(Y)):
        raise ValueError("damped trend needs at least 5 finite observations per series")
    ga, gb, gp = _damped_grid()
    errors = damped_errors(Y, ga[None, :], (ga * gb)[None, :], gp[None, :])      # (n-2, S, G)
    sse = np.sum(np.square(errors), axis=0)
    bounds = [tuple(ETS["alpha_bounds"]), tuple(ETS["beta_star_bounds"]), tuple(ETS["phi_bounds"])]
    fits = []
    for s, row in enumerate(Y):
        g = int(np.argmin(sse[s]))
        result = minimize(lambda x: _damped_sse(row, x), x0=[ga[g], gb[g], gp[g]], method="L-BFGS-B", bounds=bounds)
        x = result.x if result.fun <= sse[s, g] else np.array([ga[g], gb[g], gp[g]])
        alpha, beta, phi = float(x[0]), float(x[0] * x[1]), float(x[2])
        level, trend = damped_state(row, alpha, beta, phi)
        e = damped_errors(row, alpha, beta, phi)
        fits.append({"alpha": alpha, "beta": beta, "phi": phi, "sse": float(np.sum(e ** 2)), "n_errors": len(e),
                     "level": float(level), "trend": float(trend)})
    return fits


def fit_damped(y) -> dict:
    return fit_damped_many(_check_series(y, 5)[None, :])[0]


def damped_path(fit: dict, horizon: int) -> np.ndarray:
    phi = fit["phi"]
    cumulative = np.cumsum(phi ** np.arange(1, horizon + 1))
    return fit["level"] + cumulative * fit["trend"]


def damped_variance_factors(fit: dict, horizon: int) -> np.ndarray:
    """h-step variance / sigma^2 for ETS(A,Ad,N): 1 + sum_{j<h} c_j^2, c_j = alpha + beta*(phi+...+phi^j)."""
    phi = fit["phi"]
    j = np.arange(1, horizon)
    c = fit["alpha"] + fit["beta"] * np.cumsum(phi ** j) if horizon > 1 else np.array([])
    return 1 + np.concatenate([[0.0], np.cumsum(c ** 2)])


# ------------------------------------------------------------- autoregressions

def _aicc(sse: float, n: int, k: int) -> float:
    if n - k - 1 <= 0 or sse <= 0:
        return np.inf
    return n * np.log(sse / n) + 2 * k + 2 * k * (k + 1) / (n - k - 1)


def _lagged(x: np.ndarray, p: int, start: int):
    """Regression rows for t = start..n-1 with lags 1..p."""
    target = x[start:]
    lags = np.column_stack([x[start - i:len(x) - i] for i in range(1, p + 1)]) if p else np.empty((len(target), 0))
    return target, lags


def fit_ar_level(y) -> dict:
    """AR(p) with intercept, p by AICc on a common sample (t >= max order)."""
    y = _check_series(y, 8)
    orders = SETTINGS["ar_orders"]
    start = max(orders)
    best = None
    for p in orders:
        target, lags = _lagged(y, p, start)
        X = np.column_stack([np.ones(len(target)), lags])
        coef, *_ = np.linalg.lstsq(X, target, rcond=None)
        resid = target - X @ coef
        sse = float(resid @ resid)
        score = _aicc(sse, len(target), p + 1)
        if best is None or score < best["aicc"]:
            best = {"order": p, "intercept": float(coef[0]), "phi": [float(c) for c in coef[1:]],
                    "sse": sse, "n_errors": len(target), "aicc": score, "k": p + 1}
    return best


def fit_ari(y) -> dict:
    """ARIMA(p,1,0) without constant, p by AICc on a common sample of differences."""
    y = _check_series(y, 8)
    d = np.diff(y)
    orders = SETTINGS["ari_orders"]
    start = max(orders)
    best = None
    for p in orders:
        target, lags = _lagged(d, p, start)
        if p:
            coef, *_ = np.linalg.lstsq(lags, target, rcond=None)
            resid = target - lags @ coef
        else:
            coef, resid = np.array([]), target
        sse = float(resid @ resid)
        score = _aicc(sse, len(target), p)
        if best is None or score < best["aicc"]:
            best = {"order": p, "phi": [float(c) for c in coef], "sse": sse, "n_errors": len(target),
                    "aicc": score, "k": p}
    return best


def ar_recursion(history: np.ndarray, intercept: float, phi: list, horizon: int) -> np.ndarray:
    values = list(history[-len(phi):]) if phi else []
    out = []
    for _ in range(horizon):
        nxt = intercept + sum(c * values[-i] for i, c in enumerate(phi, start=1))
        out.append(nxt)
        values.append(nxt)
    return np.array(out)


def psi_weights(phi: list, horizon: int) -> np.ndarray:
    psi = np.zeros(horizon)
    psi[0] = 1.0
    for j in range(1, horizon):
        psi[j] = sum(phi[i - 1] * psi[j - i] for i in range(1, min(j, len(phi)) + 1))
    return psi


# ----------------------------------------------------------------- TFR methods

def forecast_tfr(method: str, log_tfr, horizon: int) -> dict:
    """Forecast log TFR for horizons 1..horizon from a training series ending at the origin.

    Returns {"log_mean": array, "log_sd_model": array or None, "params": dict}.
    """
    if method not in TFR_METHODS:
        raise ValueError(f"unsupported method {method!r}; the protocol allows {TFR_METHODS}")
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    y = _check_series(log_tfr, MIN_TFR_SERIES)
    h = np.arange(1, horizon + 1)
    last = y[-1]
    sd = None
    if method == "naive":
        step = np.diff(y)
        sigma = np.sqrt(np.mean(step ** 2))
        mean, sd, params = np.full(horizon, last), sigma * np.sqrt(h), {"sigma": float(sigma)}
    elif method == "mean10":
        mean, params = np.full(horizon, y[-SETTINGS["mean_years"]:].mean()), {}
    elif method in ("drift10", "drift10_damped"):
        k = SETTINGS["drift_years"]
        drift = (y[-1] - y[-1 - k]) / k
        if method == "drift10":
            mean, params = last + h * drift, {"drift": float(drift)}
        else:
            phi = SETTINGS["damped_drift_phi"]
            mean, params = last + drift * np.cumsum(phi ** h), {"drift": float(drift), "phi": phi}
    elif method == "converge30":
        target = y[-SETTINGS["converge_mean_years"]:].mean()
        weight = np.maximum(0.0, 1 - h / SETTINGS["converge_horizon"])
        mean, params = target + (last - target) * weight, {"target": float(target)}
    elif method == "ses":
        fit = fit_ses(y)
        sigma = np.sqrt(fit["sse"] / fit["n_errors"])
        mean = np.full(horizon, fit["level"])
        sd = sigma * np.sqrt(1 + (h - 1) * fit["alpha"] ** 2)
        params = {"alpha": fit["alpha"], "sigma": float(sigma)}
    elif method == "holt_damped":
        fit = fit_damped(y)
        sigma = np.sqrt(fit["sse"] / fit["n_errors"])
        mean, sd = damped_path(fit, horizon), sigma * np.sqrt(damped_variance_factors(fit, horizon))
        params = {k: fit[k] for k in ("alpha", "beta", "phi", "level", "trend")} | {"sigma": float(sigma)}
    elif method == "ar_level":
        fit = fit_ar_level(y)
        sigma = np.sqrt(fit["sse"] / max(fit["n_errors"] - fit["k"], 1))
        mean = ar_recursion(y, fit["intercept"], fit["phi"], horizon)
        sd = sigma * np.sqrt(np.cumsum(psi_weights(fit["phi"], horizon) ** 2))
        params = {"order": fit["order"], "intercept": fit["intercept"], "phi": fit["phi"], "sigma": float(sigma)}
    else:  # ari
        fit = fit_ari(y)
        sigma = np.sqrt(fit["sse"] / max(fit["n_errors"] - fit["k"], 1))
        d = np.diff(y)
        steps = ar_recursion(d, 0.0, fit["phi"], horizon) if fit["phi"] else np.zeros(horizon)
        mean = last + np.cumsum(steps)
        level_psi = np.cumsum(psi_weights(fit["phi"], horizon))
        sd = sigma * np.sqrt(np.cumsum(level_psi ** 2))
        params = {"order": fit["order"], "phi": fit["phi"], "sigma": float(sigma)}
    return {"log_mean": np.asarray(mean, dtype=float), "log_sd_model": None if sd is None else np.asarray(sd),
            "params": params}


# ---------------------------------------------------------- age-profile methods

def validate_rates(rates: np.ndarray) -> np.ndarray:
    rates = np.asarray(rates, dtype=float)
    if rates.ndim != 2:
        raise ValueError("rates must be a years x ages matrix")
    if not np.all(np.isfinite(rates)):
        raise ValueError("rates contain missing values")
    if np.any(rates < 0):
        raise ValueError("rates must be non-negative")
    if np.any(rates.sum(axis=1) <= 0):
        raise ValueError("every year needs a positive total fertility rate")
    return rates


def shape_of(rates: np.ndarray) -> np.ndarray:
    rates = np.maximum(rates, RATE_FLOOR)
    return rates / rates.sum(axis=-1, keepdims=True)


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def _first_component(matrix: np.ndarray):
    """Lee-Carter style decomposition: column means and the first SVD component."""
    a = matrix.mean(axis=0)
    u, s, vt = np.linalg.svd(matrix - a, full_matrices=False)
    b, k = vt[0], u[:, 0] * s[0]
    scale = b.sum() if abs(b.sum()) > 1e-8 else np.linalg.norm(b)
    return a, b / scale, k * scale


def _drift_path(k: np.ndarray, horizon: int) -> np.ndarray:
    drift = (k[-1] - k[0]) / (len(k) - 1)
    return k[-1] + drift * np.arange(1, horizon + 1)


def forecast_shape(method: str, rates, horizon: int) -> dict:
    """Forecast the age schedule from a training window (years x ages, last row = origin).

    Returns {"shape": (horizon x ages) proportions summing to 1,
             "rates": (horizon x ages) own-level rates for direct methods or None,
             "params": dict}.
    """
    if method not in SHAPE_METHODS:
        raise ValueError(f"unsupported age-profile method {method!r}; the protocol allows {SHAPE_METHODS}")
    rates = validate_rates(rates)
    if len(rates) < 2:
        raise ValueError("need at least two years of rates")
    f = shape_of(rates)
    if method == "S0_fixed":
        return {"shape": np.repeat(f[-1:], horizon, axis=0), "rates": None, "params": {}}
    if method in ("S1_shape_drift", "S2_shape_damped"):
        logf = np.log(f)
        z = logf - logf.mean(axis=1, keepdims=True)
        _, b, k = _first_component(z)
        if method == "S1_shape_drift":
            path, params = _drift_path(k, horizon), {"drift": float((k[-1] - k[0]) / (len(k) - 1))}
        else:
            fit = fit_damped(k)
            path, params = damped_path(fit, horizon), {x: fit[x] for x in ("alpha", "beta", "phi")}
        z_future = z[-1] + np.outer(path - k[-1], b)
        return {"shape": _softmax(z_future), "rates": None, "params": params}
    logm = np.log(np.maximum(rates, RATE_FLOOR))
    if method == "S3_direct_ets":
        fits = fit_damped_many(logm.T)
        paths = np.array([damped_path(fit, horizon) for fit in fits]).T          # horizon x ages
        own = np.exp(paths)
        return {"shape": own / own.sum(axis=1, keepdims=True), "rates": own,
                "params": {"median_phi": float(np.median([fit["phi"] for fit in fits]))}}
    # S4_lee_carter
    _, b, k = _first_component(logm)
    path = _drift_path(k, horizon)
    own = np.exp(logm[-1] + np.outer(path - k[-1], b))
    return {"shape": own / own.sum(axis=1, keepdims=True), "rates": own,
            "params": {"drift": float((k[-1] - k[0]) / (len(k) - 1))}}


def coherent_rates(shape: np.ndarray, tfr: np.ndarray) -> np.ndarray:
    """ASFR = TFR x shape, so rates sum exactly to the TFR in every year."""
    shape = np.asarray(shape, dtype=float)
    if np.any(shape < 0) or not np.allclose(shape.sum(axis=1), 1.0, atol=1e-12):
        raise ValueError("shape must be non-negative and sum to 1 in every year")
    return shape * np.asarray(tfr, dtype=float)[:, None]


def reconcile(rates: np.ndarray, tfr: np.ndarray) -> np.ndarray:
    """Proportional reconciliation of independently forecast rates to a TFR forecast."""
    rates = validate_rates(rates)
    return rates * (np.asarray(tfr, dtype=float) / rates.sum(axis=1))[:, None]
