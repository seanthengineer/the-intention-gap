# M10: Rental Cost Burden and Age-Specific Fertility in U.S. States, 2014–2024

This chapter asks whether, within U.S. states, years of higher rental cost burden are associated with lower birth rates among women aged 20–24 and 25–29, after accounting for each state's typical level and each year's national pattern. It is an observational, ecological analysis of state-year aggregates. It is not a study of individuals, not a causal design, and not a panel that follows a Gen Z birth cohort. **Status: FROZEN on 2026-11-20 with final scientific approval** after independent source review (section 10). This is a local backend record and has not been published. The frozen files are listed with their SHA-256 hashes in [m10_freeze.sha256](m10_freeze.sha256).

**Bottom line.**
- **Ages 20–24 (primary):** each 10-percentage-point higher share of renters paying 30% or more of income on rent is associated with 2.77 fewer births per 1,000 women (95% CI −5.81 to 0.26; p = 0.073; wild bootstrap p = 0.086). The direction is negative, but the interval includes zero and the estimate is not stable across the pre-specified robustness checks.
- **Ages 25–29:** no association (−0.06; 95% CI −2.91 to 2.80).
- **Gen Z-relevant period:** for ages 20–24 in 2021–2024 alone, the estimate is −0.10 (95% CI −2.07 to 1.87), with too little power to detect associations smaller than about 2.8.
- **What this does not show:** these data do not show that housing affordability explains the decline in fertility.

## 1. Question, estimand and protocol timing
- **Question.** Within U.S. states, how is variation in rental housing cost burden associated with age-specific fertility rates, after accounting for state and calendar-year differences?
- **Outcomes.** Births per 1,000 women aged 20–24 (primary) and 25–29 (secondary), by the mother's state of residence.
- **Exposure.** ACS B25070: the percent of renter households, among those with burden computed, whose gross rent is at least 30% of household income.
- **Estimand.** 10β: the difference in births per 1,000 women associated with a 10-percentage-point higher burden, comparing the same state across years relative to the common year pattern.
- **Primary model (C).** State and year fixed effects; standard errors clustered by state, 51 clusters (t with 50 degrees of freedom).
- **Protocol timing.**
  - Estimating equations, models, controls, inference, robustness list and interpretation rules are in [m10_analysis_protocol.md](m10_analysis_protocol.md). The protocol was locked (SHA-256 recorded in `docs/m10_protocol_lock.json`) **before any regression was fitted or any housing–fertility association was computed**.
  - One amendment, recorded before any fit, corrected a column name.
  - `analysis/m10_models.py` refuses to run if the protocol no longer matches its lock.
  - The protocol is **not externally preregistered**; the lock shows only that the file is unchanged since locking.
  - Data-feasibility summaries (coverage, exposure variation) were known when the protocol was written.

## 2. Data and panel
| Source | Use | Provenance |
|---|---|---|
| Census ACS 1-year **B25070**, 2014–2019 and 2021–2024 (no standard 2020 release) | Exposure (30%+ and 50%+ burden) | `data/raw/acs_b25070/` and its provenance file; validation in `docs/m10_data_feasibility.md` |
| ACS 1-year **B25072** (age of householder × rent burden) | Secondary, age-matched exposure | `data/raw/acs_m10_covariates/`; meets every pre-set criterion (section 7 of the protocol) |
| ACS 1-year **B23025** (unemployment, population 16+) and **B19013** (median household income) | Control (model D); sensitivity control | `data/raw/acs_m10_covariates/` |
| CDC WONDER Natality: original export (2014–2015) and 2016–2024 expanded export | Births, female population and rates | `data/raw/cdc_natality/` and its provenance file |
| NCHS *Births: Final Data* for 2019, 2023 and **2024** (NVSR 70-2, 74-1, 75-2) | Independent benchmark | `data/raw/nchs_nvsr/` and its provenance file |

**2024 official benchmark.** NVSR 75-2 (June 9, 2026), Table 6, "Birth rates, by age of mother: United States, each state and territory, 2024", by place of residence.
- **State rates:** all 102 rates (51 jurisdictions × ages 20–24 and 25–29) agree with the CDC WONDER values within the published one-decimal precision. The largest difference is 0.05, a rounding tie, and the mean differences are −0.005 (20–24) and +0.003 (25–29).
- **No discrepancies to explain:** none arose from rounding, population-estimate vintage or definitions.
- **National rates:** the 2024 rates also agree (55.8 against 55.77 recomputed; 89.5 against 89.51).
- **Records:** every state-age difference for 2019, 2023 and 2024 is listed in `data/processed/m10/nvsr_state_rate_benchmark.csv` (306 rows, all within precision).

