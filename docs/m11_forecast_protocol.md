# M11 fertility forecasting protocol

**Status.** Internally locked, not externally preregistered. The SHA-256 of this file, the lock time and every later amendment are recorded in `docs/m11_protocol_lock.json`. The M11 forecasting code reads its settings from the configuration block at the end of this file, and it refuses to run if the file's hash differs from the lock. No public registry holds a copy, so the lock shows that the protocol has not changed since the recorded time on this machine. It does not prove anything to an outside party.

**Drafted.** 2026-11-20, from about 11:38 UTC, after the M11 data-feasibility stage and the stage-1 HFD correction (`docs/m11_decision_log.md`).

**What was known when this protocol was written.**
- The full HFD period series 1933–2024 had been inspected descriptively: turning points 1957, 1976, 2007 and 2024, and the 2024 TFR of 1.593.
- Also known: the derived NCHS 2025 TFR (1.576), the Census 2023 fertility assumption and the cohort observability matrix.

**What had not been done.** No forecasting model had been fitted to any series. No forecast error, backtest metric, interval coverage or cohort projection had been computed for any method. The protocol is therefore blind to forecast performance, not to the data.

## 1. Questions

- **A.** What may happen to national period fertility (TFR) between 2025 and 2040?
- **B.** What may happen to cumulative fertility of the 1995–2012 birth cohorts by the end of 2040?
- **C.** Can these results show whether Gen Z will eventually reach its desired family size?
  - The protocol fixes the answer's scope in advance. Aggregate period or cohort forecasts do not observe individual intentions or their fulfilment.
  - M09 (NSFG 2022–2023) has no desired-family-size measure that is directly comparable with completed cohort fertility.
  - So C can only be answered as "not establishable from these data". Any comparison is descriptive context.

## 2. Data

| Role | Source | Use |
|---|---|---|
| Primary history | HFD USA, release 2 July 2026, 1933–2024 (`data/raw/hfd_usa/`, hashes in `provenance.json`) | Period ASFR by single year of age (RR, age in completed years 12–55, `12-` = 12 and younger, `55+` = 55 and older); cohort-period ASFR by age reached during the year (VV); cohort measures (VH, CCFR, CCF) |
| External 2025 check | NCHS final 2025 births (public-use file, residents) and Census vintage 2025 population estimates | 2025 plausibility check and reconstruction of a 2025 HFD-compatible estimate (section 6). Never part of the primary fit |
| External scenarios | Census 2023 National Population Projections (NP2023), four immigration scenarios | Female population exposures for scenario-conditional births; the Census fertility assumption is a comparison only |

**Primary target series.** y_t = Σ_x ASFR_RR(t, x) over x = 12…55, read from `USAasfrRR.txt`. This equals the HFD TFR (`USAtfrRR.txt`, 3 decimals) to within print precision, which is verified. It is used instead of the 3-decimal TFR so that age-specific forecasts reconcile exactly with the TFR.

**Rules.**
- Census projected fertility is never an observed predictor and never a validation target.
- NCHS 2025 values are never silently appended to the HFD series.

## 3. Targets

| Target | Definition | Years |
|---|---|---|
| **Primary** | HFD period TFR | 2025–2040 (horizons 1–16 from 2024) |
| Secondary 1 | Period ASFR by single year of age (ACY 12–55), coherent with the TFR forecast: Σ_x ASFR = TFR exactly | 2025–2040 |
| Secondary 2 | Cumulative cohort fertility by 31 December of each year to 2040, cohorts 1995–2012 (Gen Z) | Observed to 2024, projected 2025–2040 |
| Secondary 3 | Calendar-year births under the four Census immigration scenarios. Only if the exposure-alignment and rebasing tests in section 9 pass | 2025–2040 |

