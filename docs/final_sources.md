# Verified citations and source inventory

**Status:** **FROZEN, final scientific approval, 2026-11-20.** Manifest `docs/final_synthesis_freeze.sha256`; completion record `docs/final_readiness_assessment.md`. Editing this file needs a recorded decision and a new manifest.

**Verification.** `python audit/verify_final_synthesis.py` re-hashes every raw file recorded in a `data/raw/*/provenance.json`. The run on 2026-11-20 found:
- 221 files in 10 provenance records;
- 0 mismatches.

Raw files stay local and are not distributed.

## 1. Data sources

| Source | Used by | Local copy (not distributed) | Origin | Retrieved | Integrity evidence | Terms of use |
|---|---|---|---|---|---|---|
| NLSY97 public-use data, three extracts with codebooks (Bureau of Labor Statistics, U.S. Department of Labor) | M01–M08 | `data/raw/intention_gap_nlsy97_v2.*`, `_supplement.*`, `_temporal.*` | NLS Investigator (nlsinfo.org) | Extracts dated 2026-11-17 to 2026-11-19 (methodology section 1); release name not recorded | Raw CSV SHA-256 prefix `79db4479c82d80e9` equals the frozen M01–M08 reference; variable lists in `docs/extract_manifest.csv` and `docs/temporal_extract_manifest.csv` | Public-use; cite BLS; no affiliation or endorsement. **Not verified this session** (L-SRC-1) |
| NSFG 2022–2023 female and male respondent public-use files, codebooks, recode specifications, User's Guide (NCHS) | M09 | `data/raw/nsfg_2022_2023/` | cdc.gov/nchs/nsfg | Not recorded in a provenance file | Female CSV 17,054,679 bytes (SHA-256 prefix `eb10fa3bd11e671b`); male CSV 7,031,379 bytes (`1d8ca931690c6b16`); dimensions match CDC (Stage 3 Check 01) | NCHS public-use data-use restrictions (no re-identification). **Not verified this session** |
| ACS 1-year B25070 (rent as a percentage of income), 2014–2019 and 2021–2024 | M10 | `data/raw/acs_b25070/` | api.census.gov | 2026-11-20 | 20 files hashed in provenance; all match | U.S. government work; Census API terms. API key never stored |
| ACS 1-year B25072, B23025, B19013 | M10 | `data/raw/acs_m10_covariates/` | api.census.gov | 2026-11-20 | 60 files hashed; all match | As above |
| CDC WONDER Natality (2007–2024; 2016–2024 expanded), births by state and age of mother | M10 | `data/raw/cdc_natality/` | wonder.cdc.gov (manual export by the owner, query recorded) | Query date Nov 20, 2026 | 2 files hashed; all match | CDC WONDER data-use restrictions; suggested citation recorded in provenance |
| NVSR 70-2, 74-1, 75-2 (*Births: Final Data* for 2019, 2023, 2024) | M10 | `data/raw/nchs_nvsr/` | cdc.gov | 2026-11-20 | 3 files hashed; all match | U.S. government work |
| Human Fertility Database, USA (release 2 July 2026; files last modified 27 June 2026), and HFD documentation | M11 | `data/raw/hfd_usa/`, `data/raw/hfd_docs/` | humanfertility.org (account required) | 2026-11-20 | 52 + 11 files hashed; all match | HFD User Agreement: HFD-produced estimates under CC BY 4.0; input data keep their original providers' licences (owner, 2026-11-20). The local provenance note "not redistributed" is outdated. See section 5 |
| NCHS final 2025 births (Data Brief 571; VSRR 43) and natality public-use files 2024 and 2025 | M11 | `data/raw/nchs_2025/`, `data/raw/nchs_natality_puf/` | cdc.gov; ftp.cdc.gov | 2026-11-20 (publication dates recorded) | 8 + 6 files hashed; all match | Public-use files have no personal identifiers; tabulated to aggregates only |
| Census Vintage 2024 and Vintage 2025 population estimates; 2023 National Population Projections (November 2023; base July 1, 2022) | M11 | `data/raw/census_popest/`, `data/raw/census_np2023/` | www2.census.gov | 2026-11-20 | 12 + 47 files hashed; all match | U.S. government work |

## 2. Recommended data citations

