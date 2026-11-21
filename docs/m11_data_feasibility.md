# M11: Fertility forecasting to 2040 — data acquisition and feasibility audit

Status: **data acquisition and feasibility only.** No forecasting model was fitted, no forecast was produced, and no forecast error of any method was computed. Prepared 2026-11-20.

**Decision: CONDITIONAL.** All four sources were acquired and verified, and there were no FAIL results. Forecasting is feasible for period TFR and age-specific rates. Cohort trajectories are feasible only as cumulative fertility to the age reached in 2040. The conditions are listed in section 11.

| Source | Checks | PASS | WARN | FAIL | Status |
|---|---|---|---|---|---|
| Human Fertility Database, USA | 16 | 12 | 4 | 0 | **WARN** |
| NCHS final 2025 natality data | 11 | 7 | 4 | 0 | **WARN** |
| Census population estimates (V2024, V2025) | 2 | 2 | 0 | 0 | **PASS** |
| Census 2023 National Population Projections | 8 | 7 | 1 | 0 | **WARN** |

Each check is listed in `data/public/m11/m11_validation_checks.csv`. The independent verification (`audit/verify_m11.py`) is described in section 12.

Gen Z is defined here as the owner's birth cohorts 1995–2012. All rates are births per woman (HFD, Census) or per 1,000 women (NCHS), as labelled.

## 1. Source inventory and provenance

| Directory (`data/raw/`) | Content | Coverage |
|---|---|---|
| `hfd_usa/` | HFD country archive `USA.zip` plus its 51 text files. The files are byte-identical to the archive members. | Period 1933–2024 by single age 12–55+ and birth order 1–5+; cohorts 1878–2011 |
| `hfd_docs/` | HFD Methods Protocol, file formats, USA notes, references, input-data map, country page | Documentation |
| `nchs_2025/` | NCHS Data Brief 571 (final 2025, 21 Oct 2026), VSRR 43 (provisional 2025, 9 Apr 2026), NCHS index pages as evidence of publication status | 2024–2025, 5-year age groups |
| `nchs_natality_puf/` | 2024 and 2025 natality public-use files, with user guides | One record per birth; single year of mother's age |
| `nchs_nvsr/` | Births: Final Data for 2019, 2023 and 2024, saved in M10 and read only | National TFR and rates 2010–2024 |
| `census_popest/` | National estimates by single age and sex: vintage 2024 (2020–2024) and vintage 2025 (2020–2025), with method statements and release notes | July 1 populations |
| `census_np2023/` | 2023 National Population Projections: 25 data files, 10 layouts, method statement | 2022–2100 |

- **Provenance files:** each directory has a `provenance.json` giving the source URL, retrieval date (2026-11-20), size and SHA-256 of every file.
- **HFD archive:** the owner downloaded it (an HFD account is required). A copy is kept beside the extracted files, so the original source is preserved.
- **Public-use natality files:** these are record-level files without personal identifiers. They stay local and are only tabulated into aggregate counts (`data/processed/m11/`).
- **Version control:** all raw files are git-ignored under `data/*`.
- **Not retrieved:** the HFD input-data files (USAbirths, USAmonthly, USAparity) require a login.

## 2. Human Fertility Database (USA)

**Release.** The HFD country page shows a last update of 02.07.2026. Every file header reads "Last modified: 27/06/2026".

**Contents.** All required measures are present:

| Measure | File(s) | Coverage |
|---|---|---|
| Period TFR and TFR by age 40 | `USAtfrRR`, by order `USAtfrRRbo` | 1933–2024 |
| Age-specific rates, single years (Lexis squares) | `USAasfrRR`, `USAasfrRRbo` | 1933–2024, ages 12-, 13–54, 55+ |
| Births and female exposures | `USAbirthsRR`, `USAexposRR` (also TR, VH, VV shapes) | 1933–2024 |
| Cohort rates and cumulative cohort fertility | `USAasfrVH`, `USAccfrVH` | cohorts 1878–2011 (cells inside 1933–2024 only) |
| Completed cohort fertility (CCF, CCF40) | `USAtfrVH` | CCF 1918–1974; CCF40 1918–1984 |
| Tempo-adjusted TFR (Bongaarts–Feeney) | `USAadjtfrRR` | 1934–2023 |
| Parity-specific exposures, period fertility tables, PATFR | `USAexposRRpa`, `USApft`, `USApatfr` | 1963–2024 |
| Cohort fertility tables, parity progression ratios | `USAcft`, `USApprVHbo` | cohorts 1918–1999 / 1918–1974 |