**Gen Z cohort measure.**
- Fertility accumulated by the end of calendar year Y is the running sum over years t ≤ Y of HFD VV rates (age reached during year t = t − c).
- This is not fertility by an exact age. At the end of year Y a woman born in year c is between exact ages Y − c and Y − c + 1.
- The HFD CCFR (by exact age, horizontal parallelograms) is reported alongside for the fully observed ages.
- Neither measure is completed fertility, unless the reference-cohort share reached by that age is close to 1 (section 8.6).

## 4. Backtest design (all point and interval methods)

**Forecast origins.**
- For each origin T in 1952…2023, the training data are HFD years 1933…T only.
- The minimum training length is 20 years.
- Forecasts are made for every horizon h = 1…16 with T + h ≤ 2024.

**Horizons.**
- The primary evaluation horizons are 5, 10 and 15.
- Horizons 1–16 are all recorded. Horizon 16 is the 2040 horizon from 2024 and is used for interval calibration.

**No leakage.**
- Every parameter, model order and smoothing constant is re-estimated at each origin from the training data alone.
- Preprocessing (log transform, ratio estimates) uses training years only.
- Nothing about later years enters a forecast.
- Each backtest record stores the origin, the first and last training years, the horizon, the forecast, the observed value and the fitted configuration.

**Eras (by origin).**

| Era | Origins |
|---|---|
| E1 | 1952–1976 (boom and bust) |
| E2 | 1977–1999 |
| E3 | 2000–2023 |

**Dependence.**
- Errors from overlapping origins are not independent experiments. The report gives, for each horizon, the number of origins and the number of non-overlapping windows, ceil(n/h).
- Uncertainty for accuracy comparisons comes from a circular moving-block bootstrap over origins, with block length h, 2,000 replicates and seed 20261120.
- Diebold–Mariano tests use a Bartlett HAC variance with lag h − 1 and the Harvey–Leybourne–Newbold correction. They are reported as descriptive only, because at 15 years there are only four independent windows.

## 5. Primary TFR methods

All methods are fitted to log TFR, so every forecast is positive. Forecasts are back-transformed with exp(·), which gives the median, not the mean.

| Id | Method | Definition at origin T (y = log TFR) | Parameters |
|---|---|---|---|
| `naive` | B0 no change | ŷ(T+h) = y_T | 0 |
| `mean10` | B2 10-year mean | mean of y over T−9…T | 0 |
| `drift10` | B1 random walk with 10-year drift | y_T + h·d, d = (y_T − y_{T−10}) / 10 | 1 |
| `drift10_damped` | B1 damped | y_T + d·Σ_{j=1..h} φ^j, φ = 0.90 fixed | 1 |
| `converge30` | B3 rule-based convergence | μ + (y_T − μ)·max(0, 1 − h/20), μ = mean of y over the last 30 years (all years if fewer) | 1 |
| `ses` | ETS(A,N,N) simple exponential smoothing | α estimated | 1 |
| `holt_damped` | ETS(A,Ad,N) damped-trend exponential smoothing | α, β, φ estimated | 3 |
| `ar_level` | AR(p) with mean, p ∈ {1,2,3} by AICc | conditional least squares | p+1 |
| `ari` | ARIMA(p,1,0) without constant, p ∈ {0,1,2,3} by AICc (p = 0 is a random walk) | conditional least squares on first differences | p |

**Estimation details** (configuration block):
- ETS initial states are l₀ = y₁ and b₀ = y₂ − y₁.
- Parameters minimize the sum of squared one-step errors. The first step is excluded for SES; the first two are excluded for damped trend.
- The search is a fixed grid followed by L-BFGS-B refinement inside the bounds α ∈ [0.0001, 0.9999], β = α·β\*, β\* ∈ [0.0001, 1], φ ∈ [0.80, 0.98]. It is deterministic.
- AR and ARI models are fitted by OLS on a common estimation sample for all orders, so their AICc values are comparable. AICc = n·log(SSE/n) + 2k + 2k(k+1)/(n−k−1).
- Forecasts outside [0.8, 4.5] children per woman are flagged as implausible in the output. They are not clipped.

