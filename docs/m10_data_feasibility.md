# M10: Data Acquisition and Feasibility Audit

This audit checks whether two official sources can form a state-year panel of housing cost burden and fertility for women in their twenties. The sources are Census ACS table B25070 (rental cost burden) and CDC WONDER natality data (births to mothers aged 20–24 and 25–29). It covers acquisition, validation and joining only. No model is fitted, frozen M01–M09 files are untouched, and nothing has been published.

**Decision: READY.**
- Both sources are acquired, validated and reconciled.
- The primary panel has all 1,020 expected state-year-age records, every one with a birth rate.
- The limitations in section 5 concern interpretation and modelling, not data completeness.

| Component | Status | Reason |
|---|---|---|
| Census ACS B25070, 2014–2024 except 2020 | **PASS** | 510 of 510 state-years; definitions identical in every release; every integrity check passes |
| CDC WONDER natality, two exports | **PASS** | 1,122 of 1,122 analytical rows, all with births, population and rate. The two exports agree exactly on every shared value; rates recalculate; they agree with NCHS final-data reports for 2019 and 2023 |
| Combined panel (excluding 2020) | **PASS** | 1,020 of 1,020 records, all with rates; clean joins; full coverage in every year; lags checked against the previous calendar year |

**History.** The first audit (same day) was CONDITIONAL. The original export, from the bridged-race "Natality, 2007–2024" database, had no denominators or rates for 2021–2024. The owner then exported the same query from "Natality, 2016–2024 expanded", which resolves this (section 3). The first audit also said ACS sampling error was 54% of the remaining housing variation; that figure is replaced in section 5.

## 1. Dataset inventory and provenance

| Dataset | Source | Local files (unchanged) | Provenance |
|---|---|---|---|
| ACS 1-year B25070, "Gross Rent as a Percentage of Household Income in the Past 12 Months" (universe: renter-occupied housing units) | U.S. Census Bureau API, `https://api.census.gov/data/{year}/acs/acs1`, `get=NAME,group(B25070)&for=state:*` | `data/raw/acs_b25070/acs1_{year}_B25070_data.json` and `_variables.json` for 10 years | `data/raw/acs_b25070/provenance.json`: URL and parameters without the key, HTTP status, UTC retrieval time, bytes and SHA-256 per file. Retrieved 2026-11-20 |
| CDC WONDER **Natality, 2007–2024** (original export): Year × State × Age of Mother 9 (20–24, 25–29), 2014–2024 | CDC/NCHS National Vital Statistics System; manual export by the owner (query date Nov 20, 2026 7:21:44 AM) | `data/raw/cdc_natality/cdc_wonder_natality_state_age_2014_2024.xls` (SHA-256 begins `cfb3a97f`) | `data/raw/cdc_natality/provenance.json`, built from each file's own footer: hash, size, query parameters, citation, years used |
| CDC WONDER **Natality, 2016–2024 expanded**: Year × State of Residence × Age of Mother 9, 2016–2024 | As above (query date Nov 20, 2026 8:03:07 AM) | `data/raw/cdc_natality/cdc_wonder_natality_expanded_state_age_2016_2024.xls` (SHA-256 begins `e332c702`) | As above |
| NCHS "Births: Final Data for 2019" (NVSR 70-2) and "for 2023" (NVSR 74-1), Tables 2 and 8 | CDC/NCHS National Vital Statistics Reports | `data/raw/nchs_nvsr/*.pdf` and the text extracted with `pdftotext -layout` | `data/raw/nchs_nvsr/provenance.json`: URLs, citations, SHA-256, and quotations from the WONDER help page |

**Credentials.** The Census key is read from `CENSUS_API_KEY` and sent only in the request. No saved response, provenance file, processed table or log contains it; tests and a scan of the saved files confirm this.

**Processed outputs.** These are in `data/processed/m10/` (local, not under version control):
- `acs_b25070_state_year.csv` and `acs_b25070_validation.json`;
- `cdc_natality_state_year_age.csv` (with a `source` column) and `cdc_natality_validation.json`;
- `m10_panel_state_year_age.csv` and `m10_panel_validation.json`.

## 2. Census ACS B25070

**Coverage.**
- 10 releases: 2014–2019 and 2021–2024.
- Each response has 52 rows; Puerto Rico (FIPS 72) is excluded, leaving 510 state-year records, as expected.
- No duplicate state-year keys.
- 2020 is not requested. The Census Bureau released only experimental 2020 1-year estimates. Nothing is interpolated, and no 5-year estimate is substituted.

**Integrity checks.**
- **Category labels:** all 11 match the official definitions in every release, as does the table concept. Older releases differ only in punctuation ("Total" against "Total:").
- **Values:** all 22 estimate and MOE columns are present and numeric. No Census missing-value code appears in any estimate or MOE. The 22 annotation columns are all empty.
- **Category totals:** categories 002–011 sum exactly to 001 in all 510 retained records.
- **Denominators:** none is zero or negative.

**Derived measures.** The denominator is households with burden computed: 001 − 011, which equals 002 + … + 010.