The full per-file inventory is in `m11_hfd_coverage.csv`.

**Missingness.**
- **Period tables:** none of the 92 years × 44 ages is missing (`m11_hfd_period_missing.csv`).
- **Cohort files:** missing cells are structural. They are cohort-age cells outside the 1933–2024 observation window, not gaps.
- **Flags:** no file contains provisional, estimated or revision flags; every value is numeric, ".", or an open age or cohort marker.
- **Estimated or reduced-coverage early years:**
  - 1933–1938 births are HFD estimates (USA notes 16);
  - Alaska and Hawaii enter in 1959–1960;
  - unknown maternal ages are distributed across known ages.

**Calculation conventions confirmed by recomputation.**
- **Rates:** ASFR = births ÷ person-years of exposure, and the TFR is the sum of single-year rates (12- to 55+).
- **Order-specific measures:** they sum to the totals.
- **Lexis shapes:** triangles sum to squares, and each cohort cell (VH) is the two triangles of the same cohort.
- **Mean age at birth:** rates are weighted at age + 0.5.
- **CCFR(x):** fertility accumulated *before* exact age *x* (births at age *x* excluded). This convention matters for the cohort matrix.

**Exposures.** These come from Human Mortality Database population estimates, not directly from Census July 1 counts (section 5).

**Checks.** As first reported: 12 PASS and 4 WARN. After the correction below: 16 PASS and 2 WARN. Two checks on vertical parallelograms (VV) were added.
1. ~~**Cohort cumulative measures:** CCFR differs from the sum of cohort rates by up to 0.0008 in 247 of 3,042 cells. CCF and CCF40 differ by up to 0.00065 in 9 of 124 values. The cause was not identified.~~

   **Correction (2026-11-20, M11 forecasting stage 1):** this was an error in my code, not an HFD discrepancy.
   - HFD exposure files print the open ages as `12` and `55`; birth and rate files print `12-` and `55+`.
   - `hfd.validate()` joined the files on that label, so every open-age cohort cell (182 cells) was silently dropped from the sums.
   - With the join fixed (`hfd.cohort_frame()`), all 3,133 CCFR cells and all 124 CCF/CCF40 values agree with sums of exact rates to within half a unit of the third printed decimal (max 0.0005). The check is now PASS.
   - No HFD value was changed. Of the four warnings, only this one (counted as two checks) was a numerical discrepancy; the other two are coverage and access notes.
2. **Latest year:** HFD ends in 2024. 2025 is not yet included.
3. **Input data:** the HFD input-data files require a login, so HFD's own source notes for recent years were not checked.

**HFD against NCHS.** Births agree exactly with NCHS final counts for every year 2010–2024, to 0.01, because HFD prints two decimals. 2024 births by single age 12–49 equal the NCHS public-use file exactly (`m11_hfd_nchs_births_2024_by_age.csv`). NCHS collapses ages 50–54, and HFD distributes these across single ages with the same total.

## 3. NCHS final 2025 fertility data

**Publication status (verified 2026-11-20 from NCHS pages saved in `nchs_2025/`):**

| Product | Status |
|---|---|
| 2025 natality public-use file (final data) | Released; archive dated 15 Oct 2026; user guide 27 Oct 2026 |
| Data Brief 571, *Births in the United States, 2025* ("highlights from final 2025 birth data") | Released 21 Oct 2026 |
| VSRR 43, *Births: Provisional Data for 2025* | Released 9 Apr 2026 |
| *Births: Final Data for 2025* (NVSR) | **Not published.** NCHS lists *Births: Final Data for 2024* (9 Jun 2026) as the latest |
| Official 2025 TFR | **Not published** (DB571 and VSRR 43 give GFR and 5-year rates only) |