**More flexible models.**
- None is in the primary comparison: no machine learning, no regression on covariates and no Bayesian hierarchical model.
- With four independent 15-year windows, the backtest cannot support many more parameters.
- A flexible alternative can be added only by a recorded amendment, and only if every candidate shows a systematic, identifiable failure such a model could address. It would be labelled exploratory and could not become the primary forecast.

## 6. Treatment of 2025

1. **Main specification:** fit on HFD ≤ 2024 and forecast 2025–2040.
2. **External plausibility check:** compare the 2025 forecast and its interval with two values.
   - The NCHS-derived 2025 TFR of 1.576 (5 × rounded 5-year rates on vintage 2025 denominators). It is derived, not official.
   - A reconstructed HFD-compatible 2025 estimate (step 3).
3. **HFD-compatible reconstruction.**
   - Births: 2025 resident births by single age from the NCHS public-use file. The NCHS `10–12` group maps to HFD `12-`. The NCHS `50–54` group is split across HFD ages 50…55+ in proportion to HFD 2024 births at those ages.
   - Exposures, three definitions:
     - (E1) Census vintage 2025 female population on July 1, 2025;
     - (E2, primary) E1 × the ratio of HFD 2024 exposure to vintage 2025 July 1, 2024 population, by single age;
     - (E3) E1 × the mean of that ratio over 2021–2024.
   - Uncertainty: the E2 method is backtested for 2021–2024. TFR(Y) is reconstructed from HFD births in Y, vintage 2025 (and, separately, vintage 2024) populations in Y, and the ratio from Y − 1, then compared with the HFD TFR(Y).
   - The reconstruction is reported as E2 ± 2 × the root-mean-square backtest error, with E1 and E3 shown as alternative definitions.
4. **Secondary 2025-informed forecast.**
   - Append the E2 estimate (TFR and age schedule) to the HFD series, refit the selected methods, and forecast 2026–2040.
   - Label it "secondary, includes a reconstructed non-HFD 2025 value". It never replaces the primary forecast.

## 7. Evaluation and model selection (TFR)

**Point accuracy.** All on the TFR scale, by horizon, by era and overall:
- error e = observed − forecast;
- mean error (bias), MAE and RMSE;
- MASE: |e| divided by the mean absolute one-step change of TFR in that origin's training window, averaged;
- relative MAE: MAE of the method ÷ MAE of `naive` on the same origins and horizons.

**Primary loss.** R_m = mean over h ∈ {5, 10, 15} of relative MAE, on the full expanding-window backtest.

**Selection rule.** A method replaces `naive` only if all three conditions hold:
1. R_m ≤ 0.90;
2. relative MAE < 1 at each of h = 5, 10 and 15, separately within origins 1952–1976 and within origins 1977 onwards;
3. the one-sided 90% moving-block-bootstrap upper bound of R_m, the 90th percentile of its bootstrap distribution, is < 1. Each replicate resamples origins separately at each horizon, in circular blocks of length h, and recomputes the three MAE ratios and their mean.

Among qualifying methods, the lowest R_m wins. If a simpler qualifying method is within 0.02 of that minimum, it is chosen instead. Simplicity follows the fixed complexity ranks in the configuration (`parameters`), because AR orders vary by origin; ties go to the method listed first. **If no method qualifies, `naive` is retained.**

**Probabilistic accuracy.** Each method gets an empirically calibrated predictive distribution, built in pseudo-real time:
- At origin T and horizon h, the distribution is log-normal: centred on the log forecast, with σ_h(T) = root-mean-square of that method's own log errors at horizon h from origins t with t + h ≤ T. At least 10 such errors are required, otherwise the interval is not evaluated.
- Scored on 80% and 95% interval coverage, mean width (TFR scale), interval score (Gneiting & Raftery, 2007) and CRPS. CRPS uses the closed-form log-normal expression on the TFR scale.
- For the stochastic methods (`naive`, `ses`, `holt_damped`, `ar_level`, `ari`), model-based Gaussian log-scale intervals are computed for comparison: σ from training one-step residuals, horizon variance from the ψ-weights. They are scored the same way.

