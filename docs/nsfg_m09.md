# M09: Fertility Desires and Intentions of Young Adults, NSFG 2022–2023

This chapter describes how young adults in the 2022–2023 National Survey of Family Growth (NSFG) answered questions about wanting and intending children. It also tests whether demographic characteristics can identify those who want a child but say they do not intend one. It builds on the 19 validated Stage 3 checks ([nsfg_stage3_validation.md](nsfg_stage3_validation.md)). **Frozen on 2026-11-20 after the owner's approval.** The frozen files are listed with their SHA-256 hashes in [nsfg_m09_freeze.sha256](nsfg_m09_freeze.sha256). From the project root, `sha256sum -c docs/nsfg_m09_freeze.sha256` confirms they are unchanged. This is a local backend record; nothing here has been published.

**Scope in one sentence.** The NSFG is cross-sectional, so everything below describes answers given at a single interview in 2022–2023. Nothing here measures whether anyone later had, or will have, the children they want.

## 1. Status of the seven official M09 stages

| Stage | Status | Evidence |
|---|---|---|
| 01. Research specification | Complete | Section 2. Every construct was checked against the CDC codebooks and recode specifications. The timing of hypotheses is stated in section 2.3 |
| 02. Official data acquisition | Complete | The CDC public-use female and male respondent files and their official documentation are held locally (section 3). Their dimensions match the CDC (Check 01) |
| 03. Data ingestion and audit | Complete; one documented WARN | The 19 Stage 3 checks are in permanent code: 18 PASS, 1 WARN (Check 03), 0 FAIL. Implementation tasks done within this stage: tracing Check 03, resolving Check 19 from CDC documentation, and pinning the research environment (`requirements-research.txt`; a fresh environment runs Check 18 to PASS) |
| 04. Survey-weighted descriptive research | Complete | `analysis/nsfg_descriptive.py`; public tables in `data/public/nsfg_m09/` with estimates that fail the NCHS standard suppressed; three figures (section 4) |
| 05. Machine learning experiments | Complete; **negative result** | `analysis/nsfg_models.py`: leakage audit, baselines, isolated cluster holdout, calibration, stability (section 6) |
| 06. Robustness and scientific validation | Complete | Descriptive and model sensitivity tables (sections 5 and 6.5) |
| 07. Independent audit and chapter freeze | **Frozen 2026-11-20 (owner approval)** | `audit/verify_nsfg_m09.py` (section 9), the Stage 3 checks and the test suite all pass. Frozen files and hashes: `docs/nsfg_m09_freeze.sha256` |

## 2. Research specification

### 2.1 Population and age proxy
- **Target population:** the U.S. household population aged 15–49 in 2022–2023, as represented by WGT2022_2023.
- **Primary analytic population:** a "Gen Z" age proxy based on age at interview (AGER) and interview year (YEAR):
  - **Conservative (primary):** ages 18–26 if interviewed in 2022 and 18–27 in 2023. There are 2,429 respondents (1,349 women, 1,080 men).
  - **Inclusive (sensitivity):** ages 18–27 and 18–28. There are 2,726 respondents.
- **Limits of the age proxy.** The public file has no birth year. A respondent aged *a* when interviewed in year *Y* was born in *Y − a − 1* or *Y − a*. The two boundaries have different problems:
  - **Upper boundary (oldest respondents).** The age limits correspond to birth in 1995 or later.
    - The conservative proxy includes no one born before 1995.
    - It can exclude some 1995-born respondents. Someone born in 1995 who had already had their birthday when interviewed was 27 in 2022, or 28 in 2023, and falls outside the range.
    - The inclusive proxy captures every 1995-born respondent, but can also include some born in 1994.
  - **Lower boundary (youngest respondents).** Respondents under 18 are excluded, by design, from both proxies. Younger Gen Z respondents interviewed at ages 15–17 (born about 2004–2008) are therefore not covered. People born after 2008 were too young for the NSFG.
  - The age range bounds the birth cohort but does not identify it.

### 2.2 Constructs
All codes were verified against the CDC 2022–2023 codebooks and recode specifications (sources in section 11).