**Definitions.**
- Births to U.S. residents (foreign residents excluded).
- Rates are per 1,000 women in 5-year age groups, based on July 1 population estimates.
- The 10–14 rate uses births at 10–14; the 45–49 rate uses births to women 45 and older.
- **2025 rates use vintage 2025 Census estimates, which include methodological changes. 2024 rates use vintage 2024.**

**Acquired.** The most detailed official 2025 data are the final public-use file, giving births by single year of mother's age 10–12, 13–49 and 50–54, birth order and month. Only aggregates were extracted.

**Verification.**
- **Resident births:** 3,628,934 (2024) and 3,612,012 (2025), equal to the official totals.
- **Published rates:** every 2025 rate in DB571 and the GFR reproduce exactly from these births and vintage 2025 denominators. Every 2024 published rate reproduces from vintage 2024.
- **TFR convention:** in all three NVSR reports, the NCHS TFR equals 5 × the sum of the *published, rounded* 5-year rates. NCHS does not revise earlier years' rates when new population vintages appear: the 2010–2019 rates are identical in the 2019, 2023 and 2024 reports.
- **Record length:** the public-use records are 1,345 bytes, against 1,330 in the user guides. The field positions are confirmed by the exact totals and rates (WARN).

**2025 TFR (derived, not official).**
- **1.576:** 5 × the sum of the rounded DB571 rates, the NCHS convention.
- **1.5763:** unrounded.

**The 2024→2025 comparison is not like for like:**

| Age group | Published 2024 | Final 2025 | Published change | 2024 recomputed on V2025 | Change, same vintage |
|---|---|---|---|---|---|
| 20–24 | 55.8 | 52.3 | −6.3% | 53.80 | **−2.8%** |
| 25–29 | 89.5 | 85.7 | −4.2% | 87.98 | −2.6% |
| 30–34 | 93.7 | 96.3 | +2.8% | 95.51 | **+0.9%** |
| TFR (per 1,000) | 1,599.5 | 1,576.0 (derived) | −1.5% | 1,591.7 | −1.0% |

On consistent denominators, the population-estimate revision accounts for 55% of the published 2024–2025 fall at ages 20–24, 40% at 25–29 and 69% of the rise at 30–34. That part is not a change in fertility. The full table is `m11_nchs_2025_rates.csv`.

**Single-year rates for 2025.** NCHS publishes none. The project derived them as public-use births over vintage 2025 July 1 female population (`m11_nchs_single_year_2024_2025.csv`, labelled "derived"). Ages 12 and 50 carry the open groups 10–12 and 50–54. These are project calculations on NCHS conventions, not HFD values; HFD-compatible 2025 rates will exist only after an HFD update.

## 4. Census national population projections (2023 series)

**Release.** November 2023. This is the latest national series in the Census projection directories on 2026-11-20.
- **Base:** July 1, 2022 population (vintage 2022 estimates).
- **Fertility inputs:** NCHS births 1990–2020 with bridged-race denominators.

**Inventory** (`m11_census_inventory.csv`).
- Population by single year of age 0–100+ and sex (D1, D5 with nativity), 2022–2100.
- Projected births (D2), deaths (D3) and net international migration (D4), 2023–2100.
- ASFR by single age 14–54 (A1) and TFR (A5) for the total population, 2023–2100. Six nativity–race–Hispanic groups are also given, to 2060.
- Mortality assumptions (A2–A4).

**Scenarios.**
- Four: main series, high immigration, low immigration and zero immigration.
- **All four share one fertility assumption and one base population.** No fertility scenarios exist.

**Fertility assumption.** Group-specific ASFRs are interpolated linearly from 2021 towards a common target in 2123: TFR 1.52, the 2020 native-born White level, with the age pattern of foreign-born Asian/Pacific Islander women. For the total population, the assumed TFR falls from 1.6356 (2023) to 1.6161 (2040), and the peak age stays at 31.

**Reference periods.** Population is as of **July 1**. Rates and births refer to **projection years running July 1 of the previous year to June 30**, not calendar years.

**Checks.** 7 PASS and 1 WARN:
- **Internal consistency:** A5 equals the sum of the A1 rates (within 0.0006). Ages and sexes add up in every scenario. All scenarios share the 2022 base.
- **Births reproduction:** total-group ASFR × mean female population reproduces projected births to within 0.1–0.7% (ratio 0.9926–0.9988), because Census computes births within six groups.
- **WARN, assumption against later observations:**

