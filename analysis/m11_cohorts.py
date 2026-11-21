"""M11 Gen Z cohort fertility: period-to-cohort transformation, accumulation and backtests.

Protocol section 10. Period rates are forecast by Lexis square (calendar year t,
age in completed years x). A square holds two birth cohorts (t-x-1 and t-x),
so it cannot be assigned to one cohort. HFD vertical parallelograms (VV: year t,
age reached during the year a) hold exactly one cohort, c = t - a, and are the
upper triangle of age a-1 plus the lower triangle of age a. Forecast squares
are converted to VV cells (T1: average of the two squares; T2: T1 times an
observed VV/T1 ratio), then cumulated along each cohort.

"Cumulative fertility by the end of year Y" is the sum of a cohort's VV rates
over years <= Y. At the end of Y a woman born in year c has exact age between
Y - c and Y - c + 1. It is not completed fertility.
"""

import numpy as np
import pandas as pd

from analysis import hfd
from analysis.m11_backtest import AGES, era_of
from analysis.m11_protocol import load_config

CONFIG = load_config()
COH = CONFIG["cohort"]
GEN_Z = list(range(COH["gen_z"][0], COH["gen_z"][1] + 1))
A0 = list(range(COH["ages_at_origin"][0], COH["ages_at_origin"][1] + 1))
NA = len(AGES)


def vv_matrix() -> pd.DataFrame:
    """Observed HFD VV rates, year x age reached during the year (12-55)."""
    vv = hfd.vv_frame()
    wide = vv.pivot(index="Year", columns="ARDY", values="ASFR").reindex(columns=AGES)
    wide.index = wide.index.astype(int)
    if wide.isna().any().any():
        raise ValueError("missing VV rates")
    return wide.astype(float)


def t1(rr: np.ndarray) -> np.ndarray:
    """VV(t, a) = (m(t, a-1) + m(t, a)) / 2 with m(t, 11) = 0; rows are years, columns ages 12-55."""
    rr = np.atleast_2d(np.asarray(rr, dtype=float))
    left = np.concatenate([np.zeros((rr.shape[0], 1)), rr[:, :-1]], axis=1)
    return 0.5 * (left + rr)


def transform_ratios(rr_obs: pd.DataFrame, vv_obs: pd.DataFrame, origin: int,
                     years: int = COH["transform_ratio_years"]) -> np.ndarray:
    """Mean observed VV / T1 ratio by age over the `years` years ending at the origin."""
    span = [y for y in range(origin - years + 1, origin + 1) if y in rr_obs.index and y in vv_obs.index]
    if len(span) < years:
        raise ValueError(f"need {years} observed years up to {origin} for transformation ratios")
    base = t1(rr_obs.loc[span].to_numpy())
    observed = vv_obs.loc[span].to_numpy()
    return np.mean(observed / np.maximum(base, CONFIG["data"]["rate_floor"]), axis=0)


def to_vv(rr: np.ndarray, method: str, ratios: np.ndarray | None = None) -> np.ndarray:
    if method == "T1":
        return t1(rr)
    if method == "T2":
        if ratios is None:
            raise ValueError("T2 needs transformation ratios")
        return t1(rr) * ratios
    raise ValueError(f"unknown transformation {method!r}")


def cohort_increment(vv_rows: np.ndarray, first_year: int, cohort: int, last_year: int) -> float:
    """Sum of a cohort's VV rates from first_year to last_year; vv_rows[i] is year first_year + i."""
    total = 0.0
    for i, year in enumerate(range(first_year, last_year + 1)):
        a = year - cohort
        if AGES[0] <= a <= AGES[-1]:
            total += vv_rows[i][a - AGES[0]]
    return total


def validate_transformation(rr_obs: pd.DataFrame, vv_obs: pd.DataFrame, horizon: int = 16) -> pd.DataFrame:
    """In-sample check of T1 and T2: 16-year cumulative cohort increments from observed squares vs observed VV."""
    rows = []
    first = COH["transform_validation_first_year"]
    last = int(rr_obs.index.max())
    for start in range(first - 1, last - horizon + 1):
        years = list(range(start + 1, start + horizon + 1))
        observed = vv_obs.loc[years].to_numpy()
        ratios = transform_ratios(rr_obs, vv_obs, start)
        built = {"T1": to_vv(rr_obs.loc[years].to_numpy(), "T1"),
                 "T2": to_vv(rr_obs.loc[years].to_numpy(), "T2", ratios)}
        for a0 in A0:
            cohort = start - a0
            actual = cohort_increment(observed, start + 1, cohort, start + horizon)
            for name, vv in built.items():
                rows.append({"start": start, "cohort": cohort, "age_at_start": a0, "method": name,
                             "observed_increment": actual,
                             "error": actual - cohort_increment(vv, start + 1, cohort, start + horizon)})
    return pd.DataFrame(rows)


def observed_cumulative(vv_obs: pd.DataFrame, cohorts, last_year: int) -> pd.DataFrame:
    rows = []
    for c in cohorts:
        total = 0.0
        for year in range(int(vv_obs.index.min()), last_year + 1):
            a = year - c
            if AGES[0] <= a <= AGES[-1]:
                total += vv_obs.loc[year, a]
                rows.append({"cohort": c, "year": year, "ardy": a, "contribution": vv_obs.loc[year, a],
                             "cumulative": total, "segment": "observed"})
    return pd.DataFrame(rows)