**B25072, the younger-renter measure.**
- **Labels:** identical across all ten releases (apart from punctuation).
- **Integrity:**
  - age-band categories sum to their totals;
  - no Census codes appear;
  - 510 of 510 state-years are present for both age bands;
  - no denominator is zero.
- **Construction:** 30%+ is (30.0–34.9 + 35.0+) / (band total − not computed). This table has no 50% category.
- **Reliability:**
  - householders 15–24: median approximate SE 2.3 points; 10.4% of state-years above 5 points; maximum 11.3;
  - householders 25–34: median 1.6 points.
- **Relation to the general measure.**
  - Correlation with B25070 is 0.73 (15–24) and 0.87 (25–34) in levels, but only 0.42 and 0.66 after removing state and year means.
  - Householders 15–24 are more often burdened (by 11.3 points on average).
  - Householders aged 15–24 are **not** the mothers aged 20–24 whose births are counted.

**Analysis frame.**
- **Rows:** 1,020 state-year-age rows: 51 jurisdictions × 10 years × 2 age groups, all with rates and covariates.
- **Per-age-group models:** 510 state-years and 51 clusters.
- **Lag models:** 408 state-years. 2014 and 2021 are dropped because 2013 and 2020 have no ACS value; lags are matched by calendar year, never to the previous row.
- **Stacked models:** 1,020 rows but only **510 distinct housing measurements**, because both age groups share a state-year's exposure. Clustering by state accounts for this and for repeated observations.

## 3. Descriptive results
Figures: [trends](../assets/figures/m10_trends.png) and [between- vs within-state](../assets/figures/m10_between_within.png). Tables: `data/public/m10/m10_desc_*.csv`.

- **Fertility fell steadily.**
  - National births per 1,000 women aged 20–24: 79.0 (2014), 66.6 (2019), 61.5 (2021), 55.8 (2024).
  - Aged 25–29: 105.8, 93.7, 93.0, 89.5.
  - Mean state rates fell by 15.2 per 1,000 (20–24) and 9.0 (25–29) between 2014–2019 and 2021–2024.
- **Rent burden did not rise steadily.**
  - The state median of renters paying 30%+ fell from 50.2% (2014) to 46.5% (2019), then was 49.0% (2021) and 49.4% (2024).
  - The mean across state-years was 1.4 points higher in 2021–2024 than in 2014–2019.
  - Householders 15–24: median 61.7% (2014), 57.5% (2019), 61.0% (2021), 59.5% (2024).
- **Most variation is between states.**

  | Variable | Share of variance within states | Remaining SD after state and year means |
  |---|---:|---:|
  | 30%+ burden | 17% | 1.38 points |
  | Rate, ages 20–24 | 18% | 2.28 |
  | Rate, ages 25–29 | 11% | 3.44 |

- **Cross-sectional and within-state associations differ** (Pearson r, descriptive, no inference):
  - **Ages 20–24:** r = −0.22 across state averages, −0.24 within states, and −0.17 after removing state and year means.
  - **Ages 25–29:** r = −0.59 across state averages, −0.07 within states, and −0.00 after removing both.
  - The strong cross-sectional pattern for 25–29 is a difference between states, not a within-state relationship.
- **National trends are not evidence of an effect.** Fertility fell while burden first fell and then rose, so the national series give no support for the idea that affordability explains the decline.

## 4. Regression results
Births per 1,000 women per 10-percentage-point higher 30%+ burden. Standard errors are clustered by state (51 clusters); 95% intervals use t with 50 degrees of freedom. Table: `data/public/m10/m10_models.csv`; figure: [coefficients](../assets/figures/m10_coefficients.png).

| Model | Ages 20–24: estimate (95% CI), p | Ages 25–29: estimate (95% CI), p | n |
|---|---|---|---:|
| A pooled (no fixed effects) | −10.81 (−20.20, −1.42), 0.025 | −25.71 (−35.16, −16.27), <0.001 | 510 |
| B state fixed effects | −11.90 (−19.49, −4.30), 0.003 | −2.77 (−7.50, 1.97), 0.25 | 510 |
| **C state + year fixed effects (primary)** | **−2.77 (−5.81, 0.26), 0.073** | **−0.06 (−2.91, 2.80), 0.97** | 510 |
| D C + unemployment | −2.74 (−5.79, 0.31), 0.077 | 0.99 (−1.76, 3.74), 0.47 | 510 |
| E one-year lag (exact calendar year) | −3.73 (−7.52, 0.05), 0.053 | 1.37 (−1.91, 4.65), 0.41 | 408 |