| Projection year | Census assumed TFR | Observed TFR (NCHS, calendar year) |
|---|---|---|
| 2023 | 1.636 | 1.621 |
| 2024 | 1.635 | 1.599 |
| 2025 | 1.633 | 1.576 (derived) |

**Projected and observed births happen to agree.** For July 2024–June 2025, Census projected 3,636,874 births and 3,633,398 were observed, a difference of −0.1%. This is a coincidence of offsetting errors: the TFR assumption is about 3.6% too high, and the projected female population aged 15–49 is 2.2% below vintage 2025 (`m11_denominator_comparison.csv`). This is reported as a contrast with an external scenario, not as validation.

**Scenario contrasts to 2040** (`m11_census_scenarios.csv`):

| 2040 | Main | High | Low | Zero immigration |
|---|---|---|---|---|
| Women 15–49 (millions) | 77.6 | 81.7 | 74.9 | 69.5 |
| Projected births, July 2039–June 2040 | 3,592,151 | 3,861,433 | 3,412,635 | 3,053,543 |

**Use in M11.**
- **Female populations:** Census female population by single age can serve as exposure for projected births, but only (a) as scenario-conditional denominators and (b) after recalibration to vintage 2025, whose 2025 female population aged 15–49 is 2.2% larger.
- **Fertility assumption:** the projected fertility (A1/A5) is an external scenario. It is never used as an observed value or predictor, and never as validation for forecasts.

## 5. Cross-source compatibility

| Dimension | HFD | NCHS | Census projections | Reconciliation |
|---|---|---|---|---|
| Fertility concept | Period (RR, TR, VV) and cohort (VH) | Period only | Period (projection year) | Cohort measures come only from HFD. NCHS and Census are period data |
| Age detail | Single years 12-…55+ | Published: 5-year groups. Public-use: single years 10–12…50–54 | Single years 14–54 | Single-year comparison is possible only through the public-use file. Published 2025 rates stay 5-year |
| Denominator | Person-years of exposure (HMD-based) | July 1 estimates of the vintage current at release | July 1 projected population | See below |
| TFR | Σ single-year rates | 5 × Σ rounded 5-year rates | Σ single-year rates | Decomposed in `m11_hfd_nchs_reconciliation.csv` |
| Time unit | Calendar year | Calendar year | July–June | Census births and rates are offset by half a year |
| Births | Equal to NCHS (distributes 50–54 by age) | Official counts | Projected | Identical where they overlap |

**Why HFD's TFR is lower than NCHS's.** HFD's TFR is lower by 0.0025–0.0135 in 2010–2022 and 2024, and by **0.026 in 2023**. Births are identical, so the gap is entirely denominators and convention. For 2023, the decomposition runs:

| Step | TFR |
|---|---|
| NCHS published (V2023 denominators, rounded rates) | 1.6210 |
| Recomputed on V2024 | 1.6047 |
| Recomputed on V2025 | 1.5983 |
| On HFD exposures, 5-year convention | 1.5969 |
| HFD single-year TFR | 1.595 |

The 5-year grouping alone moves the TFR by −0.001 to −0.003 in every year.

**Denominator revisions are the main compatibility risk.**
- **Vintage 2024 vs 2025:** vintage 2025 raised the estimated female population aged 20–24 by 3.7–5.8% relative to vintage 2024 for 2020–2024, and lowered ages 30–34 by 0.3–1.8%.
- **HFD exposures:** they are already within 0.5% of vintage 2025 at every age group shown (ages 15–49 within 0.2%), so the HFD series is close to the current population vintage.
- **NCHS series:** the official series mixes vintages and is never back-revised.

**Consequences for forecasting.**
1. Use the HFD series as the single consistent historical series.
2. Do not splice published NCHS rates onto it.
3. Treat 2025 only through NCHS births on vintage 2025 denominators (a bridge, section 7), or wait for the HFD update.
4. Repeat any backtest on the next HFD release, which will revise recent exposures, as a revision sensitivity analysis.

**Historical against projected populations.** The Census projected female population aged 15–49 is 0.8% (2022) to 2.2% (2025) below vintage 2025. The gap is largest at young adult ages, reflecting the higher immigration in the newer estimates. Projected births from forecast rates require this level calibration and the scenario choice to be stated.

