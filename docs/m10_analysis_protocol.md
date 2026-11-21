# M10 Analysis Protocol: Rental Cost Burden and Age-Specific Fertility

**Status: locked before any regression was fitted.** The SHA-256 of this file and the UTC time of locking are recorded in `docs/m10_protocol_lock.json`. `analysis/m10_models.py` refuses to fit models if this file no longer matches the recorded hash. Any change after locking must be added as a dated amendment in section 12, with a new lock. The protocol was locked in the project's own files. It is **not externally preregistered**, and the lock shows only that the file is unchanged since that time.

**What was known when this was written.** Data-feasibility summaries from `docs/m10_data_feasibility.md` had been seen:
- coverage, and the ranges of the exposure and the rates;
- within-state and two-way-residual standard deviations of the exposure;
- national fertility rates by year.

Metadata for ACS tables B25072, B23025 and B19013 (labels only) had also been checked. **No association between housing burden and fertility had been computed** in any form, whether correlation, plot or regression.

## 1. Question and design
**Primary question.** Within U.S. states, how is variation in rental housing cost burden associated with age-specific fertility rates, after accounting for state and calendar-year differences?

This is an **observational, ecological state-year panel**. It describes associations between state-level aggregates. It is not a study of individuals, and not a Gen Z birth-cohort study: each row is an age group observed in a calendar year, so the women aged 20–24 in 2014 (born about 1989–1994) and in 2024 (born about 1999–2004) are different cohorts. Fixed effects and lags do not establish causality.

## 2. Analysis populations
- **Panel:** `data/processed/m10/m10_panel_state_year_age.csv`, covering 50 states and DC (51 jurisdictions) for 2014–2019 and 2021–2024. 2020 is excluded because there is no standard ACS 1-year release.
- **Per age group:** 510 state-years (51 × 10), all with rates.
- **Lag model:** 408 state-years. 2014 and 2021 are dropped because their previous calendar year (2013 or 2020) has no ACS value.
- **Stacked model:** 1,020 rows: 510 state-years × 2 age groups, sharing one housing value per state-year.

## 3. Variables
| Role | Variable | Definition and units |
|---|---|---|
| Primary outcome | `outcome_rate`, age group 20–24 | Births per 1,000 women aged 20–24, by mother's state of residence (CDC WONDER; 2014–2015 original export, 2016–2024 expanded export) |
| Secondary outcome | `outcome_rate`, age group 25–29 | Births per 1,000 women aged 25–29 |
| Primary exposure | B25070 30%+ burden | Percent of renter households with gross rent ≥ 30% of income, among households with burden computed: (007 + 008 + 009 + 010) / (001 − 011) × 100 |
| Alternative exposure | B25070 50%+ | 010 / (001 − 011) × 100 |
| Secondary exposure (conditional, section 7) | B25072 age-specific 30%+ | Percent of renter householders aged 15–24 (for the 20–24 outcome) or 25–34 (for the 25–29 outcome) paying ≥ 30%, among those with burden computed: (30.0–34.9 + 35.0+) / (total for the age band − not computed) × 100 |
| Control (model D) | Unemployment rate | ACS B23025: unemployed / civilian labor force × 100 (population 16+) |
| Sensitivity control | log median household income | ACS B19013, in the release year's inflation-adjusted dollars; year effects absorb national price changes |

## 4. Estimand and estimating equations
For each age group *a*, state *s* and year *t*:

Y<sub>ast</sub> = α<sub>as</sub> + λ<sub>at</sub> + β<sub>a</sub>·B<sub>st</sub> + X<sub>st</sub>′γ<sub>a</sub> + ε<sub>ast</sub>

**Estimand.** 10·β<sub>a</sub>: the difference in births per 1,000 women aged *a* associated with a 10-percentage-point higher 30%+ rental burden. It compares the same state across years, relative to the common year pattern. Every coefficient is reported as births per 1,000 women per 10 points.

| Model | Specification |
|---|---|
| A | Pooled OLS: Y on B (descriptive; between- and within-state variation combined) |
| B | State fixed effects |
| **C (primary)** | **State and year fixed effects** |
| D | C plus the unemployment rate |
| E | State and year fixed effects with B<sub>s,t−1</sub> matched to the actual previous calendar year (not the previous row) |
| F | Alternatives in section 8 |

**Fixed in advance.** Model C is the primary specification for both age groups. The preferred model is not chosen from results or p-values.

**Stacked model.** All 1,020 rows, with age-specific state effects, year effects and slopes (α<sub>as</sub>, λ<sub>at</sub>, β<sub>a</sub>) and errors clustered by state. It estimates β<sub>20–24</sub> − β<sub>25–29</sub>. The two rows of a state-year share one housing value, so the stacked model has 510 exposure measurements, not 1,020.

