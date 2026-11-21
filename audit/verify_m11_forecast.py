"""Verification of the M11 forecasting results, with every check labelled by kind.

INDEPENDENT checks import nothing from analysis/. They parse the raw HFD text
files, Census CSV files and the aggregate public-use tabulation themselves
(reusing only the raw-file readers in audit/verify_m11.py), recompute the
reported quantities with separate code, and compare them with the stored
tables in data/public/m11/forecast/.
REPRODUCIBILITY checks execute the project code: a full deterministic rerun of the
locked pipeline and the post-review analysis (skippable; the run record is restored)
and a "poisoned future" leakage test on the real series.
RECONCILIATION checks compare hashes, the protocol lock, the run record, the
decision log, frozen-chapter manifests, output labels, the source-only archive
and the numbers quoted in docs/m11_fertility_forecasts.md.

    python audit/verify_m11_forecast.py [--skip-rerun]
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit.verify_m11 import INDEPENDENT, RECONCILIATION, Checks, census_female, hfd_rows, np_rows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "public" / "m11" / "forecast"
CHAPTER = ROOT / "docs" / "m11_fertility_forecasts.md"
PROTOCOL = ROOT / "docs" / "m11_forecast_protocol.md"
LOCK = ROOT / "docs" / "m11_protocol_lock.json"
REPRO = "reproducibility"
AGES = np.arange(12, 56)
Z80, Z95 = stats.norm.ppf(0.9), stats.norm.ppf(0.975)
FLOOR = 5e-6
# Stored tables keep 10 significant digits (float_format %.10g), so comparisons with stored values
# allow 1e-9 (absolute for quantities near 1, relative otherwise). Recomputations from raw data alone
# are exact to floating point.
TOL = 1e-9
TFR_PRINT = 0.0005 + 44 * 0.000005      # TFR printed to 3 decimals; 44 rates printed to 5 decimals


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / f"{name}.csv")


def config() -> dict:
    text = PROTOCOL.read_text(encoding="utf-8")
    block = text.split("<!-- config:start -->")[1].split("<!-- config:end -->")[0]
    return json.loads(block.strip().removeprefix("```json").removesuffix("```"))


# ---------------------------------------------------------------- raw HFD

def raw_matrix(name: str, value_col: int = 2) -> dict:
    """{year: array over ages 12-55} from an RR or VV file (age column 1)."""
    out = {}
    for r in hfd_rows(name):
        out.setdefault(int(r[0]), {})[int(r[1].rstrip("+-"))] = float(r[value_col])
    return {y: np.array([v[a] for a in AGES]) for y, v in out.items()}


def raw_tfr() -> pd.Series:
    rates = raw_matrix("USAasfrRR")
    return pd.Series({y: v.sum() for y, v in sorted(rates.items())})


# ------------------------------------------------------- baseline forecasts

def baseline(method: str, y: np.ndarray, h: int, cfg: dict) -> float:
    s = cfg["method_settings"]
    if method == "naive":
        return y[-1]
    if method == "mean10":
        return y[-s["mean_years"]:].mean()
    drift = (y[-1] - y[-1 - s["drift_years"]]) / s["drift_years"]
    if method == "drift10":
        return y[-1] + h * drift
    if method == "drift10_damped":
        phi = s["damped_drift_phi"]
        return y[-1] + drift * sum(phi ** j for j in range(1, h + 1))
    target = y[-s["converge_mean_years"]:].mean()
    return target + (y[-1] - target) * max(0.0, 1 - h / s["converge_horizon"])


def parse_params(text: str) -> dict:
    out = {}
    for part in str(text).split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key] = [float(v) for v in value.strip("[]").split(",") if v] if value.startswith("[") else float(value)
    return out


def holt_sse_and_state(y, alpha, beta, phi):
    level, trend, sse = y[0], y[1] - y[0], 0.0
    for t in range(1, len(y)):
        pred = level + phi * trend
        err = y[t] - pred
        if t >= 2:
            sse += err * err
        level, trend = pred + alpha * err, phi * trend + beta * err
    return sse, level, trend


def ols(target, design):
    return np.linalg.solve(design.T @ design, design.T @ target)


# ------------------------------------------------------------- checks

def check_data_and_chronology(c: Checks, cfg: dict, tfr: pd.Series, records: pd.DataFrame):
    rates = raw_matrix("USAasfrRR")
    years = sorted(rates)
    complete = years == list(range(1933, 2025)) and all(len(v) == 44 and np.all(np.isfinite(v)) for v in rates.values())
    c.add(INDEPENDENT, "Dataset completeness: HFD RR ASFR 1933-2024, ages 12-55, no missing cell", complete,
          f"{len(years)} years x 44 ages")
    published = {int(r[0]): float(r[1]) for r in hfd_rows("USAtfrRR")}
    gap = max(abs(tfr[y] - published[y]) for y in years)
    c.add(INDEPENDENT, "Historical TFR aggregation: sum of single-year ASFR = HFD TFR (3 decimals)", gap <= TFR_PRINT + 1e-12,
          f"max abs diff {gap:.6f} (bound {TFR_PRINT:.5f})")
    obs = records["target"].map(tfr)
    c.add(INDEPENDENT, "Backtest observed values = raw HFD TFR of the target year",
          bool(np.allclose(obs, records["observed"], rtol=1e-9, atol=0)), f"{len(records):,} records")
    bt = cfg["backtest"]
    chrono = ((records["train_last"] == records["origin"]) & (records["target"] == records["origin"] + records["h"])
              & (records["train_first"] == 1933) & (records["train_years"] == records["origin"] - 1932)
              & records["origin"].between(bt["first_origin"], bt["last_origin"]) & (records["h"] <= bt["max_horizon"])
              & (records["target"] <= 2024))
    per_method = records.groupby("method").size()
    expected = sum(min(16, 2024 - o) for o in range(bt["first_origin"], bt["last_origin"] + 1))
    c.add(INDEPENDENT, "Forecast-origin chronology: training ends at the origin, targets after it, 1952-2023 x h<=16",
          bool(chrono.all()) and set(per_method) == {expected} and len(per_method) == len(cfg["methods"]),
          f"{int((~chrono).sum())} violations; {expected} records per method x {len(per_method)} methods")


def check_baselines_and_metrics(c: Checks, cfg: dict, tfr: pd.Series, records: pd.DataFrame) -> pd.DataFrame:
    logt = np.log(tfr)
    worst = 0.0
    for method in ("naive", "mean10", "drift10", "drift10_damped", "converge30"):
        sub = records[records["method"] == method]
        mine = [baseline(method, logt.loc[:o].to_numpy(), h, cfg) for o, h in zip(sub["origin"], sub["h"])]
        worst = max(worst, float(np.max(np.abs(np.array(mine) - sub["log_forecast"].to_numpy()))))
    c.add(INDEPENDENT, "Rule-based backtests recomputed (naive, mean10, drift10, damped drift, converge30)",
          worst < TOL, f"max abs diff in log forecast {worst:.2e}")

    rec = records.assign(err=records["target"].map(tfr) - np.exp(records["log_forecast"]))
    scale = {o: np.mean(np.abs(np.diff(tfr.loc[:o].to_numpy()))) for o in rec["origin"].unique()}
    rec["scaled"] = rec["err"].abs() / rec["origin"].map(scale)
    naive = rec[rec["method"] == "naive"].set_index(["origin", "h"])["err"].abs()
    rows = []
    for (m, h), g in rec[rec["h"].isin(cfg["backtest"]["primary_horizons"])].groupby(["method", "h"]):
        ref = naive.reindex(list(zip(g["origin"], g["h"])))
        rows.append({"method": m, "h": h, "mae": g["err"].abs().mean(), "rmse": np.sqrt((g["err"] ** 2).mean()),
                     "bias": g["err"].mean(), "mase": g["scaled"].mean(),
                     "relative_mae": g["err"].abs().mean() / ref.mean(), "origins": len(g)})
    mine = pd.DataFrame(rows).set_index(["method", "h"])
    stored = table("m11_fc_tfr_metrics_primary").set_index(["method", "h"])
    gaps = {k: float(((mine[k] - stored[k].reindex(mine.index)).abs() / stored[k].reindex(mine.index).abs().clip(lower=1)).max())
            for k in ("mae", "rmse", "bias", "mase", "relative_mae")}
    c.add(INDEPENDENT, "Primary metrics recomputed (MAE, RMSE, bias, MASE, relative MAE; h = 5, 10, 15; 9 methods)",
          max(gaps.values()) < TOL and (mine["origins"] == stored["origins"].reindex(mine.index)).all(),
          "; ".join(f"{k} {v:.1e}" for k, v in gaps.items()))
    return rec


def my_bootstrap_upper(rec: pd.DataFrame, method: str, horizons, reps=2000, seed=99) -> float:
    rng = np.random.default_rng(seed)
    total = np.zeros(reps)
    for h in horizons:
        a = rec[(rec["method"] == method) & (rec["h"] == h)].sort_values("origin")["err"].abs().to_numpy()
        b = rec[(rec["method"] == "naive") & (rec["h"] == h)].sort_values("origin")["err"].abs().to_numpy()
        n = len(a)
        for r in range(reps):
            idx = []
            while len(idx) < n:
                start = rng.integers(n)
                idx.extend((start + k) % n for k in range(h))
            idx = np.array(idx[:n])
            total[r] += a[idx].mean() / b[idx].mean() / len(horizons)
    return float(np.quantile(total, 0.9))


def check_selection(c: Checks, cfg: dict, rec: pd.DataFrame):
    hs = cfg["backtest"]["primary_horizons"]
    split = cfg["backtest"]["selection_split"]
    stored = table("m11_fc_tfr_selection").set_index("method")
    agree, qualifies = [], {}
    for m in cfg["methods"]:
        ratios, eras_ok = [], True
        for h in hs:
            g = rec[(rec["h"] == h)]
            own = g[g["method"] == m].set_index("origin")["err"].abs()
            ref = g[g["method"] == "naive"].set_index("origin")["err"].abs().reindex(own.index)
            ratios.append(own.mean() / ref.mean())
            for mask in (own.index < split, own.index >= split):
                eras_ok &= own[mask].mean() / ref[mask].mean() < 1
        r = float(np.mean(ratios))
        c1 = r <= cfg["selection"]["max_ratio"]
        c3 = my_bootstrap_upper(rec, m, hs) < 1 if m != "naive" and c1 and eras_ok else False
        qualifies[m] = bool(c1 and eras_ok and c3 and m != "naive")
        agree.append(abs(r - stored.loc[m, "R"]) < 1e-9 and c1 == stored.loc[m, "c1_ratio_le_0.90"]
                     and eras_ok == stored.loc[m, "c2_both_eras"] and qualifies[m] == stored.loc[m, "qualifies"])
    chosen = min((m for m in qualifies if qualifies[m]), key=lambda m: cfg["parameters"][m], default="naive")
    stored_choice = stored.index[stored["selected"]][0]
    c.add(INDEPENDENT, "Selection rule re-applied from recomputed errors (own bootstrap, different seed)",
          all(agree) and chosen == stored_choice, f"R and conditions agree for {sum(agree)}/{len(agree)} methods; "
          f"selected {chosen} (stored {stored_choice})")


def check_fitted_models(c: Checks, cfg: dict, tfr: pd.Series, records: pd.DataFrame):
    logt = np.log(tfr)
    ets = cfg["ets"]
    worst_fc, not_min, coef_gap = 0.0, 0, 0.0
    origins = [1952, 1965, 1980, 1995, 2008, 2023]
    for origin in origins:
        y = logt.loc[:origin].to_numpy()
        for method in ("ses", "holt_damped", "ar_level", "ari"):
            sub = records[(records["method"] == method) & (records["origin"] == origin)].sort_values("h")
            p = parse_params(sub["params"].iloc[0])
            hs = sub["h"].to_numpy()
            if method == "ses":
                level = y[0]
                for v in y[1:]:
                    level += p["alpha"] * (v - level)
                fc = np.full(len(hs), level)
                sse = lambda a: sum((y[t] - lv) ** 2 for t, lv in _ses_levels(y, a))
                base = sse(p["alpha"])
                for a in (p["alpha"] - 1e-3, min(p["alpha"] + 1e-3, ets["alpha_bounds"][1])):
                    not_min += sse(a) < base - 1e-12
            elif method == "holt_damped":
                base, level, trend = holt_sse_and_state(y, p["alpha"], p["beta"], p["phi"])
                fc = level + np.cumsum(p["phi"] ** np.arange(1, len(hs) + 1)) * trend
                bstar = p["beta"] / p["alpha"]
                for da, db, dp in [(1e-3, 0, 0), (-1e-3, 0, 0), (0, 1e-3, 0), (0, -1e-3, 0), (0, 0, 1e-3), (0, 0, -1e-3)]:
                    a = np.clip(p["alpha"] + da, *ets["alpha_bounds"])
                    b = np.clip(bstar + db, *ets["beta_star_bounds"]) * a
                    f = np.clip(p["phi"] + dp, *ets["phi_bounds"])
                    not_min += holt_sse_and_state(y, a, b, f)[0] < base - 1e-10
            elif method == "ar_level":
                k = int(p["order"])
                design = np.column_stack([np.ones(len(y) - 3)] + [y[3 - i:len(y) - i] for i in range(1, k + 1)])
                coef = ols(y[3:], design)
                coef_gap = max(coef_gap, abs(coef[0] - p["intercept"]), *np.abs(coef[1:] - np.array(p["phi"])))
                hist = list(y)
                fc = []
                for _ in hs:
                    hist.append(coef[0] + sum(coef[i] * hist[-i] for i in range(1, k + 1)))
                    fc.append(hist[-1])
                fc = np.array(fc)
            else:
                k = int(p["order"])
                d = np.diff(y)
                if k:
                    design = np.column_stack([d[3 - i:len(d) - i] for i in range(1, k + 1)])
                    coef = ols(d[3:], design)
                    coef_gap = max(coef_gap, *np.abs(coef - np.array(p["phi"])))
                else:
                    coef = np.array([])
                hist, level, fc = list(d), y[-1], []
                for _ in hs:
                    step = sum(coef[i - 1] * hist[-i] for i in range(1, k + 1))
                    hist.append(step)
                    level += step
                    fc.append(level)
                fc = np.array(fc)
            worst_fc = max(worst_fc, float(np.max(np.abs(fc - sub["log_forecast"].to_numpy()))))
    c.add(INDEPENDENT, "Fitted models (SES, damped trend, AR, ARI) recomputed from stored parameters at 6 origins",
          worst_fc < TOL and coef_gap < TOL, f"forecast diff {worst_fc:.1e}; OLS coefficient diff {coef_gap:.1e}")
    c.add(INDEPENDENT, "Stored ETS parameters are local minima of the one-step SSE (+/-0.001 per parameter)",
          not_min == 0, f"{not_min} perturbations lowered the SSE")


def _ses_levels(y, alpha):
    level = y[0]
    for t in range(1, len(y)):
        yield t, level
        level += alpha * (y[t] - level)


def check_intervals(c: Checks, rec: pd.DataFrame, tfr: pd.Series):
    ir = table("m11_fc_interval_records")
    ir["observed_raw"] = ir["target"].map(tfr)
    cov = ir.assign(c80=(ir["observed_raw"] >= ir["lower80"]) & (ir["observed_raw"] <= ir["upper80"]),
                    c95=(ir["observed_raw"] >= ir["lower95"]) & (ir["observed_raw"] <= ir["upper95"]))
    mine = cov.groupby(["interval", "method", "h"])[["c80", "c95"]].mean()
    stored = table("m11_fc_interval_calibration").set_index(["interval", "method", "h"])
    gap = float(max((mine["c80"] - stored["coverage80"]).abs().max(), (mine["c95"] - stored["coverage95"]).abs().max()))
    c.add(INDEPENDENT, "Interval coverage recomputed from stored bounds and raw observations (all methods, h 1-16)",
          gap < TOL, f"max coverage diff {gap:.1e} over {len(mine)} cells")
    naive = rec[rec["method"] == "naive"].assign(le=lambda d: np.log(d["target"].map(tfr)) - d["log_forecast"])
    worst = 0.0
    for origin, h in [(1980, 5), (1995, 10), (2008, 16), (2019, 5)]:
        usable = naive[(naive["h"] == h) & (naive["target"] <= origin)]
        sigma = np.sqrt(np.mean(usable["le"] ** 2))
        row = ir[(ir["interval"] == "historical_error") & (ir["method"] == "naive") & (ir["origin"] == origin)
                 & (ir["h"] == h)].iloc[0]
        fc = np.exp(naive[(naive["origin"] == origin) & (naive["h"] == h)]["log_forecast"].iloc[0])
        worst = max(worst, abs(fc * np.exp(-Z80 * sigma) - row["lower80"]), abs(fc * np.exp(Z95 * sigma) - row["upper95"]))
    c.add(INDEPENDENT, "Pseudo-real-time interval spread recomputed (only errors with target <= origin)", worst < 1e-9,
          f"max bound diff {worst:.1e} at 4 origin-horizon pairs")
    fc = table("m11_fc_tfr_forecast").set_index("h")
    sig16 = np.sqrt(np.mean(naive[naive["h"] == 16]["le"] ** 2))
    point = tfr[2024]
    expected = (point, point * np.exp(-Z80 * sig16), point * np.exp(Z80 * sig16), point * np.exp(-Z95 * sig16),
                point * np.exp(Z95 * sig16))
    got = tuple(fc.loc[16, k] for k in ("forecast", "lower80", "upper80", "lower95", "upper95"))
    c.add(INDEPENDENT, "Primary 2040 forecast and intervals recomputed (no change, sigma from 57 horizon-16 errors)",
          np.allclose(expected, got, rtol=1e-10), " / ".join(f"{v:.4f}" for v in expected))


def check_asfr(c: Checks):
    fc = table("m11_fc_asfr_forecast")
    tfr = table("m11_fc_tfr_forecast").set_index("year")["forecast"]
    sums = fc.groupby("year")["asfr"].sum()
    ages_ok = fc.groupby("year")["age"].apply(lambda a: sorted(a) == list(AGES)).all()
    gap = float((sums - tfr.reindex(sums.index)).abs().max())
    c.add(INDEPENDENT, "Age-specific/TFR reconciliation: forecast ASFR sum to the TFR forecast, ages 12-55, non-negative",
          gap < TOL and bool(ages_ok) and (fc["asfr"] >= 0).all() and len(sums) == 16, f"max |sum - TFR| {gap:.1e}")
    rates = raw_matrix("USAasfrRR")[2024]
    floored = np.maximum(rates, FLOOR)
    expected = floored / floored.sum() * rates.sum()
    worst = float(max(np.abs(g.sort_values("age")["asfr"].to_numpy() - expected).max() for _, g in fc.groupby("year")))
    c.add(INDEPENDENT, "Selected age profile (no change x fixed shape) equals the 2024 HFD schedule", worst < 1e-9,
          f"max diff {worst:.1e} (zero 2024 rates floored at 5e-6 before normalising)")
    metrics = table("m11_fc_shape_metrics_by_horizon").set_index(["method", "h"])
    raw = raw_matrix("USAasfrRR")
    worst = 0.0
    for h in (5, 10, 15):
        vals = []
        for o in range(1952, 2024 - h + 1):
            f0 = np.maximum(raw[o], FLOOR)
            vals.append(np.abs(f0 / f0.sum() - raw[o + h] / raw[o + h].sum()).sum())
        worst = max(worst, abs(np.mean(vals) - metrics.loc[("S0_fixed", h), "shape_l1"]))
    c.add(INDEPENDENT, "Fixed-shape backtest metric (shape L1 at h = 5, 10, 15) recomputed", worst < TOL,
          f"max diff {worst:.1e}")


def check_cohorts(c: Checks):
    rr = raw_matrix("USAasfrRR")
    vv = {}
    for r in hfd_rows("USAasfrVV"):
        vv[(int(r[0]), int(r[1].rstrip("+-")))] = float(r[3])
    traj = table("m11_fc_genz_trajectories")
    obs = traj[traj["segment"] == "observed"]
    mine_obs = {cohort: sum(vv[(y, y - cohort)] for y in range(cohort + 12, 2025)) for cohort in range(1995, 2013)}
    gap = max(abs(mine_obs[k] - g["cumulative"].iloc[-1]) for k, g in obs.groupby("cohort"))
    c.add(INDEPENDENT, "Observed Gen Z cumulative fertility to end-2024 = sum of raw HFD VV rates", gap < 1e-9,
          f"18 cohorts; max diff {gap:.1e}")
    t1 = lambda m: 0.5 * (np.concatenate([[0.0], m[:-1]]) + m)
    ratios = np.mean([np.array([vv[(y, a)] for a in AGES]) / np.maximum(t1(rr[y]), FLOOR) for y in range(2020, 2025)], axis=0)
    fc = table("m11_fc_asfr_forecast")
    ends = table("m11_fc_genz_endpoints_2040").set_index("cohort")
    validation = table("m11_fc_cohort_transform_validation").set_index("method")
    transform = validation.index[validation["chosen"]][0]
    worst = 0.0
    for cohort in range(1995, 2013):
        total = mine_obs[cohort]
        for year in range(2025, 2041):
            m = fc[fc["year"] == year].sort_values("age")["asfr"].to_numpy()
            v = t1(m) * (ratios if transform == "T2" else 1.0)
            a = year - cohort
            if 12 <= a <= 55:
                total += v[a - 12]
        worst = max(worst, abs(total - ends.loc[cohort, "projected_2040"]))
    c.add(INDEPENDENT, f"Gen Z 2040 cumulative fertility recomputed (forecast squares -> VV by {transform}, accumulated)",
          worst < 1e-9, f"max diff {worst:.1e}")
    proj = traj[traj["segment"] == "projected"]
    sums = proj.groupby("cohort")["contribution"].sum() + pd.Series(mine_obs)
    gap = float((sums - ends["projected_2040"]).abs().max())
    c.add(INDEPENDENT, "Cohort accumulation: observed total + annual projected contributions = 2040 endpoint",
          gap < 1e-9, f"max diff {gap:.1e}")
    ccf = {int(r[0]): float(r[1]) for r in hfd_rows("USAtfrVH") if r[1] != "."}
    shares = table("m11_fc_reference_completion_shares").set_index("ardy")
    worst = 0.0
    for a in (28, 36, 45):
        vals = [sum(vv[(cc + k, k)] for k in range(12, a + 1)) / ccf[cc] for cc in range(1965, 1975)]
        worst = max(worst, abs(min(vals) - shares.loc[a, "min"]), abs(max(vals) - shares.loc[a, "max"]))
    c.add(INDEPENDENT, "Reference completion shares (cohorts 1965-1974, VV cumulative / CCF) recomputed",
          worst < 1e-9, f"ages 28, 36, 45; max diff {worst:.1e}")


def np_female_raw(code: str) -> dict:
    out = {}
    for r in np_rows(f"np2023_d1_{code}.csv"):
        if r["SEX"] == "2" and r["ORIGIN"] == "0" and r["RACE"] == "0":
            out[int(r["YEAR"])] = np.array([float(r[f"POP_{a}"]) for a in range(0, 101)])
    return out


def check_census(c: Checks):
    v2025 = census_female("nc-est2025-agesex-res.csv")
    asfr = table("m11_fc_asfr_forecast")
    births = table("m11_fc_census_births")
    worst = 0.0
    for code in ("mid", "hi", "low", "zero"):
        proj = np_female_raw(code)
        ratio = np.array([v2025[(2025, a)] for a in range(0, 101)]) / proj[2025]
        for year in (2025, 2030, 2040):
            m = asfr[asfr["year"] == year].sort_values("age")["asfr"].to_numpy()
            pop = np.array([proj[year][x] * ratio[max(x - (year - 2025), 0)] for x in AGES])
            stored = births[(births["scenario"] == code) & (births["year"] == year)]["births"].iloc[0]
            worst = max(worst, abs((m * pop).sum() / stored - 1))
    c.add(INDEPENDENT, "Scenario births recomputed from raw NP2023 and vintage 2025 files (cohort rebasing)",
          worst < TOL, f"4 scenarios x 3 years; max relative diff {worst:.1e}")
    test = table("m11_fc_census_rebasing_test").set_index(["method", "year"])
    mid = np_female_raw("mid")
    base_ratio = np.array([v2025[(2022, a)] for a in range(0, 101)]) / mid[2022]
    worst = 0.0
    for year in (2023, 2024, 2025):
        truth = np.array([v2025[(year, a)] for a in AGES])
        raw = np.array([mid[year][a] for a in AGES])
        cohort = np.array([mid[year][a] * base_ratio[a - (year - 2022)] for a in AGES])
        worst = max(worst, abs(np.mean(np.abs(raw / truth - 1)) - test.loc[("none", year), "mape_ages_12_55"]),
                    abs(np.mean(np.abs(cohort / truth - 1)) - test.loc[("cohort", year), "mape_ages_12_55"]))
    c.add(INDEPENDENT, "Rebasing test recomputed (cohort method vs unrebased, 2023-2025)", worst < TOL,
          f"max MAPE diff {worst:.1e}")
    rates = raw_matrix("USAasfrRR")
    births_raw = raw_matrix("USAbirthsRR")
    al = table("m11_fc_census_alignment").set_index("year")
    worst = max(abs((rates[y] * np.array([v2025[(y, a)] for a in AGES])).sum() / births_raw[y].sum() - 1
                    - al.loc[y, "relative_difference"]) for y in range(2021, 2025))
    c.add(INDEPENDENT, "Exposure alignment (HFD ASFR x vintage 2025 population vs births) recomputed", worst < 1e-12,
          f"max diff {worst:.1e}")


def check_2025(c: Checks):
    tab = pd.read_csv(ROOT / "data" / "processed" / "m11" / "nchs_puf_2025_age_order.csv", dtype=str)
    tab = tab[tab["restatus"] != "4"]
    by_age = tab.assign(births=tab["births"].astype(int)).groupby(tab["mager"].astype(int))["births"].sum()
    births_rr = raw_matrix("USAbirthsRR")
    expos = raw_matrix("USAexposRR")
    v2025 = census_female("nc-est2025-agesex-res.csv")
    births = np.zeros(44)
    births[:38] = [by_age[a] for a in range(12, 50)]
    share = births_rr[2024][38:] / births_rr[2024][38:].sum()
    births[38:] = by_age[50] * share
    pop25 = np.array([v2025[(2025, a)] for a in AGES])
    ratio = expos[2024] / np.array([v2025[(2024, a)] for a in AGES])
    e2 = (births / (pop25 * ratio)).sum()
    stored = table("m11_fc_check_2025").set_index("quantity").loc["reconstructed 2025, E2_ratio_2024", "value"]
    c.close(INDEPENDENT, "2025 HFD-compatible TFR (E2) recomputed from the public-use tabulation and raw files", e2,
            stored, 1e-9)
    c.add(INDEPENDENT, "2025 resident births in the tabulation = NCHS official total (3,612,012)",
          int(births.sum().round()) == 3612012, f"{births.sum():,.0f}")


# ------------------------------------------ cohort intervals (independent)

def _t1(m):
    return 0.5 * (np.concatenate([[0.0], m[:-1]]) + m)


def raw_vv() -> dict:
    return {(int(r[0]), int(r[1].rstrip("+-"))): float(r[3]) for r in hfd_rows("USAasfrVV")}


def t2_ratios(rr: dict, vv: dict, origin: int) -> np.ndarray:
    return np.mean([np.array([vv[(y, a)] for a in AGES]) / np.maximum(_t1(rr[y]), FLOOR)
                    for y in range(origin - 4, origin + 1)], axis=0)


def cohort_records(rr: dict, vv: dict, origin: int, tfr_path: np.ndarray, transform: str) -> list[dict]:
    """Projected and observed 1-16 year cohort increments, fixed 2024-style shape at the origin."""
    floored = np.maximum(rr[origin], FLOOR)
    shape = floored / floored.sum()
    ratios = t2_ratios(rr, vv, origin) if transform == "T2" else np.ones(44)
    rows = []
    for a0 in range(12, 30):
        proj = obs = 0.0
        for h in range(1, 17):
            a = a0 + h
            if a <= 55:
                proj += (_t1(shape * tfr_path[h - 1]) * ratios)[a - 12]
                obs += vv[(origin + h, a)]
            rows.append({"origin": origin, "age_at_origin": a0, "h": h, "target": origin + h,
                         "projected": proj, "observed": obs, "log_ratio": np.log(obs / proj)})
    return rows


def pooled_sigma(frame: pd.DataFrame, a0: int, h: int, max_target=None):
    sub = frame[(frame["h"] == h) & frame["age_at_origin"].between(a0 - 1, a0 + 1)]
    if max_target is not None:
        sub = sub[sub["target"] <= max_target]
    return (float(np.sqrt(np.mean(sub["log_ratio"] ** 2))) if len(sub) else np.nan), len(sub)


def coverage80(frame: pd.DataFrame, horizons=(5, 10, 15, 16)) -> dict:
    out = {}
    for h in horizons:
        hits = []
        for row in frame[frame["h"] == h].itertuples():
            sigma, n = pooled_sigma(frame, row.age_at_origin, h, max_target=row.origin)
            if n >= 10 and sigma > 0:
                hits.append(abs(row.log_ratio) <= Z80 * sigma)
        out[h] = float(np.mean(hits)) if hits else np.nan
    return out


def check_cohort_intervals(c: Checks, rr: dict, vv: dict) -> pd.DataFrame:
    tfr = {y: v.sum() for y, v in rr.items()}
    mine = pd.DataFrame([r for o in range(1952, 2009) for r in cohort_records(rr, vv, o, np.full(16, tfr[o]), "T2")])
    stored = pd.read_csv(ROOT / "data" / "processed" / "m11" / "forecast" / "m11_fc_cohort_backtest.csv")
    stored = stored[stored["pipeline"] == "naive x S0_fixed"].set_index(["origin", "age_at_origin", "h"])
    gap = float((mine.set_index(["origin", "age_at_origin", "h"])["log_ratio"] - stored["log_ratio"]).abs().max())
    c.add(INDEPENDENT, "Cohort pseudo-backtest records (no change x fixed shape x T2, 1952-2008) recomputed from raw HFD",
          gap < 1e-9 and len(mine) == len(stored), f"{len(mine):,} records; max log-ratio diff {gap:.1e}")
    ends = table("m11_fc_genz_endpoints_2040").set_index("cohort")
    worst = 0.0
    for cohort, row in ends.iterrows():
        sigma, _ = pooled_sigma(mine, 2024 - cohort, 16)
        inc = row["projected_2040"] - row["observed_2024"]
        for col, z in (("lower80", -Z80), ("upper80", Z80), ("lower95", -Z95), ("upper95", Z95)):
            worst = max(worst, abs(row["observed_2024"] + inc * np.exp(z * sigma) - row[col]))
    c.add(INDEPENDENT, "Gen Z 2040 interval bounds recomputed (log-normal on the increment, sigma pooled over age +/- 1)",
          worst < TOL, f"max bound diff {worst:.1e}")
    cov = coverage80(mine)
    stored_cov = table("m11_fc_cohort_interval_coverage").set_index("h")["covered80"]
    gap = max(abs(cov[h] - stored_cov[h]) for h in cov)
    c.add(INDEPENDENT, "Cohort pseudo-real-time 80% coverage recomputed (h = 5, 10, 15, 16; incl. 0.964809 at h = 16)",
          gap < TOL, " / ".join(f"h{h} {v:.6f}" for h, v in cov.items()))
    return mine


# --------------------------------------------- origin-local selection (post-review)

def own_block_upper(a: np.ndarray, b: np.ndarray, h: int, rng, reps=2000) -> np.ndarray:
    n = len(a)
    starts = rng.integers(0, n, size=(reps, -(-n // h)))
    idx = ((starts[:, :, None] + np.arange(h)) % n).reshape(reps, -1)[:, :n]
    return a[idx].mean(axis=1) / b[idx].mean(axis=1)


def check_origin_local(c: Checks, cfg: dict, rec: pd.DataFrame, rr: dict, vv: dict, fixed: pd.DataFrame):
    choices = table("m11_pr_origin_local_choices").set_index("origin")
    hs = cfg["backtest"]["primary_horizons"]
    # eligibility from errors observable at each origin
    expected = {}
    for origin in range(1952, 2009):
        counts = [int(((rec["method"] == "naive") & (rec["h"] == h) & (rec["target"] <= origin)).sum()) for h in hs]
        windows = max(0, origin - 16 - 1937 + 1)
        expected[origin] = min(counts) >= 10 and windows >= 10
    mismatch = [o for o, e in expected.items() if e != bool(choices.loc[o, "eligible"])]
    excluded_ok = choices.loc[~choices["eligible"], "exclusion_reason"].str.contains("insufficient history").all()
    c.add(INDEPENDENT, "Origin-local eligibility: >= 10 errors with target <= origin at h = 5, 10, 15 and >= 10 windows",
          not mismatch and excluded_ok, f"{sum(expected.values())} eligible; mismatches {mismatch or 'none'}; "
          "every exclusion carries an insufficient-history reason")
    eligible = [o for o, e in expected.items() if e]
    # transformation choice from validation windows ending by the origin
    errs = []
    for start in range(1937, 2009):
        ratios = t2_ratios(rr, vv, start)
        for a0 in range(12, 30):
            cohort = start - a0
            actual = sum(vv[(t, t - cohort)] for t in range(start + 1, start + 17))
            for name, factor in (("T1", 1.0), ("T2", ratios)):
                pred = sum((_t1(rr[t]) * factor)[t - cohort - 12] for t in range(start + 1, start + 17))
                errs.append((start, name, abs(actual - pred)))
    errs = pd.DataFrame(errs, columns=["start", "method", "abs_error"])
    picks = {o: errs[errs["start"] + 16 <= o].groupby("method")["abs_error"].mean().idxmin() for o in eligible}
    bad = [o for o in eligible if picks[o] != choices.loc[o, "transform_choice"]]
    c.add(INDEPENDENT, "Origin-local transformation choices recomputed from windows ending by each origin",
          not bad, f"mismatches {bad or 'none'}; choices {pd.Series(picks).value_counts().to_dict()}")
    # TFR choice: R from errors observable at the origin; own bootstrap for borderline qualifiers
    rng = np.random.default_rng(31)
    disagreements = []
    for o in eligible:
        known = rec[rec["target"] <= o]
        qualifying = {}
        for m in cfg["methods"]:
            if m == "naive":
                continue
            ratios, boot = [], np.zeros(2000)
            for h in hs:
                own = known[(known["method"] == m) & (known["h"] == h)].sort_values("origin")["err"].abs().to_numpy()
                ref = known[(known["method"] == "naive") & (known["h"] == h)].sort_values("origin")["err"].abs().to_numpy()
                ratios.append(own.mean() / ref.mean())
                boot += own_block_upper(own, ref, h, rng) / len(hs)
            r = float(np.mean(ratios))
            if r <= cfg["selection"]["max_ratio"] and np.quantile(boot, 0.9) < 1:
                qualifying[m] = r
        if qualifying:
            best = min(qualifying.values())
            near = [m for m in cfg["methods"] if m in qualifying and qualifying[m] <= best + 0.02]
            mine = near[0]
        else:
            mine = "naive"
        if mine != choices.loc[o, "tfr_choice"]:
            disagreements.append((o, mine, choices.loc[o, "tfr_choice"]))
    # A disagreement is acceptable only if the decision is Monte Carlo-sensitive: across 10 own bootstrap
    # seeds both outcomes occur (the 90th percentile straddles 1), and the chapter documents that origin.
    chapter = CHAPTER.read_text(encoding="utf-8")
    unexplained, sensitive = [], []
    for o, mine, stored in disagreements:
        known = rec[rec["target"] <= o]
        method = stored if stored != "naive" else mine
        shares = []
        for seed in range(10):
            r2 = np.random.default_rng(1000 + seed)
            boot = np.zeros(2000)
            for h in hs:
                own = known[(known["method"] == method) & (known["h"] == h)].sort_values("origin")["err"].abs().to_numpy()
                ref = known[(known["method"] == "naive") & (known["h"] == h)].sort_values("origin")["err"].abs().to_numpy()
                boot += own_block_upper(own, ref, h, r2) / len(hs)
            shares.append(np.quantile(boot, 0.9) < 1)
        if 0 < np.mean(shares) < 1 and f"{o}" in chapter and "Monte Carlo" in chapter:
            sensitive.append((o, method, float(np.mean(shares))))
        else:
            unexplained.append((o, mine, stored))
    c.add(INDEPENDENT, "Origin-local TFR choices recomputed (errors with target <= origin; own bootstrap, other seed)",
          not unexplained, f"{len(eligible)} origins; {len(eligible) - len(disagreements)} identical; "
          f"Monte Carlo-sensitive and documented {sensitive or 'none'}; unexplained {unexplained or 'none'}")
    # cohort errors of the origin-local strategy, fully from raw data and the chosen rule-based TFR methods
    logt = np.log(pd.Series({y: v.sum() for y, v in rr.items()}))
    rows = []
    for o in eligible:
        if choices.loc[o, "shape_choice"] != "S0_fixed":
            raise SystemExit("verifier expects the fixed shape; extend it for other shapes")
        y = logt.loc[:o].to_numpy()
        path = np.exp([baseline(choices.loc[o, "tfr_choice"], y, h, cfg) for h in range(1, 17)])
        rows += cohort_records(rr, vv, o, path, choices.loc[o, "transform_choice"])
    mine = pd.DataFrame(rows).assign(error=lambda d: d["observed"] - d["projected"])
    stored = pd.read_csv(ROOT / "data" / "processed" / "m11" / "forecast" / "m11_pr_origin_local_cohort_backtest.csv")
    gap = float((mine.set_index(["origin", "age_at_origin", "h"])["error"]
                 - stored.set_index(["origin", "age_at_origin", "h"])["error"]).abs().max())
    fixed_same = fixed.assign(error=lambda d: d["observed"] - d["projected"])
    fixed_same = fixed_same[fixed_same["origin"].isin(eligible)]
    ratios = {h: mine[mine["h"] == h]["error"].abs().mean() / fixed_same[fixed_same["h"] == h]["error"].abs().mean()
              for h in (5, 10, 15, 16)}
    table_ratios = table("m11_pr_origin_local_cohort_comparison").query("a0_group == 'all'").set_index("h")
    rgap = max(abs(ratios[h] - table_ratios.loc[h, "ratio_origin_local_to_fixed"]) for h in ratios)
    c.add(INDEPENDENT, "Origin-local cohort errors and MAE ratios to the fixed strategy recomputed from raw data",
          gap < 1e-9 and rgap < TOL, f"max error diff {gap:.1e}; ratios " + " / ".join(f"h{h} {v:.3f}" for h, v in ratios.items()))
    cov = coverage80(mine)
    stored_cov = table("m11_pr_origin_local_interval_coverage").query("strategy == 'origin-local selection'").set_index("h")
    gap = max(abs(cov[h] - stored_cov.loc[h, "covered80"]) for h in cov)
    c.add(INDEPENDENT, "Origin-local interval coverage recomputed (spreads only from this strategy's errors with target <= origin)",
          gap < TOL, " / ".join(f"h{h} {v:.3f}" for h, v in cov.items()))
    shape = pd.read_csv(ROOT / "data" / "processed" / "m11" / "forecast" / "m11_fc_shape_backtest.csv")
    viol = []
    for o in eligible:
        known = shape[shape["target"] <= o]
        for m in ("S1_shape_drift", "S2_shape_damped", "S3_direct_ets", "S4_lee_carter"):
            r = np.mean([known[(known["method"] == m) & (known["h"] == h)]["shape_l1"].mean()
                         / known[(known["method"] == "S0_fixed") & (known["h"] == h)]["shape_l1"].mean() for h in hs])
            if r <= 0.85:          # clear qualifiers on condition 1 would contradict the stored fixed-shape choice
                viol.append((o, m, round(r, 3)))
    c.add(RECONCILIATION, "Origin-local shape choices consistent with stored shape errors (no clear qualifier ignored)",
          not viol, f"violations {viol or 'none'}")


# ---------------------------------------------------- reproducibility

def output_hashes() -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob("m11_*"))
            if p.name != "m11_run_record.json"}


def check_reproducibility(c: Checks, skip_rerun: bool):
    code = ("import numpy as np, pandas as pd\n"
            "from analysis import m11_backtest as bt\n"
            "tfr = bt.tfr_series(bt.hfd_rates())\n"
            "stored = pd.read_csv('data/public/m11/forecast/m11_fc_tfr_backtest_records.csv')\n"
            "worst = 0.0\n"
            "for origin in (1960, 1990, 2009):\n"
            "    poisoned = tfr.copy(); poisoned[poisoned.index > origin] = 9.9\n"
            "    rec = bt.tfr_backtest(poisoned, [origin])\n"
            "    ref = stored[stored.origin == origin].set_index(['method', 'h'])['log_forecast']\n"
            "    worst = max(worst, float((rec.set_index(['method', 'h'])['log_forecast'] - ref).abs().max()))\n"
            "print(worst)\n")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    worst = float(result.stdout.strip() or "nan")
    c.add(REPRO, "Leakage: overwriting every year after the origin with 9.9 leaves all forecasts unchanged",
          result.returncode == 0 and worst < TOL, f"origins 1960, 1990, 2009, all methods; max diff {worst:.1e}")
    if skip_rerun:
        c.add(REPRO, "Deterministic rerun", True, "skipped (--skip-rerun)")
        return
    record = OUT / "m11_run_record.json"
    frozen_record = record.read_bytes()
    before = output_hashes()
    runs = [subprocess.run([sys.executable, "-m", module], cwd=ROOT, capture_output=True, text=True)
            for module in ("analysis.m11_forecast", "analysis.m11_origin_local")]
    record.write_bytes(frozen_record)          # the run record documents the frozen run; restore it
    after = output_hashes()
    changed = [k for k in before if before[k] != after.get(k)]
    c.add(REPRO, "Deterministic rerun of the locked pipeline and the post-review analysis: every table and summary "
          "byte-identical", all(r.returncode == 0 for r in runs) and not changed and before.keys() == after.keys(),
          f"{len(before)} files; changed: {changed or 'none'} (run record restored)")


# ----------------------------------------------------- reconciliation

FROZEN_M01_M08 = {"inspect_data.py": "550131eebd67c076", "audit_data.py": "03d17755c4124009",
                  "streamlit_app.py": "f25d144903102044", "data/public/dashboard_summary.json": "debd94d998226995",
                  "docs/frozen_model_parameters.json": "60aa68fe21722915",
                  "data/raw/intention_gap_nlsy97_v2.csv": "79db4479c82d80e9",
                  "data/raw/intention_gap_nlsy97_supplement.csv": "b65b0a9d37cc96dc",
                  "data/processed/intention_gap_cohort.csv": "3a0735a9bcbfdf3b",
                  "data/processed/intention_gap_cohort_expanded.csv": "4b9939cbf81dad35"}

EXPECTED_FIGURES = ["m11_fc_tfr_forecast.png", "m11_fc_backtest_relative_mae.png", "m11_fc_interval_calibration.png",
                    "m11_fc_age_profiles.png", "m11_fc_genz_cohorts.png", "m11_fc_births_scenarios.png",
                    "m11_fc_sensitivity.png"]
REQUIRED_SENTENCE = "No alternative model satisfied the prespecified criteria for replacing the no-change baseline."
# Superseded claims; the post-review corrections table (section 13.1) quotes them on purpose and is skipped.
FORBIDDEN_CLAIMS = ["no method beat it", "reasonably calibrated at short horizons", "prediction interval, not historically",
                    "does not support any forecasting method", "2040 prediction interval is wide",
                    "bands are calibrated"]
ARCHIVE = ROOT.parent / "intention-gap-review-source-M11.zip"
MANIFEST = ROOT / "docs" / "m11_freeze.sha256"


def quotes() -> dict:
    """Numbers the chapter must quote, computed from the stored tables."""
    fc = table("m11_fc_tfr_forecast").set_index("year").loc[2040]
    sel = table("m11_fc_tfr_selection").set_index("method")
    ends = table("m11_fc_genz_endpoints_2040").set_index("cohort")
    check = table("m11_fc_check_2025").set_index("quantity")
    births = table("m11_fc_census_births").query("year == 2040").set_index("scenario")["births"]
    pooled = table("m11_fc_interval_coverage_pooled").set_index(["interval", "method", "level"])
    cov = table("m11_fc_cohort_interval_coverage").set_index("h")["covered80"]
    pr = table("m11_pr_origin_local_cohort_comparison").query("a0_group == 'all'").set_index("h")
    return {"2040 point": f"{fc['forecast']:.3f}", "2040 80% lower": f"{fc['lower80']:.2f}",
            "2040 80% upper": f"{fc['upper80']:.2f}", "2040 95% lower": f"{fc['lower95']:.2f}",
            "2040 95% upper": f"{fc['upper95']:.2f}", "ari R": f"{sel.loc['ari', 'R']:.3f}",
            "converge30 R": f"{sel.loc['converge30', 'R']:.3f}",
            "80% coverage": f"{pooled.loc[('historical_error', 'naive', 80), 'coverage_h5_10_15']:.2f}",
            "2025 reconstructed": f"{check.loc['reconstructed 2025, E2_ratio_2024', 'value']:.3f}",
            "1995 cohort 2040": f"{ends.loc[1995, 'projected_2040']:.2f}",
            "2012 cohort 2040": f"{ends.loc[2012, 'projected_2040']:.2f}",
            "mid births 2040": f"{births['mid'] / 1e6:.2f} million",
            "cohort coverage h16": f"{cov[16]:.4f}",
            "origin-local ratio h5": f"{pr.loc[5, 'ratio_origin_local_to_fixed']:.2f}",
            "origin-local ratio h16": f"{pr.loc[16, 'ratio_origin_local_to_fixed']:.2f}"}


def check_labels(c: Checks):
    band = table("m11_fc_check_2025")
    row = band[band["quantity"].str.contains("descriptive band")]
    ok_band = (len(row) == 1 and row[["lower95", "upper95"]].isna().all(axis=None)
               and row[["band_lower", "band_upper"]].notna().all(axis=None)
               and "not a confidence or prediction interval" in row["quantity"].iloc[0])
    c.add(RECONCILIATION, "2025 E2 +/- 2 RMSE band stored as a descriptive band, not in 95% columns", bool(ok_band),
          row["quantity"].iloc[0] if len(row) else "band row missing")
    labels = {name: set(table(name)["interval_label"].dropna()) for name in
              ("m11_fc_tfr_forecast", "m11_fc_tfr_forecast_secondary_2025", "m11_fc_genz_endpoints_2040",
               "m11_fc_genz_trajectories")}
    ok = all(v and all("not a validated probability interval" in t for t in v) for v in labels.values())
    kinds = set(table("m11_fc_interval_calibration")["interval"])
    types = set(table("m11_fc_data_dictionary")["interval_type"])
    needed = {"historical-error interval (nominal level)", "model-dependent uncertainty range", "scenario range",
              "descriptive band"}
    c.add(RECONCILIATION, "Every interval table labelled; no interval called calibrated; data dictionary covers all types",
          ok and "empirical_calibrated" not in kinds and needed <= types, f"interval kinds {sorted(kinds)}")
    figure_code = (ROOT / "analysis" / "m11_figures.py").read_text(encoding="utf-8")
    chapter = CHAPTER.read_text(encoding="utf-8")
    if "### 13.1" in chapter:
        chapter = chapter.split("### 13.1")[0] + chapter.split("### 13.2")[1]
    bad = [f for f in FORBIDDEN_CLAIMS if f in figure_code.lower() or f in chapter.lower()]
    c.add(RECONCILIATION, "Figure and chapter wording: required no-change sentence present; no overstated claims",
          REQUIRED_SENTENCE in figure_code and REQUIRED_SENTENCE in chapter and not bad,
          f"forbidden phrases found: {bad or 'none'}")


def check_archive(c: Checks):
    import zipfile
    if not ARCHIVE.exists() or not MANIFEST.exists():
        c.add(RECONCILIATION, "Source-only archive contains every frozen M11 file with the manifest hash", False,
              f"missing {'archive' if not ARCHIVE.exists() else 'manifest'}")
        return
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = {n.split("/", 1)[1]: n for n in archive.namelist()}
        manifest = [line.split(maxsplit=1) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
        wrong = [p for d, p in manifest if p not in names
                 or hashlib.sha256(archive.read(names[p])).hexdigest() != d]
        forbidden = [n for n in names if (n.startswith("data/raw/") and not n.endswith("provenance.json"))
                     or n.startswith(("data/processed/", ".venv/")) or "__pycache__" in n
                     or n in ("inspect_data.py", "audit_data.py", ".env", ".streamlit/secrets.toml")
                     or n.endswith((".zip", ".dat", ".cdb", ".NLSY97"))]
    c.add(RECONCILIATION, "Source-only archive contains every frozen M11 file with the manifest hash", not wrong,
          f"{len(manifest)} frozen files; wrong or missing {wrong or 'none'}")
    c.add(RECONCILIATION, "Archive excludes raw, processed, respondent-level, environment and secret files", not forbidden,
          f"{len(names)} files; forbidden {forbidden or 'none'}")


def check_reconciliation(c: Checks):
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    digest = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    record = json.loads((OUT / "m11_run_record.json").read_text(encoding="utf-8"))
    log = (ROOT / "docs" / "m11_decision_log.md").read_text(encoding="utf-8")
    c.add(RECONCILIATION, "Protocol matches its lock (no amendments); locked before the recorded run; decision log "
          "records the lock and the post-review stage",
          digest == lock["sha256"] == record["protocol_sha256"] and lock["locked_utc"] < record["started_utc"]
          and "Protocol locked" in log and "Post-review" in log,
          f"sha {digest[:12]}; locked {lock['locked_utc']}; run started {record['started_utc']}; "
          f"{len(lock['amendments'])} amendments")
    stale = [p for p, h in record["code_sha256"].items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    c.add(RECONCILIATION, "Run record code hashes equal the current code (outputs come from this code)", not stale,
          f"stale: {stale or 'none'}")
    result = subprocess.run([sys.executable, "audit/verify_freeze.py"], cwd=ROOT, capture_output=True, text=True)
    names = result.stdout
    c.add(RECONCILIATION, "Frozen manifests unchanged (M09, M10 and, once frozen, M11)",
          result.returncode == 0 and "nsfg_m09_freeze" in names and "m10_freeze" in names,
          "; ".join(result.stdout.strip().splitlines()) or result.stderr.strip()[-200:])
    bad = [p for p, h in FROZEN_M01_M08.items() if not (ROOT / p).exists()
           or hashlib.sha256((ROOT / p).read_bytes()).hexdigest()[:16] != h]
    c.add(RECONCILIATION, "M01-M08 reference files unchanged (9 recorded hashes)", not bad, f"changed: {bad or 'none'}")
    missing = [f for f in EXPECTED_FIGURES if not (ROOT / "assets" / "figures" / f).exists()
               or (ROOT / "assets" / "figures" / f).stat().st_size < 10_000]
    tables = list(OUT.glob("m11_*.csv"))
    c.add(RECONCILIATION, "Generated tables and figures present", not missing and len(tables) >= 51,
          f"{len(tables)} tables; missing figures: {missing or 'none'}")
    text = CHAPTER.read_text(encoding="utf-8")
    absent = {k: v for k, v in quotes().items() if v not in text}
    c.add(RECONCILIATION, "Headline numbers quoted in docs/m11_fertility_forecasts.md match the tables", not absent,
          f"missing {absent}" if absent else ", ".join(f"{k} {v}" for k, v in quotes().items()))
    check_labels(c)
    check_archive(c)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-rerun", action="store_true")
    args = parser.parse_args(argv)
    cfg = config()
    checks = Checks()
    tfr = raw_tfr()
    records = table("m11_fc_tfr_backtest_records")
    check_data_and_chronology(checks, cfg, tfr, records)
    rec = check_baselines_and_metrics(checks, cfg, tfr, records)
    check_selection(checks, cfg, rec)
    check_fitted_models(checks, cfg, tfr, records)
    check_intervals(checks, rec, tfr)
    check_asfr(checks)
    check_cohorts(checks)
    rr, vv = raw_matrix("USAasfrRR"), raw_vv()
    fixed = check_cohort_intervals(checks, rr, vv)
    check_origin_local(checks, cfg, rec, rr, vv, fixed)
    check_census(checks)
    check_2025(checks)
    check_reproducibility(checks, args.skip_rerun)
    check_reconciliation(checks)
    for kind, status, label, detail in checks.rows:
        print(f"{status}  [{kind}] {label}: {detail}")
    failed = sum(1 for row in checks.rows if row[1] == "FAIL")
    kinds = Counter(row[0] for row in checks.rows)
    print(f"\n{len(checks.rows)} checks ({kinds[INDEPENDENT]} independent, {kinds[REPRO]} reproducibility, "
          f"{kinds[RECONCILIATION]} reconciliation): {len(checks.rows) - failed} PASS, {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