| Measure | Definition | Range across state-years |
|---|---|---|
| Cost burden, 30% or more | (007 + 008 + 009 + 010) / computed | 36.1–62.1% |
| Severe burden, 50% or more | 010 / computed | 15.8–32.5% |
| Burden not computed | 011 / 001 (no or negative income, or no cash rent) | 4.4–20.4% |

**Uncertainty method.**
- ACS margins of error are published at the 90% level, so SE = MOE / 1.645. 1-year samples for different years are separate.
- **Derived MOEs** use the Census Bureau's approximation formulas (*Understanding and Using ACS Data*, 2020, ch. 8):
  - **Sums:** the root sum of squared MOEs.
  - **Proportions:** the proportion formula, with the ratio formula as a fallback when the term under the square root is negative. The fallback was never needed here.
- **Limitations:**
  - **Covariance is ignored.** The formulas assume the categories are uncorrelated. They are approximations, and less accurate when many categories are combined; the denominator combines nine.
  - **No replicate weights.** Exact standard errors would need replicate weights from ACS PUMS. Variance replicate tables exist only for selected 5-year tables. Neither is used.
  - **Comparisons need care.** A difference between two years or states needs a test that combines both MOEs; checking whether confidence intervals overlap is not a valid test.
  - **2021 onward differs.** Estimates from 2021 use population controls based on the Census Bureau's Blended Base.

## 3. CDC WONDER natality

