# Bibliography and citation audit

**Status:** citation audit, 2026-11-20. This closes item L-SRC-2 of the frozen [`docs/final_sources.md`](final_sources.md) ("method references ... not re-checked online"). Frozen documents are not edited; where their citations are incomplete or imprecise, the correction is in [`docs/publication_errata.md`](publication_errata.md).

**How references were checked.**
- Journal articles: the Crossref metadata API (`api.crossref.org`), matching title, authors, journal, volume, issue, pages and year, and recording the DOI.
- Government reports and data sources: the publisher's own page or document (section 3). Each source was also checked against the claim it supports in the chapters.

Citation style: APA 7.

## 1. Methodological references

| Reference | Used for (chapter) | Verified record | Supports the claim? | Status |
|---|---|---|---|---|
| Bruine de Bruin et al. (2000) | Reading "fifty-fifty" answers as expressions of uncertainty (M01–M08, methodology section 2) | Crossref: *Organizational Behavior and Human Decision Processes* 81(1), 115–131; DOI 10.1006/obhd.1999.2868 | Yes: the paper studies the use of "50%" to express epistemic uncertainty | Verified; frozen citation correct |
| Wilson (1927) | Wilson score intervals for calibration bins (M01–M08) | Crossref: *JASA* 22(158), 209–212; DOI 10.1080/01621459.1927.10502953 | Yes: origin of the score interval | Verified |
| Nadeau & Bengio (2003) | Corrected resampled t interval for repeated cross-validation (M01–M08; described as approximate for grouped folds) | Crossref: *Machine Learning* 52(3), 239–281; DOI 10.1023/A:1024068626366 | Yes; the project correctly calls its grouped-fold use approximate | Verified; frozen citation omits the issue number (E-03) |
| Korn & Graubard (1990) | Adjusted Wald F tests across groups (M09) | Crossref: *The American Statistician* 44(4), first page 270; full title "Simultaneous testing of regression coefficients with complex survey data: Use of Bonferroni t statistics"; DOI 10.2307/2684345 | Yes for the adjusted Wald test | Verified; the frozen citation shortens the title (E-02). Crossref gives only the first page; 270–276 is from the frozen citation |
| **Korn & Graubard (1998)** | Korn–Graubard confidence intervals for proportions (M09) | *Survey Methodology* 24(2), 193–201 (no DOI); confirmed from the reference list of Parker et al. (2017), reference 3 | Yes: this, not the 1990 paper, is the source of the interval | **Missing from the frozen bibliography (E-01)** |
| Parker et al. (2017) | NCHS presentation standard for proportions; suppression rules (M09) | Report PDF from cdc.gov: Vital and Health Statistics, Series 2, No. 175, August 2017; DHHS Publication No. 2017-1375; revised 1 November 2018 (page 4) and 8 April 2021 (Table II confidence-interval computation) | Yes. The project computes Korn–Graubard intervals itself and applies the standard's criteria (effective sample size, interval width and relative width), as listed in `docs/nsfg_m09.md` section 2.4. The 2021 revision corrected the interval calculations in the report's Table II and its accompanying text; whether that revision bears on any project estimate was not re-examined | Verified; no DOI printed |
| Cameron, Gelbach & Miller (2008) | Wild cluster bootstrap p-value (M10) | Crossref: *Review of Economics and Statistics* 90(3), 414–427; DOI 10.1162/rest.90.3.414 | Yes | Verified |
| Diebold & Mariano (1995) | Forecast-accuracy comparison tests (M11, descriptive only) | Crossref: *Journal of Business & Economic Statistics* 13(3), 253–263; DOI 10.1080/07350015.1995.10524599 | Yes | Verified |
| Harvey, Leybourne & Newbold (1997) | Small-sample correction of the Diebold–Mariano test (M11) | Crossref: *International Journal of Forecasting* 13(2), 281–291; DOI 10.1016/S0169-2070(96)00719-4 | Yes | Verified |
| Lee & Carter (1992) | Basis of the compositional Lee–Carter age-profile model (M11 sensitivity shape) | Crossref: *JASA* 87(419), first page 659; DOI 10.2307/2290201 | Yes as the method's origin. The project adapts it to fertility age profiles on a centred log-ratio scale, which the chapter states | Verified; Crossref gives only the first page; 659–671 is from the frozen citation |
| Brier (1950) | Brier score (all predictive chapters) | Crossref: *Monthly Weather Review* 78(1), 1–3; DOI 10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2 | Yes | Added: the measure is used throughout but was not cited |
| CDC/NCHS (2025), *2022–2023 NSFG Variance Estimation Report and Examples* | Survey design and variance estimation (M09) | Not retrieved: no local copy, and the NSFG pages were read only through an automated fetch. The NSFG User's Guide (rev. July 2025, local copy) confirms that variance-estimation examples for 2022–2023 are published with the documentation | Plausibly | **Not verified**: title and year as cited in the frozen record |

