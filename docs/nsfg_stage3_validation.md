# NSFG 2022–2023 Stage 3 Validation

The Stage 3 work compared stated desire for children (RWANT) with stated intention (INTENT) in the 2022–2023 National Survey of Family Growth (NSFG). It was originally run as temporary scripts. This document records the 19 checks now consolidated into permanent code, together with their results, assumptions and limitations. It is a local backend record, not a publication.

**Frozen with M09 on 2026-11-20** (see `docs/nsfg_m09_freeze.sha256`).

**Status of the 19 checks (after the M09 cleanup):** 18 PASS, 1 WARN, 0 FAIL, 0 SKIP. Every recorded Stage 3 value is reproduced exactly; no expectation was changed. The CDC variance-estimation benchmark is reproduced to four decimals by the project's own implementation and, independently, by the `svy` library.

| Check | Status |
|---|---|
| 03 Intention schema | **WARN**: 5 routing exceptions, each traced; one has no documented explanation, and none affects any estimate (see Check 03) |
| 19 Sex comparisons | PASS since M09: the shared female–male design is established from the CDC sample-design documentation (see Check 19). It was WARN at Stage 4 |
| All other checks | PASS |

**M09 change log.** Check 03 now traces each exception (MARSTAT, PSTRSTAT, ADDEXP_I) and asserts that none is a divergence case. The Stage 4 statement that MARSTAT is absent from the public file was wrong (it is in both files) and has been corrected. Check 19's WARN was resolved on documentary grounds, not on numerical agreement; the separate-file comparison is kept as a sensitivity analysis. The integration test that pinned the WARN set was updated accordingly (`tests/test_nsfg_stage3.py`). The M09 chapter, which builds on these checks, is [docs/nsfg_m09.md](nsfg_m09.md).

## Reproduction

The public-use files must be saved locally, as downloaded from the CDC:

```
data/raw/nsfg_2022_2023/female/NSFG_2022_2023_FemRespPUFData.csv
data/raw/nsfg_2022_2023/male/NSFG_2022_2023_MaleRespPUFData.csv
data/raw/nsfg_2022_2023/documentation/   CDC codebooks, recode specifications, User's Guide
```

`data/` is excluded from version control. From the project root, with the project's `.venv` active:

```
python audit/nsfg_stage3_checks.py                   # all 19 checks
python audit/nsfg_stage3_checks.py --check 17        # one check; repeat --check for several
python audit/nsfg_stage3_checks.py --list            # registered checks
python -m audit.nsfg_stage3_checks --require-data    # module form; missing data is an error
python -m unittest tests.test_nsfg_stage3 -v         # NSFG tests
python -m unittest                                   # whole test suite
```

The script form and the `python -m` form behave identically. The script adds the project root to the import path itself.

**Exit codes:**
- `0`: no check failed;
- `1`: at least one check failed, or a check was skipped under `--require-data`;
- `2`: required data are missing under `--require-data`, or the arguments are invalid.

**Statuses:**

| Status | Meaning |
|---|---|
| PASS | Every executable expectation was met |
| FAIL | An expectation was not met; the mismatch is printed |
| WARN | Every expectation was met, but a stated assumption or exception needs review |
| SKIP | A dataset or dependency was missing. A missing dataset never produces PASS |

**Dependencies:**
- Checks 01–17 and 19 need only the packages in `requirements.txt`.
- Check 18 needs `svy` 0.37.0 and `polars`. They are pinned in `requirements-research.txt`, which includes `requirements.txt`, so the dashboard install is unchanged. A fresh environment built with `pip install -r requirements-research.txt` runs Check 18 to PASS. Without `svy`, Check 18 reports SKIP.
- `pytest` and Ruff are not installed or configured in this project. The tests use `unittest`, which pytest can also collect.

## Implementation

| File | Contents |
|---|---|
| `analysis/nsfg.py` | File paths and column lists, codes, the YEAR decoding, cohort definitions, the CDC INTENT rules (`reconstruct_intent`), the intention classification (`classify_intention`), weighted shares and sex contrasts |
| `analysis/survey_design.py` | Taylor linearization shared with the NLSY97 work. `linearized_domain_difference` and `design_degrees_of_freedom` were added at Stage 4, and `linearized_domain_covariance` and `adjusted_wald_test` in M09; `linearized_mean` is unchanged in behaviour |
| `audit/nsfg_stage3_checks.py` | The 19 registered checks, the recorded expectations and the command-line runner |
| `tests/test_nsfg_stage3.py` | 31 tests: synthetic unit tests, plus full-data integration tests that are skipped when the files are absent |