- Bureau of Labor Statistics, U.S. Department of Labor. *National Longitudinal Survey of Youth 1997 cohort, 1997–2023 (rounds 1–21).* Produced and distributed by the Center for Human Resource Research, The Ohio State University. Columbus, OH. (Exact wording to be confirmed against NLS citation guidance at publication.)
- National Center for Health Statistics. *2022–2023 National Survey of Family Growth, public-use data files and documentation.* Hyattsville, MD.
- U.S. Census Bureau. *American Community Survey 1-year estimates,* tables B25070, B25072, B23025, B19013, 2014–2019 and 2021–2024, via the Census Data API.
- Centers for Disease Control and Prevention, National Center for Health Statistics. *Natality on CDC WONDER Online Database,* 2007–2024 and 2016–2024 expanded (citation text recorded in `data/raw/cdc_natality/provenance.json`).
- National Center for Health Statistics. *Births: Final Data for 2019 / 2023 / 2024.* National Vital Statistics Reports 70(2), 74(1), 75(2).
- Human Fertility Database. Max Planck Institute for Demographic Research (Germany) and Vienna Institute of Demography (Austria). Available at www.humanfertility.org (data downloaded 2026-11-20; USA release 2 July 2026).
- U.S. Census Bureau. *Vintage 2024 and Vintage 2025 Population Estimates;* *2023 National Population Projections.*

## 3. Methodological references

These are the methods named in the chapters. Bibliographic details are given as standard references and were not re-checked online in this session (L-SRC-2).

| Reference | Used for | Chapter |
|---|---|---|
| Bruine de Bruin, Fischhoff, Millstein & Halpern-Felsher (2000), *Organizational Behavior and Human Decision Processes* 81(1), 115–131 | Interpreting "fifty-fifty" answers | M01–M08 |
| Wilson (1927), *Journal of the American Statistical Association* 22(158), 209–212 | Calibration intervals | M01–M08 |
| Nadeau & Bengio (2003), *Machine Learning* 52, 239–281 | Corrected resampled-t interval (approximate) | M01–M08 |
| Korn & Graubard (1990), *The American Statistician* 44(4), 270–276 | Adjusted Wald tests; proportion intervals | M09 |
| Parker et al. (2017), *Vital and Health Statistics* Series 2, No. 175 | NCHS reliability standard for proportions | M09 |
| Cameron, Gelbach & Miller (2008), *Review of Economics and Statistics* 90(3), 414–427 | Wild cluster bootstrap | M10 |
| Diebold & Mariano (1995), *Journal of Business & Economic Statistics* 13(3), 253–263; Harvey, Leybourne & Newbold (1997), *International Journal of Forecasting* 13(2), 281–291 | Forecast accuracy tests | M11 |
| Lee & Carter (1992), *Journal of the American Statistical Association* 87(419), 659–671 | Lee–Carter age-profile method | M11 |
| CDC/NCHS (2025), *2022–2023 NSFG Variance Estimation Report and Examples* | Survey design | M09 |
| HFD Methods Protocol and Data Formats (local copies in `data/raw/hfd_docs/`) | Lexis conventions, VV rates | M11 |

## 4. Open items for publication

| ID | Item | Status |
|---|---|---|
| L-SRC-1 | Terms of use for NLSY97, NSFG, CDC WONDER and Census data checked against current provider pages | Not done; publication-readiness requirement (section 5.4) |
| L-SRC-2 | Online check of method references (DOIs) | Not done; publication phase |
| L-SRC-3 | Provenance files for NSFG and NLSY97 downloads | Not created; hashes recorded here and in `docs/m01_m08_freeze_record.md` |
| L-SRC-4 | HFD licensing of public M11 outputs | Resolved in principle (section 5): HFD-produced estimates are under CC BY 4.0 and may be redistributed with attribution and an indication of changes. The attribution notice must be added at publication, and two questions remain open (section 5.3) |

## 5. Licensing of the public outputs

### 5.1 HFD licence (owner confirmation, 2026-11-20)

- **What the agreement says.** The owner confirmed from the official HFD User Agreement that:
  - HFD-produced estimates are licensed under **CC BY 4.0**;
  - input data retain their original providers' licences.
- **Status in this session.** The agreement text was not re-fetched here, so its URL, version and access date must be recorded verbatim at publication.
- **What the project used.** The project used only HFD-produced estimate files (`USA.zip`: rates, births, exposures, TFR, CCFR). It used no HFD input-data (InDB) files. The only input-database item held locally is a documentation map (`USA_indb-map.pdf`), which is not in any public table or archive.
- **The local note is outdated.** The provenance note in `data/raw/hfd_usa/provenance.json` ("not redistributed") predates this confirmation. The file is local raw-data metadata and was left unchanged; update it at publication.

### 5.2 Classification of the public M11 outputs (`data/public/m11/`)