**Pre-specified tests.**

| Test | Role | Estimate (95% CI) | p | Wild cluster bootstrap p | Holm p |
|---|---|---|---:|---:|---:|
| β<sub>20–24</sub> = 0 (C) | Primary | −2.77 (−5.81, 0.26) | 0.073 | 0.086 | — |
| β<sub>25–29</sub> = 0 (C) | Secondary | −0.06 (−2.91, 2.80) | 0.969 | 0.967 | 0.969 |
| β<sub>20–24</sub> − β<sub>25–29</sub> = 0 (stacked) | Secondary | −2.72 (−6.74, 1.30) | 0.180 | 0.184 | 0.361 |

**Interpretation.**
- **Why year effects matter.** Models A and B are large and negative mainly because fertility fell nationwide over the decade while state burden levels differ. Once year effects absorb the common national pattern (model C), the ages 20–24 association shrinks to −2.77 and is not statistically significant at 0.05. The 25–29 association is essentially zero.
- **Scale.** A 10-point change is large relative to the variation that identifies the model: the remaining SD of burden is 1.38 points. For a 1-SD within-state, within-year difference, the primary estimate is −0.38 births per 1,000, about 0.5% of the mean rate of 69 for ages 20–24.
- **Controls.** Adding unemployment (D) barely changes ages 20–24. The variance inflation factors of the within-transformed exposure, unemployment and log income are 1.02–1.05.
- **Lags.** The lagged exposure (E) gives a similar negative estimate for 20–24, with its interval just reaching zero.

## 5. Gen Z-relevant period: ages 20–24, 2021–2024
- **Estimate:** −0.10 births per 1,000 per 10 points (95% CI −2.07 to 1.87; p = 0.92), from 204 state-years in 51 clusters.
- **Power:** with an SE of 0.98, the smallest association detectable with 80% power at α = 0.05 is about 2.8 per 10 points, roughly the size of the full-period primary estimate.
- **Reading:** this short window gives no evidence of an association, but cannot rule out one as large as the full-period estimate.
- **Who this group is:** in these years, women aged 20–24 were born about 1997–2004, mostly Gen Z. The analysis still describes an age group in a period, not a cohort followed over time.

## 6. Robustness and sensitivity (exploratory)
Tables: `data/public/m10/m10_robustness.csv` and `m10_loso.csv`. All are exploratory. Benjamini–Hochberg q-values are given for orientation only; none is below 0.20.

| Analysis | Ages 20–24 (95% CI) | Ages 25–29 (95% CI) |
|---|---|---|
| 2014–2019 only (306) | −1.21 (−4.12, 1.70) | −1.88 (−4.63, 0.86) |
| 2021–2024 only (204) | −0.10 (−2.07, 1.87) | −2.15 (−5.01, 0.71) |
| Weighted by the age group's female population | −6.61 (−11.63, −1.59) | 2.18 (−1.64, 5.99) |
| Excluding DC (50 clusters) | −2.95 (−6.04, 0.13) | 0.01 (−2.95, 2.98) |
| Contemporaneous + lag: lag coefficient | −2.97 (−6.04, 0.10) | 1.45 (−1.64, 4.54) |
| Contemporaneous + lag: contemporaneous coefficient | −2.39 (−4.79, 0.01) | −0.25 (−4.00, 3.50) |
| Severe burden 50%+ | −1.59 (−5.45, 2.26) | −0.16 (−3.17, 2.85) |
| B25072 age-matched householders 30%+ | 0.02 (−0.94, 0.98) | 0.59 (−1.38, 2.55) |
| State-specific linear trends | −0.55 (−2.02, 0.93) | −1.11 (−3.01, 0.80) |
| Unemployment + log median household income | −2.81 (−5.76, 0.14) | 0.95 (−1.82, 3.72) |
| Log rate (approx. % per 10 points) | −1.84% (−5.71, 2.02) | 1.06% (−2.31, 4.43) |
| Leave-one-state-out range | −3.44 (without Alaska) to −1.79 (without Nevada); 2 of 51 have p < 0.05 | −0.76 (without Vermont) to 0.41 (without Utah) |

**Stability.** The protocol defines a stable result as a consistent sign across C, D, E and robustness items 2–10, with estimates inside the primary 95% interval. Ages 20–24 fail this test:
- **Within the rule:** the sign is negative in most specifications.
- **Outside the rule:**
  - the population-weighted estimate (−6.61) lies outside the primary interval;
  - the age-matched B25072 exposure gives essentially zero.