## 6. Birth-cohort observability, 1995–2012

`m11_cohort_observability.csv` and `assets/figures/m11_cohort_observability.png`.

A cohort-age cell (age in completed years) needs two calendar years, c + x and c + x + 1. HFD 2024 data therefore complete cohort *c* to age 2023 − *c*, plus the 2024 lower triangle at age 2024 − *c*. The NCHS 2025 public-use file adds period data at ages 2024 − *c* to 2025 − *c*, which mixes two cohorts. HFD has no 2025 cohort split.

| Cohort | HFD complete ages | Cumulative births per woman (HFD) | Age reached in 2040 | Ages to forecast, 2026–2040 | Unobserved after 2040 | Share of CCF reached by those ages, 1965–74 cohorts |
|---|---|---|---|---|---|---|
| 1995 | 12–28 | 0.833 by exact age 29 | 45 | 30–45 | 46–55+ | 99.8–99.9% |
| 1998 | 12–25 | 0.471 by 26 | 42 | 27–42 | 43–55+ | 99.0–99.4% |
| 2000 | 12–23 | 0.289 by 24 | 40 | 25–40 | 41–55+ | 97.4–98.3% |
| 2003 | 12–20 | 0.110 by 21 | 37 | 22–37 | 38–55+ | 92.3–94.4% |
| 2005 | 12–18 | 0.035 by 19 | 35 | 20–35 | 36–55+ | 86.5–89.6% |
| 2008 | 12–15 | 0.003 by 16 | 32 | 17–32 | 33–55+ | 74.3–78.8% |
| 2011 | 12 | 0.000 by 13 | 29 | 14–29 | 30–55+ | 59.2–64.4% |
| 2012 | none | — | 28 | 13–28 | 29–55+ | 53.9–59.2% |

The CSV has all 18 cohorts. The last column brackets the share between exact ages 2040 − *c* and 2040 − *c* + 1. It describes the 1965–1974 cohorts: Gen Z has children later, so these shares probably overstate how much of Gen Z lifetime fertility falls before 2041.

**Conclusions.**
- **Observed so far:** most Gen Z childbearing is still unobserved. Only the 1995–1999 cohorts have passed age 25 in the data.
- **What 2040 yields:** births accumulated by 2040 are completed fertility only for the oldest cohorts (1995–1997, at ages 43–45). For the 2005–2012 cohorts, 2040 captures perhaps half to nine-tenths of lifetime fertility by historical standards.
- **Measure to report:** the defensible quantity is **cumulative fertility to the age reached in 2040**, never "completed" fertility.

## 7. Forecasting feasibility of the three proposed outputs

**A. National period TFR, 2026–2040. Feasible.**

| Aspect | Assessment |
|---|---|
| Observed portion | HFD 1933–2024 (92 years, consistent denominators). 2025 known only as the derived NCHS value 1.576 on V2025 denominators, about 0.017 below HFD 2024 |
| Projected portion | 2026–2040, which is 15 annual values beyond the last NCHS year and 16 beyond the last HFD year |
| Uncertainty | Must come from historical forecast errors at each horizon (section 9), plus revision uncertainty in the jump-off level |
| Interpretation | A period summary of the year's age-specific rates, which is not the number of children any cohort will have. Tempo distortion is material: the tempo-adjusted TFR was 1.750 in 2023 against a TFR of 1.595 |

**B. National age-specific rates, 2026–2040. Feasible with a coherence requirement.**

| Aspect | Assessment |
|---|---|
| Observed portion | HFD single ages 12–55+, 1933–2024. 2025 single-year rates are derived from NCHS data and flagged |
| Projected portion | 2026–2040, all ages |
| Uncertainty | Larger than for the TFR, because the age pattern has shifted: mean age at birth was 26.4 in 1957 and 30.1 in 2024. Forecast rates must sum to the TFR forecast, and intervals must be joint |
| Interpretation | Needed for births and for cohort trajectories. Reported at single ages but evaluated mainly at 5-year groups and mean age at birth |

**C. Trajectories for birth cohorts 1995–2012. Feasible only as cumulative fertility to the age reached in 2040.**