## 5. Inference
- **Standard errors:** cluster-robust by state (CR1: G/(G−1)·(N−1)/(N−K)), with **51 clusters** in each model and t on G − 1 = 50 degrees of freedom. 95% confidence intervals.
- **Bootstrap check:** wild cluster bootstrap p-values (restricted, Rademacher weights, 9,999 replicates, seed 2026) for the primary and secondary tests.
- **Primary test (H1):** β<sub>20–24</sub> = 0 in model C, two-sided, α = 0.05.
- **Secondary family (Holm-adjusted together):** β<sub>25–29</sub> = 0 in model C; and β<sub>20–24</sub> − β<sub>25–29</sub> = 0 in the stacked model.
- **Exploratory:** every other model and robustness estimate. These are reported with unadjusted p-values, plus Benjamini–Hochberg q-values across the exploratory family for orientation only.

## 6. Controls
- **Included in model D:** the state unemployment rate (ACS B23025). Labour-market conditions plausibly affect both rental burden (through incomes) and fertility timing, and the measure comes from the same survey and year as the exposure.
- **Sensitivity only:** log median household income. Income is the denominator of the burden ratio, so controlling for it partly turns the exposure into a rent-level measure (mechanical coupling, and a risk of overadjustment).
- **Excluded:** education, marriage and cohabitation, and racial and ethnic composition. These are plausible mediators or compositional consequences of housing conditions, and adjusting for them could remove part of the association being estimated.
- **Collinearity check:** collinearity of each control with the exposure is reported as the variance inflation factor (VIF) of the within-transformed regressors.

## 7. Conditions for using B25072
B25072 is used as the secondary exposure only if the full ten-year series passes **all** of these:
- labels identical across the ten releases;
- age-band categories sum to the age-band total;
- no Census annotation or missing-value codes;
- 510 of 510 state-years present for both age bands;
- every denominator (age-band total minus not computed) greater than zero.

Reliability (the distribution of approximate SEs) and within-state signal are reported descriptively, not used as pass criteria. If B25072 fails, the reason is documented and only B25070 is used. Renter householders aged 15–24 are **not** the same population as mothers aged 20–24.

## 8. Robustness and sensitivity analyses (all exploratory)
1. Ages 20–24 and 25–29 analysed separately (sections 4 and 5).
2. Periods 2014–2019 and 2021–2024 separately. The **2021–2024 analysis for ages 20–24** is the Gen Z-relevant period: only 4 years, possibly underpowered, and reported as such.
3. Weighted by the age group's female population. This estimates a population-weighted average of within-state associations, a different estimand from the unweighted state-average primary.
4. DC excluded.
5. Leave-one-state-out (range of 10β), plus each state's influence on β.
6. Lag model E, matched by exact calendar year; also the contemporaneous and lagged exposure together.
7. Alternative exposures: 50%+ burden, and B25072 (if section 7 passes).
8. State-specific linear trends added to model C.
9. Control sets: none (C), unemployment (D), unemployment plus log income (D2).
10. Log outcome (proportional association).
11. ACS measurement uncertainty, in three ways:
    - (i) re-estimate C after adding simulated sampling noise to the exposure (each state-year's approximate SE; 1,000 draws), to show coefficient stability under extra noise;
    - (ii) an exploratory SIMEX extrapolation. It assumes classical, independent, normally distributed errors with the approximate SEs as the true error SDs, and a quadratic extrapolant. It is labelled speculative and not used as a result;
    - (iii) report the assumption-dependent noise share (0.47) only as context.
12. Stacked-model contrast (section 4).

## 9. Diagnostics
- **Exposure variation:** within-state and two-way-residual SD of the exposure.
- **Collinearity:** VIF of the within-transformed regressors.
- **Influence:** leverage and cluster-level influence (change in β when a state is dropped).
- **Heteroskedasticity:** Breusch–Pagan on the within residuals.
- **Serial correlation:** the Wooldridge test, using first differences only between consecutive calendar years.
- **Common shocks:** the Pesaran CD statistic on residuals.

## 10. Interpretation rules
- Report the estimate, 95% CI and p-value for every specification, whatever its significance.
- Use association language. No causal claims.
- **Stability** means a consistent sign across C, D, E and robustness items 2–10, with estimates within the primary 95% CI.
- A null or unstable result is reported as such. M10 does not explain the individual-level desire–intention gap found in M09.

## 11. Gen Z wording
Results describe women aged 20–24 and 25–29 in the calendar years observed. Calling the 2021–2024 age 20–24 analysis "Gen Z-relevant" means only that, in those years, that age group consisted mostly of people born about 1997–2004.

## 12. Amendments
1. 2026-11-20T08:24:49+00:00, before any model was fitted: the variable-table entries for the outcomes named a non-existent column (`rate_2024`). They now name the panel column `outcome_rate` for each age group. No definition changed. Previous lock hash: be9eb3b03fa2ab41.