- **Also weaker:**
  - both single-period estimates are much smaller than the full-period estimate;
  - adding state-specific trends reduces it to −0.55.

The full-period association therefore relies heavily on changes across the 2020 gap: states whose burden rose more between 2014–2019 and 2021–2024 tended to have larger declines in fertility at ages 20–24. That comparison coincides with the pandemic and with changes in population-estimate methods, so it is especially vulnerable to confounding. Weighting by population estimates a different quantity, an average dominated by large states, and suggests the association, if any, is concentrated there. **Ages 25–29 show no association** in any specification, with signs that switch.

**Measurement error in the housing measure.** The estimated ACS sampling noise is about 47% of the remaining burden variance, a figure that depends on assumptions (see `docs/m10_data_feasibility.md`). Three checks (`m10_noise_stability.csv`, `m10_simex.csv`):
1. **Added noise.** Re-estimating model C after adding one more draw of sampling noise of the estimated size (1,000 draws) moves the 20–24 estimate toward zero: mean −1.88, middle 95% of draws −2.68 to −1.11, every draw negative. This is the pattern expected if the sampling error behaves like classical error, but it does not show that the true association is larger.
2. **SIMEX (exploratory, not a result).** Extrapolating that trend back to zero measurement error gives −4.04 for ages 20–24 and −0.47 for 25–29. This needs four assumptions that have not been verified:
   - the error is classical (independent of the true value and of other variables);
   - it is normally distributed;
   - the approximate ACS SEs are the true error SDs;
   - a quadratic extrapolation is valid.
3. **Noisier younger-renter measure.** The age-matched B25072 measure is noisier (median SE 2.3 points for ages 15–24), which may contribute to its null result.

Measurement error adds uncertainty, and it may push estimates toward zero. No corrected estimate is claimed.

**Diagnostics** (`m10_model_summary.json`).
- **Serial correlation:** strong in the residuals. The Wooldridge test's AR coefficient is −0.16 (20–24) and −0.10 (25–29) against −0.5 if there were none; p < 0.001. Standard errors clustered by state, which allow any within-state correlation, are therefore necessary.
- **Heteroskedasticity:** no evidence (Breusch–Pagan p = 0.80 and 0.64).
- **Remaining cross-sectional dependence:** no evidence after year effects (Pesaran CD −1.38, p = 0.17; −1.59, p = 0.11).
- **Leverage:** maximum 0.16. No single state drives the 20–24 sign.
- **Inference:** 51 clusters support CR1 inference with t(50), and the wild cluster bootstrap agrees closely.

## 7. Scientific interpretation and limitations
1. **Ecological inference.** State-level associations do not describe individual women. No data link the renter households measured by ACS to the women giving birth.
2. **Changing composition.** Each age group contains different birth cohorts each year. Migration, and changes in education, partnership and ethnic composition, alter who is counted.
3. **Confounding.** Partnership, education, earnings and local labor markets can affect both housing costs and fertility. Only unemployment (and income, as a sensitivity) is adjusted, deliberately. Mediators are not adjusted, and confounders that vary over time remain.
4. **Reverse causality.** Changes in fertility and household formation can change rental demand and burden.
5. **Pandemic and methods.** 2020 is missing from ACS. 2021–2024 follows the pandemic, and population controls and estimates changed (Blended Base). The full-period association relies on this period break.
6. **Measurement.** ACS burden carries substantial sampling error (section 6). The rates use July population estimates that are themselves estimates.
7. **Postponement or forgone births.** Lower birth rates at 20–24 can reflect later childbearing, not fewer births over a lifetime. The secondary 25–29 null does not settle this, and completed fertility is not observed.
8. **Short post-2020 window.** Four years, with limited power (section 5).
9. **Not a Gen Z cohort study.** Age, period and cohort cannot be separated with these data.
10. **No link to M09.** M10 does not explain the individual-level gap between wanting and intending children found in the NSFG (M09). Those are different data, units and questions.

**Conclusion.**
- **Ages 20–24:** the within-state association is small, negative and statistically inconclusive, and not robust.
- **Ages 25–29:** none.
- **Overall:** nothing here supports a causal claim that rental cost burden reduces fertility, and the evidence also cannot rule out modest associations.

## 8. Verification
`audit/verify_m10.py` labels each check by kind:

| Kind | What it covers |
|---|---|
| Independent recomputation (60 checks) | Rebuilt from raw API responses and export text with separate code: 30%+ burden, both B25072 age bands, unemployment; births, denominators and rates for the combined natality series, and rate recalculation (1,122 rows); calendar-year lag alignment; the 2024 NVSR Table 6 comparison (separate parser); the between-state SD and the pre/post means; models B, C, D and E for both age groups (coefficients and CR1 SEs) via alternating-projection demeaning; the stacked contrast and its SE via combined cluster scores; four robustness variants (both periods, excluding DC, population-weighted); leave-one-state-out minimum and maximum |
| Deterministic rerun (2 checks) | Wild cluster bootstrap p-values from the pipeline's own function |
| Reconciliation (17 checks) | Provenance hashes for every raw file; protocol lock; absence of the API key; the coefficient figure (all 28 plotted estimates and intervals equal the stored tables, and each row names its housing measure); the primary and secondary results quoted in this chapter |

**Not covered by the verifier:** SIMEX and added-noise stability, the diagnostic statistics, the log-outcome, trend, severe-burden, B25072 and lag-plus-contemporaneous variants, figure rendering, and the B23025/B19013 labels. These rest on unit tests (`tests/test_m10_models.py`) and the shared estimator. That estimator is itself independently verified for the models above.

## 9. Reproduction
```
python -m analysis.acs_housing            # B25070 (add --fetch to download; needs CENSUS_API_KEY)
python -m analysis.m10_covariates         # B25072, B23025, B19013 (add --fetch to download)
python -m analysis.cdc_natality           # natality series, reconciliation, NVSR 2019/2023/2024
python -m analysis.m10_panel              # panel, lags, coverage
python -m analysis.m10_models             # protocol check, models, robustness (about 20 s)
python -m analysis.m10_descriptive        # descriptive tables and figures
python audit/verify_m10.py                # verification
python -m unittest                        # full test suite
python audit/verify_freeze.py             # M09 and M10 freeze manifests
```
The protocol is `docs/m10_analysis_protocol.md` (lock: `docs/m10_protocol_lock.json`). Aggregate results are in `data/public/m10/`, and figures are `assets/figures/m10_*.png`.

## 10. Freeze record
- **Status:** FROZEN, final scientific approval, 2026-11-20. Independent source review approved the methodology, implementation and conclusions.
- **Last change before freezing:** the coefficient figure's axis label. It now reads "change in births per 1,000 women per 10-percentage-point increase in the housing-burden measure named in brackets", and every row names its measure (30%+ or 50%+ from B25070, the age-matched 30%+ from B25072, or the year t−1 lag). Only the figure was regenerated, and every coefficient and interval is unchanged: all 13 result tables are byte-identical.
- **Manifest:** [m10_freeze.sha256](m10_freeze.sha256) lists the SHA-256 of the frozen source, protocol and lock, tests, documentation, public results and figures. It excludes raw datasets, processed records, provenance files under `data/raw/`, credentials, environments, the README and the running audit log. `python audit/verify_freeze.py` (or `sha256sum -c docs/m10_freeze.sha256`) checks it, and `tests/test_freeze_integrity.py` checks it in the test suite.

**Accepted conclusions.**
1. **Ages 20–24:** a weak negative association (−2.77 births per 1,000 per 10 points; 95% CI −5.81 to 0.26). It is statistically inconclusive and unstable across robustness checks.
2. **Ages 25–29:** no detectable association (−0.06; 95% CI −2.91 to 2.80).
3. **Gen Z-relevant period, 2021–2024 (ages 20–24):** no detectable association (−0.10; 95% CI −2.07 to 1.87). Power is limited.
4. **No causal interpretation.**
5. **Scope:** a state-level analysis of age groups, not a longitudinal Gen Z cohort study.

**Methodological limitations:** see section 7. In short:
- ecological inference;
- changing cohort composition;
- confounding that varies over time, and reverse causality;
- the pandemic, the 2020 gap and changed population-estimate methods;
- ACS sampling error;
- postponement versus forgone births;
- a short post-2020 window.

**Outstanding nonblocking warnings.**
- The protocol is locked internally, not externally preregistered.
- Ruff is not configured.
- These are covered by unit tests rather than independent recomputation:
  - SIMEX and added-noise stability;
  - the diagnostic statistics;
  - the log-outcome, trend, severe-burden, B25072 and lag-plus-contemporaneous variants.
- The B19013 labels differ by release year (dollar year in the label), which is expected.

**Changes after freezing.** Editing any file in the manifest requires a new, recorded decision and a new manifest.