## 8. Predictive uncertainty for the published forecast

1. **Primary intervals (TFR).** Log-normal around the selected method's 2025–2040 forecast. σ_h = root-mean-square of the selected method's log errors at horizon h over all backtest origins (h = 1…16; h = 16 uses origins 1952–2008). Published at 80% and 95%. This calibrates the intervals to historical forecasting performance, including past regime changes. Each h is an h-step error, so annual errors are not assumed independent.
2. **Calibration evidence.**
   - Pseudo-real-time coverage of the intervals in section 7, by horizon and era, with block-bootstrap 90% intervals for coverage.
   - If the 80% coverage averaged over h ∈ {5, 10, 15} lies outside 65–95%, every output labels the intervals "not historically calibrated".
3. **Sensitivity intervals**, reported but not primary:
   - σ_h from origins 1977+ only;
   - empirical quantiles instead of the log-normal;
   - model-based intervals.
4. **Model-selection uncertainty.** The 2040 forecasts of all nine methods; the method each origin would have chosen under a pseudo-real-time version of the selection rule, using only errors observable at that origin; and the accuracy of that selection procedure. The pseudo-real-time rule applies conditions 1 and 3 of section 7 to errors with t + h ≤ T. Condition 2 is not applied, because both origin groups are not yet observable early in the history. It needs at least 10 errors at each of h = 5, 10 and 15, which first occurs at origin 1976. Before then `naive` is used.
5. **Scenarios are not intervals.** Alternative trend assumptions are labelled "model-dependent projections, not probability intervals": the non-selected methods, training from 1977 and rolling 30-year windows. The same applies to Census immigration scenarios. None is drawn as a 95% band.
6. **Cohort intervals** (section 10.4) are calibrated separately from cohort backtest errors.

## 9. Age-specific fertility (secondary 1)

**Notation.** Shape f(t, x) = ASFR(t, x) / TFR(t), x = 12…55 (44 ages, ACY, open at both ends). Rates are floored at 5 × 10⁻⁶ (half the HFD print unit) before any logarithm. The shape window is the last W = 30 training years (all years if fewer; at least 20).

| Id | Approach | Definition |
|---|---|---|
| `S0_fixed` | Profile, no change | f(T+h) = f(T) |
| `S1_shape_drift` | Profile model | Compositional Lee–Carter: centred log-ratio z = log f − mean_x log f; a_x = window mean; first SVD component b_x k_t; k as a random walk with drift (window drift); jump-off z(T+h) = z(T) + b·(k̂(T+h) − k(T)); back-transformed with softmax |
| `S2_shape_damped` | Profile model | As S1, with k forecast by `holt_damped` |
| `S3_direct_ets` | Direct age-specific | `holt_damped` on log ASFR at each age separately (window W) |
| `S4_lee_carter` | Direct age-specific | log ASFR = a_x + b_x k_t (window W), k as a random walk with drift, jump-off from the observed year |

**Coherence.**
- The published ASFR is TFR_selected(T+h) × f_selected(T+h), so Σ_x ASFR = TFR exactly.
- Direct methods (S3, S4) give their own implied TFR. They are evaluated unreconciled and after proportional reconciliation (ASFR × TFR_selected / Σ ASFR), and the effect of reconciliation on accuracy is reported.

**Metrics** at h = 5, 10, 15:
- shape L1 distance Σ_x |f̂ − f| (0 to 2);
- error in the mean age at birth, Σ(x + 0.5)f;
- ASFR mean absolute error over ages, per 1,000 women, for coherent schedules;
- implied-TFR error for unreconciled direct methods.