| Aspect | Assessment |
|---|---|
| Observed portion | Section 6: up to exact age 29 for the 1995 cohort, and nothing beyond age 13 for 2011–2012 |
| Projected portion | Forecast rates along each cohort diagonal, 2025/26–2040 |
| Uncertainty | Accumulates along the diagonal. It is largest for the youngest cohorts, which are almost entirely forecast |
| Interpretation | Population averages for birth cohorts, not individual outcomes. **These data cannot show whether individual Gen Z respondents will achieve their intended family sizes.** NSFG intentions (M09) are cross-sectional answers from different people, and no record links them to these births |

## 8. Recommended targets

- **Primary target: the national period TFR (HFD definition), annual, 2026–2040**, with prediction intervals, evaluated at 5-, 10- and 15-year horizons. It has the longest consistent series, it is the quantity Census assumes, and it can be backtested directly.
- **Secondary targets.** These are derived from a rate forecast that must be coherent with the primary target:
  1. **Single-year age-specific rates, 15–49** (open ends at 12- and 50+). Their sum must equal the TFR forecast. They are evaluated by 5-year groups and mean age at birth.
  2. **Cumulative cohort fertility to the age reached in 2040**, cohorts 1995–2012. This combines observed HFD cohort cells with forecast rates on diagonals, and is never labelled "completed".
  3. **Annual births, conditional on a scenario:** forecast rates × Census female populations for the main, high and low immigration scenarios, after level calibration to vintage 2025. They are presented as scenario-conditional, not as unconditional forecasts.
- **Excluded:** forecasts by race or nativity, state-level forecasts, and any individual-level prediction.

## 9. Backtesting and uncertainty methodology (proposed, not run)

**Data.** The frozen HFD release of 2 July 2026, 1933–2024. Its hashes are recorded in `data/raw/hfd_usa/provenance.json`. At forecast origin *o*, only years ≤ *o* may be used. This is a pseudo-real-time design: the HFD vintage contains population revisions that were unknown at *o*. A sensitivity run on the NCHS published series (2010–2024, real-time vintages) shows the size of this effect over the short window where it is possible.

**Origins and horizons** (`m11_backtest_design.csv`, minimum 20 training years, last target year 2024):

| Training data from | Horizon 5 | Horizon 10 | Horizon 15 |
|---|---|---|---|
| 1933 (full series) | 68 origins (1952–2019); 14 non-overlapping windows | 63 (1952–2014); 7 | 58 (1952–2009); 4 |
| 1977 (after the 1976 trough) | 24 (1996–2019); 5 | 19 (1996–2014); 2 | 14 (1996–2009); 1 |
| 1990 | 11 (2009–2019); 3 | 6; 1 | 1; 1 |

Rolling origins overlap heavily. The number of independent error windows is the binding constraint: **at 15 years there are four in the whole history and one in the post-1977 regime.** Long-horizon evaluation is therefore only weakly supported. 15-year intervals must be presented as indicative, and error distributions from different regimes must not be pooled silently.

**Structural periods** (`m11_structural_periods.csv`; turning points found by stated rules):

| Year | Event | TFR |
|---|---|---|
| 1957 | Baby-boom peak | 3.738 |
| 1965 | Largest one-year fall | — |
| 1976 | Post-boom trough | 1.739 |
| 2007 | Pre-recession peak | 2.122 |
| 2008–2024 | Decline, including the 2020 pandemic year | — |
| 2024 | Series low | 1.593 |

Over the same span, mean age at birth rose from 26.4 (1957) to 30.1 (2024). Data breaks also apply:
- 1933–1938 estimated births;
- the 1959–1960 territorial change;
- the 2020 census base;
- the 2025 vintage revision.

The backtest should report errors separately for origins before 1977, 1977–1999 and 2000 onward.

**Baselines, to be fixed in a protocol before any error is computed:**

| Baseline | Definition |
|---|---|
| B0 | No change: TFR and the age schedule held at the jump-off year |
| B1 | Random walk with drift on log TFR, drift from the last 10 years, plus a damped variant |
| B2 | Mean of the last 10 years |
| B3 | Rule-based convergence to a target fixed at the origin from past data only (for example, the 30-year mean). This is structurally like the official projections without using them |