| Class | Tables | Content | Licence and obligation |
|---|---|---|---|
| H. HFD-produced estimates reproduced verbatim | `m11_fc_asfr_observed_1995_2024.csv` (ASFR); `m11_structural_periods.csv` (TFR, mean age at birth); `observed`/`hfd_*` columns of `m11_fc_tfr_backtest_records.csv`, `m11_fc_interval_records.csv`, `m11_fc_rob_pandemic_origin_2019.csv`, `m11_fc_rob_origin_sensitivity.csv`, `m11_fc_reconstruction_backtest.csv`, `m11_fc_census_alignment.csv`, `m11_hfd_nchs_reconciliation.csv`, `m11_hfd_nchs_births_2024_by_age.csv`, `m11_nchs_single_year_2024_2025.csv`, `m11_denominator_comparison.csv`, `m11_census_vs_observed.csv`; observed segments of `m11_fc_genz_trajectories.csv`; `observed_2024`, `hfd_ccfr` and related columns of `m11_fc_genz_endpoints_2040.csv`, `m11_fc_rob_cohort_conventions.csv` and `m11_cohort_observability.csv` | HFD rates, TFR, CCFR, births and exposures | CC BY 4.0: attribution, a licence link, and a statement that the tables are extracts |
| D. Project estimates derived from HFD estimates | All forecasts, intervals, backtest metrics, selections, shapes, cohort projections and origin-local tables (`m11_fc_*`, `m11_pr_*` not listed under H; `m11_fc_summary.json`, `m11_pr_summary.json`); `m11_completed_share_reference.csv`, `m11_fc_reference_completion_shares.csv` | Adapted material (new computations on HFD estimates) | CC BY 4.0 attribution to HFD, plus an indication that the material was changed. The project's own licence for its analysis is to be chosen at publication |
| N. NCHS-derived aggregates | `m11_nchs_2025_rates.csv`; NCHS columns of `m11_hfd_nchs_*`, `m11_nchs_single_year_2024_2025.csv`, `m11_fc_check_2025.csv` | National births by single year of age from the public-use natality files; published NCHS rates | U.S. government work; cite NCHS. National single-age counts are large, but the public-use data-use terms must still be confirmed (5.4) |
| C. Census-derived aggregates | `m11_census_*.csv`, `m11_fc_census_*.csv` (population, assumed TFR, projected births) | Census estimates and 2023 projections, and births combining Census population with HFD-derived rates | U.S. government work; cite the Census Bureau. Combined tables also carry the HFD attribution |
| P. Project metadata | `m11_backtest_design.csv`, `m11_source_inventory.csv`, `m11_source_status.csv`, `m11_validation_checks.csv`, `m11_hfd_coverage.csv`, `m11_hfd_period_missing.csv`, `m11_fc_data_dictionary.csv`; live run record (not frozen; excluded from archives) | Descriptions, checks and counts | No third-party data (the coverage tables describe HFD files) |

### 5.3 Required attribution, and unresolved questions

**Attribution** (for the README, data folder and figures that show HFD-derived values):
- "Human Fertility Database. Max Planck Institute for Demographic Research (Germany) and Vienna Institute of Demography (Austria). Available at www.humanfertility.org (data downloaded on 2026-11-20; USA release 2 July 2026). Licensed under CC BY 4.0. Tables in `data/public/m11/` include extracts of HFD estimates and estimates derived from them by this project."
- Follow the HFD citation guidelines verbatim at publication.

**Unresolved:**
1. The exact User Agreement text, version and URL must be quoted and archived at publication. It was not re-fetched in this session.
2. HFD input data are not used, so no input-data licence applies. If a future revision uses HFD input files, their original providers' terms apply.

### 5.4 Remaining publication-readiness requirements (verification incomplete)

| Source | Requirement | Status |
|---|---|---|
| CDC WONDER (M10) | Confirm the CDC WONDER data-use restrictions and suggested citation (recorded in the provenance file), including any rules on publishing sub-national counts. The public M10 tables report model results and state rates | Not verified |
| NSFG 2022–2023 (M09) | Confirm the NCHS public-use data-use restrictions; the public tables already apply the NCHS reliability standard and suppression | Not verified |
| NLSY97 (M01–M08) | Confirm the NLS terms and required citation; the dashboard data enforce the project's disclosure rules (methodology section 9) | Not verified |
| Census and NCHS publications | Confirm the citation forms; U.S. government works | Not verified |
| Method references | Check each bibliographic entry and DOI online | Not verified |

Restricted data are not published or redistributed. Raw and processed files remain local and are excluded from every archive.
