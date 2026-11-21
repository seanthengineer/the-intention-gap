# The Intention Gap: Methodology and Results

How accurately did women predict whether they would have a child within five years? This document describes the data, the outcome definition, the evaluation design, the results and their limitations. All results are aggregate and, unless stated otherwise, unweighted.

**Contents:** [1 Data and sample](#1-data-and-sample) · [2 The survey question](#2-the-survey-question) · [3 Five-year outcome](#3-five-year-outcome) · [4 Evaluation design](#4-evaluation-design) · [5 Results](#5-results) · [6 Robustness](#6-robustness) · [7 Survey weighting](#7-survey-weighting) · [8 Limitations](#8-limitations) · [9 Reproduction](#9-reproduction) · [10 Pregnancy and expanded histories](#10-supplementary-extract-pregnancy-and-expanded-birth-histories) · [11 Population validity](#11-population-validity-and-final-inference-audit) · [12 Out-of-period validation](#12-out-of-period-validation-pre-specified-protocol-201516-baseline) · [13 Survey design and weighting](#13-survey-design-weighting-and-population-inference)

## 1. Data and sample

The data are a public-use NLSY97 extract downloaded from NLS Investigator. The NLSY97 has followed a cohort born in 1980–1984 since 1997. Variable meanings and missing-value codes were checked against the extract's codebook. Dates use the NLSY97 continuous-month scheme (January 1980 = 1).

| Role | Variable | Reference number(s) |
|---|---|---|
| Sex | KEY!SEX (2 = female) | R0536300 |
| Fertility expectation (2009) | YFER-4861, 0–100 | T4356900 |
| Baseline interview month | CV_INTERVIEW_CMONTH, Round 13 | T3609900 |
| Follow-up interview months | CV_INTERVIEW_CMONTH, 2015 and 2017 | U0013100, U1850600 |
| Biological child birth months, 2009 | CV_CHILD_BIRTH_MONTH.01–.09 | T3603100–T3603900 |
| Biological child birth months, 2015 | CV_CHILD_BIRTH_MONTH.01–.12 | U0003200–U0004300 |
| Biological child birth months, 2017 | CV_CHILD_BIRTH_MONTH.01–.12 | U1839900–U1841000 |
| Respondent birth month and year | KEY!BDATE | R0536401, R0536402 |
| Household identifier | SIDCODE | R1193000 |
| Round 13 sampling weight | SAMPLING_WEIGHT_CC | T3613300 |
| Secondary-school grade attainment | CV_HGC_0910: highest elementary or secondary grade completed before the 2009/10 school year (5–12; 95 = ungraded) | T3606400 |
| Marital status | CV_MARSTAT_COLLAPSED, as of the 2009–10 interview | T3611100 |

`CV_HGC_0910` stops at 12th grade, so it does not distinguish high-school graduates from women with post-secondary education. Among eligible women with a value, 78.9% are at 12. The code keeps the column name `highest_grade_2009`; this document calls it secondary-school grade attainment.

**Provenance.** The extract (`intention_gap_nlsy97_v2`, 48 variables, 8,984 respondents) was created with NLS Investigator. The extract files record no release name or date. All files carry the timestamp 2026-11-17 08:09 (local time), and the raw CSV's SHA-256 hash begins `79db4479c82d80e9`. An [NLSY97 erratum posted 8/29/2025](https://nlsinfo.org/content/cohorts/nlsy97/other-documentation/errata/errata-nlsy97-round-20-release) corrected `CV_CHILD_BIRTH_MONTH` and related roster variables for "a limited number of cases". It states that the corrected values are in the current public release, and it publishes no case list. A November 2026 download should therefore include the corrections, but this is **probable, not confirmed**: neither the file timestamps nor the extract prove which release was used. For the next download, record the release shown in NLS Investigator and the download date.

**Eligibility.** Female respondents who gave a substantive expectation (0–100) in Round 13 (2009–10). Refusal (−1), don't know (−2) and non-interview (−5) are excluded. This gives **3,660 eligible women** out of 8,984 respondents (4,385 women). At baseline they were aged 24.8–30.2 (mean 27.3).

| | n | % of 3,660 |
|---|---:|---:|
| Confirmed birth within five years | 1,234 | 33.7 |
| Confirmed no birth | 2,170 | 59.3 |
| Unknown outcome | 256 | 7.0 |

The analysis sample is the **3,404 women with a confirmed outcome** (36.3% had a birth), from 3,015 households.

## 2. The survey question

The local codebook gives Round 13 item YFER-4861 (T4356900), universe "All", as:

> "In five years, what is the percent chance that you will have (a/another) child?"

The wording matches the official [Round 13 Fertility questionnaire](https://www.nlsinfo.org/sites/default/files/attachments/121129/nlsy97r13fer.html). The item has no universe restriction: every path through the section reaches it, and the answer is entered as a number. The operational target, at least one biological birth in the five years after the interview, is a reasonable but imperfect match.

| Issue | Assessment |
|---|---|
| "In five years" | Most naturally read as "within the next five years", which matches a cumulative event. A respondent could instead read it as a status five years from now. That reading gives the same answer for a birth but adds noise. |
| "Have a child" | The section opens by asking about "biological or adopted children", and its screener asks whether the respondent "had or adopted" a child, so respondents may have counted adoption. The target counts biological births only. Adoptions are rare in the NLSY97, but this cannot be checked here. |
| "(a/another)" | The fill depends on whether the respondent already has children. The questionnaire does not state the rule for choosing it, and our parity measure counts biological children only, so the two may not line up exactly. |
| Time window | The question refers to five years from the interview date. Confirmed births must fall in months *B* + 1 to *B* + 59 (section 3). Births in the boundary months are left unknown; section 6 shows they barely affect results. |
| Pregnancy at the interview | A pregnant woman could truthfully answer near 100%. This is correct use of the question, not leakage, but such an answer may partly report a pregnancy rather than an expectation. Round 13 asked women directly in the self-administered section; the supplementary extract adds those items, and section 10 analyses them. |
| Bunching at 0%, 50% and 100% | 70% of answers are exactly 0%, 50% or 100%. The 50% group has a birth rate of 33.5%, well below the stated value. Survey research has found that "fifty-fifty" answers sometimes express uncertainty rather than a considered probability (Bruine de Bruin et al., 2000), but these data cannot show what any respondent meant. The answers are evaluated as forecasts in their own right, not as precise subjective probabilities, and no claim is made about respondents' psychological confidence. |
| Item nonresponse | Women who refused or answered "don't know" are not eligible, so results apply only to women willing to give a number. |

## 3. Five-year outcome

### Window

Let *B* be the baseline interview month. Only the month is known for the interview and for each birth, so the months at either end of the window are only partly inside it.

| Birth month *b* | Treatment |
|---|---|
| *b* < *B* | Before baseline; does not qualify |
| *b* = *B* | **Baseline month.** Pre-interview if the child is already in the 2009 roster; otherwise ambiguous |
| *B* < *b* < *B* + 60 | **Qualifying birth** |
| *b* = *B* + 60 | **Anniversary month.** Ambiguous: the birth may fall before or after the fifth anniversary |
| *b* > *B* + 60 | After the window; does not qualify |

- **Confirmed birth (1):** every usable follow-up roster shows at least one qualifying birth that cannot be explained as a re-dated pre-baseline child.
- **Confirmed no birth (0):** every usable follow-up roster shows no qualifying birth, no ambiguous boundary-month birth, and no record conflict that could hide a window birth.
- **Unknown:** anything else, with one primary reason recorded.

An ambiguous birth does not block a positive when another qualifying birth is established. The qualifying window (*B* + 1 to *B* + 59) is slightly shorter than five calendar years, so positives are conservative rather than inflated.

### Missing data

A roster is **usable** when the respondent was interviewed in that round, every slot holds a birth month or a valid skip (−4), birth months fill the leading slots with no gaps, and no birth is dated after the interview.

- A valid skip (−4) in slot 1 for an interviewed respondent means no biological children: a true zero, not missing data.
- Refusal (−1), don't know (−2) and invalid skip (−3) in any slot make that round's roster incomplete. Birth dates are never imputed.
- Non-interview (−5) means the round contributes no evidence.
- A follow-up round counts only if its interview took place after *B* + 60. Every 2015 and 2017 interview (months 430–465) meets this, because the latest anniversary month is 424.
- A respondent with no usable follow-up roster is never classified as having no birth.
- If only one follow-up round is usable, it is used. A 2015 roster alone covers the whole window.
- Baseline covariates with negative NLSY97 codes are set to missing, not filled. Highest grade 95 ("ungraded") is also set to missing.

### Reconciliation across rounds

The child rosters are treated as **cumulative**: each round lists every biological child ever reported. The codebook does not state this, but the data are consistent with it: 98.8% of women usable in both 2009 and 2015 have identical pre-2009 births in both rosters, and the 2015 rosters include births from the 1990s. This remains an assumption until confirmed against NLSY97 documentation for the created fertility variables.

Slot numbers are not stable across rounds (9 slots in 2009, 12 later), so children are matched by birth month and count, never by slot. For each usable follow-up roster:

1. Pre-baseline births (plus baseline-month births matched to the 2009 roster) are compared with the 2009 roster.
2. **Missing baseline births:** if children in the 2009 roster are absent from the follow-up's pre-baseline births, they may have been re-dated into the window. Qualifying births support a positive only if they outnumber the missing children.
3. **Extra pre-baseline births:** a pre-baseline birth the 2009 roster did not have may be a misdated window birth or a 2009 omission. Either way it blocks a negative.
4. Reconciliation is by count. If the follow-up roster has the same number of pre-baseline births as the 2009 roster but some dates differ, the change is flagged and does not affect the outcome. A stricter date-matching rule is tested in section 6.
5. **When both 2015 and 2017 are usable, they must agree.** Neither round is preferred.

A respondent whose 2009 roster is unusable is unknown, because baseline-month timing and re-dating cannot be checked without it.

### Unknown outcomes

| Reason | n |
|---|---:|
| No follow-up interview in 2015 or 2017 | 219 |
| Follow-up roster(s) incomplete | 4 |
| 2009 roster unusable | 2 |
| 2015 and 2017 disagree | 2 |
| Birth-record conflict | 9 |
| Baseline-month timing | 8 |
| Anniversary-month timing | 12 |
| **Total** | **256** |

Compared with a preliminary audit using an inclusive window (1,247 positive, 2,188 negative), these rules moved 13 provisional positives and 18 provisional negatives to unknown: an anniversary-month birth only (12 positives), an unmatched baseline-month birth (8 negatives), an unexplained extra pre-baseline birth (9 negatives), and an unusable 2009 roster (one of each).

**Attrition.** A descriptive, unweighted comparison of the 256 unknown and 3,404 labelled women shows similar mean expectation (42.4 vs 41.6), age (27.6 vs 27.3), schooling and marital status. The unknown group is more often childless at baseline (51% vs 42%) and less often Black (19% vs 29%). Childlessness is strongly related to both the expectation and the outcome, so complete-case estimates may be biased. This is not a test of whether data are missing at random.

### Research file

`analysis/build_outcomes.py` writes `data/processed/intention_gap_cohort.csv`, one row per eligible woman. It is respondent-level, stays local and is excluded from version control.

| Column group | Columns | Use |
|---|---|---|
| Identifiers | `respondent_id`, `household_id` | Linkage and household-grouped splits. Never features |
| Target | `outcome` (1, 0, blank), `outcome_status`, `unknown_reason` | Label |
| Label provenance | `followup_rounds_used`, `interviewed_2015`, `interviewed_2017`, `flag_*` | Post-baseline information. Never features |
| Forecast | `expectation_prob` (0–1), `expectation_pct` | Calibration analysis |
| Baseline covariates | `age_at_baseline`, `parity_at_baseline`, `race_ethnicity`, `cross_sectional_sample`, `highest_grade_2009`, `family_income_2009`, `marital_status_2009`, `baseline_interview_cmonth` | Candidate features (2009 or earlier) |
| Weight | `sampling_weight_2009` | Round 13 cumulative-cases weight |

## 4. Evaluation design

### Stated probabilities as forecasts

The stated probability (`expectation_prob` = T4356900 / 100) is scored directly on all 3,404 labelled women, with no fitting.

- **Brier score:** mean of (*p* − *y*)², where *p* is the forecast and *y* the outcome (0 is perfect).
- **ROC AUC:** the probability that a randomly chosen woman who had a birth received a higher forecast than one who did not, with ties counted as half.
- **Calibration:** observed birth frequency within fixed ranges of stated probability (0, 1–19, 20–39, 40–49, 50, 51–69, 70–89, 90–99, 100%), with 95% Wilson intervals. Ranges were fixed before results were seen. Groups under 50 women are marked as imprecise.
- **Linear calibration slope:** the ordinary least-squares slope of the outcome (0/1) on the stated probability. 1 means perfectly calibrated; below 1 means the stated values are more extreme than the outcomes support. This is not the conventional logistic calibration slope (outcome on the logit of the forecast), which is undefined for forecasts of exactly 0 or 1. With forecasts clipped to [0.01, 0.99] the logistic slope is 0.261, and with [0.001, 0.999] it is 0.180. Both point the same way, but their size depends on the clipping.
- **Log loss:** exact 0 and 1 forecasts make log loss infinite for any miss, so it is reported after clipping to [0.01, 0.99] and [0.001, 0.999]. Brier and AUC use the unclipped probabilities.
- **Uncertainty:** 2,000 household (cluster) bootstrap resamples, because sisters in the same household are not independent.

### Predictive baselines

One fixed split: 75% of households for training and 25% for testing (`GroupShuffleSplit`, seed 1997, chosen before results were seen; no other split was tried). No household appears in both sets; this is checked in code and tests. Test set: 852 women in 754 households, 305 with a birth.

| | Approach | Inputs | Fitted on training data |
|---|---|---|---|
| A | Constant | Training birth prevalence (0.364) | Prevalence only |
| B | Stated probability | `expectation_prob` | Nothing |
| C | Logistic recalibration | `expectation_prob` | Coefficients |
| D | Logistic regression | `expectation_prob`, `age_at_baseline`, `parity_at_baseline`, `highest_grade_2009` (secondary-school grade attainment), `marital_status_2009` | Imputation, scaling, encoding, coefficients |

- Every feature must come from an approved list of baseline variables, so identifiers, label-provenance flags and follow-up information cannot enter a model.
- Missing secondary-school grade (24 training cases) is filled with the training median plus a missing indicator. Missing marital status (7 training cases) is its own category. All preprocessing sits inside a scikit-learn pipeline fitted on training data only.
- Logistic regressions use scikit-learn defaults (L2 penalty, C = 1) on standardised inputs. No tuning.
- Approaches are compared with paired bootstrap differences on the same resampled test households.

### Repeated cross-validation

This analysis is **exploratory**. It was added after the held-out results were known, to check whether the single split was representative; the held-out split remains the confirmatory evaluation. Approaches A–D were re-evaluated with 10 repeats of 5-fold `StratifiedGroupKFold` (seeds 101–110) inside the training partition only: 2,552 women in 2,261 households. The test set was not used. All preprocessing and fitting happen inside each fold. Fold scores share training data, so intervals for differences use the Nadeau–Bengio corrected resampled-t method. It is an **approximate** correction, derived for random resampling of independent observations rather than household-grouped folds:

SE = √((1/*k* + *n*<sub>validation</sub>/*n*<sub>fit</sub>) · *s*²), with *k* = 50 folds and *s*² the variance of the fold differences.

## 5. Results

### Distribution of stated probabilities

| Response | Women | Share |
|---|---:|---:|
| 0% | 1,160 | 34.1% |
| 50% | 615 | 18.1% |
| 100% | 612 | 18.0% |
| 0%, 50% or 100% | 2,387 | 70.1% |
| Any multiple of 10% | | 86.6% |
| Any multiple of 5% | | 97.3% |

Among all 3,660 eligible women the shares are almost identical (33.9%, 18.3% and 18.0%).

### Stated probabilities as forecasts

| Measure | Value | 95% CI |
|---|---:|---|
| Mean stated probability | 0.416 | |
| Observed birth frequency | 0.363 | |
| Brier score | 0.2415 | 0.2300–0.2534 |
| ROC AUC | 0.726 | 0.709–0.744 |
| Linear calibration slope | 0.476 | 0.441–0.510 |
| Log loss, clipped at 0.01 | 0.896 | |
| Log loss, clipped at 0.001 | 1.148 | |

| Stated range | n | Births | Mean stated | Observed | 95% CI |
|---|---:|---:|---:|---:|---|
| 0% | 1,160 | 213 | 0.0% | 18.4% | 16.2–20.7% |
| 1–19% | 244 | 60 | 7.2% | 24.6% | 19.6–30.4% |
| 20–39% | 240 | 69 | 25.2% | 28.8% | 23.4–34.8% |
| 40–49% † | 33 | 5 | 40.9% | 15.2% | 6.7–30.9% |
| 50% | 615 | 206 | 50.0% | 33.5% | 29.9–37.3% |
| 51–69% † | 33 | 11 | 60.9% | 33.3% | 19.8–50.4% |
| 70–89% | 309 | 138 | 77.0% | 44.7% | 39.2–50.2% |
| 90–99% | 158 | 85 | 92.2% | 53.8% | 46.0–61.4% |
| 100% | 612 | 447 | 100.0% | 73.0% | 69.4–76.4% |

† Fewer than 50 women; imprecise.

- Higher stated probabilities go with higher observed birth rates, so the answers carry real information.
- They are too extreme. Women who said 0% had a birth 18.4% of the time (213 of 1,160); women who said 100% had none 27.0% of the time (165 of 612). Above roughly 25%, stated probabilities exceed observed frequencies.
- Pooled across all women, they are about 5 percentage points too high on average (41.6% vs 36.3%). This pooled gap comes from women without children; mothers, asked about another child, underestimated on average (section 11).
- Women who said 50% had a birth 33.5% of the time; what the 50% answer meant to respondents cannot be determined from these data.

### Held-out baselines

Test set: 852 women, 305 births (35.8%).

| Approach | Mean forecast | Brier [95% CI] | Brier skill vs A | AUC [95% CI] |
|---|---:|---|---:|---|
| A. Constant | 0.364 | 0.230 [0.222, 0.239] | 0 | n/a |
| B. Stated probability | 0.408 | 0.249 [0.226, 0.271] | −0.081 | 0.708 [0.671, 0.743] |
| C. Logistic recalibration | 0.359 | 0.198 [0.185, 0.211] | +0.139 | 0.708 [0.671, 0.743] |
| D. Logistic: stated + covariates | 0.358 | 0.188 [0.175, 0.202] | +0.181 | 0.743 [0.708, 0.778] |

| Paired comparison | Brier difference [95% CI] | AUC difference [95% CI] |
|---|---|---|
| B − A | +0.019 [−0.004, +0.043] | n/a |
| C − A | −0.032 [−0.043, −0.021] | n/a |
| C − B | −0.051 [−0.063, −0.038] | 0 (same ranking) |
| D − C | −0.010 [−0.015, −0.005] | +0.035 [+0.018, +0.052] |

Clipped log loss on the test set: A 0.652; B 0.941 (ε = 0.01) or 1.227 (ε = 0.001); C 0.584; D 0.562.

- **Raw answers vs a constant (B vs A): no clear difference.** The stated probabilities rank women usefully, but their extreme values cost about as much in Brier score as the ranking gains.
- **Recalibration (C) is a clear improvement.** It keeps the same ranking, so AUC is identical, and reduces Brier score well beyond the bootstrap uncertainty. Most of the gap between the stated probabilities and a good forecast is a calibration problem, not missing information. Fitted on the training data, C maps 0% to about 17%, 50% to about 38% and 100% to about 66%.
- **Adding baseline covariates (D vs C): a modest improvement** in both accuracy and ranking. Cross-validation (below) shows the typical gain is smaller than this split suggests.
- **Coefficients describe prediction, not cause.** No coefficient should be read as the effect of age, parity, marriage or schooling on fertility.

### Repeated cross-validation

| Approach | Brier, mean (SD) | Brier range | AUC, mean (SD) |
|---|---|---|---|
| A. Constant | 0.2315 (0.0002) | 0.231–0.232 | n/a |
| B. Stated probability | 0.2391 (0.0149) | 0.199–0.274 | 0.732 (0.020) |
| C. Logistic recalibration | 0.1942 (0.0071) | 0.179–0.209 | 0.732 (0.020) |
| D. Logistic: stated + covariates | 0.1882 (0.0074) | 0.172–0.202 | 0.745 (0.021) |

| Paired difference | Mean | Approximate corrected 95% CI | Folds favouring first model |
|---|---:|---|---:|
| Brier, D − C | −0.0060 | −0.0081 to −0.0039 | 50 / 50 |
| AUC, D − C | +0.012 | +0.004 to +0.021 | 48 / 50 |
| Brier, C − B | −0.0449 | −0.0535 to −0.0363 | 50 / 50 |
| Brier, C − A | −0.0373 | −0.0446 to −0.0300 | 50 / 50 |
| Brier, B − A | +0.0076 | −0.0079 to +0.0231 | 15 / 50 |

- **Recalibration is the robust result.** C beats B and A in every fold, by margins far larger than the variation between folds.
- **B vs A: no reliable difference.** The sign changes across folds, matching the held-out result.
- **D improves on C consistently, but modestly.** The average gains (0.006 Brier, 0.012 AUC) are smaller than on the held-out split (0.010 and 0.035). The held-out AUC gain is above every fold's value, so it was probably an optimistic draw.
- **Fold counts depend on model settings.** An independent re-implementation with unpenalised logistic regression gives the same averages (−0.0058 Brier, +0.0121 AUC) but favours D in 49 of 50 folds (Brier) and 47 of 50 (AUC), so the fold counts should not be read as exact.

## 6. Robustness

### Code and data review

Each model input was recomputed from the raw extract and compared with the processed cohort.

| Check | Result |
|---|---|
| Leakage from later rounds | None. Every feature is on the approved baseline list and measured in Round 13 or earlier. |
| Negative missing-value codes | Secondary-school grade: 34 negative codes plus 2 "ungraded" (95) became missing (36). Marital status: 8. Family income: 448 (not a model feature). No feature contains a negative value. |
| Imputation and scaling | Fitted on training data only. A test confirms predictions do not change when test outcomes are altered. |
| Households in both training and test | None, in the held-out split and in every cross-validation fold. |
| Probability scale | `expectation_prob` equals `expectation_pct / 100` for all 3,660 women and matches raw T4356900 with 0 mismatches. |
| Parity, age, household ID | 0 mismatches against independent recomputation (parity range 0–8). |
| Bootstrap | Whole households resampled; comparisons paired on the same resampled households. |

No defects were found.

### Outcome-definition sensitivity

The outcome logic was rerun with alternative rules through `OutcomeRules` in `analysis/build_outcomes.py`; the defaults reproduce the primary definition exactly. An independent reconstruction (`audit/verify_outcomes.py`), which uses no project code, reproduces all 3,660 labels and unknown reasons. Two kinds of check are reported separately:

- **Rule alternatives** are defensible reclassifications of the same evidence.
- **Bounds** assign every unknown case in a group the same outcome. They show the most a group could move the results, are never treated as labels and are computed only in memory. "Ambiguous" unknowns (31) are round disagreements, record conflicts and boundary-month births; "missing-data" unknowns (225) had no usable follow-up or 2009 roster.

The calibration finding is tested with three checks set in advance: (1) the upper 95% bound of the linear calibration slope (household bootstrap, 1,000 resamples) is below 1; (2) the mean stated probability exceeds the observed rate; (3) logistic recalibration, cross-fitted by household-grouped 5-fold cross-validation (seed 211), has a lower Brier score than the raw stated probabilities.

| Scenario | Kind | Labels changed | Labelled n | Observed rate | Mean stated | Linear slope [95% CI] | Finding holds |
|---|---|---:|---:|---:|---:|---|:-:|
| Primary definition | rule | 0 | 3,404 | 0.363 | 0.416 | 0.476 [0.441, 0.510] | yes |
| Unmatched baseline-month births qualify | rule | 8 (unknown → 1) | 3,412 | 0.364 | 0.417 | 0.478 [0.442, 0.514] | yes |
| Baseline-month births never qualify | rule | 8 (unknown → 0) | 3,412 | 0.362 | 0.417 | 0.471 [0.436, 0.508] | yes |
| Anniversary-month births qualify | rule | 12 (unknown → 1) | 3,416 | 0.365 | 0.416 | 0.476 [0.439, 0.511] | yes |
| Anniversary-month births never qualify | rule | 12 (unknown → 0) | 3,416 | 0.361 | 0.416 | 0.474 [0.436, 0.509] | yes |
| Both boundary months qualify | rule | 20 (unknown → 1) | 3,424 | 0.366 | 0.417 | 0.478 [0.443, 0.514] | yes |
| Neither boundary month qualifies | rule | 20 (unknown → 0) | 3,424 | 0.360 | 0.417 | 0.469 [0.432, 0.505] | yes |
| No reconciliation with the 2009 roster | rule | 9 (unknown → 0) | 3,413 | 0.362 | 0.415 | 0.476 [0.442, 0.513] | yes |
| Disagreeing rounds resolved by 2015 | rule | 3 (unknown → 0) | 3,407 | 0.362 | 0.415 | 0.476 [0.440, 0.512] | yes |
| Disagreeing rounds resolved by 2017 | rule | 2 (unknown → 1) | 3,406 | 0.363 | 0.415 | 0.475 [0.440, 0.512] | yes |
| Strict date reconciliation of pre-baseline births | rule | 11 (4 from 1, 7 from 0 → unknown) | 3,393 | 0.363 | 0.416 | 0.477 [0.440, 0.513] | yes |
| Ambiguous unknowns all births | bound | 31 | 3,435 | 0.368 | 0.416 | 0.474 [0.439, 0.512] | yes |
| Ambiguous unknowns all non-births | bound | 31 | 3,435 | 0.359 | 0.416 | 0.470 [0.434, 0.510] | yes |
| Missing-data unknowns all births | bound | 225 | 3,629 | 0.402 | 0.416 | 0.448 [0.412, 0.486] | yes |
| Missing-data unknowns all non-births | bound | 225 | 3,629 | 0.340 | 0.416 | 0.448 [0.412, 0.486] | yes |

- No rule alternative flips a confirmed label between 1 and 0. Every boundary, reconciliation or round rule gives a label to an unknown case. The strict date rule is the only one that removes labels: it treats a re-dated pre-baseline child as both missing and extra, so 11 labelled women (4 with a birth, 7 without) become unknown. Every date difference involved is among births dated at or before the baseline month in both rosters. The rule changes no key statistic by more than 0.003, and on the held-out split C − B (−0.050) and D − C (−0.010 Brier, +0.036 AUC) are essentially unchanged. The dashboard still shows the 14 scenarios reviewed in M02.1; this one is reported here only. Preferring one round resolves the 2 women whose rounds disagree outright, plus 1 woman whose 2015 roster is negative while her 2017 roster is conflicting or ambiguous.
- Under every scenario, women who said 0% had a birth 17–23% of the time and women who said 100% did so 69–75% of the time. The linear slope stays between 0.45 and 0.48. The cross-fitted recalibration Brier (0.193–0.209) is always below the raw stated Brier (0.241–0.257).
- The weakest part is the **size of the average overestimate**: about 5 percentage points under every rule, but 1.4 points under the extreme bound in which all 225 missing-data women had a birth. Attrition could change the size of the overall bias, but not the finding that the answers are too extreme.

### Births soon after the interview (possible pregnancy at interview)

The original extract has no measure of pregnancy at the 2009–10 interview; section 10 replaces this proxy with the women's own report. As a proxy, this analysis uses how soon after the interview each confirmed birth occurred: a birth within 8 months of the interview month implies conception at or before the interview. This proxy is defined by the outcome itself. It does **not** show that a woman was pregnant when she answered, or that she knew it. The code is in `analysis/robustness_analysis.py` (`qualifying_birth_timing`, `early_birth_scenarios`, `held_out_sensitivity`).

Of the 1,234 confirmed births, the first qualifying birth came within 7, 8 and 9 months for 186, 223 and 254 women respectively. Using the 8-month threshold:

| Stated answer | Women | Births | First birth within 8 months | Share of births | Birth rate | Birth rate without those women |
|---|---:|---:|---:|---:|---:|---:|
| 0% | 1,160 | 213 | 17 | 8.0% | 18.4% | 17.1% |
| 1–49% | 517 | 134 | 5 | 3.7% | 25.9% | 25.2% |
| 50% | 615 | 206 | 13 | 6.3% | 33.5% | 32.1% |
| 51–99% | 500 | 234 | 16 | 6.8% | 46.8% | 45.0% |
| 100% | 612 | 447 | 172 | 38.5% | 73.0% | 62.5% |

Early births are concentrated among women who said 100%. Two alternative analyses bracket their influence. **Both are biased, and neither estimates the causal contribution of a known pregnancy:**

- **Exclusion** removes women whose first qualifying birth came within the threshold. It drops only pregnancies that ended in an observed live birth. Women pregnant at the interview whose pregnancy ended otherwise stay in the sample, and the remaining sample is selected on the outcome. Birth rates are therefore pushed down.
- **Later-birth outcome** keeps every woman but counts only births in months 9–59. The 124 women whose only qualifying birth was early become non-events, although a recent birth makes another birth within five years less likely. 99 early-birth women also had a later qualifying birth and remain positive.

| Analysis | n | Births | Mean stated | Observed | Birth rate at 0 / 50 / 100% | Linear slope [95% CI] | Stated Brier | Cross-fitted recalibrated Brier | AUC | Checks hold |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|:-:|
| All labelled women (primary) | 3,404 | 1,234 | 0.416 | 0.363 | 18.4 / 33.5 / 73.0% | 0.476 [0.441, 0.510] | 0.241 | 0.195 | 0.726 | yes |
| Exclude first births within 7 months | 3,218 | 1,048 | 0.387 | 0.326 | 17.7 / 33.0 / 63.6% | 0.404 [0.365, 0.443] | 0.251 | 0.195 | 0.694 | yes |
| Exclude first births within 8 months | 3,181 | 1,011 | 0.384 | 0.318 | 17.1 / 32.1 / 62.5% | 0.398 [0.359, 0.438] | 0.251 | 0.193 | 0.693 | yes |
| Exclude first births within 9 months | 3,150 | 980 | 0.381 | 0.311 | 16.7 / 31.3 / 61.4% | 0.392 [0.353, 0.431] | 0.250 | 0.192 | 0.692 | yes |
| Births in months 9–59 only | 3,404 | 1,110 | 0.416 | 0.326 | 17.6 / 32.2 / 57.5% | 0.371 [0.335, 0.410] | 0.268 | 0.198 | 0.686 | yes |

On the original held-out split (same households, models refitted on the altered training data):

| Analysis | Test n | C − B Brier [95% CI] | D − C Brier [95% CI] | D − C AUC [95% CI] | AUC of B and C | AUC of D |
|---|---:|---|---|---|---:|---:|
| Primary | 852 | −0.051 [−0.063, −0.038] | −0.010 [−0.015, −0.005] | +0.035 [+0.018, +0.052] | 0.708 | 0.743 |
| Exclude first births within 8 months | 802 | −0.061 [−0.077, −0.046] | −0.008 [−0.013, −0.004] | +0.036 [+0.016, +0.056] | 0.677 | 0.713 |
| Births in months 9–59 only | 852 | −0.074 [−0.091, −0.057] | −0.007 [−0.011, −0.003] | +0.032 [+0.013, +0.051] | 0.669 | 0.701 |

**What this means for the conclusions.**
- *Discrimination* is partly carried by births that followed soon after the interview. Without them, the stated answers' AUC falls from about 0.73 to 0.69, so part of the predictive information may reflect pregnancies already under way rather than expectations about the future.
- *Calibration:* the answers remain too extreme, and more so (linear slope 0.37–0.40).
- *Recalibration* still improves accuracy, with a larger gain.
- *Baseline characteristics (D vs C)* add a similar small gain.

None of the pre-specified checks fails under either bound.

**Direct measure.** The supplementary extract now contains the Round 13 pregnancy items. Section 10 reports the analysis based on women's own report of pregnancy at the interview, which does not depend on the outcome.

## 7. Survey weighting

**Official NLSY97 guidance** ([sample weights and design effects](https://www.nlsinfo.org/content/cohorts/nlsy97/using-and-understanding-the-data/sample-weights-design-effects), [custom weights](https://www.nlsinfo.org/content/weights/nlsy97), [custom weighting program](https://nlsinfo.org/content/weights/custom-weighting-program-documentation)):

- Round-specific weights (`SAMPLING_WEIGHT_CC`, T3613300 here) apply to that round's participants.
- Analyses that pool rounds need custom weights from the NLS custom weighting program, which can produce weights for respondents in all of the selected years, in any or all of them, or for a list of respondent IDs.
- Correct standard errors need the design variables `VSTRAT` and `VPSU`, now in the temporal extract (section 13).
- Weights do not correct for item nonresponse.

**Reportable now:** unweighted results labelled as describing the sample, and Round 13 weighted point estimates of the baseline expectation among eligible women. The mean stated probability is 41.6% unweighted and 43.9% weighted; 33.9% vs 30.6% stated 0%; 18.3% vs 19.4% stated 50%; 18.0% vs 18.7% stated 100%. Design-based standard errors are in section 13; there is no adjustment for item nonresponse.

Section 11 assesses what the current data can support. **Not yet reportable:** population-representative calibration, Brier scores or AUC. These use 2015 and 2017 outcomes, and applying the Round 13 weight to the labelled sample would not correct for later attrition.

**Plan (not started):**

1. Download `VSTRAT`, `VPSU` and the 2015 and 2017 round weights.
2. Obtain a custom longitudinal weight. The closest fit is the respondent-ID option for the 3,404 labelled women, which requires submitting public-use IDs to the NLS website and needs the project owner's approval. The alternative is "all of the selected years" for 2009, 2015 and 2017, which covers only women interviewed in all three rounds.
3. Report weighted calibration, mean stated vs observed and Brier score alongside unweighted results, with standard errors from a bootstrap that resamples `VPSU` within `VSTRAT`. Model fitting stays unweighted; weights are used for evaluation only.
4. Add an attrition check with response-propensity weights built from baseline variables.

**Status after M07 (section 13):**
- Step 1 is done for `VSTRAT`, `VPSU` and the 2015 weight.
- Step 2 is not done; it needs the owner's authorization.
- Step 3 is done as sensitivity analyses, using cross-sectional weights and a jackknife over PSUs within strata.
- Step 4 is done in sections 11 and 13.

## 8. Limitations

- **One historical cohort.** Women born 1980–1984, asked in 2009–10 at ages 25–30. These are not Gen Z results and may not transfer to other cohorts, ages or periods. The 2015–16 check (section 12) follows the same women six years later. It shows transfer over time within one cohort, not validation in an independent cohort.
- **Pregnancy at baseline.** 187 women (5.1%) reported being pregnant at the interview, and they gave 169 of the 659 answers of 100%. Among confirmed not-pregnant women the AUC is 0.694 rather than 0.726, and the linear slope is 0.405 rather than 0.476 (section 10). Pregnancy status rests on a self-administered report and is unknown for 55 women.
- **Unknown outcomes are excluded** (7.0%), mostly through attrition, and they differ from labelled women at baseline.
- **Two questions in one.** Women without children were asked about a first child and mothers about another. The pooled average overestimate comes from the childless group; mothers underestimated on average (section 11).
- **Unweighted.** Outcome-based estimates describe this sample, not U.S. women born in 1980–1984. The NLSY97 oversamples Black and Hispanic youth. The household bootstrap accounts for household clustering only; design-based standard errors (section 13) are up to about 20% larger and change no conclusion. The weighted outcome analyses in section 13 are sensitivity analyses, not population estimates. Only the baseline descriptions there are design-based.
- **Labels are not independently validated** against an external source such as vital records.
- **Month resolution.** Births in the baseline and anniversary months cannot be placed relative to the interview day; they are left unknown.
- **Biological births only.** Adoptions and step-children are not counted; pregnancies not ending in a live birth are not observed.
- **Retrospective reporting.** Window births come from rosters collected 5–8 years after baseline. The 2010, 2011 and 2013 rosters agree with them for almost all women (section 10), but every roster comes from the same survey, so consistent misreporting cannot be detected.
- **Implausible dates.** Five women have a recorded birth before age 13 (one before age 10). All are before baseline; they are flagged, not removed.
- **Topcoding.** Family income is topcoded at the 2% level (not a model feature).
- **Single independent test.** Cross-validation covers only the training partition, so the held-out set remains the only fully independent test within the 2009 analysis.
- **Untested assumptions.** The weighted sensitivity analyses assume that missing answers and missing outcomes are ignorable within adjustment cells. Worst-case bounds for the 2009 recalibration gain were not established. Model D was not evaluated on the 2015–16 baseline.

### Analyses not yet run

- Evaluation with custom longitudinal weights (sections 12 and 13), which needs the owner's authorization.
- An exploratory evaluation of model D on the 2015–16 baseline (section 12), which needs the owner's approval as a protocol deviation.
- Use of the pregnancy-outcome items (YSAQ2-326C, -326F and the pregnancy loop YSAQ2-329 to -337), which would show how pregnancies at the interview ended when no live birth followed.

## 9. Reproduction

The research pipeline needs three local NLSY97 extracts in `data/raw/`, each saved as a CSV file with its NLS Investigator codebook (`.cdb`):

| Extract | Files in `data/raw/` | Variables listed in | Needed by |
|---|---|---|---|
| Original (48 variables) | `intention_gap_nlsy97_v2.csv`, `.cdb` | `docs/extract_manifest.csv`, rows `v2` | the whole pipeline, directly or through the processed cohort; `audit.verify_outcomes` and `audit.verify_temporal` also read the codebook |
| Supplement (70 variables) | `intention_gap_nlsy97_supplement.csv`, `.cdb` | `docs/extract_manifest.csv`, rows `supplement` | `supplement_extract`, `pregnancy_status`, `expanded_histories`, `population_validity`, `temporal_validation`, `survey_design` |
| Temporal (44 variables) | `intention_gap_nlsy97_temporal.csv`, `.cdb` | `docs/temporal_extract_manifest.csv` | `temporal_validation`, `survey_design`, `audit.verify_temporal` |

Run from the project root, in this order. `expanded_histories` writes the sensitivity cohort that `population_validity` reads, and `temporal_validation --freeze` is needed only if `docs/frozen_model_parameters.json` is missing; it never overwrites the file.

```
python -m analysis.birth_history_audit      # birth-history availability audit
python -m analysis.build_outcomes           # writes data/processed/intention_gap_cohort.csv
python -m analysis.analyze_calibration      # M02 results and assets/figures/
python -m analysis.robustness_analysis      # cross-validation and sensitivity
python -m analysis.export_dashboard_data    # writes data/public/dashboard_summary.json
python -m analysis.supplement_extract       # validates and joins the supplementary extract
python -m analysis.pregnancy_status         # section 10, pregnancy at baseline
python -m analysis.expanded_histories       # section 10; writes intention_gap_cohort_expanded.csv
python -m analysis.population_validity      # section 11
python -m analysis.temporal_validation      # section 12; stops if the temporal extract is absent
python -m analysis.survey_design            # section 13
python -m unittest
```

All seeds are fixed in the code: split 1997, bootstrap 2009, cross-validation 101–110, cross-fitting 211. `python -m audit.verify_outcomes` and `python -m audit.verify_models` re-derive the labels and main statistics independently of the `analysis` package. `python -m audit.verify_temporal` does the same for section 12; it imports the `analysis` package only in its final section, to compare labels and forecasts.

### Public data

`data/public/dashboard_summary.json` is the only data file published, and `check_public_payload` in `analysis/export_dashboard_data.py` enforces these rules:

1. No respondent rows, identifiers or fitted model objects.
2. A birth count or birth rate for a subgroup is published only if the subgroup has at least 20 women. Counts of reclassified women by direction (for example, unknown to birth) are not published.
3. A count of women giving an answer or falling in a category is published only if it is at least 10. Rarer exact answers are reported only as one combined total (16 answers, 44 women). Unknown-outcome reasons with fewer than 10 women are combined into one category (25 women).
4. No individual extreme values: the age range is published in whole years.

Scenario-level statistics are rounded to three decimals. Even so, comparing whole-sample statistics across alternative outcome definitions can indicate the net reclassification of small, rule-defined groups of 2–31 women. These groups are defined by documented rules applied to public-use data, and no identifiers are published. The dashboard shows only the 14 outcome scenarios reviewed in M02.1.

## 10. Supplementary extract: pregnancy and expanded birth histories

### Data

`data/raw/intention_gap_nlsy97_supplement.csv` was downloaded from NLS Investigator (release of 23 January 2026). It has 70 variables, listed with their reference numbers in `docs/extract_manifest.csv`, which was generated from the supplement's codebook. Its contents:

- Round 13 pregnancy items YSAQ2-314, -314C, -315, -316 and -317;
- birth-month rosters and interview months for 2010 (9 slots), 2011 (9), 2013 (11) and 2019 (13);
- `CV_BIO_CHILD_HH` and `CV_BIO_CHILD_NR` for 2009–2017;
- `CVC_TTL_BIO_CHILD` (Z9085400).

The 2019 child counts and YSAQ2-318 and -319 were planned but are not in the download. `analysis.supplement_extract` joins the supplement to the original extract one-to-one on PUBID in memory: 8,984 respondents, 3,660 eligible women. The five demographic variables present in both extracts agree for every respondent. The joined data reproduce the primary cohort exactly (1,234 / 2,170 / 256). The primary cohort file is unchanged; revised labels are written to a separate local file, `data/processed/intention_gap_cohort_expanded.csv`.

### Pregnancy at the Round 13 interview

**Routing.** The supplement codebook gives the same universe for all four items: not interviewed in an insecure prison setting, ever had sexual intercourse, and female. YSAQ2-314 ("ever pregnant") goes to women with no earlier valid answer; everyone else gets YSAQ2-314C ("pregnant since the last interview, including a pregnancy current at that interview"). A "yes" to either leads to YSAQ2-315 ("Are you pregnant now?"), and a "yes" there leads to YSAQ2-316 (weeks, 1–40).

**Classification rules** (`analysis/pregnancy_status.py`, `classify_pregnancy`):
- **Pregnant:** YSAQ2-315 = 1.
- **Not pregnant:**
  - YSAQ2-315 = 0;
  - YSAQ2-314 = 0, so she has never been pregnant;
  - YSAQ2-314C = 0, so no pregnancy since the last interview, which includes now.

  In the second and third cases YSAQ2-315 is a valid skip reached by an explicit "no".
- **Unknown:**
  - refusal or don't know at any of these items;
  - a valid skip of both 314 and 314C, which means the woman did not pass the intercourse or prison gate (that gate is not in the extract);
  - any combination of codes that contradicts the routing (none occurred).

| Status | Reason | Women | % |
|---|---|---:|---:|
| Pregnant | Reported pregnant now | 187 | 5.1 |
| Not pregnant | Reported not pregnant now | 457 | 12.5 |
| Not pregnant | Never pregnant | 398 | 10.9 |
| Not pregnant | No pregnancy since last interview | 2,563 | 70.0 |
| Unknown | Refusal or don't know at 314 or 314C | 37 | 1.0 |
| Unknown | Refusal or don't know at 315 | 11 | 0.3 |
| Unknown | Skipped the pregnancy block | 7 | 0.2 |

Of the 187 pregnant women, 186 gave a number of weeks (median 23, interquartile range 14–32). One answered "don't know" and then refused the follow-up question about her last period (YSAQ2-317).

**Expectations and outcomes by status** (primary labels):

| Status | Women | Mean stated | Said 0 / 50 / 100% | Labelled | Birth rate | First birth within 8 months |
|---|---:|---:|---|---:|---:|---:|
| Pregnant | 187 | 96.1% | 1.6 / 1.6 / 90.4% | 168 | 97.6% | 154 of 164 births |
| Not pregnant | 3,418 | 38.6% | 35.6 / 19.3 / 14.0% | 3,186 | 32.8% | 63 of 1,046 births |
| Unknown | 55 | 41.8% | 38.2 / 16.4 / 23.6% | 50 | 48.0% | 6 of 24 births |

**Documented pregnancy and the early-birth proxy.** The proxy from section 6 (first qualifying birth within 8 months) identifies 223 labelled women: 154 who reported being pregnant, 63 who reported not being pregnant and 6 of unknown status. Of the 168 labelled pregnant women, 14 had no birth within 8 months: 4 had no birth in the window, and 10 had their first birth later. The proxy therefore mixes documented pregnancies with two other groups:
- births to women who did not report a pregnancy. Of the 63 confirmed not-pregnant women with an early birth, 41 gave birth 7–8 months after the interview, consistent with conception around the interview. 22 gave birth within 6 months, which would require a very early or unrecognised pregnancy at the interview, a preterm birth, misreporting or a dating error.
- the 14 pregnancies that did not end in an early recorded birth, which the proxy misses.

**Reported weeks against birth timing.** For the 163 pregnant women with valid weeks and a confirmed birth, the expected delivery month is calculated as (40 − weeks) × 7 / 30.44 months after the interview. 150 first births fall within 2 months of it, 3 earlier and 10 later; the median difference is −0.07 months. This supports the dating of both the self-report and the rosters, but both come from the same survey.

**Performance among confirmed not-pregnant women.** These are descriptive analyses on all labelled women in each group, with a household bootstrap (seed 2009) and cross-fitting (seed 211):

| Group | n | Births | Mean stated | Observed | Birth rate at 0 / 50 / 100% | Linear slope [95% CI] | Stated Brier [95% CI] | Cross-fitted constant / recalibrated Brier | AUC [95% CI] |
|---|---:|---:|---:|---:|---|---|---|---|---|
| All labelled (M02) | 3,404 | 1,234 | 0.416 | 0.363 | 18.4 / 33.5 / 73.0% | 0.476 [0.441, 0.510] | 0.241 [0.230, 0.253] | 0.231 / 0.195 | 0.726 [0.709, 0.744] |
| Confirmed not pregnant | 3,186 | 1,046 | 0.386 | 0.328 | 17.9 / 33.3 / 64.4% | 0.405 [0.366, 0.445] | 0.252 [0.240, 0.264] | 0.221 / 0.196 | 0.694 [0.675, 0.713] |
| Excluding confirmed pregnant | 3,236 | 1,070 | 0.387 | 0.331 | 18.2 / 33.3 / 64.5% | 0.406 [0.365, 0.449] | 0.252 [0.240, 0.264] | 0.221 / 0.197 | 0.694 [0.675, 0.714] |
| Pregnancy status unknown | 50 | 24 | 0.429 | 0.480 | 38.9 / 37.5 / 66.7% | 0.407 [0.078, 0.716] | 0.283 [0.184, 0.399] | 0.250 / 0.242 | 0.663 [0.502, 0.800] |
| Confirmed pregnant | 168 | 164 | 0.969 | 0.976 | too few women at 0% and 50% / 98.7% | — | 0.038 | — | — |

The Wilson 95% intervals for confirmed not-pregnant women are:
- 0%: 17.9% [15.8, 20.2] (n = 1,140);
- 50%: 33.3% [29.6, 37.1] (n = 604);
- 100%: 64.4% [59.9, 68.7] (n = 447).

The confirmed-pregnant group has only 4 women without a birth, so no slope, intervals or cross-fitting are computed for it.

**Held-out comparison** on the M02 household split (seed 1997). Women are filtered within each side, so no woman changes side:

| Analysis | Train n | Test n | Brier A / B / C / D | AUC B / D | C − B Brier [95% CI] | D − C Brier [95% CI] | D − C AUC [95% CI] |
|---|---:|---:|---|---|---|---|---|
| All labelled (M02) | 2,552 | 852 | 0.230 / 0.249 / 0.198 / 0.188 | 0.708 / 0.743 | −0.051 [−0.063, −0.038] | −0.010 [−0.015, −0.005] | +0.035 [+0.018, +0.052] |
| M02 models, not-pregnant test women | 2,552 | 807 | 0.221 / 0.259 / 0.201 / 0.192 | 0.675 / 0.712 | −0.058 [−0.073, −0.045] | −0.009 [−0.014, −0.004] | +0.037 [+0.018, +0.057] |
| Refit and test on not-pregnant women | 2,379 | 807 | 0.220 / 0.259 / 0.199 / 0.190 | 0.675 / 0.713 | −0.060 [−0.076, −0.045] | −0.009 [−0.013, −0.004] | +0.038 [+0.018, +0.059] |
| Refit and test excluding pregnant women | 2,421 | 815 | 0.221 / 0.259 / 0.199 / 0.191 | 0.677 / 0.715 | −0.059 [−0.075, −0.043] | −0.009 [−0.013, −0.004] | +0.038 [+0.018, +0.057] |

**Interpretation.**
- Among women who were not pregnant when they answered, the stated chances are still too extreme: the linear slope is 0.405, further from 1 than the full-sample 0.476. They are still too high on average (38.6% stated, 32.8% observed), and recalibration still improves accuracy.
- Discrimination is weaker without pregnant women: AUC 0.694 and 0.675 held-out, compared with 0.726 and 0.708. Part of the original discrimination came from women who already knew they were expecting a child.
- Answers of 100% from non-pregnant women were followed by a birth 64% of the time, compared with 73% for all 100% answers.
- The D − C gain from baseline characteristics is unchanged.
- These results match the early-birth bounds in section 6, which were computed without the self-report.

### Expanded birth histories

**Roster quality and implausible dates** (counts of women):

| Round | Interviewed | Usable | Missing code | Gap or unexpected value | Women with births | Birth before age 13 | Births 1 month apart | Births 2–6 months apart |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2009 | 3,660 | 3,658 | 2 | 0 | 2,104 | 3 | 0 | 1 |
| 2010 | 3,516 | 3,516 | 0 | 0 | 2,159 | 3 | 0 | 1 |
| 2011 | 3,464 | 3,464 | 0 | 0 | 2,235 | 3 | 0 | 1 |
| 2013 | 3,354 | 3,353 | 1 | 0 | 2,340 | 4 | 0 | 1 |
| 2015 | 3,324 | 3,321 | 3 | 1 | 2,465 | 4 | 0 | 1 |
| 2017 | 3,213 | 3,208 | 5 | 1 | 2,505 | 5 | 2 | 1 |
| 2019 | 3,239 | 3,231 | 8 | 1 | 2,587 | 5 | 3 | 1 |

- No roster has every slot filled, so no roster appears truncated.
- No birth is dated after the interview.
- Women with a birth before age 13 in any round: 1 confirmed positive, 3 confirmed negatives and 1 unknown.
- Women with births 1–6 months apart: 1 confirmed positive, 3 confirmed negatives and 2 unknown. Births 1 month apart may be twins born either side of a month boundary.

These dates are flagged, not corrected.

**Cross-round agreement.** Rosters are compared by date, not slot. Later births dated before the earlier interview are compared with the earlier roster. A later birth dated in the earlier interview month is matched first and otherwise ignored, because it may have occurred after that interview.

| Rounds | Both usable | Identical | Same count, re-dated | Births missing later | Earlier-dated births added later |
|---|---:|---:|---:|---:|---:|
| 2009 → 2010 | 3,514 | 3,500 | 3 | 0 | 11 |
| 2010 → 2011 | 3,408 | 3,395 | 6 | 0 | 7 |
| 2011 → 2013 | 3,279 | 3,263 | 4 | 0 | 12 |
| 2013 → 2015 | 3,204 | 3,187 | 4 | 4 | 9 |
| 2015 → 2017 | 3,092 | 3,077 | 6 | 0 | 9 |
| 2017 → 2019 | 3,042 | 3,030 | 5 | 2 | 5 |
| 2009 → 2019 | 3,229 | 3,200 | 10 | 1 | 18 |
| 2015 → 2019 | 3,081 | 3,063 | 7 | 2 | 9 |

More than 99% of pairs are identical. The usual discrepancy is a later roster adding a child dated before the earlier interview; dropped children are rare. Two re-dated children moved by more than 12 months between 2015 and 2017, and two between 2017 and 2019.

**Child counts.** `CV_BIO_CHILD_HH` + `CV_BIO_CHILD_NR` is compared with the number of children in the same round's roster. Both counts are valid skips when there are no children.

| Round | Usable roster | Missing count code | Agree | Roster larger | Roster smaller |
|---|---:|---:|---:|---:|---:|
| 2009 | 3,658 | 5 | 3,608 | 45 | 0 |
| 2010 | 3,516 | 14 | 3,456 | 46 | 0 |
| 2011 | 3,464 | 3 | 3,410 | 51 | 0 |
| 2013 | 3,353 | 9 | 3,284 | 59 | 1 |
| 2015 | 3,321 | 12 | 3,245 | 64 | 0 |
| 2017 | 3,208 | 9 | 3,132 | 66 | 1 |

The household counts describe children who are resident or non-resident at the survey date. The codebook does not say whether deceased children are included, and child mortality variables are not in the extract, so "roster larger" (1–2%) is consistent with deceased children but is not verified. A roster smaller than the living-child count (2 women: 1 positive, 1 negative) suggests a roster missing a child.

**`CVC_TTL_BIO_CHILD` (Z9085400).** The codebook defines it as children ever born, cumulative to the respondent's most recent interview. Deceased children are included and children removed from the roster by the parent are excluded. `CVC_RND`, the round of that interview, is not in the extract, and the most recent interview may be after 2019. Compared with the latest usable roster here:

| Latest usable roster | Total equals roster | Total larger | Total smaller | Skip code, empty roster |
|---|---:|---:|---:|---:|
| 2019 | 2,320 | 318 | 20 | 573 |
| Earlier round | 248 | 44 | 2 | 134 |

One woman has a missing code. No woman has a skip code with roster births. A larger total is expected for births after the latest roster here.

The variable is therefore not suitable for validating five-year outcomes:
- it carries no birth dates;
- its reference date is unknown;
- it is derived from the same rosters.

It is used only as a consistency check. A total below the 2019 roster (20 women: 10 confirmed positive, 7 confirmed negative) suggests a child removed from the roster after 2019. It was not used to change labels.

### Revised outcomes (sensitivity cohort)

**Rules** (`analysis/expanded_histories.py`, `classify_expanded`). Every roster is reconciled with the 2009 roster by `evaluate_followup_roster`, unchanged.
- **Complete rosters:** 2015, 2017 and 2019, when usable and collected after the anniversary month. They must all agree, as in the primary rule, and no round is preferred.
- **Interim rosters:** 2010, 2011 and 2013. Every interim interview (months 370–415) precedes every anniversary month (417–424), so an interim roster can show that a birth occurred but never that none did.
- **Conservative variant.** A label is withdrawn when either of these holds:
  - an interim roster conflicts with the 2009 roster;
  - the window births an interim roster records up to its interview differ from those a later roster dates in the same period.

  A woman with no complete roster is positive only if an interim roster shows a qualifying birth and none of these discrepancies exists.
- **Lenient variant.** As conservative, but window discrepancies are flagged rather than withdrawing the label.
- Both rule sets were fixed before the revised labels were inspected.

**Results.**

| | Conservative | Lenient |
|---|---:|---:|
| Labels retained | 3,375 | 3,392 |
| Labels reversed (1 ↔ 0) | 0 | 0 |
| Confirmed labels now unknown | 29 (26 positive, 3 negative) | 12 (10 positive, 2 negative) |
| Previously unknown, now resolved | 76 (41 positive, 35 negative) | 76 (41 positive, 35 negative) |
| Remains unknown | 180 | 180 |
| Usable outcomes | 3,451 (1,249 positive, 2,202 negative) | 3,468 (1,265 positive, 2,203 negative) |
| Unknown share | 5.7% | 5.2% |

The original unknown share was 7.0%.

**Why confirmed labels were withdrawn** (conservative):
- **Interim conflict with the 2009 roster: 10 (8 positive, 2 negative).** These women's 2010, 2011 or 2013 roster has a different number of pre-baseline children from the 2009 roster.
- **Window births differ across rounds: 17 (16 positive, 1 negative).** Of all 22 women with such a discrepancy:
  - in 18, a later roster dates a window birth before an interim interview whose roster lacks it;
  - in 4, an interim window birth is missing or re-dated later.

  None is explained by a shift of 2 months or less around the interim interview. The first pattern suggests an interim roster missed a birth, not that the birth fell outside the window. That is why the lenient variant keeps these labels.
- **2019 roster disagrees with 2015 and 2017: 2 positives.**

**Which unknowns were resolved.** All 76 newly resolved women belong to the 219 with no 2015 or 2017 interview:
- 59 by a 2019 roster (24 positive, 35 negative). 50 of these were also checked against at least one interim roster. 9 had no interview between 2009 and 2019, so their outcome rests on a single 10-year retrospective roster.
- 17 positives by interim rosters alone.

Their mean stated chance was 53.8%, against 40.1% for those still unknown.

**Which unknowns remain** (180):
- 144 still have no complete roster:
  - 33 were last interviewed in 2009;
  - 107 were last interviewed in 2010–2013 with no birth recorded by then, which cannot establish a negative;
  - 4 were last interviewed in 2019 with an incomplete roster.
- Other unresolved reasons:
  - anniversary-month timing (12) and baseline-month timing (10). The day of birth is not available in any round;
  - birth-record conflicts (9);
  - disagreeing rounds (2);
  - an unusable 2009 roster (2);
  - an interim conflict (1).

**Consequences** (descriptive, all labelled women):

| Labels | n | Births | Observed | Mean stated | Birth rate at 0 / 50 / 100% | Linear slope [95% CI] | Stated / cross-fitted recalibrated Brier | AUC |
|---|---:|---:|---:|---:|---|---|---|---:|
| Primary (M02) | 3,404 | 1,234 | 0.363 | 0.416 | 18.4 / 33.5 / 73.0% | 0.476 [0.441, 0.510] | 0.241 / 0.195 | 0.726 |
| Conservative expanded | 3,451 | 1,249 | 0.362 | 0.417 | 18.2 / 34.0 / 72.9% | 0.473 [0.435, 0.509] | 0.242 / 0.195 | 0.725 |
| Lenient expanded | 3,468 | 1,265 | 0.365 | 0.418 | 18.3 / 34.4 / 73.1% | 0.476 [0.440, 0.514] | 0.242 / 0.196 | 0.726 |

**Held-out split.** Households in the M02 split keep their side. Households new to the labelled sample are split once with the M02 seed and test share.

| Labels | Test n | Brier A / B / C / D | AUC B / D | C − B Brier [95% CI] | D − C Brier [95% CI] | D − C AUC [95% CI] |
|---|---:|---|---|---|---|---|
| Primary (M02) | 852 | 0.230 / 0.249 / 0.198 / 0.188 | 0.708 / 0.743 | −0.051 [−0.063, −0.038] | −0.010 [−0.015, −0.005] | +0.035 [+0.018, +0.052] |
| Conservative, M02 sample only | 847 | 0.229 / 0.248 / 0.197 / 0.187 | 0.709 / 0.744 | −0.051 [−0.064, −0.038] | −0.010 [−0.015, −0.005] | +0.035 [+0.017, +0.053] |
| Conservative, with newly resolved | 867 | 0.230 / 0.249 / 0.199 / 0.189 | 0.708 / 0.742 | −0.051 [−0.064, −0.038] | −0.010 [−0.014, −0.005] | +0.034 [+0.016, +0.051] |
| Lenient, with newly resolved | 870 | 0.230 / 0.249 / 0.199 / 0.189 | 0.708 / 0.742 | −0.050 [−0.064, −0.037] | −0.010 [−0.015, −0.005] | +0.034 [+0.017, +0.051] |
| Conservative, confirmed not pregnant | 821 | 0.220 / 0.262 / 0.200 / 0.192 | 0.671 / 0.707 | −0.062 [−0.078, −0.046] | −0.008 [−0.013, −0.003] | +0.036 [+0.015, +0.057] |

**Assessment.**
- **The primary labels are stable.** No label reverses, and 99% of labels are retained under either variant. Calibration and model comparisons move by less than 0.005.
- **The cumulative-roster assumption is supported:** more than 99% of adjacent roster pairs are identical. Interim rosters collected 1–4 years after baseline agree with the later window births for all but about 1% of women.
- **Retrospective corrections are real but rare.** They affect labels only through the 29 (conservative) or 12 (lenient) withdrawals.
- **Attrition is reduced but not removed.** 144 women still lack a complete roster, and the women resolved had higher stated chances than those still missing.
- **Agreement across rounds is consistency within one survey, not independent validation.**

## 11. Population validity and final inference audit

Code: `analysis/population_validity.py`. Results are unweighted and describe the sample unless a row says otherwise. Bootstrap intervals resample households (seed 2009).

### Reconciliation

Every total below was recomputed from the files:
- **Pregnancy status:** 187 pregnant, 3,418 not pregnant, 55 unknown.
- **Primary cohort (frozen):** 1,234 positive, 2,170 negative, 256 unknown.
- **Conservative expanded cohort:** 1,249 positive, 2,202 negative, 209 unknown. The 209 unknowns are 180 originally unknown women who remain unresolved plus 29 previously confirmed labels that became unknown (26 positive, 3 negative). The 76 resolved women all came from the original 256 unknowns, and no label reversed.

**What "more than 99% agreement" means.** It refers to pairs of rounds in which both rosters are usable. For each pair, the later roster's births dated before the earlier interview must match the earlier roster exactly. Across the eight pairs in section 10, the denominators are 3,042–3,514 women and agreement is 99.1–99.6%.

Childless women agree trivially, so the denominator restricted to women with at least one child in the earlier roster is more informative: 1,868–2,371 women per pair, with agreement of 98.8% (2009 → 2019) to 99.5%.

The interim-roster window check covers 3,565 women who have an interim roster and a later roster. 39 of them (1.1%) have a window discrepancy or a conflict with the 2009 roster.

### Selection and attrition

**Who has an unknown outcome.** Unknown minus known, with 95% household-bootstrap intervals and standardised mean differences (SMD):

| Baseline characteristic | Primary: difference [95% CI] | SMD | Conservative: difference [95% CI] | SMD |
|---|---|---:|---|---:|
| Stated chance (percentage points) | +0.8 [−4.3, +5.6] | 0.02 | −1.6 [−7.2, +4.1] | −0.04 |
| Stated 100% (share) | +0.004 [−0.044, +0.051] | 0.01 | +0.012 [−0.042, +0.064] | 0.03 |
| Age (years) | +0.26 [+0.08, +0.45] | 0.18 | +0.33 [+0.13, +0.52] | 0.23 |
| No children at baseline | +0.093 [+0.030, +0.157] | 0.19 | +0.087 [+0.019, +0.158] | 0.17 |
| Secondary-school grade | −0.03 [−0.19, +0.11] | −0.03 | −0.07 [−0.24, +0.09] | −0.06 |
| Married | +0.024 [−0.043, +0.083] | 0.05 | −0.046 [−0.115, +0.020] | −0.10 |
| Black | −0.101 [−0.150, −0.053] | −0.24 | −0.059 [−0.116, +0.001] | −0.13 |
| Non-Black, non-Hispanic | +0.088 [+0.024, +0.155] | 0.18 | +0.040 [−0.029, +0.110] | 0.08 |
| Cross-sectional sample | +0.051 [−0.001, +0.102] | 0.12 | +0.003 [−0.059, +0.061] | 0.01 |
| Reported pregnant | +0.025 [−0.004, +0.058] | 0.10 | +0.027 [−0.010, +0.065] | 0.11 |

Women with unknown outcomes stated the same chances as women with known outcomes. They were slightly older and more often childless, and in the primary cohort they were less often Black. The expanded cohort narrows the race and sample-type differences.

A logistic model of whether the outcome is known, using these baseline characteristics, predicts it only weakly: AUC 0.61 primary and 0.62 conservative when scored on the women it was fitted to (in-sample), and 0.57 for both under 5-fold cross-validation by household (10 repeats; ranges 0.56–0.59 and 0.55–0.60). None of this shows that outcomes are missing at random; it shows only that observed baseline differences are modest.

**How unknown outcomes could change the calibration findings** (primary cohort; the conservative cohort gives the same conclusions):

| Scenario | Kind | Observed | Overestimate (stated − observed) | At 0% / 100% | Linear slope |
|---|---|---:|---:|---|---:|
| Complete cases | observed | 0.363 | +0.053 | 18.4 / 73.0% | 0.476 |
| Every unknown had a birth | worst-case bound | 0.407 | +0.009 | 23.8 / 75.0% | 0.446 |
| No unknown had a birth | worst-case bound | 0.337 | +0.079 | 17.1 / 67.8% | 0.442 |
| Births only where stated chance is above its mean | bound most favourable to the slope | 0.375 | +0.041 | 17.1 / 75.0% | 0.522 |
| Births only where stated chance is at or below its mean | bound least favourable to the slope | 0.369 | +0.047 | 23.8 / 67.8% | 0.366 |
| Missing at random given baseline (model D imputation) | model-based estimate | 0.362 | +0.054 | 18.3 / 72.5% | 0.475 |
| Odds of a birth ×0.37 to ×2.72 among unknowns | model-based, departure from missing at random | 0.351–0.376 | +0.040 to +0.066 | 17.7–19.6 / 70.9–73.8% | 0.465–0.477 |
| Inverse-probability weighting | model-based estimate [95% CI] | 0.363 [0.349, 0.379] | +0.053 [+0.037, +0.069] | 18.3 / 73.3% | 0.480 [0.441, 0.513] |

**How to read the two kinds of row.** The worst-case bounds assume nothing about the unknowns, so they are not estimates. The model-based rows are plausible estimates only under their stated assumptions.

**What the bounds show.**
- No assignment of the unknown outcomes brings the linear slope near 1: the most favourable bound gives 0.522. "Too extreme" therefore does not depend on how missing outcomes fell.
- The average overestimate is positive in every scenario, but under the worst-case bound it shrinks to 0.9 percentage points. Its size depends on the missing outcomes.

**Composition and weighting.** Round 13 weights shift the eligible sample sharply:

| Group | Eligible, unweighted | Eligible, Round 13 weighted | Labelled, unweighted |
|---|---:|---:|---:|
| Non-Black, non-Hispanic | 48.9% | 70.5% | 48.2% |
| Black | 28.5% | 15.7% | 29.2% |

As an illustration only, labelled women were weighted by the Round 13 weight, and by that weight divided by the estimated probability that the outcome is known. These are point estimates without valid standard errors and are not population estimates. The results:
- linear slope 0.524 and 0.527 (unweighted 0.476);
- overestimate +0.062 (unweighted +0.053);
- observed rate at 100%: 76% (unweighted 73%).

The qualitative pattern is unchanged, but the numbers would move under a proper population analysis.

### Baseline parenthood

YFER-4861 asks, "In five years, what is the percent chance that you will have (a/another) child?" Women without children were asked about a first child and mothers about another child. These are different events with different base rates, so pooling them mixes two questions. The comparisons below are descriptive and not causal: parenthood is associated with age, marital status, pregnancy and other characteristics.

| Group (all eligible) | Women | Mean stated | Said 0 / 50 / 100% | Reported pregnant | Outcome unknown | Labelled | Births |
|---|---:|---:|---|---:|---:|---:|---:|
| No children | 1,556 | 53.1% | 16.1 / 23.3 / 21.0% | 4.3% | 8.4% | 1,426 | 463 |
| One or more children | 2,102 | 33.1% | 47.1 / 14.6 / 15.8% | 5.7% | 5.9% | 1,978 | 771 |

Two women have an unusable 2009 roster and are in neither group.

| Group (labelled) | n | Observed | Mean stated | Birth rate at 0 / 50 / 100% [Wilson 95% CI] | Linear slope [95% CI] | Stated Brier [95% CI] | Cross-fitted constant / recalibrated | AUC [95% CI] |
|---|---:|---:|---:|---|---|---|---|---|
| No children | 1,426 | 0.325 | 0.532 | 9.1 [6.0, 13.5] / 25.4 [21.0, 30.3] / 66.4 [60.9, 71.5] | 0.516 [0.457, 0.568] | 0.258 [0.241, 0.274] | 0.219 / 0.181 | 0.753 [0.726, 0.778] |
| No children, not pregnant | 1,344 | 0.292 | 0.512 | — | 0.445 [0.379, 0.505] | 0.269 [0.252, 0.287] | 0.207 / 0.180 | 0.725 [0.694, 0.754] |
| One or more children | 1,978 | 0.390 | 0.332 | 20.7 [18.2, 23.4] / 43.0 [37.3, 48.8] / 79.4 [74.6, 83.5] | 0.537 [0.488, 0.584] | 0.230 [0.214, 0.245] | 0.238 / 0.194 | 0.738 [0.716, 0.760] |
| One or more children, not pregnant | 1,842 | 0.355 | 0.295 | — | 0.479 [0.421, 0.531] | 0.238 [0.222, 0.254] | 0.229 / 0.198 | 0.708 [0.684, 0.731] |

The 0/50/100% points have 231/331/301 women without children and 929/284/311 mothers.

Held-out (M02 split and M02 models, which were fitted on the whole training partition), scored on each group's test women:

| Group | Test n | Brier A / B / C / D | AUC B / D | C − B Brier [95% CI] | D − C Brier [95% CI] | D − C AUC [95% CI] |
|---|---:|---|---|---|---|---|
| All | 852 | 0.230 / 0.249 / 0.198 / 0.188 | 0.708 / 0.743 | −0.051 [−0.063, −0.038] | −0.010 [−0.015, −0.005] | +0.035 [+0.018, +0.052] |
| No children | 367 | 0.213 / 0.262 / 0.189 / 0.172 | 0.729 / 0.756 | −0.073 [−0.095, −0.051] | −0.017 [−0.024, −0.010] | +0.028 [+0.010, +0.045] |
| One or more children | 485 | 0.243 / 0.238 / 0.205 / 0.201 | 0.733 / 0.729 | −0.034 [−0.050, −0.018] | −0.004 [−0.010, +0.003] | −0.004 [−0.029, +0.020] |

**Findings.**
- **"Too extreme" holds in both groups.** Each group's slope (0.52–0.54) is closer to 1 than the pooled 0.476. Part of the pooled miscalibration comes from mixing the groups: women without children state higher chances but give birth less often.
- **The average overestimate is a composition effect.** Women without children stated 53% and 32% had a birth. Mothers stated 33% and 39% had a birth, so on average they *underestimated*. The same reversal appears with Round 13 weights (+0.19 and −0.05). The pooled "overestimate on average" therefore depends on the share of childless women and is not a general property of the answers.
- **Each group's ranking is about as good as the pooled ranking or better** (AUC 0.75 and 0.74 against 0.73), because pooling adds between-group miscalibration rather than ranking error.
- **The gain from baseline characteristics (D − C) comes from women without children.** Among mothers it is indistinguishable from zero. Because model D includes parity, part of its pooled gain is the correction for the difference between the two questions.

### Pregnancy: target populations

The two AUCs answer different questions, and both are reported:
- **0.726** (held-out 0.708): all labelled women who answered the 2009–10 question. This is the original estimand.
- **0.694** (held-out 0.675): labelled women who reported in the self-administered section that they were not pregnant. This is closer to "expectations about future births", but self-reported non-pregnancy does not prove the biological absence of pregnancy. 22 such women gave birth within 6 months.

**Which models produced the not-pregnant held-out results** (section 10):
- **"M02 models, not-pregnant test women"** uses the M02 models, fitted on the whole M02 training partition including pregnant women. It measures how the original models perform for this subgroup. Approach A there uses the training prevalence of all women (0.36), not the subgroup's.
- **"Refit and test on not-pregnant women"** refits the models on not-pregnant training women. It measures what a model built for that population achieves.

Both use the same test women and give nearly identical results (D − C −0.009 in each). The stated-answer AUC itself (B) involves no fitting.

### Survey design and representativeness

These points come from the official NLSY97 guidance on [sample weights and design effects](https://www.nlsinfo.org/content/cohorts/nlsy97/using-and-understanding-the-data/sample-weights-design-effects) and [custom weights](https://www.nlsinfo.org/content/weights/nlsy97):

1. **Population.** The NLSY97 is "a sample of American youth born between 1980–1984". It combines a cross-sectional area-probability sample of U.S. housing units in 1997 with a supplemental oversample of Hispanic and non-Hispanic Black youths. The eligible women here are the Round 13 respondents among them who answered the expectation question.
2. **The 2009 weight.** `SAMPLING_WEIGHT_CC` (T3613300) is "a weight for everyone who participated in that particular round". It supports point estimates describing Round 13 participants, such as the distribution of stated chances. It is not corrected for item nonresponse to the expectation question, and it has no valid standard errors here.
3. **Longitudinal outcomes.** Outcomes combine 2009 with 2015, 2017 and 2019, which needs multi-year weights: "no single set of survey weights provides an accurate adjustment" for multi-year data. The custom weighting program produces them in three ways:
   - for respondents in all of the selected years;
   - for respondents in any of the selected years;
   - for a list of respondent IDs.

   The ID option requires submitting IDs and was not used. Neither year option matches the label rule exactly, because a label can come from any one of several follow-up rounds.
4. **Further selection in the labelled sample.** Beyond round participation, the labelled sample depends on:
   - answering the expectation item;
   - roster usability;
   - the outcome rules (boundary months, conflicts);
   - follow-up.

   Section 11's selection analysis shows modest but real differences in age, parenthood and race/ethnicity.
5. **VSTRAT and VPSU** are the variance stratum and the primary sampling unit (two PSUs per stratum). Design-based variance uses them, with linearisation or replication that resamples PSUs within strata. Subgroups should be analysed as domains of the full design, and strata left with a single PSU merged. The documented design effects (DEFT about 1.3–1.9) mean simple standard errors are too small by about 30–90% for those variables; for this project's baseline statistics the estimated DEFTs are 0.8–1.7 (section 13). This project's household bootstrap reflects only household clustering.
6. **Description versus prediction.** NLS guidance recommends weights for descriptive statistics and suggests not weighting regressions. Accordingly:
   - model fitting stays unweighted;
   - population-level evaluation of calibration, Brier score and AUC would use longitudinal weights with design-based variance;
   - unweighted evaluation describes performance in this sample only.

**Conclusion.** The current data cannot support valid population-level estimates of calibration or predictive performance. All headline results describe the observed cohort.

**Data needed for population estimates:**
- `VSTRAT` (R1489700) and `VPSU` (R1489800), Round 1. The owner supplied these reference numbers and confirmed them against the NLSY97 sampling documentation; they are now in the temporal extract and are used in section 13.
- A custom longitudinal weight matched to the label definition. This needs the owner's decision on the ID-list option, or acceptance of an "any of 2009, 2015, 2017" approximation.
- Optionally, `CVC_RND` and reason-for-non-interview codes for an attrition model.

### Assessment of the research claims

| Claim | Status | Basis |
|---|---|---|
| Stated probabilities carry predictive information | Supported within the observed sample | AUC 0.726 [0.709, 0.744] (held-out 0.708); 0.694 among not-pregnant women; 0.74–0.75 within each parenthood group. This is association and prediction, not causation. |
| Answers are too extreme (miscalibrated at the extremes) | Supported within the observed sample | Slope below 1 under every outcome rule, every missing-outcome bound (at most 0.522), every pregnancy and parenthood subgroup, and the weighted illustration. |
| Stated chances are too high on average | Supported with important qualifications | True for the pooled sample under every scenario, but it reverses among mothers (stated 33%, observed 39%). It shrinks to +0.9 points under the worst-case bound and depends on the share of childless women. |
| Recalibration improves accuracy | Supported within the observed sample | Held-out C − B −0.051 [−0.063, −0.038]; the improvement holds in every subgroup and modelled scenario. Respondent-specific worst-case bounds were established for the 2015–16 check (section 13), not for the 2009 held-out set. The recalibration is specific to this cohort. |
| Baseline characteristics add predictive value | Supported with important qualifications | Small (held-out D − C −0.010 Brier, +0.035 AUC). Concentrated among women without children; not distinguishable from zero among mothers; cross-validation exploratory. |
| Findings generalise to U.S. women born 1980–84 | Not established | Unweighted; no design variables or longitudinal weights; attrition selective on age, parenthood and race. |
| Findings generalise to other cohorts or to Gen Z | Not established | One historical cohort; no evidence. |
| Any causal effect of intentions on births | Not established | Observational association only; not studied. |

## 12. Out-of-period validation: pre-specified protocol (2015–16 baseline)

This protocol was fixed during M06 (November 2026), before any later outcome was examined. The 2017 and 2019 rosters are already local, but no birth after the 2015–16 interview has been tabulated. The code is in `analysis/temporal_validation.py`. The later variables listed in `docs/temporal_extract_manifest.csv` were downloaded afterwards, and the validation was then run unchanged; the results are at the end of this section.

### The later question

- **Identical wording.** Round 17 asks YFER-4861 in the same words as Round 13 (T4356900): "In five years, what is the percent chance that you will have (a/another) child?" The check YFER-FERTEXP-CHECK sends Rounds 17, 19 and 21 to it ([Round 17 fertility questionnaire](https://nlsinfo.org/sites/default/files/attachments/17036/NLSY97R17Fertility.html)). No age, sterility or partner filter comes before it.
- **Coding.** In Round 13 the universe is "All", and the values are 0–100, −1, −2 and −5. The Round 17 coding and missing codes must be confirmed from the downloaded codebook; the module prints code counts.
- **The respondents have changed.** The question is the same, but the women are six years older and more of them are mothers (table below). "Another child" therefore applies to more of them, and section 11 shows that mothers and women without children answer differently.
- **Round 19 is not usable as a baseline.** It also asks YFER-4861, but Round 21 (fielded September 2023 to September 2024) cannot cover five years from a 2019–20 interview.
- **Pregnancy at the later baseline.** The Round 17 CAPI fertility section has no current-pregnancy item. The Round 16 self-administered section (YSAQ2-315) and Round 19 (YFER-SAQ2-315) carry one, so its Round 17 location must be confirmed in NLS Investigator. If it is found, pregnancy will be described as in section 10. It does not change the primary evaluation.

### Timing

- **Baseline and anniversary.** Women were interviewed in Round 17 between October 2015 and August 2016, so their anniversaries fall between October 2020 and August 2021.
- **Interim rounds.** Every 2017 interview (October 2017 to September 2018) and every 2019 interview (September 2019 to July 2020) precedes every woman's anniversary: 0 of 3,287 women with both interviews had a 2019 interview after it. Neither round can show that no birth occurred, and the primary rule does not use them.
- **Rounds that can close the window.** Only the Round 20 (2021) and Round 21 (2023) rosters can. Each roster is used only if it is usable and the woman's interview there followed her own anniversary month.
- **No overlap with the 2009 windows.** Every 2009 window closed before any 2015 interview (0 of 3,324 women interviewed in both rounds).

### Frozen models

- **Rebuilt, not refitted on new data.** Models A–D are rebuilt by the M02 code on the same cohort, labelled sample, household split (`GroupShuffleSplit`, seed 1997, test share 0.25) and preprocessing. The training partition has 2,552 women in 2,261 households.
- **Fingerprint.** The fitted parameters are stored in `docs/frozen_model_parameters.json`: training prevalence, scaler means and scales, imputer medians, marital categories and coefficients. These are aggregate values only. Every run checks the rebuilt models against them to within 1e-8 and stops if anything differs.
- **Exact reproduction.** The rebuilt models reproduce the published held-out results exactly. Brier: A 0.2299, B 0.2485, C 0.1980, D 0.1884. AUC: 0.708 (B and C) and 0.743 (D).
- **Applied unchanged to later women:**
  - A predicts 0.364, the 2009 training prevalence;
  - B is the stated chance divided by 100;
  - C is the frozen one-variable logistic recalibration;
  - D is the frozen covariate model.
- **Model D at the later baseline.** D is scored only if every feature has a verified 2015 counterpart. Its grade feature, CV_HGC_0910, is specific to the 2009/10 school year, and no counterpart with the same definition has been verified yet. Even with one, D would be extrapolating: ages at the later baseline (30.8–36.5) lie outside the training range (24.8–30.2).

### Sample and outcomes

- **Eligibility.** Women interviewed in Round 17 who answered YFER-4861 with a value from 0 to 100. Item nonresponse and valid skips are counted and excluded.
- **Features.** Measured at the Round 17 interview and nothing later: age, number of children in a usable 2015 roster, 2015 marital status, and the grade variable if it is verified. They are fed to model D under its original column names.
- **Outcome.** The primary rules of `build_outcomes` apply unchanged, through the same `classify_outcome` function with the baseline and follow-up rounds as arguments:
  - births in months B+1 to B+59 count;
  - baseline-month and anniversary-month births are ambiguous;
  - births before baseline are reconciled with the 2015 roster by count;
  - all usable complete rosters must agree.
- **Unknown outcomes are never scored.** They are reported by reason, with worst-case bounds on the observed birth rate.

### Two settings, interpreted separately

| Setting | Who | What it measures | What it is not |
|---|---|---|---|
| A. Same cohort | All eligible labelled women. Most were in the 2009 cohort (93% of women with a usable 2015 roster), and some trained the models. | Whether forecasts built in 2009 transfer six years later within the same people. | Not independent of the training data, and not a new generation. |
| B. Households outside the training partition | Women whose household contributed nobody to the M02 training partition: 2009 test households, unlabelled 2009 households and women outside the 2009 cohort. | Transfer without re-using any training household. | Still the same cohort, survey and period. Not a new generation. |

The two settings share women, so their difference is described, not tested.

### Metrics and household-aware uncertainty

- **Primary metric:** the Brier score. The main comparisons are C − A and C − B; B − A is also reported, and D − C if D is scored. All are paired differences, with intervals from a household bootstrap (2,000 replicates, seed 2015).
- **Secondary metrics:** AUC, mean forecast versus observed rate (mean error), and the linear calibration slope, each with a household-bootstrap interval.
- **Reference values:** the M02 held-out results for C (AUC 0.708, Brier 0.198).
- **Variance.** The household bootstrap captures household clustering only. Design-based standard errors (`VSTRAT`, `VPSU`) apply to the weighted descriptions below, not to these sample-level metrics.

### Interpretation rules (fixed in the code)

1. Discrimination is retained if the lower bound of C's AUC interval is above 0.5.
2. A change in discrimination is material if C's AUC differs from 0.708 by 0.05 or more. This is descriptive only, because the populations differ.
3. Calibration-in-the-large has drifted if C's mean error is 0.05 or more in either direction. Some drift is expected: the women are older, more are mothers, and the 2009 prevalence is built into A and C. Drift would show that the frozen recalibration does not transfer. It would not show that the answers lost information.
4. Recalibration transfers if the upper bound of C − B is below 0. The frozen model beats the constant if the upper bound of C − A is below 0.
5. Nothing is refitted or recalibrated on the later outcomes. A model re-estimated on them would be a new model needing its own validation.
6. Results are reported as temporal validation within the 1980–84 cohort, never as validation in a new generation.

### What changed between the baselines

These figures use no later outcome. The Round 17 expectation answers are not downloaded yet, so the 2015 columns cover all women interviewed in 2015 with a usable 2015 roster.

| | 2009 eligible cohort | 2015, all women | 2015, of whom in the 2009 cohort |
|---|---:|---:|---:|
| Women | 3,658 | 3,573 | 3,321 |
| Mean age (range) | 27.3 (24.8–30.2) | 33.4 (30.8–36.5) | 33.4 (30.8–36.5) |
| No children | 42.5% | 26.4% | 25.9% |
| Mean number of children | 1.15 | 1.71 | 1.73 |
| Three or more children | 15.3% | 27.5% | 28.3% |

The change in birth prevalence between the periods is reported under Results below.

### Weighting decision framework

The NLS guidance on [sample weights and design effects](https://www.nlsinfo.org/content/cohorts/nlsy97/using-and-understanding-the-data/sample-weights-design-effects) says:
- a final-year weight may be used when a sample is limited to that year's respondents;
- multi-year analyses need the [custom weighting program](https://www.nlsinfo.org/content/weights/nlsy97);
- without `VSTRAT` and `VPSU`, software "will assume a simple random sample and underestimate standard errors";
- regressions are best left unweighted.

| Approach | Addresses | Does not address | Requires |
|---|---|---|---|
| 1. Unweighted, sample-level (current primary) | Valid description of the observed sample; household clustering via bootstrap | Oversampling, attrition, design variance. No population inference. | Nothing more |
| 2. Round 13 (or Round 17) cross-sectional weight, descriptions only | Oversampling and nonresponse in that round, for point estimates about that round's respondents | Item nonresponse to the expectation question; selection into outcome labels; anything longitudinal | `VSTRAT`/`VPSU` for standard errors (R1489700, R1489800; to download) |
| 3. Custom weight for respondents in all, or any, of selected years | Participation across the chosen rounds | Selection by roster usability and the outcome rules. The "all years" option drops women labelled from one round; the "any years" option includes women whose outcome is unknown. Both are approximations. | Owner's approval to use the custom weighting program (no IDs submitted); `VSTRAT`/`VPSU` |
| 4. Custom weight for the exact analytic sample | Closest match to the women actually analysed | Selection on unobserved characteristics; not designed for predictive metrics | Submitting a respondent ID list to the NLS service, which needs explicit authorization. Not done. |
| Add-on: inverse-probability weighting for unknown outcomes (section 11) | Selection on observed baseline characteristics | Selection on unobserved factors; it assumes outcomes are missing at random given the baseline characteristics | Nothing more. The response model is weak (cross-validated AUC 0.57). |

**Valid now, with no additional variables:**
- every unweighted, sample-level result;
- Round 13-weighted point estimates describing Round 13 respondents who answered the question, without standard errors.

**Once `VSTRAT` and `VPSU` are downloaded:** design-based standard errors for those weighted descriptions, and for weighted descriptions of the later baseline using the 2015 weight.

**Population-level calibration or predictive performance:** this would need option 3 or 4 together with the design variables, and still rests on assumptions about selection into outcome labels. Weighted estimates will be reported alongside the unweighted ones, never instead of them.

### Results (run after the protocol was fixed)

**Data.** The temporal extract (`data/raw/intention_gap_nlsy97_temporal.*`, 44 variables) contains every required item; the reference numbers are in `docs/temporal_extract_manifest.csv`. The models matched the stored fingerprint, and nothing was refitted. `python -m audit.verify_temporal` reproduces every number below independently: its own roster rules, model C computed from the stored coefficients by formula, and its own Brier, AUC and bootstrap code.

**Eligibility and outcomes.**
- **Eligibility.** 3,579 women were interviewed in Round 17. Of these, 95 did not give a usable answer (90 don't know, 5 refusals), leaving **3,484 eligible**.
- **Outcomes.** **734 births, 2,469 no births and 281 unknown.** The audit's labels agree with the module's for all 3,484 women.
- **Why outcomes are unknown.** In the module: 253 had no follow-up interview, 8 had a record conflict, 6 a birth in the baseline month, 6 a birth in the anniversary month, 5 an incomplete follow-up roster, and 3 had rounds that disagreed. Six women also had an unusable 2015 roster. The module reports their follow-up status first, and the audit reports the unusable roster first. Totals are identical.
- **Rosters used.** 2,931 labelled women have both follow-up rosters, 165 only 2021 and 107 only 2023.
- **Bounds on the birth rate.** Over the unknowns, the observed birth rate lies between 0.211 and 0.291.

**Dates and completeness of the follow-up rosters (eligible women).**
- **Timing.** Every 2021 interview took place 2–23 months after the woman's anniversary, and every 2023 interview 25–47 months after it. None fell on or before the anniversary.
- **Usability.** In 2021, 3,119 rosters were usable and 3 incomplete (−3 codes). In 2023, 3,060 were usable and 6 incomplete. No roster filled all 15 slots, and no birth is dated after its interview.
- **Agreement between rounds.** For 2,953 women with both rosters usable, the births up to the 2021 interview are identical in 2,940 cases; 4 have revised dates and 9 have different counts.
- **Implausible dates.** Three births per round are dated before the mother's 12th birthday. They precede the baseline, and the count-based reconciliation does not depend on their dates.

**Who is in each setting.**

| Woman's own 2009 role | Setting A (n 3,203) | Setting B (n 937) |
|---|---:|---:|
| Her 2009 outcome trained the models | 2,236 | 0 |
| Her 2009 outcome was in the M02 held-out test set | 748 | 748 |
| In the 2009 cohort, outcome unknown | 28 | 18 |
| Not in the 2009 cohort | 191 | 171 |

- **Setting B is mostly the 2009 held-out women.** No setting B household appears in the training partition. Of the 937 women, 752 are in 2009 test households (748 test women themselves, 1 woman with an unknown 2009 outcome, 3 not in the 2009 cohort), 22 are in unlabelled 2009 households, and 163 are in households outside the 2009 cohort. So setting B is mostly the 2009 held-out women, six years later. Their 2009 data never trained the models, but their 2009 held-out results had already been examined.

**Principal results (frozen models; household bootstrap, 2,000 replicates).**

| | Setting A: same cohort | Setting B: outside training households |
|---|---|---|
| Women (births; households) | 3,203 (734; 2,852) | 937 (240; 853) |
| Observed birth rate | 0.229 | 0.256 |
| Brier A / B / C | 0.1948 / 0.1567 / 0.1359 | 0.2022 / 0.1553 / 0.1385 |
| C − B | −0.0208 [−0.0263, −0.0152] | −0.0169 [−0.0277, −0.0068] |
| C − A | −0.0589 [−0.0638, −0.0538] | −0.0637 [−0.0729, −0.0540] |
| AUC (B and C identical) | 0.798 [0.779, 0.817] | 0.819 [0.785, 0.851] |
| Mean error B / C | +0.040 / +0.065 | +0.039 / +0.051 |
| Linear slope B / C | 0.58 / 1.21 | 0.62 / 1.30 |

- **Bootstrap.** The audit's own bootstrap, run with five other seeds, reproduces each interval to within 0.0005, and no replicate was dropped.
- **Pre-specified rules.** All five rules gave the same answer in both settings:
  - discrimination was retained;
  - the AUC changed materially, but **upward** (+0.090 and +0.111), so this is not a deterioration;
  - calibration-in-the-large drifted (C mean error ≥ 0.05);
  - C beat B;
  - C beat A.

**Sensitivity of C − B to the 281 unknown outcomes (setting A, all 3,484 eligible women).**

| Scenario | Kind | C − B |
|---|---|---:|
| Complete cases | observed | −0.0208 |
| Every unknown had a birth | bound | −0.0303 |
| No unknown had a birth | bound | −0.0272 |
| Each unknown given the outcome least favourable to C | bound | −0.0138 |
| Each unknown given the outcome most favourable to C | bound | −0.0438 |
| Missing at random within answer × parenthood cells | estimate (assumption) | −0.0208 |
| Same, odds of a birth ×0.5 / ×2 | estimate (assumption) | −0.0222 / −0.0201 |

The improvement of C over B survives every assignment of the unknown outcomes, including the adversarial bound.

**Interpretation.**
- **Better Brier is not better average calibration.** C's Brier score is lower than B's, yet its mean error is larger (+0.065 against +0.040). By answer category:
  - The 54% of women who said 0% had a birth 8.1% of the time. B gives them 0, which pulls B's mean error down by 0.044. C gives them 0.170, which pushes its mean error up by 0.048.
  - Above 0%, B overestimates heavily: at 100%, B says 1 and 70.5% had a birth. These positive errors cancel B's negative error at 0%, so B's average looks good.
  - C's errors are much smaller in squared terms everywhere except at 0% (0.0825 against 0.0813).
  - Over the bins of identical forecasts, resolution (0.0480) and uncertainty (0.1766) are identical for B and C. The whole Brier difference is reliability: 0.0280 for B against 0.0072 for C.
  - So C is better calibrated across the range of answers, while B's small average error comes from opposite errors cancelling.
- **Ranking versus recalibration.** C is a monotone transformation of the stated answer, so B and C rank women identically and have the same AUC. The ranking comes entirely from the stated answers; recalibration changes only the probability scale. The frozen 2009 recalibration is now **under-dispersed** (linear slope 1.21; it was built for 2009, when answers were more extreme relative to outcomes). Its floor of 0.17 at 0% is too high for women in their thirties.
- **Changes in prevalence, parenthood and age.**
  - **Prevalence.** The birth rate fell from 0.358 (2009 held-out) to 0.229, so the uncertainty term fell from 0.230 to 0.177, and Brier scores fall mechanically. Relative to uncertainty, skill still rose: B from −0.081 to +0.113, C from +0.138 to +0.231.
  - **Parenthood.** Reweighting the 2015 groups to the 2009 parenthood mix leaves Brier B at 0.170 and C at 0.141, so the change in parenthood mix explains little.
  - **Ranking within groups.** The AUC rose within both groups: without children 0.729 → 0.812, mothers 0.733 → 0.795.
  - **Most likely cause.** More women in their thirties said 0% (54% against 34%), and few of them had a birth. That is a life-stage change.
  - **Age and period cannot be separated.** Within one cohort, every woman is exactly six years older, so age and calendar period are confounded.
- **By parenthood at the 2015 interview** (setting A, frozen models, not pre-specified):

| | Without children (n 820) | Mothers (n 2,383) |
|---|---|---|
| Birth rate | 0.257 | 0.219 |
| AUC | 0.812 [0.780, 0.843] | 0.795 [0.771, 0.818] |
| Mean error B / C | +0.195 / +0.122 | −0.013 / +0.046 |
| C − B | −0.053 [−0.067, −0.040] | −0.010 [−0.015, −0.004] |

  - **Average overestimation is again concentrated among women without children.** Mothers' stated answers are close to unbiased on average.
  - **The C over B gain among mothers is small.** In setting B it is not distinguishable from zero (−0.006 [−0.016, +0.005], n 678).
- **Transfer within the cohort, not across cohorts.** The results show that stated chances given by women born in 1980–84 still rank five-year births well six years later, and that the 2009 recalibration still beats the raw answers, though it is no longer calibrated in the large. This is temporal generalization within one longitudinal cohort. The same women answer at both times, and setting B differs from A only in excluding training households. It says nothing about a new generation.

**Model D.**
- **The education variable is not a like-for-like replacement.** `CV_HGC_EVER_EDT` (U0008800) records the highest grade completed as of the 2015 survey date, including college years (13–20). `CV_HGC_0910` records the highest elementary or secondary grade completed before the 2009/10 school year (5–12).
- **A capped version almost matches.** Capped at 12, the 2015 value equals the 2009 value for 3,130 of 3,286 women with both (95.3%). It is never lower.
- **It diverges where the feature is informative.** It differs for 156 of the 699 women below grade 12 in 2009: most of them have 13 or more in 2015, which suggests a different treatment of GED holders as well as later schooling.
- **The ages are far outside the training range.** Ages at the later baseline lie 2.4–6.4 training standard deviations above the training mean, and no 2015 woman is as young as the oldest training woman.
- **Conclusion.** A capped mapping could support only an exploratory run of D, labelled as a deviation from the protocol, and even then it would measure extrapolation in age more than transfer. Model D remains unscored. Running the exploratory version needs the owner's approval.

**Survey design.**
- **The design variables are complete.** `VSTRAT` (R1489700) takes values 1–117 for all 8,984 respondents, and `VPSU` (R1489800) takes values 1–2. Every stratum has both PSUs, and every stratum keeps both PSUs among the 3,203 labelled women.
- **Weights.** The Round 17 weight is positive for every labelled woman.
- **What these support.** They allow design-based standard errors for weighted descriptions of the 2015 baseline.
- **What weighted longitudinal inference still needs:**
  - a weight for women interviewed in 2015 and in 2021 or 2023. This means options 3 or 4 of the framework above: approval to use the custom weighting program, and an ID list only with explicit authorization;
  - an assumption about selection into outcome labels beyond participation.

  Predictive metrics remain unweighted and describe the sample.

## 13. Survey design, weighting and population inference

Code: `analysis/survey_design.py`. Tests: `tests/test_survey_design.py`. No model is refitted. Model C is the frozen 2009 recalibration, checked against `docs/frozen_model_parameters.json`.

### Design variables and weights (verified)

Sources: the downloaded codebooks, and the official pages on [sample weights and design effects](https://www.nlsinfo.org/content/cohorts/nlsy97/using-and-understanding-the-data/sample-weights-design-effects), [custom weights](https://www.nlsinfo.org/content/weights/nlsy97) and the [custom weighting program](https://nlsinfo.org/node/129).

| Item | Check | Result |
|---|---|---|
| `VSTRAT` R1489700, `VPSU` R1489800 | Coverage, codes, structure | All 8,984 respondents; 117 strata (1–117); VPSU 1–2; no missing codes. Every stratum has two PSUs. PSUs hold 7–111 respondents, and at least 4 respondents in each of the 2009 and 2015 rounds. |
| `SAMPLING_WEIGHT_CC` 2009, T3613300 | Scale, zeros, total | Two implied decimals (divided by 100). Zero for exactly the 1,425 non-interviewed and positive for all 7,559 interviewed. The sum is 19,378,453, matching the published round total. Positive weights range from 866 to 18,912. |
| `SAMPLING_WEIGHT_CC` 2015, U0017100 | Scale, zeros, total | Zero for exactly the 1,881 non-interviewed and positive for all 7,103 interviewed. The sum is 19,378,454. Positive weights range from 891 to 19,804. |

**What the weights represent.** Under the cumulating-cases method, the base weight is the inverse of the summed selection probabilities of the cross-sectional and oversample. It is adjusted for screener and interview nonresponse and poststratified to national totals. Each round's weights therefore represent the population of youths born 1980–84 and living in the U.S. in 1997, as seen through that round's respondents.

**What they do not cover:**
- item nonresponse;
- anything that depends on a later round.

### Variance methods

- **Primary: stratified delete-one-PSU jackknife (JKn).**
  - There is one replicate per PSU, 234 in all. In each, that PSU's weights are set to 0 and the other PSU in its stratum is doubled.
  - The variance is $v = \sum_h \frac{n_h-1}{n_h}\sum_j(\hat\theta_{hj}-\hat\theta)^2$.
  - Every statistic, including any weight adjustment, is recomputed in each replicate.
- **Cross-check: Taylor linearization for weighted means.** It agrees with the jackknife to three decimals for every mean reported.
- **Assumptions shared by both methods:**
  - PSUs are treated as drawn with replacement within strata, and the finite-population correction is ignored;
  - subgroups are domains of the full design, so a PSU with no members of a subgroup still counts;
  - no strata needed merging.
- **DEFT** is the jackknife standard error of the weighted estimate divided by the standard error of a simple random sample of the same size, computed from the weighted variance of the item. It therefore combines the effects of unequal weighting, stratification and clustering. The NLS documentation does not state the reference behind its published DEFTs, so the two are not strictly comparable.
- **Synthetic validation (9 tests).** The tests check five properties:
  - equal weights with one unit per PSU reproduce the textbook standard error;
  - the jackknife equals linearization exactly for a total, and within 2% for a mean;
  - domain estimates use the full design;
  - weighting-class adjustments preserve cell totals;
  - in 300 repeated two-PSU samples from a clustered population, the mean linearized variance matches the empirical variance of the estimates.

### Design-based baseline estimates (verified)

These are design-based estimates for the population represented by each round's female respondents who answered YFER-4861. They describe baselines only; no outcome is involved. Item nonresponse (3.4% weighted in 2009, 2.2% in 2015) is not adjusted.

| Statistic | 2009 unweighted | 2009 weighted (SE) | DEFT | 2015 unweighted | 2015 weighted (SE) | DEFT |
|---|---:|---:|---:|---:|---:|---:|
| Mean stated chance | 41.6% | 43.9% (0.8) | 1.25 | 27.0% | 28.4% (0.8) | 1.18 |
| Answered 0% | 33.9% | 30.6% (1.0) | 1.37 | 54.2% | 52.2% (1.0) | 1.16 |
| Answered 50% | 18.3% | 19.4% (0.7) | 1.05 | 13.1% | 13.6% (0.5) | 0.82 |
| Answered 100% | 18.0% | 18.7% (0.8) | 1.18 | 11.1% | 11.6% (0.6) | 1.07 |
| No children | 42.5% | 47.1% (1.2) | 1.41 | 25.8% | 27.8% (0.9) | 1.23 |
| Mean stated, no children | 53.1% | 53.4% (1.0) | | 45.5% | 44.6% (1.2) | |
| Mean stated, mothers | 33.1% | 35.5% (1.0) | | 20.7% | 22.2% (0.9) | |
| Mothers minus no children (points) | −20.0 | −17.9 (1.4) | | −24.8 | −22.5 (1.4) | |
| Black / Hispanic | 28.5% / 21.7% | 15.7% / 12.4% | | 28.3% / 21.4% | 15.2% / 12.2% | |
| Item nonresponse | 3.0% | 3.4% (0.5) | 1.72 | 2.7% | 2.2% (0.3) | 1.18 |

**How weighting changes the picture:**
- **Oversampling.** Weighting mainly undoes the oversample: Black and Hispanic women fall from about half of the sample to about 28%.
- **Expectations.** Weighted expectations are 1.3–2.3 points higher, and the weighted share of childless women is 2–5 points higher.
- **Ranking of groups.** The ordering of groups and the large gap between mothers and childless women are unchanged.
- **Design effects.** For these statistics they range from 0.8 to 1.7 (DEFT as defined above), mostly below the 1.30–1.86 documented for other NLSY97 variables.

### Longitudinal weighting: options and requirements

| Approach | Primary cohort (2009 baseline; outcome from 2015 or 2017) | Temporal cohort (2015 baseline; outcome from 2021 or 2023) | What it does not address |
|---|---|---|---|
| Round-specific cross-sectional weight | Available (2009). Represents 2009–10 respondents, not women followed to an outcome. | Available (2015). Same limitation. | Attrition after the baseline; missing outcome labels; item nonresponse |
| Custom weight, respondents in **all** of the selected years | 2009 + 2015 + 2017: 3,096 of 3,660 eligible women interviewed in all three, 3,065 of them labelled. Drops 339 labelled women interviewed in only one follow-up round. | 2015 + 2021 + 2023: 2,957 eligible and 2,932 labelled women. Drops 271 labelled women. | Roster usability and the outcome rules; item nonresponse; women labelled from a single follow-up |
| Custom weight, respondents in **any or all** of the selected years | Includes people never interviewed in 2009, who cannot be eligible. It does not match the cohort. | The same mismatch. | As above, plus the mismatch |
| Custom weight for the **exact analytic sample** (ID list) | 3,404 labelled women | 3,203 labelled women | Selection on unobserved characteristics. The program only re-poststratifies base-year weights in cells of at least 20, so it reweights *who was labelled* to population totals but cannot know why labels are missing. |
| Additional adjustment for missing labels | Weighting-class adjustment (below) or response propensity (section 11) | Same | Assumes labels are missing at random within the adjustment cells |

**Which option fits each cohort.** For both cohorts, the closest match is the ID-list weight, then the "all selected years" weight with the single-follow-up women analysed as a sensitivity check. The ID-list option requires pasting public-use IDs into the NLS website, which needs the owner's explicit authorization. It has not been used, and no custom weight has been requested.

**Requirements for any custom-weight analysis:**
1. The owner's written authorization for the specific option, and for submitting IDs if the ID list is chosen.
2. The exact list or year selection: 2009, 2015 and 2017 for the primary cohort; 2015, 2021 and 2023 for the temporal cohort.
3. The returned file is saved under `data/raw/` and joined on PUBID in memory, as with the extracts. Its two implied decimals are removed.
4. Variance comes from the same jackknife over `VSTRAT`/`VPSU`, with the custom weights treated as fixed. The program's poststratification cannot be replicated, so the standard errors are slightly conservative or anticonservative in unknown direction.
5. The results are reported beside the unweighted and cross-sectionally weighted results, never instead of them.

**Selection assumptions no weight can remove:**
- the expectation item is missing at random (about 3%);
- outcome labels are missing at random given the weighting cells, for the 7–8% unknown in each cohort;
- baseline nonresponse and attrition are ignorable within the NLS adjustment cells;
- the 1997 sampling frame defines the population. Immigrants who arrived after 1997 are not represented.

### Exploratory longitudinal sensitivity (not design-based)

**None of the results in this subsection is a design-based population estimate.** The only verified design-based estimates in this section are the baseline descriptions above.
- **The weighted rows** apply each cohort's baseline cross-sectional weight to women with outcome labels. That cannot correct for attrition after baseline.
- **The adjusted rows** add a weighting-class adjustment for missing labels, built from cells of answer category × parenthood × race group and collapsed when a cell holds fewer than 20 labelled women. They assume labels are missing at random within those cells.
- **Standard errors** come from the jackknife and include re-estimation of the adjustment.
- **Recalibration** (C − B) is judged on the 852 held-out women in 2009, and on all labelled women in 2015.

**Two kinds of assignment for unknown outcomes.** Both keep the eligible cohort, the frozen forecasts and the weights fixed.
- **Uniform assignment** gives every unknown the same outcome, all births or no births. It bounds a statistic only if every unknown moves that statistic in the same direction when given a birth. That holds for averages within fixed groups, such as the observed rate, the overestimate within a parenthood group, and the birth rate after 0% or 100%. It fails for statistics where unknowns pull in opposite directions: the gap between mothers and childless women, the linear slope, and the Brier difference C − B.
- **Respondent-specific bounds** choose each unknown's outcome separately, to give the smallest or largest possible value. Every statistic here is a sum of per-woman terms over fixed denominators, so each unknown shifts it by its own amount, and the bounds collect every negative or every positive shift. They are the true worst cases. The code checks this additivity on each run, and a test confirms the bounds against exhaustive enumeration.

| | 2009 unweighted (SE) | 2009 weighted + adjusted (SE) | 2009 bounds, weighted | 2015 unweighted (SE) | 2015 weighted + adjusted (SE) | 2015 bounds, weighted |
|---|---|---|---|---|---|---|
| Average overestimate | +0.053 (0.008) | +0.063 (0.009) | +0.014 to +0.089 | +0.040 (0.007) | +0.043 (0.008) | **−0.021** to +0.064 |
| Overestimate, no children | +0.207 (0.012) | +0.190 (0.013) | +0.130 to +0.218 | +0.195 (0.014) | +0.170 (0.013) | +0.102 to +0.199 |
| Overestimate, mothers | −0.058 (0.010) | −0.050 (0.011) | −0.089 to −0.025 | −0.013 (0.008) | −0.006 (0.010) | −0.067 to +0.013 |
| Mothers minus no children | −0.265 (0.015) | −0.240 (0.017) | −0.307 to −0.155 | −0.208 (0.016) | −0.176 (0.016) | −0.265 to −0.089 |
| Birth rate after 0% | 0.184 (0.011) | 0.176 (0.012) | 0.164 to 0.239 | 0.081 (0.007) | 0.073 (0.008) | 0.067 to 0.151 |
| Birth rate after 100% | 0.730 (0.019) | 0.761 (0.020) | 0.708 to 0.778 | 0.705 (0.025) | 0.749 (0.023) | 0.681 to 0.769 |
| Linear slope | 0.476 (0.020) | 0.523 (0.023) | 0.401 to 0.569 | 0.579 (0.020) | 0.627 (0.020) | 0.468 to 0.676 |
| C − B (Brier) | −0.051 (0.008) | −0.044 (0.009) | **not established** | −0.021 (0.003) | −0.015 (0.003) | −0.040 to −0.008 |

**Correction to the first version of this table.** It reported uniform assignments as bounds. For the three statistics where unknowns pull in opposite directions, the uniform values fall inside the true bounds:

| Statistic | Uniform assignments (weighted) | Respondent-specific bounds (weighted) |
|---|---|---|
| Mothers minus no children, 2009 | −0.243 to −0.218 | −0.307 to −0.155 |
| Mothers minus no children, 2015 | −0.186 to −0.168 | −0.265 to −0.089 |
| Linear slope, 2009 | 0.481 to 0.488 | 0.401 to 0.569 |
| Linear slope, 2015 | 0.566 to 0.578 | 0.468 to 0.676 |
| C − B, 2015 | −0.025 to −0.023 | −0.040 to −0.008 |

For the other statistics, the uniform values are the true bounds.

**C − B in 2015, weighted and unweighted.** Respondent-specific bounds over all 3,484 eligible women give:
- weighted: −0.040 to −0.008;
- unweighted: −0.044 to −0.014, the same as the M06.1 bounds.

Weighting narrows the margin, but no assignment of the 281 unknown outcomes makes C worse than B.

**C − B in 2009: bounds not established.** The held-out set was drawn by splitting the households of *labelled* women, so the held-out population cannot be defined without using the missing labels. Of the 256 unlabelled women:
- 214 live in households with no labelled woman, and so were never assigned to either side;
- 32 live in training households;
- 10 live in held-out households.

Including any of them would mean redefining the evaluation population after seeing which labels are missing.

The cross-sectional weight without the adjustment gives almost the same values as with it (for example +0.062 and +0.042). The standard errors in the unweighted columns are design-based (jackknife with equal weights). They are up to about 20% larger than the household-bootstrap standard errors reported earlier, and no earlier conclusion changes.

**What the sensitivity analyses show:**
- **Too extreme: robust.** Under every weighting and every bound, births follow 0% answers 7–24% of the time and 100% answers only 68–78% of the time. The slope stays between 0.40 and 0.68 (weighted), or 0.37 and 0.63 (unweighted).
- **Recalibration improves accuracy: robust where it can be bounded.** In 2015, C − B is negative under every scenario and every respondent-specific assignment. In 2009 the estimates are negative, but worst-case bounds were not established.
- **Mothers differ from childless women: robust in direction.** Mothers' average overestimate is smaller than childless women's under every scenario and every assignment. The gap is 9–31 points across the bounds, against 17–26 points in the point estimates.
- **Average overestimation is pooled and fragile.**
  - In 2009 it stays positive under every scenario, but falls to +0.014 under the bound.
  - In 2015 its sign depends on the missing outcomes (−0.021 to +0.064).
  - Among childless women it is positive in every scenario.
  - Among mothers it is negative in 2009 and indistinguishable from zero in 2015.

### Which population claims are justified

| Claim | Status |
|---|---|
| Distribution of stated expectations, and the share of childless women, among respondents in 2009–10 and 2015–16 (the population represented by the 1997 sample, as of each round) | **Design-based estimates** with jackknife standard errors (table above), assuming item nonresponse is missing at random |
| Mothers state lower chances than childless women at both baselines | Design-based, at baseline |
| Answers too extreme; recalibration improves accuracy; mothers and childless women differ in average error | Supported in the sample and robust in direction in every weighting and respondent-specific bound. The exception is 2009 recalibration, where bounds were not established. **Not** a design-based population estimate, because no longitudinal weight is available |
| Women on average overestimate their chance | Not established as a population claim. True for childless women in every scenario. The pooled sign depends on composition and, in 2015, on missing outcomes |
| Any calibration or predictive metric for the U.S. 1980–84 cohort | Needs a custom longitudinal weight (see the requirements above) and the stated selection assumptions |

**Recommended corrections:**
- describe pooled average overestimation as a property of childless women's answers;
- keep "unweighted, sample-level" on every outcome-based figure;
- replace "DEFT 1.3–1.9" (documented for other variables) with the estimated 0.8–1.7 when describing this project's baseline statistics.

## Reference

Bruine de Bruin, W., Fischhoff, B., Millstein, S. G., & Halpern-Felsher, B. L. (2000). Verbal and numerical expressions of probability: "It's a fifty-fifty chance." *Organizational Behavior and Human Decision Processes*, 81(1), 115–131.