**Selection.** As section 7, applied to mean shape L1 relative to `S0_fixed`: ≤ 0.90; < 1 at each horizon in both origin groups; bootstrap upper bound < 1. Otherwise `S0_fixed` is retained.

**Plausibility diagnostics.** Non-negativity, exact sum, and the maximum absolute second difference of log ASFR over ages 15–45 compared with the observed 1995–2024 range. Also year-on-year shape change (L1) at the jump-off compared with the largest observed annual change.

## 10. Gen Z cohort projections (secondary 2)

1. **Observed segment.** HFD VV rates through 2024, cumulated by cohort (open `12-` cell included). For each cohort the report shows:
   - the last observed year and age reached (2024, age 2024 − c);
   - the last fully observed HFD cohort-age cell (age 2023 − c);
   - the HFD CCFR at exact age 2024 − c.
2. **Period-to-cohort transformation.** A forecast square (year t, ACY x) contains two cohorts, so the cohort is not identified by t − x. VV(t, a) belongs to the single cohort t − a and combines the upper triangle of age a − 1 with the lower triangle of age a. Two transformations of forecast RR rates m(t, x) to VV:
   - T1: VV(t, a) = ½[m(t, a−1) + m(t, a)], with m(t, 11) = 0;
   - T2: T1 × r_a, where r_a is the mean observed ratio VV / T1 over the 5 years up to the origin.

   Both are validated in-sample (a data-definition step, not a forecast evaluation). Observed RR for 1938–2024 is transformed, and 16-year cumulative cohort increments are compared with observed VV increments for cohorts reached at ages 12–29.
   - The method with the smaller mean absolute increment error is used.
   - If that error is not below 0.01 children per woman, the cohort deliverable is marked incomplete.
3. **Projection.** Cumulative(c, Y) = observed cumulative to 2024 + Σ_{t=2025..Y} VV̂(t, t − c), for Y ≤ 2040, using the selected TFR method, the selected shape method and the chosen transformation. It is verified that annual contributions sum to the cumulative totals.
4. **Pseudo-cohort backtests.**
   - For each origin T = 1952…2008, the full pipeline is re-estimated on data ≤ T. Cohorts aged 12–29 (age reached in T) are projected to T + h, h = 1…16, and compared with observed cumulative fertility.
   - Errors are reported by age at origin and horizon (Gen Z in 2024 = ages 12–29; in 2040, horizon 16).
   - Uncertainty: q = log(observed increment / projected increment). σ(a₀, h) = root-mean-square of q over all origins, pooled over ages a₀ − 1 … a₀ + 1. Log-normal 80% and 95% intervals on the increment are added to the observed cumulative.
   - Pseudo-real-time coverage of these intervals is reported as in section 7.
   - Pipelines evaluated: selected TFR × selected shape (primary); `naive` × `S0_fixed` (baseline); selected TFR × each other shape method (sensitivity).
5. **Endpoint interpretation.** For each Gen Z cohort, the share of completed fertility (CCF) that reference cohorts 1965–1974 had reached by the end of the year in which they reached age 2040 − c, cumulated from VV. Labels:
   - ≥ 0.95 in every reference cohort: "nearly complete by historical standards";
   - 0.75–0.95: "substantial but incomplete";
   - < 0.75: "partial".

   Later childbearing in recent cohorts makes these shares upper bounds on completeness. The report must not equate fertility by 2040 with completed fertility, or a cohort average with an individual's family size.

## 11. Census scenarios and births (secondary 3)

1. **Inputs.**
   - NP2023 female population on July 1 by single age 12–55, 2025–2040, scenarios `mid`, `hi`, `low` and `zero`. The four differ only in immigration; all share one fertility assumption, which is not used.
   - Exposure for calendar year t is the July 1 population of year t (mid-year approximation). Age 55 is applied to the HFD `55+` rate, and age 12 to `12-`.
