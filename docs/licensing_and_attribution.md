# Licensing, attribution and data-use register

**Status:** publication preparation, 2026-11-20. Source terms were checked against the providers' current pages on that date (section 1). The project licence in section 4 is a **proposal awaiting the owner's authorization**; no licence has been granted, and the repository contains no `LICENSE` file yet.

This document closes the open licensing items of the frozen [`docs/final_sources.md`](final_sources.md) (L-SRC-1 and L-SRC-4) without editing it. Corrections to frozen text are listed in [`docs/publication_errata.md`](publication_errata.md).

## 1. Source register (verified 2026-11-20)

| Source | Used by | Published here | Terms (provider page, date shown) | Redistribution | Required attribution | Disclosure rules and how they are met |
|---|---|---|---|---|---|---|
| **Human Fertility Database (HFD)**, USA, release 2 July 2026 | M11 | Extracts of HFD estimates and values derived from them (`data/public/m11/`, `m11_*` figures, README header) | [User Agreement](https://www.humanfertility.org/Data/UserAgreement) and [Citation Guidelines](https://www.humanfertility.org/Data/CitationGuidelines); archived copy: [`source_terms/hfd_user_agreement_2026-11-20.md`](source_terms/hfd_user_agreement_2026-11-20.md) | HFD-constructed estimates: **CC BY 4.0**. HFD "Input Data" stay under their providers' licences and may not be re-published; **none is used or published**. The HFD asks users not to pass on copies of its data, so the HFD files themselves are not redistributed | HFD citation with download date, CC BY 4.0 licence link, and an indication of changes (section 3) | None beyond attribution; all values are national aggregates |
| **NLSY97** public-use data (Bureau of Labor Statistics) | M01–M08 | Aggregate results only (`data/public/dashboard_summary.json`, figures, chapter tables) | [Citing NLS data](https://www.nlsinfo.org/bibliography/citing-nls-data); [Accessing data](https://www.nlsinfo.org/content/access-data-investigator) (no date shown) | Respondent-level extracts are not redistributed (anyone can build them free of charge in NLS Investigator) | NLS suggested citation (section 2); no BLS endorsement | Public-use data only; no geocode or other restricted files were requested. Published aggregates follow the project's rules: outcome cells of at least 20 and counts of at least 10 (methodology section 9) |
| **NSFG 2022–2023** public-use files (NCHS) | M09 | Weighted aggregate estimates (`data/public/nsfg_m09/`), figures | [NCHS Data User Agreement](https://www.cdc.gov/nchs/data_access/restrictions.htm) (dated September 17, 2024); [2022–2023 NSFG documentation page](https://www.cdc.gov/nchs/nsfg/documentation/2022-2023.html) | Microdata are not redistributed. The agreement does not address aggregate statistics | NSFG User's Guide (rev. July 2025, local copy): acknowledge "National Center for Health Statistics, National Survey of Family Growth"; suggested table and graph footer "Data Source: National Center for Health Statistics, National Survey of Family Growth, 2022-2023"; a disclaimer crediting the analyses and conclusions to the author, not NCHS (sections 2 and 3) | Statistical use only; no linkage with identifiable data; no re-identification attempts. Estimates that fail the NCHS presentation standard for proportions are blanked and not drawn (audit section 17.1). Suppressed rows keep their unweighted denominators, including eight rows (four groups) with 2–4 respondents in residual categories such as "not provided or other"; these counts are not identifying |
| **CDC WONDER Natality** (2007–2024; 2016–2024 expanded) | M10 | Model results and state-rate descriptives (`data/public/m10/`) | [CDC WONDER Data Use Restrictions](https://wonder.cdc.gov/datause.html) and [Natality expanded documentation](https://wonder.cdc.gov/wonder/help/natality-expanded.html) (both reviewed November 17, 2026) | The exports are not redistributed | WONDER suggested citation (section 2) | Statistical reporting and analysis only. **No statistic representing nine or fewer births, and no rate based on such counts, may be presented.** Checked: the smallest state-by-age birth count behind any published rate is 598 |
| **NCHS natality public-use files 2024–2025; NVSR 70-2, 74-1, 75-2; Data Brief 571; VSRR 43** | M10, M11 | National birth counts and rates by single year of age (`m11_nchs_*`, reconciliation columns) | NCHS Data User Agreement (as above); [CDC use of agency materials](https://www.cdc.gov/other/agencymaterials.html) (reviewed October 28, 2026) | Record-level files are not redistributed. Published statistics are U.S. government works in the public domain | Cite NCHS; state that CDC/NCHS do not endorse the project | National aggregates only; the public-use files carry no personal identifiers |
| **Census Bureau ACS 1-year** tables B25070, B25072, B23025, B19013 (Census Data API) | M10 | State-year shares and model inputs in aggregate form | [Census Data API Terms of Service](https://www.census.gov/data/developers/about/terms-of-service.html); [Census citation guidance](https://www.census.gov/about/policies/citation.html) | Public domain (U.S. government work); modified content may not be presented as Census content | **Required notice:** "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau." | No identification of persons or households; published state-level estimates only. The API key is never stored |
| **Census Vintage 2024/2025 population estimates; 2023 National Population Projections** | M11 | Scenario births and comparisons (`m11_census_*`, `m11_fc_census_*`) | Census citation guidance (as above) | Public domain | Cite the Census Bureau | National aggregates only |
| **Third-party software** (Python packages in `requirements-lock.txt`) | All | Not redistributed; installed from PyPI | Each package's own licence | — | — | — |

Retrieval notes. The CDC and NLS pages were read through an automated fetch on 2026-11-20. The NSFG 2022–2023 documentation page contains no data-use statement or suggested citation of its own; the NCHS Data User Agreement is the governing text. The NLS citation page gives the reference format used in section 2.

## 2. Data citations

- Human Fertility Database. Max Planck Institute for Demographic Research (Germany) and Vienna Institute of Demography (Austria). Available at www.humanfertility.org (data downloaded on 20 November 2026; USA release of 2 July 2026). U.S. birth counts in the HFD come from NCHS vital statistics; population exposures are estimated by the HFD from Human Mortality Database data.
- Bureau of Labor Statistics, U.S. Department of Labor. National Longitudinal Survey of Youth 1997 cohort, 1997–2023 (rounds 1–21). Produced and distributed by the Center for Human Resource Research (CHRR), The Ohio State University. Columbus, OH: 2026.
- National Center for Health Statistics. National Survey of Family Growth, 2022-2023. Public use data file and documentation. http://www.cdc.gov/nchs/nsfg/nsfg-2022-2023-puf.htm (form suggested in the NSFG User's Guide; the address printed there was not re-checked, and on 2026-11-20 the 2022–2023 files were listed at https://www.cdc.gov/nchs/nsfg/documentation/2022-2023.html).
- Centers for Disease Control and Prevention, National Center for Health Statistics. National Vital Statistics System, Natality on CDC WONDER Online Database. Data are from the Natality Records 2016–2024, as compiled from data provided by the 57 vital statistics jurisdictions through the Vital Statistics Cooperative Program. (The 2014–2015 values come from the Natality, 2007–2024 database, whose help page gives the same citation with "Natality Records 2005–2024".)
- National Center for Health Statistics. Births: Final Data for 2019, 2023 and 2024. National Vital Statistics Reports 70(2), 74(1) and 75(2); Data Brief 571; Vital Statistics Rapid Release 43; natality public-use files 2024 and 2025.
- U.S. Census Bureau. "American Community Survey 1-Year Estimates," tables B25070, B25072, B23025 and B19013, 2014–2019 and 2021–2024, Census Data API, accessed on 20 November 2026.
- U.S. Census Bureau. Vintage 2024 and Vintage 2025 Population Estimates; 2023 National Population Projections.

Method references are in [`docs/bibliography.md`](bibliography.md).

## 3. Attribution and change notices (carried in the README)

**HFD (CC BY 4.0).** "Tables in `data/public/m11/`, the M11 figures and the README header contain extracts of estimates from the Human Fertility Database (Max Planck Institute for Demographic Research and Vienna Institute of Demography; www.humanfertility.org; data downloaded 20 November 2026; USA release 2 July 2026), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). This project changed the material: it selected years and ages, combined HFD estimates with NCHS and Census data, and computed forecasts, backtests, intervals and cohort projections from them. The HFD does not endorse this project."

**Census Data API.** "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."

**CDC/NCHS.** "Natality and NSFG data: Centers for Disease Control and Prevention, National Center for Health Statistics (NSFG figures and tables: Data Source: National Center for Health Statistics, National Survey of Family Growth, 2022-2023). The analyses, interpretations and conclusions are the author's; NCHS is responsible only for the initial data release. Their use does not imply endorsement by CDC, NCHS, HHS or the U.S. Government. The original data are available free of charge from CDC."

The frozen M09 figures do not print the suggested NSFG footer. The visual atlas captions supply it ([`docs/publication_errata.md`](publication_errata.md), E-08).

**BLS.** "This project uses NLSY97 public-use data. It is independent and is not affiliated with or endorsed by the Bureau of Labor Statistics."

## 4. Proposed licensing structure (owner authorization required)

| Material | Proposed licence | Why | Condition |
|---|---|---|---|
| Original code: `analysis/`, `audit/`, `tools/`, `tests/`, workflows and configuration | **MIT** | Permissive and widely understood; compatible with the libraries used | Copyright holder to be named by the owner |
| Original documentation: README and the project's `docs/*.md`, `audit/scientific-audit.md` | **CC BY 4.0** | Suits prose and research records; requires attribution; matches the HFD licence | As above |
| Project figures (`assets/`) | **CC BY 4.0**, with the HFD notice on M11 figures and the README header | Figures embed HFD-derived values | The HFD notice travels with them |
| Derived aggregate tables (`data/public/`) | **CC BY 4.0** for the project's contribution; each source's terms continue to apply (section 1) | Mixed sources: HFD (CC BY 4.0) and U.S. government statistics under data-use agreements | Source notices in section 3; no licence is claimed over the source data |
| Third-party material: HFD terms in `docs/source_terms/`, quoted provider wording | Not relicensed | Quoted for the record | Rights stay with their owners |
| Raw and respondent-level data | Not published | Restricted, or redistribution discouraged | Kept local |

`docs/release_inventory.csv` records the proposed licence class of every published file.

**Owner actions before release:**
1. Name the copyright holder, then add `LICENSE` (MIT) and `LICENSE-docs` (CC BY 4.0 notice), or choose different licences.
2. Confirm the notices in section 3.
3. Confirm the right to license AI-assisted work. Code and text were produced with AI assistance under the owner's direction (README, "Author contribution").

## 5. Frozen artifacts and redistribution

All 221 frozen files can be redistributed under the terms above: none contains restricted microdata, HFD input data or identifiers. No frozen artifact is excluded from the proposed release, so strict local full-data verification and the public freeze checks cover the same files. The volatile M11 run record is excluded because every run rewrites it; its frozen copy, `docs/m11_frozen_run_record.json`, is published.

## 6. Local provenance note

The local, unpublished file `data/raw/hfd_usa/provenance.json` said "data may be used for research with citation; not redistributed". On 2026-11-20 its `terms` field was updated to the verified terms (the old wording is kept as `terms_previous`); no file hash in it changed. The frozen module `analysis/m11_sources.py` still contains the old wording in `PROVENANCE_NOTES` and would write it back if the acquisition step were rerun; see [`docs/publication_errata.md`](publication_errata.md), item E-04. No result is affected.