**Format.**
- Both `.xls` files are tab-delimited text (CDC WONDER's export format), not binary or XLSX workbooks.
- They are read as text and never modified; their hashes are recorded in the provenance file and checked by a test.
- The parser accepts the expanded export's `State of Residence` / `State of Residence Code` headers as equivalent to the original's `State` / `State Code`, and rejects any other header.

**Query configuration (from each footer).**

| | Original export | Expanded export |
|---|---|---|
| Dataset | Natality, 2007–2024 | Natality, 2016–2024 expanded |
| Years | 2014–2024 | 2016–2024 |
| Group by | Year; State; Age of Mother 9 | Year; State of Residence; Age of Mother 9 |
| Ages | 20–24, 25–29 | 20–24, 25–29 |
| Show totals / zero values / suppressed | True / True / False | True / **False** / False |
| Rates per | 1,000 | 1,000 |

- **Residence:** location is the mother's legal residence (WONDER natality help).
- **Zero values:** the expanded export hides zero-count rows. That could only drop a combination with no births, and every expected combination is present.

**Validation of each export.**

| Check | Original | Expanded |
|---|---|---|
| Detail rows / expected | 1,122 / 1,122 | 918 / 918 |
| Duplicate keys, missing combinations, unexpected categories | 0 / 0 / 0 | 0 / 0 / 0 |
| Suppressed cells (smallest count) | 0 (598 births) | 0 (598 births) |
| Rows with population and rate | 714 (none for 2021–2024: "Not Available") | 918 (all years) |
| Rates recalculated from births and population | 714, largest difference 0.0005 | 918, largest difference 0.0005 |
| Subtotal rows (state-year, year, grand) matching their detail rows | 561, 11, 1: all match | 459, 9, 1: all match |

Subtotal and grand-total rows are used only for these checks. They never enter the analytical data.

**Reconciliation between the two exports.** Each comparison is exact, and a test reproduces it with an independent `csv` parser and fails on any disagreement.
- **2016–2020:** all 510 shared rows agree exactly on births, female population and rate.
- **2021–2024:** all 408 shared rows agree exactly on births. Here the expanded export supplies the populations and rates the original lacks.
- **State names:** identical.
- **The same total populations.** For all races combined, the bridged-race and single-race population totals by age are identical for 2016–2020. So the switch of source at 2016 introduces no break in the denominator series.

**Analytical series.**
- **Sources:** 2014–2015 come from the original export (204 rows) and 2016–2024 from the expanded export (918 rows).
- **Size:** 1,122 rows, with no missing rate and no duplicate key.
- **Rate definition:** "Fertility Rate" for an age group is births per 1,000 women in that group, which NCHS calls the age-specific birth rate.

**Independent validation against NCHS final-data reports.**
- **State rates, 2019 and 2023 (NVSR Table 8, "by place of residence"):** all 102 state-age rates in each year lie within the published one-decimal precision. The largest difference is 0.05, a rounding tie.
- **National rates, 2014–2019 and 2021–2023:** recomputed from summed births and population, they agree with NVSR 74-1 Table 2 within ±0.05 for both age groups.
- **2020:** WONDER is lower by 0.28 (20–24) and 0.69 (25–29). NVSR's 2020 rates use April 1, 2020 populations, while WONDER uses July 1 estimates. 2020 is outside the primary panel.
- **2024 (added in the M10 analysis stage):** NVSR 75-2, *Births: Final Data for 2024* (June 9, 2026), Table 6. All 102 state-age rates lie within the published precision (largest difference 0.05). National 2024 rates agree too. Every state difference is listed in `data/processed/m10/nvsr_state_rate_benchmark.csv`.

## 4. Primary panel

`analysis/m10_panel.py` joins the analytical natality series to ACS on state FIPS code and calendar year.

| Item | Result |
|---|---|
| Records (2020 excluded) | **1,020** = 51 jurisdictions × 10 years × 2 age groups, as expected |
| Records with a birth rate and housing measures | **1,020** (100%) |
| Duplicate keys / unmatched joins / state-name disagreements | 0 / 0 / 0 |
| Geographic coverage | 51 jurisdictions in every year; 2 rows per state-year |
| CDC 2020 rows | 102, kept in the natality table outside the panel |
| 1-year housing lag (actual calendar year t − 1) | 816 records, each equal to the ACS value of the previous calendar year (816 checked, 0 mismatches). None in 2014 (2013 not acquired) or 2021 (no ACS 2020); 2019 is never carried to 2021 |

**Fixed-effects feasibility.**
- **Panel shape:** 51 states and 10 years, balanced, with rates throughout.
- **Variation over time:** every state varies in 30%+ burden (smallest within-state SD 0.98 points).
- **Remaining variation:** removing state and year means leaves a residual SD of 1.38 points (variance 1.91), against a raw SD of 4.11.
- **Identification:** state and year fixed effects are identified. Two caveats follow:
  - the identifying variation in housing burden is small;
  - inference would rest on 51 state clusters.

## 5. Limitations and comparability

**ACS sampling error in the housing measure (reassessed).** The first audit divided the average raw sampling variance (1.03) by the residual variance (1.91) and reported 54%. That overstated the share, because removing state and year means also removes part of the sampling noise. The corrected analysis:
- simulates sampling errors from each estimate's approximate SE;
- puts them through the same two-way demeaning (2,000 draws, seed 2026);
- compares the result with the observed residual variance.

| SE assumption | Expected noise variance after demeaning | Share of residual variance |
|---|---:|---:|
| Approximate SEs × 0.75 | 0.51 | 0.27 |
| Approximate SEs as computed | 0.91 | **0.47** |
| Approximate SEs × 1.25 | 1.42 | 0.74 |

How to read this:
- This describes the **measure**, not any regression. If the SEs are right, roughly half of the within-state, within-year variation in 30%+ burden could come from sampling, but the share is highly sensitive to SE accuracy, and these SEs are approximations.
- The calculation assumes three things:
  - the approximate SEs are correct on average;
  - sampling errors are independent across states and years (shared population controls make this only approximately true);
  - sampling errors are uncorrelated with the true burden.
- Whether this would bias a future estimate, and in which direction, depends on further assumptions that have not been established. These include the model specification and whether the measurement error is independent of the outcome and of the other covariates. No claim of attenuation bias is made here. A modelling stage would need to address this directly, for example with measurement-error models or sensitivity analysis.

**Other limitations.**
- **Age-period-cohort.** Each row is an age group observed in a calendar year. Women aged 20–24 in 2014 were born about 1989–1994; in 2024, about 1999–2004. Age, period and birth cohort are linked exactly (cohort = period − age), so models with age and year effects cannot separate cohort effects. The panel describes how age-specific rates change over time in each state. It is **not** a panel that follows a Gen Z birth cohort, and must not be presented as one.
- **Housing-measure scope.** The measure covers all renter households, not women aged 20–29, and not owners.
- **Comparability over time.**
  - **2020:** the ACS gap.
  - **Population estimates:** from 2021, the ACS controls and CDC's population estimates (Vintage 2021 onward) are both based on the Blended Base.
  - **Pandemic:** effects around 2020–2021.
  - **ACS definitions:** B25070 definitions are unchanged across releases.
- **2024 natality** was checked against NVSR 75-2 in the M10 analysis stage (all within published precision).
- **Uncertainty in birth rates.** Rates are treated as exact. NCHS regards vital-statistics counts as complete enumerations, although they can show random variation. All cells here have at least 598 births.

## 6. Reproduction

From the project root (the download step needs `CENSUS_API_KEY`):

```
python -m analysis.acs_housing --fetch   # download 10 ACS releases, then validate
python -m analysis.acs_housing           # validate saved responses (no network)
python -m analysis.cdc_natality          # parse both exports, reconcile, NVSR checks, provenance
python -m analysis.m10_panel             # join, lags, coverage, fixed effects, sampling noise
python -m unittest tests.test_m10_data   # 29 tests (unit tests need no data or network)
```

## Sources
- U.S. Census Bureau, American Community Survey 1-year estimates, table B25070, via the Census Data API.
- U.S. Census Bureau (2020), *Understanding and Using American Community Survey Data: What All Data Users Need to Know*, chapter 8.
- CDC/NCHS, Natality on CDC WONDER Online Database: Natality, 2007–2024 and Natality, 2016–2024 expanded, with their help pages.
- Martin J.A. et al., Births: Final Data for 2019, *National Vital Statistics Reports* 70(2), 2021.
- Osterman M.J.K. et al., Births: Final Data for 2023, *National Vital Statistics Reports* 74(1), 2025.