Only aggregate counts and estimates are printed.

## Definitions

These follow the CDC 2022–2023 recode specifications and codebooks.

- **Desire.** RWANT (female GA-1, male HA-2): wants a(nother) baby some time. 1 yes, 5 no, 8 refused, 9 don't know.
- **Intention items.**
  - JINTEND (GB-1, HB-2) is the joint question, asked of married or cohabiting respondents when neither partner is sterile.
  - INTEND (GC-1, HC-2) is the individual question, asked of other non-sterile respondents who want, or don't know whether they want, a(nother) baby.
  - Women answer 1 yes or 5 no. Men answer 1 definitely yes, 2 probably yes, 3 probably no or 4 definitely no.
- **INTENT (CDC recode).** 1 intends, 2 does not intend, 3 does not know, 4 did not provide.
  - INTENT = 2 is assigned whenever the respondent, or the current partner, is sterile (RSTRSTAT ≠ 0 or PSTRSTAT ≠ 0). The intention question is then not asked.
  - The male rule differs slightly: for an unmarried man, his own sterility gives INTENT = 2 only when INTEND is missing.
- **Ability to have children.** RSTRSTAT and PSTRSTAT give the sterility status of the respondent and the current partner: 0 not sterile, 1 surgically, 2 nonsurgically sterile. The female file also has FECUND and STRLOPER.
- **Divergence:** RWANT = 1 with INTENT = 2. Each divergent case is placed in one of three groups:
  - **explicit negative:** the respondent answered the intention question "no";
  - **sterility-linked:** the question was blank because of the respondent's or partner's sterility;
  - **unexplained:** neither of the above (none occur).

  Sterility-linked cases are **not** voluntary choices not to have children. Wanting children, intending them and being able to have them are kept distinct.
- **Gen Z age proxy.**
  - Conservative (primary): ages 18–26 if interviewed in 2022 (YEAR = 1), 18–27 in 2023 (YEAR = 2).
  - Inclusive (sensitivity): 18–27 and 18–28.

  Neither identifies birth year exactly.
- **Design.**
  - The weight is `WGT2022_2023`, with `VEST` strata (20) and `VECL` clusters (4 per stratum).
  - Variance uses Taylor linearization with clusters treated as sampled with replacement within strata. Subgroups are domains of the full design, and inference uses t with 60 design degrees of freedom.

## The 19 checks

### 01 Dataset integrity: PASS
- **Objective:** validate the dimensions of the female and male files.
- **Calculation:** rows and columns counted from the raw CSV text (`nsfg.file_dimensions`).
- **Finding:** female 5,586 × 1,912; male 4,371 × 1,157. Both match the record and the User's Guide.

### 02 Variable availability: PASS
- **Objective:** audit the demographic, fertility, sterility and design fields.
- **Variables:** AGER, YEAR, CMINTVW, RWANT, JINTEND, INTEND, INTENT, RMARIT, RSTRSTAT, PSTRSTAT, WGT2022_2023, VEST, VECL; female only, FECUND, STRLOPER and CONSTAT1.
- **Finding:** all 16 female and 13 male required columns are present. There are no blanks in age, year, INTENT or the design fields, and every weight is positive.
- **Limitation:** FECUND, STRLOPER and CONSTAT1 exist only in the female file, so male sterility is described by RSTRSTAT and PSTRSTAT alone.