| Construct | Variable(s) | Definition used | Universe |
|---|---|---|---|
| Desire | RWANT (GA-1 / HA-2) | 1 = wants a(nother) child some time; 5 no, 8 refused, 9 don't know | All respondents |
| Joint intention | JINTEND (GB-1 / HB-2) | 1 yes, 5 no | Married or cohabiting, neither partner sterile |
| Individual intention | INTEND (GC-1 / HC-2) | Women 1 yes / 5 no; men 1–2 yes, 3–4 no | Not married or cohabiting, not sterile, RWANT = 1 or don't know |
| Intention (CDC recode) | INTENT | 1 intends, 2 does not, 3 does not know, 4 not provided; sterility assigns 2 without asking | All respondents |
| Intention category | derived from the four above | positive (INTENT = 1); **explicit negative** (item answered "no"); **sterility-linked** (INTENT = 2, item blank, respondent or partner sterile); unknown; not provided | All respondents |
| Number intended | JINTENDN / INTENDN | Number of (more) children intended; refused and don't know are missing | Intenders (INTENT = 1) |
| Expected additional births | ADDEXP / 10 (CDC recode, imputed) | Central expected number; set to 0 if sterile or the intention answer is "no"; adds 1 for a current pregnancy (or, for men, a partner's) | All respondents |
| Observed fertility | Women: PARITY (imputed recode). Men: EVBIOKID, NUMBIOKID (raw FA-1/FA-2) | Live births / biological children fathered. Men who never had sex or fathered a child have 0; refused or unknown answers are missing (32 men) | All respondents |
| Expected total births | PARITY + ADDEXP / 10 | **Women only.** Both terms count live births to the respondent | Women |

**Measures not constructed.**
- **Desired family size.** The 2022–2023 NSFG has no numeric desired or ideal family-size question; desire is measured only by RWANT, which is yes/no.
- **Desired versus expected family size.** Because there is no desire count, this comparison is not possible.
- **Intended versus expected number among intenders.** This comparison would be circular, because ADDEXP equals the intended number by construction.
- **Expected total births for men.** These are not combined. The men's count comes from raw items with unimputed refusals, and their expectations include partners' pregnancies, so it is not equivalent to the women's measure.

**Respondent versus joint intentions.** Partnered respondents answer for the couple (JINTEND); others answer for themselves (INTEND). Which item a respondent gets depends on current partnership. Results are therefore reported overall and by item, and partnership is excluded from the primary model (section 4).

### 2.3 Outcomes, hypotheses and estimands
- **Primary estimands (conservative cohort, weighted):**
  - the prevalence of wanting a(nother) child;
  - the prevalence of intending a(nother) birth;
  - among those who want a child, the share with INTENT = 2 (divergence), split into explicit-negative and sterility-linked parts.
- **How much the record shows about timing.** The project keeps no time-stamped analysis protocol for M09. M06 had one: methodology section 12, fixed before the outcomes were examined. Labels here follow what the record shows; none of these analyses is pre-registered.
- **Planned contrast carried over from Stage 3 (H1).**
  - The female − male difference in divergence, among those who want a child, equals zero. Two-sided, α = 0.05.
  - The owner's Stage 3 checklist (Check 19) listed this comparison, and it was computed at Stage 3. Its result was therefore known before this specification was written.
  - It is reported as a planned comparison, not as a confirmatory test.
- **Planned comparisons (H2, H3; Holm-adjusted as one family).** They were named in the analysis code before the first M09 run, but no time-stamped record shows this. Among those who want a child, the explicit-negative share
  - does not differ across age groups (18–21, 22–24, 25 or older) (H2);
  - does not differ across number of children (0, 1, 2 or more) (H3).
- **Planned prediction comparison (H4).**
  - The claim tested: the primary set of demographic and socioeconomic predictors identifies explicit-negative respondents, among those who want a child, better than the class prior on held-out clusters.
  - The test: the holdout ROC-AUC interval excludes 0.5, and PR-AUC exceeds prevalence.
  - The feature set, model grids, holdout split and threshold rule were fixed in code before any model was fitted, but not in a time-stamped protocol.
- **Exploratory:** every other subgroup estimate and test; expected and intended numbers; observed fertility; the association between children and intentions. Exploratory p-values are Holm-adjusted within each measure and population, and are labelled as exploratory.

### 2.4 Survey design and uncertainty
- **Design:** weights WGT2022_2023; strata VEST (20); clusters VECL (80); Taylor linearization with clusters treated as sampled with replacement; 60 design degrees of freedom.
- **Pooled sample:** the two files are stacked into one 9,957-respondent design. Subgroups are domains of the full design and are never subset away.
- **Proportions:** Korn–Graubard 95% intervals, with reliability assessed against the NCHS standard for proportions (Parker et al., 2017):
  - suppressed if the effective sample size is below 30;
  - suppressed if the interval is wider than 30 points;
  - suppressed if the interval is wider than 5 points and its width relative to the estimate exceeds 130%.
- **Means:** t intervals; flagged if the relative SE exceeds 30% and suppressed if n < 30.
- **Public release of suppressed estimates:**
  - In `data/public/nsfg_m09/`, a suppressed row keeps its label, its unweighted denominator and its reliability reason. Its estimate, SE, interval, effective sample size and event count are left blank.
  - Figures do not draw suppressed estimates.
  - The complete tables are kept locally in `data/processed/nsfg_m09_internal/`, which is not under version control, for validation.
  - Design-based differences, Wald tests and model metrics are not proportions, so the standard does not apply to them.
- **Differences:** linearized contrasts within the pooled design.
- **Tests across several groups:** Korn–Graubard adjusted Wald F tests, F(q, 61 − q).
- **Variance checks:** the JKn delete-one-cluster jackknife, and separate-file (independent-samples) SEs.

### 2.5 Exclusion and missing-data rules
- No respondent is dropped from the design. Analyses select domains.
- **Unknown (15) and not-provided (4) intentions** among wanters in the conservative cohort stay in the denominator of the decomposition as their own categories. The decomposition bounds them in section 5.
- **Sterility-linked cases** are reported separately. They are never treated as a choice not to have children.
- **The model sample** excludes sterility-linked, unknown and not-provided cases.
- **Refused or unknown counts** (number intended; men's children) are missing for that measure only.
- **Imputation:** CDC-imputed recodes (PARITY, ADDEXP, HIEDUC, POVERTY and others) are used as released. Inside the model, the one missing predictor value (a man's number of children) is imputed by the training-fold median, with a missing indicator.

## 3. Data provenance
- **Source:** the CDC/NCHS 2022–2023 NSFG public-use female and male respondent files (CSV; 5,586 × 1,912 and 4,371 × 1,157), with the codebooks, recode specifications and User's Guide (revised July 2025). These are saved in `data/raw/nsfg_2022_2023/`, which is not under version control.
- **Variance documentation:** the CDC Variance Estimation Report and examples, and the 2022–2023 FAQ (linked in section 11).
- **Outputs:**
  - aggregate tables in `data/public/nsfg_m09/` (CSV and `model_results.json`);
  - figures in `assets/figures/nsfg_*.png`.
- **Local only:** respondent-level holdout predictions for the audit, in `data/processed/` (not under version control).

## 4. Descriptive results

### 4.1 Wanting and intending (conservative cohort, weighted)

| Measure | All | Women | Men | Women − men (95% CI) |
|---|---:|---:|---:|---|
| Wants a(nother) child | 69.9% (SE 1.3) | 64.1% | 75.7% | −11.6 pp (−17.3, −5.9) |
| Intends a(nother) birth | 62.8% (1.5) | 55.9% | 69.6% | −13.8 pp (−20.0, −7.5) |
| Divergence among those who want a child | 11.2% (1.0) | 12.3% | 10.4% | +1.9 pp (−2.3, 6.1), p = 0.37 |
| Explicit negative among those who want a child | 6.6% (0.7) | 7.8% | 5.5% | +2.3 pp (−0.9, 5.5), p = 0.15 |
| Sterility-linked among those who want a child | 4.7% (0.8) | 4.5% | 4.9% | −0.4 pp (−3.2, 2.4), p = 0.77 |

Unweighted denominators: 2,429 respondents and 1,703 who want a child (881 women, 822 men). Every estimate in the table meets the NCHS standard.

- **The full answer distributions:**
  - RWANT: 25.5% no, 4.2% don't know, 0.4% refused.
  - INTENT: 34.7% does not intend, 2.1% does not know, 0.4% not provided.
- **Among those who want a child:**
  - 87.5% intend one;
  - 6.6% gave an explicit "no";
  - 4.7% are sterility-linked;
  - 1.1% don't know and 0.2% did not provide an answer ([decomposition figure](../assets/figures/nsfg_intention_decomposition.png)).

**Answer to the core question.** About one in nine young adults who want a child does not intend one. Roughly 40% of that gap is sterility-linked rather than a stated "no". Women are less likely than men to want or intend children. There is no evidence that the desire–intention gap differs by sex (H1 not rejected).

### 4.2 Age, children and partnership
- **Age (H2).** Among those who want a child, the explicit-negative share is:
  - 5.1% at ages 18–21 (n 751);
  - 5.2% at 22–24 (n 449);
  - 10.6% at 25 or older (n 503).

  This gives F(2, 59) = 4.79, p = 0.012, Holm-adjusted 0.024, so the planned comparison **H2 rejects equality**. The explicit "no" is about twice as common at the top of the age range. The pattern is cross-sectional. It cannot separate ageing from cohort differences.
- **Number of children (H3).**
  - The explicit-negative share is 5.9% among respondents with no children (n 1,485).
  - The estimates for respondents with one child (n 151) and two or more (n 66) fail the NCHS reliability standard and are suppressed.
  - The design-based test across the three groups gives F = 1.85, p = 0.17, so **H3 does not reject equality**. This sample cannot establish a difference by number of children.
- **Parents versus childless respondents (exploratory):**
  - Parents are much less likely to want another child (−19.6 pp, 95% CI −26.1 to −13.0) or to intend one (−23.0 pp).
  - Among parents who want another child, divergence is higher (+8.0 pp, CI 0.4 to 15.5, p = 0.039, unadjusted).
  - The wording differs: parents are asked about "another" child and childless respondents about "a" child.
- **Partnership (exploratory):**
  - The explicit-negative share is 11.0% among married, 8.4% among cohabiting and 5.6% among other respondents who want a child.
  - The global test is not significant (p = 0.18).
  - Partnered respondents answer the joint item, so these numbers mix partnership with the form of the question (section 5).

### 4.3 Other characteristics (exploratory)
The full subgroup tables are in `subgroups.csv` and `subgroup_tests.csv` ([subgroup figure](../assets/figures/nsfg_explicit_negative_subgroups.png)). Suppressed estimates are blank in the tables and not drawn in the figures.
- **Characteristics with differences in wanting and intending** (Holm-adjusted p < 0.01):
  - family income relative to poverty (wanting: 76.4% at 400%+ against 61.4% below poverty);
  - religious affiliation (wanting: 61.3% with no religion against 76.7–77.0% for Catholic and Protestant respondents);
  - labour-force status, insurance and number of children.
- **Divergence among those who want a child:** only religious affiliation passes the within-measure Holm adjustment (15.8% with no religion against 6.8% for Catholics).
- **Explicit negative among those who want a child:** no grouping passes.
- **No differences after adjustment:** education, race and ethnicity, and metropolitan residence show none on any intention measure. Education and intending has unadjusted p = 0.033 and Holm-adjusted p = 0.20.

These are descriptive associations at one point in time. They are not evidence that income, religion or employment cause fertility intentions.

### 4.4 Expected births and observed fertility

| Measure (weighted mean or share) | All | Women | Men |
|---|---:|---:|---:|
| Has had at least one child | 14.6% | 19.2% | 9.9% |
| Children so far | 0.24 | 0.32 | 0.16 |
| Expected additional births (ADDEXP) | 1.48 | 1.29 | 1.67 |
| Number intended, among intenders | 2.31 | 2.25 | 2.35 |
| Expected total births (women only) | — | 1.61 | — |

- **Women versus men:**
  - Women have more children so far than men of the same ages (+0.16, p < 0.001).
  - They expect fewer additional births (−0.38, CI −0.54 to −0.22).
  - The number intended among intenders does not differ (−0.10, p = 0.16).
- **Expected births by intention category:**
  - Those with a positive intention expect 2.31 additional births.
  - Explicit negatives expect almost none: exactly 0 for women and 0.04 for men, which reflects partners' current pregnancies.
  - This follows from the CDC rule that sets ADDEXP to 0 after a "no", and it is why ADDEXP is excluded from the model.
- **Expected total births:** women's expected total of 1.61 is an expectation stated at ages 18–27. It is not a forecast of completed fertility.

## 5. Descriptive robustness (`sensitivity.csv`, `weighted_vs_unweighted.csv`)

| Variation | Divergence | Explicit negative | Sterility-linked |
|---|---:|---:|---:|
| Primary: conservative cohort, RWANT = 1 | 11.2% | 6.6% | 4.7% |
| Inclusive cohort | 11.3% | 6.6% | 4.7% |
| All ages 15–49 (context) | 19.8% | 9.9% | 9.9% |
| Add RWANT = don't know but "probably want" | 10.9% | 7.2% | 4.5% |
| Joint item only (partnered, n 372) | 15.8% | 9.5% | 6.2% |
| Individual item only (n 1,331) | 9.9% | 5.6% | 4.2% |
| Sterility-linked removed from the denominator | — | 6.9% | — |
| Unknown and not provided excluded / counted as "no" | — | 7.0% / 7.9% | — |
| Unweighted | 11.3% | 6.8% | 4.5% |

- **Robust:**
  - The level of divergence is about 11%, whichever age proxy, eligibility rule or weighting is used.
  - The explicit-negative share is 6.6–7.9% under every coding of unknown answers.
  - Sterility-linked cases make up roughly 40% of divergence.
  - The female–male differences are not significant under every variant.
- **Sensitive:**
  - The joint item shows more explicit "no" answers than the individual item (+3.9 pp, CI −0.4 to 8.2, p = 0.075). This is not significant, and it cannot be separated from partnership and age.
- **Context:**
  - Across all ages 15–49, divergence is almost twice as high, mainly because sterility rises with age.
- **Variance:**
  - Jackknife SEs equal the linearization SEs to within 0.0001.
  - Separate-file SEs for the sex contrasts are 0.93–1.04 times the pooled SEs.
  - Weighted and unweighted shares differ by at most 1.7 points.
- **Unsupported:** any subgroup estimate the reliability standard suppresses is not interpreted. These are mainly estimates of explicit-negative shares within small groups.

## 6. Classification experiment

### 6.1 Target and eligibility
- **Target:** among conservative-cohort respondents who want a child and gave a yes/no intention answer, 1 = explicit negative and 0 = positive intention.
- **Eligible:** 1,607 respondents, of whom 116 are positive (7.2%). By group:
  - women: 829 respondents, 73 positive (8.8%);
  - men: 778 respondents, 43 positive (5.5%);
  - individual item: 1,271 respondents, 85 positive;
  - joint item: 336 respondents, 31 positive.
- **Excluded:** sterility-linked (77), unknown (15) and not-provided (4) cases are excluded. They are described in section 4 instead.
- **Meaning of the label:** a survey answer at interview. It is not future childlessness.

### 6.2 Leakage audit
The full feature dictionary, with the reason for each inclusion or exclusion, is in `feature_dictionary.csv`. `assert_no_leakage` enforces it in code and the independent verifier checks it again.
- **Included:** age, number of children, education, family income relative to poverty, children in the household, sex, interview year, race and ethnicity, labour-force status, metropolitan residence, religious affiliation and insurance. All are CDC recodes measured at the same interview.
- **Excluded:**
  - every item that defines the label (RWANT, JINTEND, INTEND, INTENT);
  - every item asked conditionally on it: certainty, number intended or expected, and timing;
  - ADDEXP, which is 0 after a "no";
  - the partner's desire (PWANT), from the same question block;
  - the sterility and fecundity variables that route the question (RSTRSTAT, PSTRSTAT, FECUND, INFERT);
  - the design variables and identifiers.
- **Partnership:** current partnership (RMARIT) and ever-married status decide whether the joint or individual item is asked. They are excluded from the primary model and tested only as a sensitivity analysis.
- **Univariate screen:** on development clusters, no predictor alone reaches AUC 0.9. The highest is 0.62, for poverty.
- **Where preprocessing happens:** imputation, scaling and one-hot encoding are fitted inside each training fold.

### 6.3 Design
- **Holdout:** one quarter of the clusters, chosen by StratifiedGroupKFold with seed 2023. It has 397 respondents, 28 positives and 19 clusters. It was used once, after every choice had been fixed.
- **Development:** 1,210 respondents, 88 positives and 61 clusters. No cluster is in both partitions.
- **Models:**
  - a class-prior dummy;
  - an L2 logistic regression (C 0.01–3, with or without class weighting);
  - a shallow gradient-boosted tree model (depth 2, 50–200 iterations, at least 20–40 cases per leaf, with or without class weighting). It is kept small because there are only 88 development positives.
- **Selection:** by mean PR-AUC over 5 × 5 repeated grouped cross-validation within the development clusters.
- **Threshold:** maximum F1 on development out-of-fold predictions.
- **Calibration:** assessed on the holdout without refitting.
- **Uncertainty:** a 2,000-replicate cluster bootstrap on the holdout.
- **Weights:** models are fitted without survey weights. Weighted fit and metrics are a sensitivity analysis. Weighted predictive metrics are not design-based inference.

### 6.4 Results

| Holdout (n 397, 28 positives, prevalence 0.071) | Dummy | Logistic (C 0.01) | Boosting |
|---|---:|---:|---:|
| ROC-AUC (95% cluster-bootstrap CI) | 0.50 | 0.51 (0.41, 0.58) | 0.44 (0.33, 0.54) |
| PR-AUC (baseline = prevalence 0.071) | 0.071 | 0.078 (0.053, 0.123) | 0.067 |
| Brier score (skill vs prior) | 0.0656 (0) | 0.0669 (−0.02) | 0.2322 (−2.54) |
| Threshold (from development) | 0.072 | 0.079 | 0.565 |
| TP / FP / FN / TN | 28 / 369 / 0 / 0 | 7 / 92 / 21 / 277 | 3 / 79 / 25 / 290 |
| Precision / recall / F1 | 0.07 / 1.00 / 0.13 | 0.07 / 0.25 / 0.11 | 0.04 / 0.11 / 0.05 |
| Balanced accuracy | 0.50 | 0.50 | 0.45 |
| Calibration slope | — | −0.09 | −0.48 |

- **Logistic minus dummy:** ROC-AUC difference −0.09 to 0.08 (95% interval); PR-AUC difference −0.005 to 0.045.
- **Accuracy is not evidence of value here.** The logistic model's accuracy is 0.72, but it is entirely the imbalance; balanced accuracy is 0.50.
- **Within-development cross-validation:**
  - logistic: AUC 0.66 (SD over folds 0.05), PR-AUC 0.17;
  - boosting: AUC 0.64, PR-AUC 0.14.
- **The chosen penalty is at the edge of the grid.** C = 0.01, the strongest penalty considered, was selected, which is itself a sign of weak signal.
- **Stability:** repeated grouped 5-fold cross-validation over all 80 clusters with 20 seeds and fixed hyperparameters:
  - logistic: AUC 0.618 (range 0.593–0.628), PR-AUC 0.114 against a prevalence of 0.072, Brier skill +0.010;
  - boosting: AUC 0.579, Brier skill −2.32. Its selected class weighting distorts its probabilities.
  - The pooled dummy AUC of 0.489 is an artefact of fold-specific priors.

**Conclusion (planned comparison H4 not supported).** No model beats the class-prior baseline on the isolated holdout. Across repeated cross-validation, the logistic model shows modest, stable discrimination (AUC about 0.62). Its probabilistic gain over the prior is negligible (Brier skill 1%), and the holdout did not confirm it. The negative result stands: these demographic and socioeconomic characteristics do not usefully identify who, among those who want a child, says they do not intend one.

### 6.5 Model robustness (`model_robustness.csv`; repeated grouped CV, 5 seeds)

| Variation | n (positives) | Logistic AUC | Boosting AUC |
|---|---:|---:|---:|
| Primary | 1,607 (116) | 0.62 | 0.59 |
| Inclusive cohort | 1,777 (134) | 0.64 | 0.63 |
| All ages 15–49 | 4,312 (521) | 0.72 | 0.72 |
| Include "probably want" | 1,636 (126) | 0.63 | 0.61 |
| Women only | 829 (73) | 0.58 | 0.55 |
| Men only | 778 (43)* | 0.59 | 0.53 |
| Joint item only | 336 (31)* | 0.68 | 0.71 |
| Individual item only | 1,271 (85) | 0.59 | 0.56 |
| Complete cases | 1,606 (116) | 0.62 | 0.59 |
| Survey-weighted fit and metrics | 1,607 (116) | 0.60 | 0.60 |
| Demographic features only | 1,607 (116) | 0.60 | 0.57 |
| Without number of children | 1,607 (116) | 0.62 | 0.59 |
| Plus partnership (routing-related) | 1,607 (116) | 0.61 | 0.59 |

\* Fewer than 50 positives, so the estimate is not reliable.

- **Where discrimination is higher:** only in the all-age sample (0.72). That sample has older respondents with completed families, and age dominates. It does not change the conclusion for young adults.
- **Little change from:**
  - imputation compared with complete cases;
  - weighting;
  - adding partnership;
  - removing the number of children.
- **Class weighting** leaves ranking unchanged and harms calibration (Brier skill −2.44 for the logistic model).
- **Holdout subgroups:**
  - women (19 positives): AUC 0.46;
  - men (9 positives): too few to evaluate.

### 6.6 Interpretation of associations
- **Permutation importance** (holdout, mean AUC drop over 50 permutations, ± SD):
  - clearly above zero: age (0.057 ± 0.024) and religious affiliation (0.025 ± 0.012);
  - marginal: sex (0.012 ± 0.011) and education (0.008 ± 0.007);
  - every other feature is at or below zero.
- **Standardized logistic coefficients:** these are heavily shrunk by the penalty, so they are small. The ones whose sign is stable in at least 99.5% of 200 cluster-bootstrap refits are:
  - older age (odds ratio 1.12 per SD);
  - more children (1.12);
  - more children in the household (1.09);
  - higher income relative to poverty (0.85);
  - no religious affiliation (1.11).
- **The coefficients match the descriptive results:** an older age, children already and lower income go with an explicit "no".
- **What these are and are not:** they are associations in a model that predicts poorly. They are not causal effects and not individual-level predictions. The experiment supports no deployment or screening use.

## 7. Survey design limitations
- The pooled female–male design is established from the CDC sample-design documentation (Check 19). The CDC provides no worked pooled example.
- Linearization ignores the calibration of the weights to population totals, as the CDC examples do. This is usually conservative.
- With 60 design degrees of freedom, tests across many groups lose power. The adjusted Wald F accounts for this.
- 98 subgroup estimates fail the NCHS reliability standard, mostly explicit-negative and divergence shares within small groups. So do 12 expected-birth means for the small unknown and not-provided categories. They are blank in the public tables, not drawn and not interpreted.
- Predictive metrics come from the sample. Cluster-grouped evaluation and the cluster bootstrap address dependence within clusters, but not weighting to the population.

## 8. Conclusions

**What the data answer.** In 2022–2023:
- about 70% of U.S. adults aged roughly 18–27 wanted a(nother) child, and about 63% intended one;
- women were less likely than men to do either;
- of those who wanted a child, about 11% did not intend one;
- 6.6% of those who wanted a child gave an explicit "no", and 4.7% were classified as not intending only because they or their partner were sterile;
- the gap did not differ by sex;
- the explicit "no" was about twice as common at ages 25 and older as at ages 18–24.

**What the data answer partly.**
- Associations with income, religion, employment, partnership and existing children are descriptive and mostly exploratory.
- The joint and individual questions cannot be separated from partnership.
- Parent subgroups are too small for reliable estimates of the explicit "no".
- Expected births are stated expectations, not outcomes.

**What needs future longitudinal evidence.**
- Whether respondents later have the children they want or intend.
- Whether explicit negatives change their minds.
- Whether the difference by age is ageing or a difference between cohorts.
- **Whether Gen Z will achieve its desired family size. M09 does not answer this question.** The NSFG measures neither completed fertility nor a desired number of children.

**Questions reserved for M10 and M11.** Economic and housing explanations of the gap, and any forecast of completed fertility. M09 makes no causal or forecasting claim.

**Machine learning.** It adds no predictive value beyond the class prior for this target, and that negative result is kept.

## 9. Reproduction and verification

These commands are run from the project root. The `svy` dependency needs `pip install -r requirements-research.txt` (Python 3.12+; tested on 3.15).

```
python audit/nsfg_stage3_checks.py --require-data   # 19 checks: 18 PASS, 1 WARN (03)
python -m analysis.nsfg_descriptive                 # tables and figures, about 10 s
python -m analysis.nsfg_models                      # model experiment, about 3 min
python audit/verify_nsfg_m09.py --require-data      # independent verification
python -m unittest                                  # full test suite
```

`audit/verify_nsfg_m09.py` labels each of its checks with one of three kinds.

| Kind | What it does | Coverage |
|---|---|---|
| Independent recomputation | Re-codes constructs from the raw CSVs with polars and re-estimates with `svy`. Shares no coding or estimation code with the pipeline | Conservative-cohort estimates and SEs for nine measures for all respondents, women and men; the three female − male differences (point estimates); explicit "no" by age group and wanting by race and ethnicity (point estimates); sample-flow counts; model sample size and positives; holdout ROC-AUC, PR-AUC and Brier score recomputed from the stored predictions with rank and step formulas, without scikit-learn (the predictions themselves come from the pipeline) |
| Same-code reproducibility | Re-runs the pipeline's own model code from the stored configuration and seeds | Holdout metrics of all three models. This shows determinism, not correctness |
| Reconciliation | Compares reported or configured values with generated ones | Suppression in every public table; the primary feature list against an independently written list of intention-block variables; holdout size; headline numbers in this chapter |

- **Not covered by the verifier:**
  - Korn–Graubard intervals and reliability flags;
  - Wald tests;
  - other subgroups, the inclusive cohort, and the sensitivity, parity-contrast and expected-birth tables;
  - the model stability, robustness, bootstrap and interpretation outputs.
- **How the uncovered parts are checked instead:**
  - unit tests on synthetic data, including a check that Korn–Graubard reproduces Clopper–Pearson in a simple random sample, and a covariance check against the existing linearization;
  - the shared Taylor linearization, which reproduces the CDC benchmark;
  - the integration test that compares stored public tables with a fresh run.
- **Seeds:** all random choices use seed 2023 or fixed offsets from it (`CONFIG` in `analysis/nsfg_models.py`, stored in `model_results.json`).

## 10. Outstanding limitations and warnings

| Issue | Classification |
|---|---|
| Check 03 WARN: one routing exception has no documented explanation, and three are explained by inference; none affects any estimate | Nonblocking, documented |
| No birth year; the age proxy only bounds the cohort | Methodological limitation |
| No numeric desired family size in the 2022–2023 NSFG | Methodological limitation (data) |
| Cross-sectional data; intentions are not outcomes | Methodological limitation |
| Small holdout (28 positives), so holdout metrics have wide intervals | Methodological limitation; addressed with repeated cross-validation |
| The CDC publishes no pooled female–male worked example | Nonblocking; design documented |
| Ruff is not configured, and pytest is not installed (unittest is used) | Nonblocking; tooling |

## 11. Sources
- CDC/NCHS, 2022–2023 NSFG Female and Male Respondent Public Use File Codebooks and Recode Specifications, and the User's Guide (revised July 2025); local copies are in `data/raw/nsfg_2022_2023/documentation/`.
- CDC/NCHS, [2022–2023 NSFG Variance Estimation Report](https://www.cdc.gov/nchs/data/nsfg/NSFG-2022-2023-VarianceEstimationReport.pdf), [Variance Estimation Examples](https://cdc.gov/nchs/data/nsfg/varest/2022-2023-NSFG-VarEst-all.pdf) and [FAQ](https://cdc.gov/nchs/data/nsfg/guidefaqs/NSFG-2022-2023-FAQ.pdf).
- Parker J.D. et al. (2017), *National Center for Health Statistics Data Presentation Standards for Proportions*, Vital Health Stat 2(175).
- Korn E.L. and Graubard B.I. (1990), Simultaneous testing of regression coefficients with complex survey data, *The American Statistician* 44(4).
