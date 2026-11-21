"""M11 fertility forecasting: run the locked protocol end to end.

Refuses to run unless docs/m11_forecast_protocol.md matches docs/m11_protocol_lock.json.
Public tables go to data/public/m11/forecast/, large per-age backtest files to
data/processed/m11/forecast/ (local), and a run record with code hashes and
UTC times to data/public/m11/forecast/m11_run_record.json.

    python -m analysis.m11_forecast           # ~5-10 minutes
"""

import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats

from analysis import m11_backtest as bt
from analysis import m11_cohorts as coh
from analysis import m11_models as models
from analysis import m11_scenarios as scen
from analysis import m11_sources as src
from analysis.m11_protocol import PROJECT_ROOT, load_config, protocol_sha, utc_now, verify_lock

CONFIG = load_config()
OUT = PROJECT_ROOT / "data" / "public" / "m11" / "forecast"
LOCAL = PROJECT_ROOT / "data" / "processed" / "m11" / "forecast"
FC = CONFIG["forecast"]
YEARS = list(range(FC["first_year"], FC["last_year"] + 1))
H = len(YEARS)
CODE = ["analysis/m11_protocol.py", "analysis/m11_models.py", "analysis/m11_backtest.py", "analysis/m11_cohorts.py",
        "analysis/m11_scenarios.py", "analysis/m11_forecast.py", "analysis/hfd.py", "analysis/m11_sources.py",
        "analysis/m11_origin_local.py", "analysis/m11_figures.py"]
Z = {level: float(stats.norm.ppf(0.5 + level / 2)) for level in CONFIG["intervals"]["levels"]}


def save(table: pd.DataFrame, name: str, folder: Path = OUT) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    table.to_csv(folder / f"{name}.csv", index=False, float_format="%.10g")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_table(origin: int, out: dict, years) -> pd.DataFrame:
    return pd.DataFrame({"year": years, "log_forecast": out["log_mean"], "forecast": np.exp(out["log_mean"])})


def add_intervals(frame: pd.DataFrame, sigma: pd.Series, prefix: str = "") -> pd.DataFrame:
    frame = frame.copy()
    s = sigma.reindex(frame["h"]).to_numpy()
    frame[f"{prefix}sigma"] = s
    for level, z in Z.items():
        tag = int(round(level * 100))
        frame[f"{prefix}lower{tag}"] = np.exp(frame["log_forecast"] - z * s)
        frame[f"{prefix}upper{tag}"] = np.exp(frame["log_forecast"] + z * s)
    return frame