### 03 Intention schema: WARN
- **Objective:** verify the individual, joint and derived intention variables and their routing.
- **Calculation:** observed codes against the codebook domains, and answers outside (or blanks inside) each question's printed universe. Each exception is then traced with questionnaire marital status (MARSTAT, AD-7b), partner sterility status (PSTRSTAT) and the ADDEXP imputation flag.
- **Finding:**
  - All codes are within the codebook domains, and no respondent answered both intention items.
  - There are 5 routing exceptions:

    | Case | Count | What the data show | Classification |
    |---|---:|---|---|
    | Cohabiting men (RMARIT = 2, MARSTAT = 2) asked INTEND instead of JINTEND | 3 | PSTRSTAT, computed in the partner section (flow check C-13), is blank for exactly these 3 of the 1,737 partnered men; CDC recodes them INTENT = 4 and imputes ADDEXP (ADDEXP_I = 1) | Routing consistent with missing partner data; CDC treats the intention as not provided. Inferred, not stated by CDC |
    | Woman in the joint universe with JINTEND blank | 1 | The whole Section G is blank, including RWANT (the codebook's single missing RWANT) | Section nonresponse; INTENT = 4 by the "not ascertained" rule |
    | Married man in the joint universe with JINTEND blank | 1 | RWANT = 5 answered, JINTEND blank, INTENT = 4 | Item nonresponse with no documented explanation |

  - MARSTAT is in both public files (the Stage 4 note said otherwise). It explains none of the 5: the printed universes give the same exceptions under MARSTAT and RMARIT.
  - **Effect on estimates:** all 5 have INTENT = 4. None is RWANT = 1 with INTENT = 2, so the divergence, explicit-negative and sterility-linked counts are unaffected; the check asserts this. The 3 men answered "yes" to INTEND, so reclassifying them by their direct answer would move at most 3 respondents from "not provided" to "positive".
  - Check 08 reproduces INTENT for every respondent, so the reconstructed classification is correct.
- **Why this is still WARN:** one case has no documented explanation, and the explanation for the three men is inferred from the data, not stated by the CDC.

### 04 Distribution analysis: PASS
- **Objective:** examine the RWANT and INTENT frequencies.
- **Finding:**
  - Female RWANT: 2,474 / 2,945 / 34 / 132 / 1 missing (codes 1 / 5 / 8 / 9 / blank).
  - Female INTENT: 1,888 / 3,593 / 88 / 17 (codes 1–4).
  - Male RWANT: 2,380 / 1,852 / 31 / 108.
  - Male INTENT: 1,978 / 2,333 / 47 / 13.

  All except male INTENT match the CDC codebook distributions.
- **Limitation:** the male codebook's INTENT frequencies could not be read from the PDF text, so male INTENT has no external comparison.

### 05 Cross-tabulation: PASS
- **Objective:** analyse RWANT × INTENT.
- **Finding:** the divergence cell (RWANT = 1, INTENT = 2) holds 581 women and 420 men, 1,001 in all, as recorded. The full tables are printed by the audit.

### 06 Age stratification: PASS (internal consistency only)
- **Objective:** investigate divergence across age groups.
- **Finding** (divergence among RWANT = 1, unweighted):

  | Age | Women | Men |
  |---|---|---|
  | 15–19 | 8.5% | 7.5% |
  | 20–24 | 11.8% | 10.3% |
  | 25–29 | 17.1% | 13.0% |
  | 30–34 | 23.5% | 18.0% |
  | 35–39 | 37.4% | 31.3% |
  | 40–50 | 65.6% | 40.6% |

  The group counts add up to the all-age totals.
- **Limitation:**
  - No age-specific Stage 3 values were recorded, so only internal consistency is tested.
  - The figures are descriptive and unweighted.
  - AGER reaches 50 for respondents who turned 50 after screening.

### 07 Interview-year decoding: PASS
- **Objective:** verify that YEAR = 1 means 2022 and YEAR = 2 means 2023.
- **Calculation:** `nsfg.interview_year` decodes YEAR and rejects any other code. Each decoded year's interview century months (CMINTVW) must fall in 1465–1476 (2022) or 1477–1488 (2023).
- **Finding:** every interview month falls in its decoded year. Counts are 1,579 / 4,007 for women and 1,454 / 2,917 for men, matching the codebooks.

### 08 CDC recode interpretation: PASS
- **Objective:** validate the official INTENT construction rules.
- **Calculation:** `nsfg.reconstruct_intent` implements the female specification (Section G recodes, pp. 93–94) and the male specification (pp. 52–53). It is compared with the released INTENT respondent by respondent.
- **Finding:** INTENT is reproduced for 5,586 of 5,586 women and 4,371 of 4,371 men.
- **Scope:** the executable test covers the rules as implemented. Reading the specification text is a manual review step and is not counted as an automated test.

### 09 All-age classification: PASS
- **Objective:** analyse the original 1,001 divergence cases.
- **Finding:**
  - Women: 303 explicit negatives and 278 sterility-linked.
  - Men: 218 explicit negatives and 202 sterility-linked.
  - None is unexplained.

### 10 Conservative Gen Z proxy: PASS
- **Objective:** reproduce the 2,429-respondent cohort.
- **Finding:**
  - 1,349 women (343 interviewed in 2022, 1,006 in 2023) and 1,080 men (320 and 760), 2,429 in all.
  - 193 divergence cases.

### 11 Blank-response audit: PASS
- **Objective:** investigate the 77 blank intention responses.
- **Calculation:** conservative cohort, RWANT = 1, INTENT = 2, with neither JINTEND nor INTEND answered.
- **Finding:**
  - 39 women: 23 neither married nor cohabiting, 5 married, 11 cohabiting.
  - 38 men: 27, 4 and 7.
  - No respondent with a blank item has INTENT = 1.

### 12 Reproductive status: PASS
- **Objective:** analyse RSTRSTAT, PSTRSTAT, FECUND and STRLOPER among the 77 cases.
- **Finding:**
  - **Women:** RSTRSTAT 0 / 1 / 2 = 5 / 5 / 29. FECUND is surgically sterile for 9 and nonsurgically sterile for 30. STRLOPER: 2 tubal, 4 partner vasectomy, 3 other female operation, 30 none.
  - **Men:** RSTRSTAT 0 / 2 = 7 / 31. Of the 11 men with a partner sterility status, 7 have a sterile partner.
  - Every female case has a sterile FECUND status (codes 1–3).

### 13 Sterility verification: PASS
- **Objective:** confirm that all 77 cases have a sterility link.
- **Finding:** 77 of 77 have RSTRSTAT ≠ 0 or PSTRSTAT ∈ {1, 2}.
  - Women: 34 own sterility, 5 partner's only.
  - Men: 31 own, 7 partner's only.

  These cases are reported as sterility-linked, never as voluntary negatives.

### 14 Boundary sensitivity: PASS
- **Objective:** compare the conservative and inclusive cohorts.
- **Finding:**

  | | Conservative | Inclusive |
  |---|---:|---:|
  | Respondents | 2,429 | 2,726 |
  | RWANT = 1 | 1,703 | 1,882 |
  | Divergence | 193 | 220 |
  | Explicit negative | 116 | 134 |
  | Sterility-linked | 77 | 86 |

  The conservative cohort is a subset of the inclusive one.

### 15 Survey weighting: PASS
- **Objective:** calculate weighted descriptive estimates.
- **Finding:**
  - The weights sum to 74,936,917.9 for women and 75,700,206.4 for men, matching the User's Guide (74.9 and 75.7 million).
  - Weighted divergence among RWANT = 1, both sexes pooled: **11.24% (SE 0.98 pp)** in the conservative cohort, and 11.28% (SE 0.96) in the inclusive cohort.
- **Assumption:** pooling the files assumes a shared design (see Check 19).

### 16 Outcome decomposition: PASS
- **Objective:** separate explicit negatives from sterility-linked cases.
- **Finding:**
  - Conservative cohort, RWANT = 1 (n 1,703): 1,491 positive, 116 explicit negative, 77 sterility-linked, 15 unknown, 4 not provided or other, 0 unexplained.
  - Weighted: **explicit 6.56% (SE 0.74)** and **sterility-linked 4.68% (SE 0.81)**. They sum exactly to the 11.24% divergence.

### 17 Taylor linearization: PASS
- **Objective:** reproduce the CDC benchmark and design-adjusted standard errors.
- **Calculation:** the project's linearization (`survey_design.linearized_mean`) applied to CDC variance estimation example 1: women currently using the pill (CONSTAT1 = 6), by AGER group.
- **Finding:**
  - Design: 20 strata, 80 clusters, 60 df; female weight sum 74,936,917.9. All match the CDC output.
  - **Ages 20–24: 18.9586% (SE 2.0226 pp, n 606)**, identical to the CDC SAS SURVEYFREQ and Stata output.
  - Ages 15–19: 14.2348% (SE 1.6792, n 730). Ages 25–29: 14.6057% (SE 1.8889, n 803).

### 18 Independent verification: PASS
- **Objective:** validate the estimates with Python's `svy` library.
- **Calculation:** `svy` 0.37.0 Taylor estimates of the CDC benchmark, the weighted shares from Checks 15–16, and the Check 19 contrasts. They are compared with the project implementation at a tolerance of 1e-9.
- **Finding:** `svy` gives 18.9586% (SE 2.0226, df 60) for the benchmark. The largest absolute difference across all estimates, SEs and p-values is 1.4e-15.
- **Requirement:** this check reports SKIP if `svy` is not installed.

### 19 Sex comparisons: PASS (WARN at Stage 4)
- **Objective:** calculate survey-design-aware female–male contrasts.
- **Calculation:** the two files are pooled with their shared VEST/VECL codes. The female-minus-male difference is linearized, with a t interval and p-value on 60 df. The independent-samples SE, √(SE_f² + SE_m²), is reported as a sensitivity analysis. The check also asserts that each file alone carries the full 20-stratum, 80-cluster design.
- **Finding:**

  | Cohort | Measure | Women | Men | Difference (SE) | 95% CI | p |
  |---|---|---:|---:|---:|---|---:|
  | Conservative | Divergence | 12.27% | 10.37% | +1.90 (2.09) | [−2.29, 6.08] | 0.3676 |
  | Conservative | Explicit negative | 7.81% | 5.50% | +2.31 (1.58) | [−0.86, 5.47] | 0.1504 |
  | Conservative | Sterility-linked | 4.46% | 4.87% | −0.41 (1.39) | [−3.18, 2.37] | 0.7703 |
  | Inclusive | Divergence | 12.38% | 10.36% | +2.01 (1.84) | [−1.68, 5.70] | 0.2794 |
  | Inclusive | Explicit negative | 8.01% | 5.47% | +2.54 (1.38) | [−0.22, 5.29] | 0.0701 |
  | Inclusive | Sterility-linked | 4.37% | 4.89% | −0.52 (1.28) | [−3.08, 2.03] | 0.6832 |

  None of the differences is statistically significant.
- **Validity of pooling (documentary basis):**
  - The 2022–2023 NSFG is one area probability sample. Within the same sampled PSUs and segments, one eligible person, female or male, was selected per screened household, with selection rates set so that 55% of interviews were with women (User's Guide, Survey and Sample Design, pp. 13–14).
  - WGT2022_2023 is "the final, fully adjusted weight that should be used in all analyses using the 2022-2023 NSFG sample of 4,371 male and 5,586 female respondents", together with VEST and VECL (2022–2023 FAQ, question 7; User's Guide p. 17).
  - The sampling variance is defined for "the NSFG sample of 9,957 respondents", who represent "150.6 million women and men" (User's Guide p. 18).
  - VEST and VECL were formed once from PSUs and segments, not by sex (Variance Estimation Report, section 2). Both files carry the identical 20 strata and 80 clusters.
  - The stacked file is therefore the full sample, each sex is a domain of it, and the pooled covariance is the design-consistent one.
- **Sensitivity (not the basis of the decision):** the pooled SEs are 0.93–1.04 times the separate-file SEs, and both give the same conclusions at the 0.05 level.
- **Remaining caveat:** the CDC publishes no worked female–male pooled example. This is a gap in the examples, not an unverified design assumption, and it does not change the status.

## Assumptions and limitations

- **The age proxy is not a birth-year definition.** Age at interview and interview year bracket birth years: the age limits correspond to birth in 1995 or later.
  - **Upper boundary:** the conservative cohort includes no one born before 1995, but can exclude 1995-born respondents interviewed after their birthday, who are 27 in 2022 or 28 in 2023. The inclusive cohort keeps all 1995-born respondents but may include some born in 1994.
  - **Lower boundary:** both cohorts exclude respondents under 18, so younger Gen Z respondents interviewed at ages 15–17 are not covered. This is a separate limitation. See [nsfg_m09.md](nsfg_m09.md), section 2.1.
- **Intention is not ability.** Sterility-linked INTENT = 2 reflects the recode rule, not a stated choice. Reports must keep sterility-linked cases separate from explicit negatives.
- **Coverage.** Descriptive estimates represent the U.S. household population aged 15–49 in 2022–2023. Unknown (15) and not-provided (4) intentions stay in the denominator as their own categories.
- **Pooled inference** rests on the shared design documented under Check 19; the separate-file analysis is a sensitivity check.
- **Routing exceptions** (Check 03) are few, traced, reproduced by the CDC recode and without effect on any estimate; one remains unexplained.
- **Documentation checks.** Comparisons with the codebooks and the CDC example rely on values transcribed from the official PDFs into `audit/nsfg_stage3_checks.py`.
- **No modelling in these checks.** The M09 classification experiment is documented in [docs/nsfg_m09.md](nsfg_m09.md).

## Sources

The documentation was downloaded to `data/raw/nsfg_2022_2023/documentation/`:
- 2022–2023 NSFG Female and Male Respondent Recode Specifications;
- the Female and Male Public Use File Codebooks;
- the User's Guide (revised July 2025).

Also used:
- [Variance Estimation Examples](https://cdc.gov/nchs/data/nsfg/varest/2022-2023-NSFG-VarEst-all.pdf): example 1 is the benchmark;
- the [Variance Estimation Report](https://www.cdc.gov/nchs/data/nsfg/NSFG-2022-2023-VarianceEstimationReport.pdf): construction of VEST and VECL;
- the [2022–2023 NSFG FAQ](https://cdc.gov/nchs/data/nsfg/guidefaqs/NSFG-2022-2023-FAQ.pdf): question 7, on using WGT2022_2023 with VEST and VECL for the sample of men and women.