## 2. Consolidated bibliography

### Methods

- Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review, 78*(1), 1–3. https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2
- Bruine de Bruin, W., Fischhoff, B., Millstein, S. G., & Halpern-Felsher, B. L. (2000). Verbal and numerical expressions of probability: "It's a fifty-fifty chance." *Organizational Behavior and Human Decision Processes, 81*(1), 115–131. https://doi.org/10.1006/obhd.1999.2868
- Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2008). Bootstrap-based improvements for inference with clustered errors. *The Review of Economics and Statistics, 90*(3), 414–427. https://doi.org/10.1162/rest.90.3.414
- Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics, 13*(3), 253–263. https://doi.org/10.1080/07350015.1995.10524599
- Harvey, D., Leybourne, S., & Newbold, P. (1997). Testing the equality of prediction mean squared errors. *International Journal of Forecasting, 13*(2), 281–291. https://doi.org/10.1016/S0169-2070(96)00719-4
- Korn, E. L., & Graubard, B. I. (1990). Simultaneous testing of regression coefficients with complex survey data: Use of Bonferroni t statistics. *The American Statistician, 44*(4), 270–276. https://doi.org/10.2307/2684345
- Korn, E. L., & Graubard, B. I. (1998). Confidence intervals for proportions with small expected number of positive counts estimated from survey data. *Survey Methodology, 24*(2), 193–201.
- Lee, R. D., & Carter, L. R. (1992). Modeling and forecasting U.S. mortality. *Journal of the American Statistical Association, 87*(419), 659–671. https://doi.org/10.2307/2290201
- Nadeau, C., & Bengio, Y. (2003). Inference for the generalization error. *Machine Learning, 52*(3), 239–281. https://doi.org/10.1023/A:1024068626366
- Parker, J. D., Talih, M., Malec, D. J., et al. (2017). *National Center for Health Statistics data presentation standards for proportions* (Vital and Health Statistics, Series 2, No. 175; DHHS Publication No. 2017-1375). National Center for Health Statistics.
- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association, 22*(158), 209–212. https://doi.org/10.1080/01621459.1927.10502953

### Data

- Bureau of Labor Statistics, U.S. Department of Labor. (2026). *National Longitudinal Survey of Youth 1997 cohort, 1997–2023 (rounds 1–21)* [Data set]. Produced and distributed by the Center for Human Resource Research (CHRR), The Ohio State University.
- Centers for Disease Control and Prevention, National Center for Health Statistics. (2026). *Natality on CDC WONDER Online Database: Natality Records 2016–2024 (expanded) and 2007–2024* [Data set]. National Vital Statistics System. https://wonder.cdc.gov/
- Human Fertility Database. (2026). *United States, release of 2 July 2026* [Data set]. Max Planck Institute for Demographic Research and Vienna Institute of Demography. www.humanfertility.org (data downloaded 20 November 2026). CC BY 4.0.
- National Center for Health Statistics. (2024). *National Survey of Family Growth, 2022–2023: Public use data file and documentation* [Data set]. https://www.cdc.gov/nchs/nsfg/documentation/2022-2023.html
- National Center for Health Statistics. *Births: Final data for 2019*; *for 2023*; *for 2024*. National Vital Statistics Reports 70(2), 74(1), 75(2).
- National Center for Health Statistics. *Data Brief 571* and *Vital Statistics Rapid Release 43* (final 2025 births); natality public-use files 2024 and 2025.
- U.S. Census Bureau. *American Community Survey 1-year estimates*, tables B25070, B25072, B23025, B19013, 2014–2019 and 2021–2024 [Data set]. Census Data API, accessed 20 November 2026.
- U.S. Census Bureau. *Vintage 2024 and Vintage 2025 population estimates*; *2023 National Population Projections* [Data sets].

Full provider terms, required notices and dataset-specific citation wording: [`docs/licensing_and_attribution.md`](licensing_and_attribution.md).

## 3. Citation audit summary

| Check | Result |
|---|---|
| Method references verified against an authoritative record | 11 of 12, including the two added references (the NSFG variance report was not retrieved) |
| DOIs | 9 recorded; none was printed in the frozen documents |
| Incorrect citations | None found. Every verified title, journal, volume and year matches |
| Incomplete citations | Korn & Graubard (1990) title shortened; Nadeau & Bengio (2003) issue missing (cosmetic) |
| Missing citations | Korn & Graubard (1998), the source of the proportion intervals; Brier (1950), the Brier score |
| Unsupported attributions | None. The one imprecise attribution (Korn & Graubard 1990 cited for intervals) is E-01 |
| Data citations | NLSY97, CDC WONDER, NSFG and HFD wording checked against provider guidance; Census wording follows the Census citation page |
| Project metadata | [`CITATION.cff`](../CITATION.cff) describes the project as an independent research project; author name, ORCID, affiliation and DOI are left for the owner to supply |