def project_cohorts(vv_future: np.ndarray, first_year: int, observed: pd.DataFrame, cohorts) -> pd.DataFrame:
    """Append projected annual contributions to each cohort's observed cumulative fertility."""
    rows = []
    for c in cohorts:
        past = observed[observed["cohort"] == c]
        total = float(past["cumulative"].iloc[-1]) if len(past) else 0.0
        for i in range(len(vv_future)):
            year = first_year + i
            a = year - c
            contribution = vv_future[i][a - AGES[0]] if AGES[0] <= a <= AGES[-1] else 0.0
            total += contribution
            rows.append({"cohort": c, "year": year, "ardy": a, "contribution": float(contribution),
                         "cumulative": total, "segment": "projected"})
    return pd.DataFrame(rows)


def pseudo_cohort_backtest(rr_obs: pd.DataFrame, vv_obs: pd.DataFrame, paths: dict, pipeline: str,
                           transform: str, origins) -> pd.DataFrame:
    """Errors of projected cumulative increments for cohorts aged 12-29 at each origin.

    paths[origin] = forecast period rates (horizons x ages) made with data <= origin.
    """
    rows = []
    last = int(vv_obs.index.max())
    for origin in origins:
        if origin not in paths:
            continue
        horizon = min(len(paths[origin]), last - origin)
        if horizon < 1:
            continue
        ratios = transform_ratios(rr_obs, vv_obs, origin) if transform == "T2" else None
        vv_hat = to_vv(paths[origin][:horizon], transform, ratios)
        observed = vv_obs.loc[origin + 1:origin + horizon].to_numpy()
        for a0 in A0:
            cohort = origin - a0
            proj = obs = 0.0
            for h in range(1, horizon + 1):
                a = origin + h - cohort
                if AGES[0] <= a <= AGES[-1]:
                    proj += vv_hat[h - 1][a - AGES[0]]
                    obs += observed[h - 1][a - AGES[0]]
                rows.append({"pipeline": pipeline, "origin": origin, "cohort": cohort, "age_at_origin": a0, "h": h,
                             "target": origin + h, "age_at_target": a, "projected_increment": proj,
                             "observed_increment": obs, "error": obs - proj,
                             "log_ratio": float(np.log(obs / proj)) if obs > 0 and proj > 0 else np.nan})
    out = pd.DataFrame(rows)
    out["era"] = out["origin"].map(era_of)
    return out


def cohort_sigma(records: pd.DataFrame, a0: int, h: int, max_target: int | None = None) -> tuple[float, int]:
    """RMS of log(observed / projected increment), pooled over ages at origin a0-1..a0+1."""
    pool = COH["sigma_age_pool"]
    sub = records[(records["h"] == h) & records["age_at_origin"].between(a0 - pool, a0 + pool)]
    if max_target is not None:
        sub = sub[sub["target"] <= max_target]
    values = sub["log_ratio"].dropna().to_numpy()
    if len(values) == 0:
        return np.nan, 0
    return float(np.sqrt(np.mean(values ** 2))), int(len(values))


def cohort_real_time_coverage(records: pd.DataFrame, horizons=(5, 10, 15, 16)) -> pd.DataFrame:
    """Pseudo-real-time coverage of cohort increment intervals (sigma from errors with target <= origin)."""
    from scipy import stats
    rows = []
    min_cal = CONFIG["intervals"]["min_calibration_errors"]
    for h in horizons:
        sub = records[records["h"] == h].dropna(subset=["log_ratio"])
        for idx, row in sub.iterrows():
            sigma, n = cohort_sigma(records, int(row["age_at_origin"]), h, max_target=int(row["origin"]))
            if n < min_cal or not np.isfinite(sigma) or sigma <= 0:
                continue
            out = {"origin": row["origin"], "h": h, "age_at_origin": row["age_at_origin"], "n_cal": n}
            for level in CONFIG["intervals"]["levels"]:
                z = stats.norm.ppf(0.5 + level / 2)
                out[f"covered{int(round(level * 100))}"] = abs(row["log_ratio"]) <= z * sigma
            rows.append(out)
    return pd.DataFrame(rows)


def reference_shares(vv_obs: pd.DataFrame) -> pd.DataFrame:
    """Share of completed fertility (HFD CCF) reached by the end of the year of each age, cohorts 1965-1974."""
    ref = range(COH["reference_cohorts"][0], COH["reference_cohorts"][1] + 1)
    ccf = hfd.read_hfd("USAtfrVH").set_index("Cohort")["CCF"]
    cum = observed_cumulative(vv_obs, ref, int(vv_obs.index.max()))
    cum["share"] = cum["cumulative"] / cum["cohort"].map(ccf)
    return cum.groupby("ardy")["share"].agg(["min", "median", "max"]).reset_index()


def completion_label(share_min: float, share_max: float) -> str:
    labels = COH["labels"]
    if share_min >= labels["nearly_complete"]:
        return "nearly complete by historical standards"
    if share_max < labels["partial_below"]:
        return "partial"
    return "substantial but incomplete"


def ccfr_exact(cohorts) -> pd.DataFrame:
    """HFD CCFR at the last exact age observed for each cohort (fully observed cohort-age cells only)."""
    ccfr = hfd.read_hfd("USAccfrVH").dropna(subset=["CCFR"])
    vh = hfd.cohort_frame()
    rows = []
    for c in cohorts:
        cells = vh[vh["Cohort"] == c]
        if cells.empty:
            rows.append({"cohort": c, "last_complete_age": None, "ccfr_exact_age": None, "ccfr": None,
                         "sum_exact_rates": None})
            continue
        last = int(cells["Age"].max())
        match = ccfr[(ccfr["Cohort"] == c) & (ccfr["Age"] == last + 1)]
        rows.append({"cohort": c, "last_complete_age": last, "ccfr_exact_age": last + 1,
                     "ccfr": float(match["CCFR"].iloc[0]) if len(match) else None,
                     "sum_exact_rates": float((cells["Total"] / cells["Exposure"]).sum())})
    return pd.DataFrame(rows)