2. **Exposure-alignment test.** HFD ASFR(Y) × vintage 2025 female population(Y) must reproduce HFD births(Y) within 1% for each Y in 2021–2024. Otherwise no birth counts are published.
3. **Rebasing to vintage 2025.**
   - Cohort-ratio method: P*(t, x) = NP(t, x) × V2025(2025, 2025 − c) / NP(2025, 2025 − c) for cohort c = t − x. Cohorts born after 2025 use the age-0 ratio.
   - Age-ratio alternative: the ratio by age in 2025, held constant.
   - **Evaluated before use:** each method is applied at 2022 with V2025(2022) and predicts V2025 female population for 2023, 2024 and 2025 (ages 12–55). This is compared with unrebased NP2023 by mean absolute percentage error.
   - A method is valid only if it beats the unrebased series at every one of the three horizons. The cohort method is preferred if both are valid.
   - If neither is valid, the population projections stay as external comparisons and no birth counts are published.
4. **Births.** B(t, s) = Σ_x ASFR_published(t, x) × P*_s(t, x), calendar years.
   - Census birth years run July to June. They are compared with our births averaged over the two calendar years each spans: Census year t ≈ ½ B(t−1) + ½ B(t).
5. **Uncertainty is kept separate.**
   - Fertility uncertainty: births at the TFR interval bounds, population fixed at `mid`.
   - Population uncertainty: the scenario range at the point fertility forecast. This is not a probability interval.
6. **Census fertility assumption.** Compared with our TFR forecast and intervals, and labelled "assumption, not observation or validation".

## 12. Robustness (all pre-specified)

| Id | Analysis |
|---|---|
| R1 | Training from 1977 (expanding): backtest (origins 1996+) and 2040 forecast for every method |
| R2 | Rolling 30-year training windows: backtest and 2040 forecast |
| R3 | Error metrics by era E1/E2/E3, and selection rule applied within origins 1977+ |
| R4 | 2040 forecasts of all nine methods |
| R5 | Stability over origins of AR/ARI orders, ETS parameters and shape-model drift |
| R6 | 2040 forecast from each origin 2015–2024 with the selected method |
| R7 | Long-horizon error growth: RMSE by horizon 1–16 and the fitted exponent of RMSE_h ∝ h^γ |
| R8 | Pandemic: forecasts from origin 2019 against observed 2020–2024 |
| R9 | Age-profile assumption: Gen Z projections under every shape method |
| R10 | Cohort conventions: end-of-year (VV) against exact-age (CCFR) cumulative; T1 against T2 |
| R11 | The secondary 2025-informed forecast against the primary |
| R12 | Births with unrebased NP2023 against rebased; scenario range |
| R13 | Interval calibration from origins 1977+ only |

Unstable results are reported. No method, window or scenario is chosen because of its 2040 value.

## 13. Verification

A separate script (`audit/verify_m11_forecast.py`) recomputes core results with its own parsing and code.
- **Independent recomputation:**
  - HFD TFR aggregation from the raw text;
  - the `naive`, `mean10`, `drift10`, `drift10_damped` and `converge30` backtests;
  - all point metrics and relative MAE from raw data;
  - the selection decision from the locked rule;
  - interval coverage and widths from stored intervals and raw data;
  - ASFR/TFR sums;
  - cohort accumulation from raw VV and the published projected contributions;
  - births from raw Census files;
  - the 2025 reconstruction from public-use tabulations and raw population estimates.
- **Deterministic reproducibility:** the pipeline is rerun and its outputs are hashed.
- **Model checks:** for fitted models (ETS, AR), forecasts are recomputed from stored parameters with separate recursions, and the parameters are checked to be local minima.
- **Leakage:** a "poisoned future" test — overwriting years after the origin must not change any forecast.
- **Reconciliation:** numbers quoted in the chapter are checked against the tables, and the frozen M09/M10 manifests and M01–M08 hashes are checked.
- **Unit tests** use synthetic data and cover: data gaps, leakage, invalid ages, negative rates, incoherent totals, missing exposures and unsupported model settings.