More complex models should be considered only if they beat B0–B3 in the locked backtest. Candidates are Lee–Carter or functional-data models of the age schedule, Bayesian TFR models, and cohort-completion models. Census assumptions may serve as a comparison series for 2023+ only. Earlier Census projection vintages (2012, 2014, 2017) could serve as historical benchmarks if acquired, never as predictors.

**Metrics.**
- **TFR:** signed error (bias), absolute and log-ratio error by horizon.
- **Rates:** mean absolute error over 5-year groups and error in mean age at birth.
- **Cohorts:** error in cumulative fertility at fixed ages.
- **Intervals:** empirical coverage at 80% and 95%, and the interval score.

**Prediction intervals.** Use empirical quantiles of historical log-ratio errors at each horizon from the rolling origins, applied to the 2025/2026 jump-off. Calibrate them by checking coverage on held-out eras, reporting the full-series and post-1977 versions side by side. Add jump-off uncertainty from the 2024–2025 revision, about 0.008 in TFR between vintages.

**Scenarios.** These are a separate, clearly labelled layer, not probabilities. Examples are continued decline, constant 2025 rates, and the Census-style slow path, plus the Census immigration scenarios for births.

## 10. Remaining limitations

- **No official 2025 TFR.** The derived 1.576 should be checked against *Births: Final Data for 2025* when it appears.
- **No HFD 2025.** The next HFD release will add 2025 and may revise 2020–2024 exposures.
- **No Census fertility scenarios.** The 2023 Census assumption is already above observed fertility, and its population base predates the vintage 2025 immigration revisions.
- ~~**Tiny HFD discrepancies.** The CCFR, CCF and CCF40 differences (≤ 0.0008) were not explained.~~ Resolved: an implementation error in my code, corrected (section 2).
- **HFD input files not checked.** They need an HFD login.

## 11. Decision

**CONDITIONAL.** There are no blocking data gaps. Forecast modelling may proceed once these conditions are met:

1. **Owner approval of the scope:** the primary and secondary targets in section 8, and the restriction of cohort output to cumulative fertility by 2040.
2. **A locked backtest protocol before any error is computed:** baselines B0–B3, origins, horizons, metrics, era-specific reporting and interval method (section 9). It must be hashed, as in M10.
3. **A decision on the jump-off:** either use HFD 2024 with the derived NCHS 2025 values as a flagged bridge, or wait for the HFD release that includes 2025.
4. **Births are scenario-conditional:** they require Census population recalibration to vintage 2025 and an explicit immigration scenario.

**Data that would strengthen the work** (none is required to start):
- the final 2025 NVSR;
- the HFD release with 2025;
- earlier Census projection vintages, as benchmarks;
- the HFD input-data files.

## 12. Reproducibility

```
python -m analysis.m11_sources --provenance   # hash every raw file into provenance.json
python -m analysis.m11_sources --tabulate     # aggregate the 2024 and 2025 public-use files (~1 min; needs Info-ZIP unzip for Deflate64)
python -m analysis.m11_sources                # NCHS and Census parsing and checks
python -m analysis.hfd                        # HFD validation and cohort observability
python -m analysis.m11_feasibility            # all M11 tables and figures; prints PASS/WARN/FAIL and the decision
python audit/verify_m11.py                    # independent verification (~2 min; --skip-puf skips the recount)
python -m unittest                            # full test suite, including tests/test_m11_data.py
python audit/verify_freeze.py                 # frozen M09 and M10 manifests
```

- **Text extraction:** PDF texts were made with `pdftotext -layout` (xpdf 4.06).
- **Downloads:** files were retrieved on 2026-11-20 from the URLs recorded in each `provenance.json`. The HFD archive needs an HFD account.

**Outputs.**
- `data/public/m11/`: 18 aggregate tables.
- `assets/figures/m11_tfr_sources.png`, `assets/figures/m11_cohort_observability.png`.
- `data/processed/m11/`: public-use aggregates, local.

**Code.**
- `analysis/m11_sources.py`, `analysis/hfd.py`, `analysis/m11_feasibility.py`;
- `audit/verify_m11.py`;
- `tests/test_m11_data.py`.

No frozen M01–M10 file was modified.