def run() -> dict:
    lock = verify_lock()
    started = utc_now()
    rates = bt.hfd_rates()
    tfr = bt.tfr_series(rates)
    vv_obs = coh.vv_matrix()
    last = int(tfr.index.max())
    origins = list(range(CONFIG["backtest"]["first_origin"], CONFIG["backtest"]["last_origin"] + 1))
    results = {"protocol_sha256": lock["sha256"], "locked_utc": lock["locked_utc"]}   # run times: m11_run_record.json

    # ---------------------------------------------------- TFR backtest (section 4, 7)
    records = bt.tfr_backtest(tfr, origins)
    save(records, "m11_fc_tfr_backtest_records")
    by_h = bt.point_metrics(records)
    save(by_h, "m11_fc_tfr_metrics_by_horizon")
    primary = by_h[by_h["h"].isin(bt.PRIMARY_H)].copy()
    dm = [bt.dm_test(records, m, h) | {"method": m, "h": h} for m in models.TFR_METHODS for h in bt.PRIMARY_H]
    primary = primary.merge(pd.DataFrame(dm), on=["method", "h"])
    save(primary, "m11_fc_tfr_metrics_primary")
    save(bt.point_metrics(records[records["h"].isin(bt.PRIMARY_H)], by=("method", "era", "h")), "m11_fc_tfr_metrics_by_era")
    selection = bt.selection_table(records, list(models.TFR_METHODS), "naive", complexity=CONFIG["parameters"])
    selected = bt.choose(selection, "naive", list(models.TFR_METHODS))
    selection["selected"] = selection["method"] == selected
    save(selection, "m11_fc_tfr_selection")
    results["selected_tfr_method"] = selected

    # ---------------------------------------------------- intervals (section 7, 8)
    timed = bt.real_time_sigma(records)
    empirical = bt.score_intervals(timed, "sigma_rt").assign(interval="historical_error")
    model_based = bt.score_intervals(records[records["method"].isin(models.STOCHASTIC)], "log_sd_model") \
        .assign(interval="model_based")
    scored = pd.concat([empirical, model_based], ignore_index=True)
    keep = ["interval", "method", "origin", "h", "target", "era", "observed", "forecast", "lower80", "upper80",
            "lower95", "upper95", "covered80", "covered95", "crps"]
    save(scored[keep], "m11_fc_interval_records")
    calib = bt.coverage_summary(scored, by=("interval", "method", "h"))
    save(calib, "m11_fc_interval_calibration")
    save(bt.coverage_summary(scored[scored["h"].isin(bt.PRIMARY_H)], by=("interval", "method", "era")),
         "m11_fc_interval_calibration_by_era")
    pooled = []
    for kind, group in scored.groupby("interval"):
        for m in group["method"].unique():
            for tag in (80, 95):
                cov, lo, hi = bt.coverage_bootstrap(group, m, tag)
                pooled.append({"interval": kind, "method": m, "level": tag, "coverage_h5_10_15": cov,
                               "bootstrap_p05": lo, "bootstrap_p95": hi})
    pooled = pd.DataFrame(pooled)
    save(pooled, "m11_fc_interval_coverage_pooled")
    flag_lo, flag_hi = CONFIG["intervals"]["coverage_flag"]
    sel80 = pooled[(pooled["interval"] == "historical_error") & (pooled["method"] == selected)
                   & (pooled["level"] == 80)]["coverage_h5_10_15"].iloc[0]
    results["selected_coverage80_h5_10_15"] = float(sel80)
    results["intervals_historically_calibrated"] = bool(flag_lo <= sel80 <= flag_hi)

    # ------------------------------------------- pseudo-real-time selection (8.4)
    rt = bt.real_time_selection(records, origins)
    picks = rt.set_index("origin")["chosen"]
    proc = records.merge(picks.rename("chosen"), left_on="origin", right_index=True)
    proc = proc[proc["method"] == proc["chosen"]].assign(method="realtime_selection")
    proc_metrics = bt.point_metrics(pd.concat([records[records["method"] == "naive"], proc]),
                                    by=("method", "h"))
    save(rt, "m11_fc_realtime_selection")
    save(proc_metrics[proc_metrics["h"].isin(bt.PRIMARY_H)], "m11_fc_realtime_selection_accuracy")

    # ------------------------------------------------ final forecast (2025-2040)
    log_tfr = np.log(tfr)
    final = {m: models.forecast_tfr(m, log_tfr.to_numpy(), H) for m in models.TFR_METHODS}
    all_methods = pd.concat([path_table(last, out, YEARS).assign(method=m, h=range(1, H + 1))
                             for m, out in final.items()], ignore_index=True)
    sigma_all = bt.calibrated_sigma(records, selected)
    sigma_1977 = bt.calibrated_sigma(records, selected, first_origin=CONFIG["intervals"]["sensitivity_start"])
    forecast = path_table(last, final[selected], YEARS).assign(h=range(1, H + 1), method=selected)
    forecast = add_intervals(forecast, sigma_all)
    forecast = add_intervals(forecast, sigma_1977, prefix="sens1977_")
    errs = records[records["method"] == selected]
    for level in Z:
        tag = int(round(level * 100))
        q = errs.groupby("h")["log_error"].quantile([(1 - level) / 2, (1 + level) / 2]).unstack()
        forecast[f"quantile_lower{tag}"] = np.exp(forecast["log_forecast"] + q.iloc[:, 0].reindex(forecast["h"]).to_numpy())
        forecast[f"quantile_upper{tag}"] = np.exp(forecast["log_forecast"] + q.iloc[:, 1].reindex(forecast["h"]).to_numpy())
    if final[selected]["log_sd_model"] is not None:
        sd = final[selected]["log_sd_model"]
        for level, z in Z.items():
            tag = int(round(level * 100))
            forecast[f"model_lower{tag}"] = np.exp(forecast["log_forecast"] - z * sd)
            forecast[f"model_upper{tag}"] = np.exp(forecast["log_forecast"] + z * sd)
    forecast["calibration_errors"] = errs.groupby("h").size().reindex(forecast["h"]).to_numpy()
    forecast["interval_label"] = tfr_interval_label(results["intervals_historically_calibrated"])
    save(forecast, "m11_fc_tfr_forecast")
    save(all_methods, "m11_fc_tfr_forecast_all_methods")
    f2040 = forecast[forecast["year"] == FC["last_year"]].iloc[0]
    results["tfr_2040"] = {k: float(f2040[k]) for k in ("forecast", "lower80", "upper80", "lower95", "upper95")}
    results["tfr_2040_all_methods"] = {m: float(np.exp(out["log_mean"][-1])) for m, out in final.items()}
    results["final_params"] = {m: out["params"] for m, out in final.items()}

    # ------------------------------------------------------ 2025 (section 6)
    rec = scen.reconstruct_2025()
    save(rec["backtest"], "m11_fc_reconstruction_backtest")
    f2025 = forecast[forecast["year"] == 2025].iloc[0]
    nchs_derived = 1.576
    check = pd.DataFrame([
        {"quantity": "primary forecast 2025 (HFD <= 2024)", "value": f2025["forecast"],
         "lower80": f2025["lower80"], "upper80": f2025["upper80"], "lower95": f2025["lower95"], "upper95": f2025["upper95"]},
        *[{"quantity": f"reconstructed 2025, {k}", "value": v} for k, v in rec["tfr"].items()],
        {"quantity": BAND_LABEL, "value": rec["primary"], "band_lower": rec["band"][0], "band_upper": rec["band"][1]},
        {"quantity": "NCHS-derived 2025 TFR (5 x rounded rates, V2025; not official)", "value": nchs_derived}])
    check["inside_primary_80"] = check["value"].between(f2025["lower80"], f2025["upper80"])
    check["inside_primary_95"] = check["value"].between(f2025["lower95"], f2025["upper95"])
    check["interval_note"] = ("lower/upper columns: nominal 80% and 95% historical-error intervals of the primary "
                              "forecast (not calibrated); band columns: descriptive band, not a probability interval")
    save(check, "m11_fc_check_2025")
    results["reconstruction_2025"] = {"tfr": rec["tfr"], "primary": rec["primary"], "rmse": rec["rmse"],
                                      "descriptive_band_2rmse": list(rec["band"])}
    secondary_series = pd.concat([log_tfr, pd.Series({2025: np.log(rec["primary"])})])
    sec = models.forecast_tfr(selected, secondary_series.to_numpy(), H - 1)
    secondary = path_table(2025, sec, YEARS[1:]).assign(h=range(1, H), method=selected)
    secondary = add_intervals(secondary, sigma_all).assign(label="secondary: includes a reconstructed non-HFD 2025 value",
                                                           interval_label=tfr_interval_label(results["intervals_historically_calibrated"]))
    save(secondary, "m11_fc_tfr_forecast_secondary_2025")
    results["secondary_2040"] = float(secondary["forecast"].iloc[-1])

    # ------------------------------------------------ age profiles (section 9)
    sel_records = records[records["method"] == selected][["origin", "h", "forecast"]]
    shape_metrics, paths = bt.shape_backtest(rates, origins, sel_records)
    LOCAL.mkdir(parents=True, exist_ok=True)
    shape_metrics.to_csv(LOCAL / "m11_fc_shape_backtest.csv", index=False, float_format="%.10g")
    shape_sum = bt.shape_summary(shape_metrics)
    save(shape_sum, "m11_fc_shape_metrics_by_horizon")
    save(bt.shape_summary(shape_metrics[shape_metrics["h"].isin(bt.PRIMARY_H)], by=("method", "era", "h")),
         "m11_fc_shape_metrics_by_era")
    shape_records = shape_metrics.rename(columns={"shape_l1": "loss"})
    shape_sel = bt.selection_table(shape_records, list(models.SHAPE_METHODS), "S0_fixed", loss_col="loss",
                                   complexity={m: i for i, m in enumerate(models.SHAPE_METHODS)})
    shape_selected = bt.choose(shape_sel, "S0_fixed", list(models.SHAPE_METHODS))
    shape_sel["selected"] = shape_sel["method"] == shape_selected
    save(shape_sel, "m11_fc_shape_selection")
    results["selected_shape_method"] = shape_selected
    direct = shape_metrics.dropna(subset=["implied_tfr_error"]) if "implied_tfr_error" in shape_metrics else pd.DataFrame()
    if len(direct):
        recon = direct[direct["h"].isin(bt.PRIMARY_H)].groupby(["method", "h"]).agg(
            implied_tfr_mae=("implied_tfr_error", lambda e: e.abs().mean()),
            asfr_mae_unreconciled=("asfr_mae_unreconciled", "mean"),
            asfr_mae_reconciled=("asfr_mae_coherent", "mean")).reset_index()
        tfr_mae = primary[primary["method"] == selected].set_index("h")["mae"]
        recon["selected_tfr_mae"] = recon["h"].map(tfr_mae)
        save(recon, "m11_fc_direct_reconciliation")

    window = rates.iloc[-CONFIG["shape"]["window"]:].to_numpy()
    tfr_point = forecast["forecast"].to_numpy()
    shape_final = {m: models.forecast_shape(m, window, H) for m in models.SHAPE_METHODS}
    asfr = pd.DataFrame(models.coherent_rates(shape_final[shape_selected]["shape"], tfr_point), index=YEARS,
                        columns=bt.AGES)
    long = asfr.stack().rename("asfr").reset_index().rename(columns={"level_0": "year", "level_1": "age"})
    for tag in (80, 95):
        for side in ("lower", "upper"):
            scale = (forecast.set_index("year")[f"{side}{tag}"] / forecast.set_index("year")["forecast"])
            long[f"asfr_{side}{tag}_tfr_driven"] = long["asfr"] * long["year"].map(scale)
    long["shape_method"], long["tfr_method"] = shape_selected, selected
    save(long, "m11_fc_asfr_forecast")
    obs_long = rates.loc[1995:].stack().rename("asfr").reset_index().rename(columns={"Year": "year", "Age": "age"})
    save(obs_long, "m11_fc_asfr_observed_1995_2024")
    results["asfr_sum_max_gap"] = float(np.abs(asfr.sum(axis=1).to_numpy() - tfr_point).max())
    results["asfr_diagnostics"] = asfr_diagnostics(asfr, rates)
    save(pd.DataFrame([results["asfr_diagnostics"]]), "m11_fc_asfr_diagnostics")
    mab = pd.DataFrame({"year": YEARS, **{m: (shape_final[m]["shape"] * (np.array(bt.AGES) + 0.5)).sum(axis=1)
                                          for m in models.SHAPE_METHODS}})
    save(mab, "m11_fc_mean_age_by_shape_method")

    # ------------------------------------------------------- cohorts (section 10)
    validation = coh.validate_transformation(rates, vv_obs)
    vsum = validation.groupby("method")["error"].agg(mean_abs_error=lambda e: e.abs().mean(),
                                                     bias="mean", max_abs_error=lambda e: e.abs().max()).reset_index()
    transform = str(vsum.sort_values("mean_abs_error").iloc[0]["method"])
    vsum["chosen"] = vsum["method"] == transform
    save(vsum, "m11_fc_cohort_transform_validation")
    transform_ok = bool(vsum.loc[vsum["chosen"], "mean_abs_error"].iloc[0] < CONFIG["cohort"]["transform_max_error"])
    results["cohort_transform"] = {"method": transform, "acceptable": transform_ok,
                                   "mean_abs_error": float(vsum.loc[vsum["chosen"], "mean_abs_error"].iloc[0])}

    coh_origins = [o for o in origins if o <= CONFIG["cohort"]["last_origin"]]
    naive_level = records[records["method"] == "naive"].set_index(["origin", "h"])["forecast"]
    pipelines = {f"{selected} x {shape_selected}": {o: paths[(shape_selected, o)]["coherent"] for o in coh_origins}}
    pipelines.setdefault("naive x S0_fixed", {o: paths[("S0_fixed", o)]["shape"] *
                                              np.array([naive_level[(o, h)] for h in range(1, len(paths[("S0_fixed", o)]["shape"]) + 1)
                                                        if (o, h) in naive_level])[:, None]
                                              for o in coh_origins})
    for m in models.SHAPE_METHODS:
        pipelines.setdefault(f"{selected} x {m}", {o: paths[(m, o)]["coherent"] for o in coh_origins})
    primary_pipeline = f"{selected} x {shape_selected}"
    cohort_records = pd.concat([coh.pseudo_cohort_backtest(rates, vv_obs, p, name, transform, coh_origins)
                                for name, p in pipelines.items()], ignore_index=True)
    cohort_records.to_csv(LOCAL / "m11_fc_cohort_backtest.csv", index=False, float_format="%.10g")
    cohort_records["a0_group"] = pd.cut(cohort_records["age_at_origin"], [11, 17, 23, 29], labels=["12-17", "18-23", "24-29"])
    csum = cohort_records[cohort_records["h"].isin([5, 10, 15, 16])].groupby(
        ["pipeline", "a0_group", "h"], observed=True).agg(
        origins=("origin", "nunique"), mae=("error", lambda e: e.abs().mean()), bias=("error", "mean"),
        rmse=("error", lambda e: np.sqrt(np.mean(e ** 2))), rms_log_ratio=("log_ratio", lambda e: np.sqrt(np.mean(e ** 2))),
        mean_observed_increment=("observed_increment", "mean")).reset_index()
    save(csum, "m11_fc_cohort_backtest_summary")
    prim_records = cohort_records[cohort_records["pipeline"] == primary_pipeline]
    ccov = coh.cohort_real_time_coverage(prim_records)
    save(ccov.groupby("h")[["covered80", "covered95"]].mean().reset_index().merge(
        ccov.groupby("h").size().rename("evaluations").reset_index(), on="h"), "m11_fc_cohort_interval_coverage")

    vv_final_ratios = coh.transform_ratios(rates, vv_obs, last) if transform == "T2" else None
    observed_cum = coh.observed_cumulative(vv_obs, coh.GEN_Z, last)
    shares = coh.reference_shares(vv_obs)
    genz = {}
    for name, shape_method in [("primary", shape_selected)] + [(m, m) for m in models.SHAPE_METHODS]:
        rr = models.coherent_rates(shape_final[shape_method]["shape"], tfr_point)
        genz[name] = coh.project_cohorts(coh.to_vv(rr, transform, vv_final_ratios), FC["first_year"], observed_cum, coh.GEN_Z)
    projected = genz["primary"].copy()
    base_cum = observed_cum.groupby("cohort")["cumulative"].last()
    projected["a0"] = last - projected["cohort"]
    projected["h"] = projected["year"] - last
    projected["increment"] = projected["cumulative"] - projected["cohort"].map(base_cum)
    for level, z in Z.items():
        tag = int(round(level * 100))
        sig = [coh.cohort_sigma(prim_records, int(a0), int(h))[0] for a0, h in zip(projected["a0"], projected["h"])]
        projected["sigma"] = sig
        projected[f"lower{tag}"] = projected["cohort"].map(base_cum) + projected["increment"] * np.exp(-z * projected["sigma"])
        projected[f"upper{tag}"] = projected["cohort"].map(base_cum) + projected["increment"] * np.exp(z * projected["sigma"])
    trajectories = pd.concat([observed_cum, projected], ignore_index=True).sort_values(["cohort", "year"])
    trajectories["pipeline"] = primary_pipeline
    trajectories["transform"] = transform
    cohort_label = cohort_interval_label(ccov)
    trajectories.loc[trajectories["segment"] == "projected", "interval_label"] = cohort_label
    save(trajectories, "m11_fc_genz_trajectories")
    endpoints = genz_endpoints(trajectories, base_cum, shares, genz, last).assign(interval_label=cohort_label)
    save(endpoints, "m11_fc_genz_endpoints_2040")
    save(shares, "m11_fc_reference_completion_shares")
    results["genz"] = endpoints.set_index("cohort")[["observed_2024", "projected_2040", "lower80", "upper80",
                                                    "completion_label"]].to_dict(orient="index")
    contributions = trajectories[trajectories["segment"] == "projected"].groupby("cohort")["contribution"].sum()
    results["cohort_accumulation_max_gap"] = float((base_cum + contributions - endpoints.set_index("cohort")["projected_2040"]).abs().max())

    # ------------------------------------------------- Census (section 11)
    alignment = scen.exposure_alignment()
    save(alignment, "m11_fc_census_alignment")
    rtest = scen.rebasing_test()
    save(rtest, "m11_fc_census_rebasing_test")
    method = scen.valid_rebasing(rtest) if alignment["within_tolerance"].all() else None
    results["census_rebasing"] = method
    census_tfr = src.load_np_tfr().set_index("year")["tfr"]
    ctfr = forecast[["year", "forecast", "lower80", "upper80", "lower95", "upper95"]].copy()
    ctfr["census_assumed_tfr_projection_year"] = ctfr["year"].map(census_tfr)
    ctfr["census_inside_80"] = ctfr["census_assumed_tfr_projection_year"].between(ctfr["lower80"], ctfr["upper80"])
    ctfr["census_inside_95"] = ctfr["census_assumed_tfr_projection_year"].between(ctfr["lower95"], ctfr["upper95"])
    save(ctfr, "m11_fc_census_tfr_comparison")
    if method is not None:
        births = scen.scenario_births(asfr, method)
        unrebased = scen.scenario_births(asfr, "none")
        mid = births[births["scenario"] == "mid"].set_index("year")["births"]
        for tag in (80, 95):
            for side in ("lower", "upper"):
                scale = forecast.set_index("year")[f"{side}{tag}"] / forecast.set_index("year")["forecast"]
                births.loc[births["scenario"] == "mid", f"fertility_{side}{tag}"] = (mid * scale).to_numpy()
        births.loc[births["scenario"] == "mid", "fertility_range_label"] = (
            "births at the bounds of the nominal TFR historical-error intervals (not calibrated), main-series population")
        births["scenario_label"] = "immigration scenario at the point fertility forecast; not a probability"
        save(births, "m11_fc_census_births")
        save(unrebased, "m11_fc_census_births_unrebased")
        save(scen.census_births_comparison(births), "m11_fc_census_births_comparison")
        b2040 = births[births["year"] == FC["last_year"]].set_index("scenario")
        results["births_2040"] = b2040["births"].to_dict()
        results["births_2040_mid_fertility80"] = [float(b2040.loc["mid", "fertility_lower80"]),
                                                   float(b2040.loc["mid", "fertility_upper80"])]
    else:
        results["births_2040"] = None

    # ------------------------------------------------------- robustness (section 12)
    robustness(tfr, records, selected, final, results, shape_final, genz, endpoints, trajectories, vv_obs, rates,
               observed_cum, transform, tfr_point, last)

    save(data_dictionary(), "m11_fc_data_dictionary")
    finished = utc_now()
    (OUT / "m11_fc_summary.json").write_text(json.dumps(results, indent=1, default=_json), encoding="utf-8")
    record = {"protocol": lock["protocol"], "protocol_sha256": protocol_sha(), "locked_utc": lock["locked_utc"],
              "amendments": len(lock["amendments"]), "started_utc": started, "finished_utc": finished,
              "code_sha256": {p: file_sha(PROJECT_ROOT / p) for p in CODE},
              "hfd_zip_sha256": file_sha(src.HFD_DIR / "USA.zip"),
              "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
              "scipy": scipy.__version__}
    (OUT / "m11_run_record.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return results


INTERVAL_TYPES = [
    ("m11_fc_tfr_forecast", "lower80, upper80, lower95, upper95", "historical-error interval (nominal level)",
     "Log-normal; spread = RMS of no-change log errors at each horizon over all backtest origins. Failed the "
     "prespecified calibration criterion (pseudo-real-time 80% coverage 0.96). Not a validated probability interval."),
    ("m11_fc_tfr_forecast", "sens1977_*, quantile_*", "historical-error interval (nominal level), sensitivity",
     "Spread from origins 1977+ (under-covers at long horizons) or empirical error quantiles. Not calibrated."),
    ("m11_fc_tfr_forecast", "model_lower*, model_upper*", "model-dependent uncertainty range",
     "Random-walk model variance from one-step residuals; under-covered historically."),
    ("m11_fc_tfr_forecast_secondary_2025", "lower80 ... upper95", "historical-error interval (nominal level)",
     "Same spreads as the primary forecast; secondary forecast containing a reconstructed non-HFD 2025 value."),
    ("m11_fc_check_2025", "band_lower, band_upper", "descriptive band",
     "Reconstructed 2025 TFR (E2) +/- 2 x RMSE of a four-year ratio-method backtest; not a confidence or "
     "prediction interval."),
    ("m11_fc_check_2025", "lower80 ... upper95, inside_primary_*", "historical-error interval (nominal level)",
     "Primary 2025 forecast interval and whether each 2025 estimate falls inside it."),
    ("m11_fc_genz_trajectories, m11_fc_genz_endpoints_2040", "lower80 ... upper95", "historical-error interval (nominal level)",
     "Log-normal on the projected increment; spread from pseudo-cohort backtest errors (fixed strategy). "
     "Pseudo-real-time 80% coverage 0.78-0.96 by horizon; over-covers at long horizons; not calibrated."),
    ("m11_fc_genz_endpoints_2040", "projected_2040_S*", "model-dependent uncertainty range",
     "Endpoints under alternative age-profile methods; sensitivity, not a probability interval."),
    ("m11_fc_asfr_forecast", "asfr_*_tfr_driven", "historical-error interval (nominal level), propagated",
     "Fixed age shape scaled to the TFR interval bounds; inherits the TFR interval's lack of calibration."),
    ("m11_fc_census_births", "fertility_lower*, fertility_upper*", "historical-error interval (nominal level), propagated",
     "Main-series births at the TFR interval bounds; fertility uncertainty only."),
    ("m11_fc_census_births", "scenario (hi, low, zero, mid)", "scenario range",
     "Census immigration scenarios at the point fertility forecast; no probability interpretation."),
    ("m11_fc_rob_2040_by_method_and_window, m11_fc_tfr_forecast_all_methods", "tfr_2040, forecast",
     "model-dependent uncertainty range", "Alternative methods and training windows; not probability intervals."),
]


def data_dictionary() -> pd.DataFrame:
    return pd.DataFrame(INTERVAL_TYPES, columns=["table", "columns", "interval_type", "meaning"])


BAND_LABEL = ("reconstructed 2025 descriptive band: E2 +/- 2 x RMSE of the 2021-2024 ratio-method backtest "
              "(4 errors; not a confidence or prediction interval)")


def tfr_interval_label(calibrated: bool) -> str:
    if calibrated:
        return "historical-error interval (nominal level); met the prespecified calibration criterion"
    return ("historical-error interval (nominal level); failed the prespecified calibration criterion "
            "(pseudo-real-time coverage outside 65-95%); not a validated probability interval")


def cohort_interval_label(coverage: pd.DataFrame) -> str:
    """Describe cohort intervals by their pseudo-real-time coverage; never as calibrated."""
    parts = ", ".join(f"{c:.2f}" for c in coverage.sort_values("h")["covered80"])
    hs = "/".join(str(int(h)) for h in coverage.sort_values("h")["h"])
    return (f"historical-error interval (nominal level) from pseudo-cohort backtest errors; pseudo-real-time "
            f"80% coverage {parts} at h {hs}; over-covers at long horizons; not a validated probability interval")


def _json(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return str(value)


def asfr_diagnostics(asfr: pd.DataFrame, rates: pd.DataFrame) -> dict:
    lo, hi = CONFIG["shape"]["smooth_ages"]
    ref0, ref1 = CONFIG["shape"]["smooth_reference"]
    cols = [a for a in bt.AGES if lo <= a <= hi]
    second = lambda m: np.abs(np.diff(np.log(np.maximum(m[cols].to_numpy(), CONFIG["data"]["rate_floor"])), n=2, axis=1)).max()
    obs = rates.loc[ref0:ref1]
    shape = lambda m: (m.to_numpy() / m.to_numpy().sum(axis=1, keepdims=True))
    obs_change = np.abs(np.diff(shape(obs), axis=0)).sum(axis=1)
    jump = np.abs(shape(asfr.iloc[:1]) - shape(rates.iloc[-1:])).sum()
    fc_change = np.abs(np.diff(shape(asfr), axis=0)).sum(axis=1)
    return {"min_rate": float(asfr.to_numpy().min()), "negative_rates": int((asfr < 0).sum().sum()),
            "max_second_difference_log_forecast": float(second(asfr)),
            "max_second_difference_log_observed_1995_2024": float(second(obs)),
            "jump_off_shape_l1": float(jump), "max_annual_shape_l1_forecast": float(fc_change.max()),
            "max_annual_shape_l1_observed_1995_2024": float(obs_change.max())}


def genz_endpoints(trajectories, base_cum, shares, genz, last) -> pd.DataFrame:
    rows = []
    hfd_exact = coh.ccfr_exact(coh.GEN_Z).set_index("cohort")
    for c in coh.GEN_Z:
        end = trajectories[(trajectories["cohort"] == c) & (trajectories["year"] == FC["last_year"])].iloc[0]
        ardy_2040 = FC["last_year"] - c
        share = shares.set_index("ardy").loc[ardy_2040] if ardy_2040 in set(shares["ardy"]) else None
        row = {"cohort": c, "age_reached_2024": last - c, "observed_2024": float(base_cum[c]),
               "hfd_last_complete_age": hfd_exact.loc[c, "last_complete_age"],
               "hfd_ccfr_exact_age": hfd_exact.loc[c, "ccfr_exact_age"], "hfd_ccfr": hfd_exact.loc[c, "ccfr"],
               "age_reached_2040": ardy_2040, "projected_2040": float(end["cumulative"]),
               "projected_increment": float(end["cumulative"] - base_cum[c]),
               "lower80": float(end["lower80"]), "upper80": float(end["upper80"]),
               "lower95": float(end["lower95"]), "upper95": float(end["upper95"]), "sigma_log_increment": float(end["sigma"]),
               "reference_share_min": float(share["min"]) if share is not None else np.nan,
               "reference_share_max": float(share["max"]) if share is not None else np.nan}
        for m in models.SHAPE_METHODS:
            g = genz[m]
            row[f"projected_2040_{m}"] = float(g[(g["cohort"] == c) & (g["year"] == FC["last_year"])]["cumulative"].iloc[0])
        row["completion_label"] = coh.completion_label(row["reference_share_min"], row["reference_share_max"])
        rows.append(row)
    return pd.DataFrame(rows)


def robustness(tfr, records, selected, final, results, shape_final, genz, endpoints, trajectories, vv_obs, rates,
               observed_cum, transform, tfr_point, last) -> None:
    rob = {}
    log_tfr = np.log(tfr)
    # R1, R2: alternative training windows
    r1 = bt.tfr_backtest(tfr, range(1996, CONFIG["backtest"]["last_origin"] + 1), start=1977)
    r2 = bt.tfr_backtest(tfr, range(CONFIG["backtest"]["first_origin"], CONFIG["backtest"]["last_origin"] + 1), window=30)
    rows = []
    for name, recs in [("expanding_1933 (primary)", records), ("expanding_1977", r1), ("rolling_30", r2)]:
        m = bt.point_metrics(recs[recs["h"].isin(bt.PRIMARY_H)])
        rows.append(m.assign(training=name))
    save(pd.concat(rows, ignore_index=True), "m11_fc_rob_training_windows")
    f2040 = []
    for name, start, window in [("expanding_1933 (primary)", None, None), ("expanding_1977", 1977, None),
                                ("rolling_30", None, 30)]:
        train = bt.training_slice(log_tfr, last, start, window).to_numpy()
        for m in models.TFR_METHODS:
            f2040.append({"training": name, "method": m,
                          "tfr_2040": float(np.exp(models.forecast_tfr(m, train, H)["log_mean"][-1]))})
    save(pd.DataFrame(f2040), "m11_fc_rob_2040_by_method_and_window")
    # R3: selection within origins 1977+ (era condition split at 2000)
    late = records[records["origin"] >= 1977]
    late_sel = bt.selection_table(late, list(models.TFR_METHODS), "naive", split=2000, complexity=CONFIG["parameters"])
    late_sel["selected"] = late_sel["method"] == bt.choose(late_sel, "naive", list(models.TFR_METHODS))
    save(late_sel, "m11_fc_rob_selection_from_1977")
    rob["selection_from_1977"] = str(late_sel.loc[late_sel["selected"], "method"].iloc[0])
    # R5: parameter stability
    stab = records[records["h"] == 1][["method", "origin", "params"]]
    save(stab[stab["method"].isin(["ses", "holt_damped", "ar_level", "ari"])], "m11_fc_rob_parameter_stability")
    # R6: 2040 forecast from origins 2015-2024 (selected method)
    r6 = [{"origin": o, "tfr_at_origin": float(tfr[o]),
           "tfr_2040": float(np.exp(models.forecast_tfr(selected, log_tfr.loc[:o].to_numpy(), FC["last_year"] - o)["log_mean"][-1]))}
          for o in range(2015, last + 1)]
    save(pd.DataFrame(r6), "m11_fc_rob_origin_sensitivity")
    # R7: error growth
    growth = bt.point_metrics(records)[["method", "h", "rmse", "rms_log_error", "origins"]]
    gamma = {}
    for m, g in growth.groupby("method"):
        gamma[m] = float(np.polyfit(np.log(g["h"]), np.log(g["rmse"]), 1)[0])
    growth["gamma_rmse_vs_h"] = growth["method"].map(gamma)
    save(growth, "m11_fc_rob_error_growth")
    rob["gamma_selected"] = gamma[selected]
    # R8: pandemic check, origin 2019
    save(records[records["origin"] == 2019][["method", "target", "forecast", "observed", "error"]], "m11_fc_rob_pandemic_origin_2019")
    # R9, R10: age-profile assumption and cohort conventions
    conv = endpoints[["cohort", "observed_2024", "hfd_ccfr_exact_age", "hfd_ccfr", "projected_2040"]
                     + [f"projected_2040_{m}" for m in models.SHAPE_METHODS]].copy()
    other = "T1" if transform == "T2" else "T2"
    ratios = coh.transform_ratios(rates, vv_obs, last) if other == "T2" else None
    rr = models.coherent_rates(shape_final[results["selected_shape_method"]]["shape"], tfr_point)
    alt = coh.project_cohorts(coh.to_vv(rr, other, ratios), FC["first_year"], observed_cum, coh.GEN_Z)
    conv[f"projected_2040_{other}"] = conv["cohort"].map(alt[alt["year"] == FC["last_year"]].set_index("cohort")["cumulative"])
    save(conv, "m11_fc_rob_cohort_conventions")
    # R13 intervals from 1977+ errors: pseudo-real-time coverage
    timed = bt.real_time_sigma(records[records["origin"] >= CONFIG["intervals"]["sensitivity_start"]])
    scored = bt.score_intervals(timed, "sigma_rt")
    save(bt.coverage_summary(scored, by=("method", "h")), "m11_fc_rob_interval_calibration_1977")
    results["robustness"] = rob


def main() -> int:
    results = run()
    print(json.dumps({k: results[k] for k in ("selected_tfr_method", "selected_shape_method", "tfr_2040",
                                               "intervals_historically_calibrated", "cohort_transform",
                                               "census_rebasing")}, indent=1, default=_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