## 14. Reporting rules

- Every figure separates observed from projected values (solid against dashed or open markers) and states its units, source, scenario and uncertainty type.
- Each interval is labelled with what kind it is: calibrated prediction interval, model-dependent projection, or scenario range.
- Null, negative and unstable results are reported in the chapter.
- The chapter answers A, B and C separately. C is answered as in section 1.
- M11 is not frozen by this work. Closure requires human review.

## 15. Amendments

Any change to this file after locking is an amendment. Each one is recorded in the lock file with:
- its UTC time;
- the previous hash;
- the reason;
- whether any forecast result had been seen.

Analyses added after results are known are labelled exploratory in the chapter and the decision log (`docs/m11_decision_log.md`). They cannot change the primary selection.

## Machine-readable configuration

<!-- config:start -->
```json
{
  "data": {"first_year": 1933, "last_year": 2024, "ages": [12, 55], "rate_floor": 5e-06},
  "backtest": {"min_train": 20, "first_origin": 1952, "last_origin": 2023, "max_horizon": 16,
               "primary_horizons": [5, 10, 15], "eras": {"E1": [1952, 1976], "E2": [1977, 1999], "E3": [2000, 2023]},
               "selection_split": 1977, "bootstrap_reps": 2000, "seed": 20261120},
  "forecast": {"origin": 2024, "first_year": 2025, "last_year": 2040, "plausible_range": [0.8, 4.5]},
  "methods": ["naive", "mean10", "drift10", "drift10_damped", "converge30", "ses", "holt_damped", "ar_level", "ari"],
  "parameters": {"naive": 0, "mean10": 0, "drift10": 1, "drift10_damped": 1, "converge30": 1, "ses": 1,
                 "ari": 2, "ar_level": 3, "holt_damped": 3},
  "method_settings": {"mean_years": 10, "drift_years": 10, "damped_drift_phi": 0.90, "converge_mean_years": 30,
                      "converge_horizon": 20, "ar_orders": [1, 2, 3], "ari_orders": [0, 1, 2, 3]},
  "ets": {"alpha_bounds": [0.0001, 0.9999], "beta_star_bounds": [0.0001, 1.0], "phi_bounds": [0.80, 0.98],
          "alpha_grid": [0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99],
          "beta_star_grid": [0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0],
          "phi_grid": [0.80, 0.84, 0.88, 0.92, 0.96, 0.98]},
  "selection": {"max_ratio": 0.90, "bootstrap_upper": 0.90, "simplicity_margin": 0.02},
  "intervals": {"levels": [0.80, 0.95], "min_calibration_errors": 10, "coverage_flag": [0.65, 0.95],
                "sensitivity_start": 1977},
  "shape": {"window": 30, "min_window": 20, "methods": ["S0_fixed", "S1_shape_drift", "S2_shape_damped",
            "S3_direct_ets", "S4_lee_carter"], "smooth_ages": [15, 45], "smooth_reference": [1995, 2024]},
  "cohort": {"gen_z": [1995, 2012], "ages_at_origin": [12, 29], "last_origin": 2008,
             "transform_ratio_years": 5, "transform_validation_first_year": 1938,
             "transform_max_error": 0.01, "sigma_age_pool": 1,
             "reference_cohorts": [1965, 1974], "labels": {"nearly_complete": 0.95, "partial_below": 0.75}},
  "reconstruction_2025": {"ratio_backtest_years": [2021, 2024], "band_multiplier": 2},
  "census": {"scenarios": ["mid", "hi", "low", "zero"], "rebase_test_base": 2022, "rebase_test_years": [2023, 2024, 2025],
             "rebase_year": 2025, "alignment_years": [2021, 2024], "alignment_tolerance": 0.01}
}
```
<!-- config:end -->
