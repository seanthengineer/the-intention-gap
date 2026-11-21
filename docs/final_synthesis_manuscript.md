# Will Generation Z Have the Families They Say They Want? An integrated assessment of four U.S. studies of fertility intentions, outcomes, housing and forecasts

**Status:** **FROZEN, final scientific approval, 2026-11-20.** Manifest `docs/final_synthesis_freeze.sha256`; completion record `docs/final_readiness_assessment.md`. Editing this file needs a recorded decision and a new manifest.

**Basis:** the synthesis uses only the frozen chapters:
- M01–M08 (`docs/methodology.md`);
- M09 (`docs/nsfg_m09.md`);
- M10 (`docs/m10_housing_fertility.md`);
- M11 (`docs/m11_fertility_forecasts.md`).

**What is new here:** no estimate in this manuscript is new. Every number is copied from a frozen output or a frozen chapter. Bracketed identifiers such as [C09.01] point to the claim-to-evidence matrix (`docs/final_claim_evidence_matrix.csv`), which gives each claim's exact source, population, denominator, uncertainty and verification status. `python audit/verify_final_synthesis.py` checks every matrix entry against its source. It also checks token coverage: every numeric token in this document is represented among the verified matrix figures. That scan does not establish that each statement uses its number correctly; material claims were also reviewed in their textual context (`audit/scientific-audit.md` section 22).

**Companion documents:**
- executive summary: `docs/final_executive_summary.md`;
- limitations register: `docs/final_limitations_register.md`;
- sources: `docs/final_sources.md`;
- reproduction guide: `docs/final_reproducibility_guide.md`;
- readiness assessment: `docs/final_readiness_assessment.md`;
- audit record: `audit/scientific-audit.md`, sections 21 and 22.

## Abstract

**Question.** Will people born 1995–2012 (Generation Z, including Zillennials) have the families they say they want?

**Data.** Four frozen studies, each answering part of the question:
- **M01–M08:** a longitudinal test of stated birth expectations against later births, in an earlier cohort (NLSY97, women born 1980–84).
- **M09:** a weighted cross-section of desires and intentions among U.S. adults aged about 18–27 in 2022–2023 (NSFG).
- **M10:** a state-year panel associating rental cost burden with birth rates, 2014–2024.
- **M11:** national forecasts of period fertility to 2040, and projections of cumulative fertility for the 1995–2012 birth cohorts (Human Fertility Database).

**Results.**
- **Desire and intention (M09).** In 2022–2023, 69.9% of U.S. adults aged about 18–27 (born about 1995–2005, the older part of Generation Z) wanted a(nother) child [C09.01] and 62.8% intended one [C09.02].
  - Among those who wanted a child, 11.2% did not intend one [C09.03].
  - About 42% of that gap consisted of respondents whom the survey classifies as not intending because they or their partner were reported sterile, rather than respondents who answered "no" [C09.06].
- **Expectations against outcomes, earlier cohort (M01–M08).** Stated chances of a birth within five years ranked women well (AUC 0.726) [C01.04] but were far too extreme as forecasts (linear calibration slope 0.476) [C01.05].
  - Childless women's stated chances exceeded their births in every weighting and missing-data bound [C01.08].
  - Mothers, on average, understated theirs [C01.07].
- **Population fertility (M11).**
  - No alternative model met the prespecified criteria for replacing a no-change forecast, so the 2040 period total fertility rate (TFR) is forecast at the 2024 level of 1.593 [C11.01]. Its nominal 80% historical-error interval is 1.05–2.42, which failed its calibration check [C11.02].
  - If 2024 rates persist, women born in 1995 reach about 1.75 births each by the end of 2040, which is nearly complete by historical standards but is not completed lifetime fertility [C11.06]. Women born in 2012 reach about 0.62 by then, which is partial [C11.07].
- **Housing (M10).** Within states, higher rent burden had a weak, statistically inconclusive and non-robust negative association with births at ages 20–24, and none at 25–29 [C10.01, C10.02].

**Conclusion.** The evidence cannot establish whether Generation Z will have the families it says it wants.
- A population-average comparison of desired and achieved family size would need a numeric desired family size measured for Generation Z and completed fertility for the same birth cohorts. Neither exists: desire is measured only as yes/no, and completed lifetime fertility lies in the future for every Generation Z cohort.
- Measuring whether individuals fulfil their intentions needs more: linked longitudinal observations of the same people. No source provides them.
- The evidence does establish four things:
  - most U.S. adults aged about 18–27 in 2022–2023 wanted children;
  - forward-looking fertility statements in an earlier cohort were informative but systematically too extreme;
  - in that cohort, childless women's near-term expectations overstated their births;
  - current period rates, if they persist, imply below-replacement cumulative fertility for the oldest Generation Z cohorts.
- None of these is a measured gap between desired and achieved family size, and none should be read as one [C00.04].

## 1. Executive summary

1. **The question cannot be answered as posed with existing data.** A population-average answer would need Generation Z's numeric desired family size and the completed fertility of the same birth cohorts. An answer about individuals would also need linked longitudinal records of the same people.
   - The project has neither for Generation Z.
   - M09 measures desire only as yes/no, and has no numeric desired or ideal family size [C09.13].
   - M11 projects population averages, partly before childbearing is complete [C11.07].
2. **Most adults aged about 18–27 in 2022–2023 wanted and intended children.** This is the older part of Generation Z (born about 1995–2005); younger cohorts were not surveyed as adults.
   - In 2022–2023, about 70% wanted a(nother) child and 63% intended one [C09.01, C09.02].
   - Women were less likely than men to want a child (64.1% against 75.7%) [C09.08].
3. **Wanting without intending is uncommon, and a large part of it is a survey classification linked to reported sterility.**
   - Of those who wanted a child, 11.2% did not intend one [C09.03]: 6.6% said "no" [C09.04], and 4.7% were classified as not intending because they or their partner were reported sterile [C09.05].
   - Models using demographic and socioeconomic characteristics failed to demonstrate meaningful out-of-sample improvement over a prior-only baseline in predicting the explicit "no" (holdout AUC 0.51 against 0.50) [C09.12].
4. **Stated expectations are informative but over-confident at both ends.**
   - In the earlier NLSY97 cohort, 18.4% of women who said there was no chance of a birth had one within five years [C01.03]. Only 73.0% of those who said 100% did [C01.03].
   - The ranking held six years later in the same women (AUC 0.798), while the frozen 2009 recalibration drifted [C01.11].
   - This is evidence about the reliability of stated expectations as forecasts, not about Generation Z directly.
5. **Near-term over-statement is concentrated among the childless.** In that cohort:
   - women without children stated a 53.2% chance on average, and 32.5% had a birth [C01.07];
   - mothers stated 33.2%, and 39.0% had a birth [C01.07].
6. **Current population fertility is low, and the record gives no reliable signal of direction.**
   - The 2040 TFR forecast is the 2024 level, 1.593 [C11.01].
   - The 2025 reconstruction, 1.577, shows the decline continued for one more year [C11.05].
   - The forecast intervals are wide and are not validated probabilities [C11.02, C11.03].
7. **Cumulative fertility of Generation Z.** If 2024 rates persist, the 1995–2002 cohorts reach 1.48–1.75 births per woman by 2040. That is nearly complete by historical standards, but it is not completed lifetime fertility [C11.06]. Younger cohorts are far from complete [C11.07].
8. **Housing costs do not robustly explain fertility differences across states over time** [C10.01, C10.04]. That is an ecological finding, not a causal one.
9. **The defensible answer:** the share of Generation Z who will have the families they say they want is unknown. A shortfall, especially in timing and among people who are childless at young adult ages, is plausible on the earlier-cohort evidence, but it is not measured [C00.04].

## 2. Conceptual framework

The question links two quantities that no single study observes:
- what individuals want;
- what they eventually achieve.

The four chapters measure different points along the path between them.

| Construct | Definition used here | Measured by | Not measured |
|---|---|---|---|
| Desire | Wanting a(nother) child (yes/no) | M09 (RWANT) | A numeric desired or ideal family size, in any chapter |
| Intention | Intending a(nother) birth; number intended among intenders | M09 (INTENT, JINTEND/INTEND, number intended) | Intentions of the 1980–84 NLSY97 cohort |
| Expectation | Stated percent chance of a birth within five years; expected additional births | M01–M08 (YFER-4861); M09 (ADDEXP) | — |
| Observed fertility | Births in a defined window; children born so far | M01–M08 (five-year births); M09 (parity at interview); M11 (cumulative to 2024) | — |
| Cumulative cohort fertility by an age | Running sum of cohort birth rates to a date | M11 (to end-2024 observed; to end-2040 projected) | Individual-level cumulative fertility of Generation Z |
| Completed fertility | Births by the end of the reproductive span | Not observed for any Generation Z cohort | Everything after 2024; for cohorts born 2003 onward, most of it |
| Association | Within-state co-movement of rent burden and birth rates | M10 | Any causal effect |
| Model prediction | Recalibrated probabilities (M01–M08); classification (M09); forecasts and scenarios (M11) | M01–M11 | Validated probability statements about 2040 |

**Three rules follow, and the synthesis applies them throughout:**
1. A stated desire, an intention, an expectation and an observed or projected birth count are different quantities. They are not subtracted from one another.
2. Cohort fertility "by 2040" is never completed lifetime fertility. For cohorts born 1995–2002 it is nearly complete by historical standards and approximates completed fertility; for later cohorts it is partial [C11.06].
3. Associations (M10) and forecasts (M11) are not causal effects or validated probabilities.

**Who is observed.** `assets/figures/final_evidence_map.png` places each chapter on a calendar-year by birth-cohort grid (table: `data/public/final/final_population_map.csv`).
- The NLSY97 women were born in 1980–84 and are not Generation Z.
- M09's age proxy bounds its respondents' birth years to 1995–2005 [C00.02].
- M10's ages 20–24 in 2021–2024 were born 1996–2004 [C00.02], but M10 follows age groups, not cohorts.
- M11 covers every Generation Z cohort but observes only population rates.

No chapter follows Generation Z individuals from stated desire to completed fertility [C00.03].

## 3. Data and methodology overview

| Chapter | Data | Design and population | Key methods | Inference | Pre-specification | Verification |
|---|---|---|---|---|---|---|
| M01–M08 | NLSY97 public-use extracts (three, with codebooks) | Women interviewed in 2009–10 who gave a number: 3,660 eligible, 3,404 with a confirmed outcome [C01.01]; temporal check at 2015–16 | Conservative five-year outcome from cumulative birth rosters; Brier, AUC, calibration tables with Wilson intervals; logistic recalibration on a household-grouped split; bounds for unknown outcomes | Unweighted, sample-level; household bootstrap; design-based (jackknife) estimates for baselines only | Held-out split fixed before results; 2015–16 temporal protocol fixed before outcomes were examined; repeated cross-validation exploratory | `audit/verify_outcomes.py`, `verify_models.py`, `verify_temporal.py` |
| M09 | NSFG 2022–2023 public-use female and male files | U.S. household population aged 18–26 (2022) or 18–27 (2023): 2,429 respondents, 1,703 who want a child [C09.07] | CDC intention recodes; weighted prevalence and decomposition; isolated-cluster classification experiment | Design-based Taylor linearization (20 strata, 80 clusters), Korn–Graubard intervals, NCHS reliability suppression | Planned comparisons, not pre-registered | `audit/nsfg_stage3_checks.py`, `audit/verify_nsfg_m09.py` |
| M10 | ACS 1-year B25070 and B25072; CDC WONDER natality; NVSR benchmarks | 51 jurisdictions × 10 years × 2 age groups | Two-way fixed effects (state and year) | Standard errors clustered by state, t with 50 df; wild cluster bootstrap | Internally locked protocol, not externally preregistered | `audit/verify_m10.py` |
| M11 | Human Fertility Database (USA, 1933–2024); NCHS 2025 births; Census estimates and 2023 projections | National period and cohort rates | Nine TFR methods backtested at 72 origins; locked selection rule; age-shape and period-to-cohort transformation; Census rebasing | Historical-error intervals (nominal; failed calibration); scenario ranges | Internally locked protocol; post-review robustness analysis labelled as such | `audit/verify_m11.py`, `audit/verify_m11_forecast.py` |

All four chapters are frozen under SHA-256 manifests. The synthesis changed no frozen file except through the owner-authorized controlled M11 revision F21-1, which changed wording only (`docs/m11_freeze_revision_F21-1.md`).

## 4. Integrated findings

### 4.1 What U.S. adults aged about 18–27 said (M09, 2022–2023; the older part of Generation Z)

| Measure (conservative age proxy, weighted) | Estimate (95% CI) | Claim |
|---|---|---|
| Wants a(nother) child | 69.9% (67.2–72.4) | [C09.01] |
| Intends a(nother) birth | 62.8% (59.8–65.7) | [C09.02] |
| Among those who want a child: does not intend one | 11.2% (9.3–13.4) | [C09.03] |
| of which an explicit "no" | 6.6% (5.1–8.2) | [C09.04] |
| of which sterility-linked | 4.7% (3.2–6.6) | [C09.05] |
| Women's children so far plus expected additional births | 1.61 (1.51–1.70) | [C09.10] |
| Number intended, among intenders | 2.31 (2.24–2.38) | [C09.11] |

- **Who wants children.** Women were less likely than men to want a child (64.1% against 75.7%) [C09.08].
- **The explicit "no".** It was about twice as common at ages 25 and older (10.6%) as at 18–21 (5.1%) [C09.09]. The data are cross-sectional, so ageing cannot be separated from cohort differences.
- **Sterility.** About 42% of the desire–intention gap (4.7 of 11.2 points) is sterility-linked [C09.06]. These respondents were not asked the intention question: the CDC recode classifies them as not intending because they or their partner were reported sterile. Their preferences are not observed.
- **Prediction.** In a planned (not pre-registered) experiment, the evaluated models failed to demonstrate meaningful out-of-sample improvement over the class-prior baseline in identifying the explicit "no" (holdout AUC 0.51 against 0.50) [C09.12]. This does not show that demographic characteristics are unrelated to intentions.
- **Expectations are not desires.** Women's expected total of 1.61 is an expectation, set by the survey's recode to zero additional births after a "no". It is not a desire, and it is not completed fertility [C09.10].

### 4.2 How well forward-looking statements predicted births in an earlier cohort (M01–M08)

The NLSY97 is the only source here that follows the same people from a stated expectation to observed births.
- Its women were born in 1980–84.
- Its question asks for the percent chance of a(nother) birth within five years.

It is therefore a test of near-term expectations in an earlier cohort, not of lifetime desires.

| Result | Value | Claim |
|---|---|---|
| Answers at exactly 0%, 50% or 100% | 70.1% | [C01.02] |
| Birth within five years after saying 0% | 18.4% (16.2–20.7) | [C01.03] |
| Birth within five years after saying 50% | 33.5% | [C01.03] |
| Birth within five years after saying 100% | 73.0% (69.4–76.4) | [C01.03] |
| Ranking (AUC) | 0.726 (0.709–0.744) | [C01.04] |
| Linear calibration slope (1 = calibrated) | 0.476 (0.441–0.510) | [C01.05] |
| Held-out Brier score, stated → recalibrated | 0.249 → 0.198; difference −0.0505 (−0.063 to −0.038) | [C01.06] |
| Women without children: mean stated / observed | 53.2% / 32.5% | [C01.07] |
| Mothers: mean stated / observed | 33.2% / 39.0% | [C01.07] |
| Six years later (2015–16 baseline): AUC; frozen recalibration's mean error | 0.798 (0.779–0.817); +0.065 | [C01.11] |

What holds, and how firmly:
- **Answers carry information but are too extreme.** This is robust to every outcome rule, every missing-outcome bound and the pregnancy restriction: AUC 0.694 and slope 0.405 among women not pregnant at interview [C01.10].
- **Over-statement by childless women** is positive under every weighting and respondent-specific bound: +0.130 to +0.218 in 2009 and +0.102 to +0.199 in 2015 [C01.08].
- **The pooled average over-statement is fragile.** In 2015 its sign depends on the 281 unknown outcomes (bounds −0.021 to +0.064) [C01.09].
- **Unweighted, sample-level results.** No longitudinal weight was applied. None of these is a population estimate for U.S. women born 1980–84 [C01.12].

### 4.3 Where population fertility stands, and how far Generation Z has come (M11)

**Period fertility.**
- The U.S. TFR was 1.593 in 2024 [C11.01]. The 2025 value reconstructed from NCHS births is 1.577 (NCHS-derived 1.576), and is not an official or HFD value [C11.05].
- Nine forecasting methods were backtested at 72 origins under a protocol locked before any model was fitted. No alternative model satisfied the prespecified criteria for replacing the no-change baseline.
  - The closest, an ARIMA model on yearly changes, reduced average error by 5.8% (R = 0.942) against a required R ≤ 0.90 [C11.04].
- The 2040 point forecast is therefore 1.593, with nominal intervals of 1.05–2.42 (80%) and 0.84–3.03 (95%) [C11.02].
  - These intervals contained past outcomes 0.96 of the time at 5–15 years against a nominal 80%, which fails the calibration criterion [C11.03].
  - Built only from post-1977 errors, they would have been badly overconfident.
  - The interval is a description of past forecast errors, not a probability statement about 2040.
- Across methods, 2040 forecasts range from 1.24 to 1.83 [C11.13].
- The Census Bureau's assumed TFR (1.633 in 2025, 1.616 in 2040) lies inside the nominal interval [C11.12].

**Cohort fertility of Generation Z** (births per woman, if 2024 period rates persist):

| Born | By end-2024 (observed) | By end-2040 (projected) | Nominal 80% historical-error interval | Status by 2040 | Claim |
|---|---|---|---|---|---|
| 1995 | 0.88 | 1.75 | 1.57–1.98 | nearly complete (historical completion share 0.998–0.999) | [C11.06] |
| 2002 | 0.19 | 1.48 | 1.25–1.76 | nearly complete by historical standards | [C11.06] |
| 2008 | — | 1.03 | 0.82–1.28 | substantial but incomplete | [C11.07] |
| 2012 | — | 0.62 | 0.46–0.85 | partial (historical completion share 0.562–0.589) | [C11.07] |

How to read the cohort projections:
- **Sensitivity to postponement.** Continued postponement would move the endpoints by about ±0.1, for example to 1.83 for the 1995 cohort and 0.51 for the 2012 cohort [C11.11].
- **Interval coverage.** In pseudo-real-time backtests, cohort intervals covered 0.78, 0.83, 0.94 and 0.96 of outcomes at 5, 10, 15 and 16 years [C11.08]. These are historical-error intervals, not calibrated ones.
- **Origin-local comparison.** A post-review analysis, not pre-specified, chose each strategy only from information available at its origin. It had 1.07–1.17 times the average cohort error of the fixed strategy [C11.09].
  - **The calculation reproduces,** but the scientific interpretation is limited. The difference is concentrated in six early origins (1976–1981), where sparse historical errors and unstable bootstrap selection limit generalization: the bootstrap condition was degenerate at the 15-year horizon.
  - It is therefore not a general measure of how optimistic the fixed-strategy backtest is.
  - The frozen M11 chapter was corrected accordingly under a controlled revision (finding F21-1; `docs/m11_freeze_revision_F21-1.md`).
- **Births.** Births in 2040 are 3.63 million under the main immigration series at no-change fertility, and 3.27–3.81 million across immigration scenarios [C11.10]. These are scenarios, not probabilities.

### 4.4 Housing affordability (M10)

Within states, comparing years relative to the national pattern:

| Estimate (births per 1,000 women per 10-point higher share of renters paying 30%+ of income) | Value (95% CI) | Claim |
|---|---|---|
| Ages 20–24, 2014–2024 (primary) | −2.77 (−5.81 to 0.26); p = 0.073 | [C10.01] |
| Ages 25–29, 2014–2024 | −0.06 (−2.91 to 2.80) | [C10.02] |
| Ages 20–24, 2021–2024 only (mostly Generation Z) | −0.10 (−2.07 to 1.87); minimum detectable effect about 2.8 | [C10.03] |

- **Not robust.** The primary estimate failed the protocol's stability rule:
  - population weighting gives −6.61;
  - the age-matched renter measure gives 0.02;
  - adding state trends gives −0.55 [C10.04].
- **National trends.** Fertility fell steadily: at ages 20–24, 79.0 per 1,000 in 2014 against 55.8 in 2024. The median rent burden fell and then recovered: 50.2% in 2014 against 49.4% in 2024 [C10.05].
- **Interpretation.** The national series therefore offer no support for affordability explaining the decline. The analysis is ecological and cannot identify causal effects [C10.06].

### 4.5 Agreements and tensions across chapters

| Theme | What agrees | What is in tension, and why it is not a contradiction | Combinable? |
|---|---|---|---|
| Fertility is low and has kept falling | M10's national rates (age-specific) and M11's TFR series (all ages) both show a decline to 2024, and M11's 2025 reconstruction shows it continued [C10.05, C11.05] | M10 measures rates for two age groups; M11 the full TFR. Same direction, different quantities | No; they describe the same trend at different levels of aggregation |
| Wanting children is common; projected cohort fertility is below replacement | M09: most adults aged about 18–27 in 2022–23 wanted and intended children [C09.01, C09.02]. M11: oldest Generation Z cohorts project to about 1.75 by age 45 [C11.06] | These are compatible: a yes/no desire says nothing about how many children; an average of 1.75 is consistent with many different distributions of family size and childlessness | **No.** M09 is individuals' answers; M11 is a cohort average under an assumption. No gap can be computed |
| Expectations exceed realisations | M01–M08: childless women's five-year expectations exceeded their births in every bound [C01.08] | Applies to the 1980–84 cohort and a five-year window; M09's expectations of 18–27-year-olds have no follow-up | No; it motivates, but does not measure, a Generation Z gap |
| Economic constraints | M09: higher income goes with a lower chance of an explicit "no" in a model that predicts poorly (odds ratio 0.85 per SD) [C09.14]; M10: no robust state-level association with rent burden [C10.04] | Individual associations and ecological null results answer different questions; neither identifies causes | No |
| Period versus cohort | M11's 2024 TFR (1.593) is below the 1995 cohort's projected 1.75 [C11.01, C11.06] | Cohort totals include the higher rates these women experienced at younger ages; there is no inconsistency | Only within M11's own accounting |
| Uncertainty | M11's TFR and cohort intervals, and M01–M08's calibration drift (+0.065 in 2015) [C11.03, C01.11] | Both show that relationships estimated in one period may not transfer to another | Qualitatively only |

### 4.6 The answer to the question

**Can it be answered?** Not with the precision the question implies [C00.04]. Two levels of answer need different data:
- **A population-average desired-versus-achieved difference** would need a numeric desired family size for Generation Z and the completed lifetime fertility of the same birth cohorts. Neither is available: desire is measured as yes/no, and completed fertility lies in the future (even the 1995–2002 cohorts are only nearly complete by 2040).
- **Individual fulfilment of intentions** would need, in addition, linked longitudinal observations of the same people from stated desire to completed fertility. No source provides them.

**What the evidence does support**, graded:
1. **Most adults aged about 18–27 wanted children in 2022–2023** (well supported, weighted; the older part of Generation Z only) [C09.01].
2. **Among adults aged about 18–27 who wanted a child but did not intend one, about 42% are classified as not intending because they or their partner were reported sterile.** For the explicit "no", the evaluated models failed to demonstrate meaningful out-of-sample improvement from demographic characteristics (well supported) [C09.06, C09.12].
3. **Forward-looking statements are informative but over-confident** (well supported, earlier cohort, unweighted). By extension, expectations stated by Generation Z should not be read as forecasts [C01.03, C01.04, C01.05].
4. **Near-term over-statement concentrated among the childless** (supported in the earlier cohort under every bound) [C01.08]. If this pattern transferred, timing shortfalls would be likely. Whether it transfers to Generation Z is untested.
5. **On current rates, the oldest Generation Z cohorts are on course for about 1.75 births per woman** (a projection under a stated assumption, not a forecast with calibrated uncertainty) [C11.06]. The record gives no reliable signal whether rates will rise or fall [C11.02].
6. **Rent burden does not robustly explain state fertility differences** (ecological, not causal) [C10.04].

**In one sentence:** most of the older part of Generation Z wanted children in 2022–2023, and current rates imply below-replacement fertility for its oldest members, but whether its members will have the families they say they want has not been measured and cannot be inferred from these data [C00.04].

## 5. Discussion

**Desire, intention, expectation and outcome can diverge.**
- The NSFG shows a small desire–intention gap. About 42% of it consists of respondents classified as not intending because of reported sterility; their preferences are not observed.
- The NLSY97 shows a larger and more systematic gap between expectation and outcome. Answers cluster at 0, 50 and 100%, and near-term statements by childless women overstate births.
- Together, these suggest that the larger risk of unfulfilled intentions lies after intentions are formed, in timing and realisation, rather than in the formation of intentions.

That inference crosses cohorts and question formats, so it is offered as a hypothesis, not a finding.

**Aggregate projections.**
- M11's projections show what persisting current rates would imply for cohort fertility. The oldest Generation Z cohorts would end close to their current trajectory, and younger cohorts are too early to judge.
- The forecasting evidence is deliberately modest. No alternative model satisfied the locked model-selection criteria for replacing the no-change baseline, none improved on it consistently across fertility regimes, and long-horizon errors were dominated by regime shifts.
- A reader should therefore treat the 2040 figures as a baseline for comparison, not a prediction of stability.

**Economic explanations.**
- Housing costs are a common explanation for low fertility.
- At the level M10 can measure (state, year and age group), the association is weak, unstable and absent for ages 25–29.
- This does not rule out effects on individuals, effects through other housing measures, or effects on timing rather than completed fertility.

## 6. Competing explanations for a possible shortfall

| Explanation | Evidence in this project | Strength | What would test it |
|---|---|---|---|
| Postponement rather than forgone births | M11: births shift to later ages; postponement changes cohort endpoints by about ±0.1 [C11.11]. M10: lower rates at 20–24 with no association at 25–29 is consistent with timing | Plausible, not established | Completed fertility of the 1995–2002 cohorts after 2040 |
| Infecundity and sterility | M09: about 42% of the desire–intention gap is classified as sterility-linked [C09.06] | Supported as a classification share; individual circumstances and preferences not observed | Longitudinal fecundity and outcome data |
| Partnership | M09: joint and individual intention items differ with partnership; cannot be separated | Possible, not tested | Panel data on union formation |
| Economic constraints (housing) | M10: no robust state-level association [C10.04] | Weak at the ecological level | Individual-level linked housing and fertility data |
| Reporting behaviour (round-number answers) | M01–M08: 70.1% of answers at 0, 50 or 100% [C01.02]; answers act as categories | Supported for expectations | Alternative elicitation formats |
| Changing preferences | M09: cross-sectional; age differences in the explicit "no" cannot be separated from cohort [C09.09] | Untested | Repeated measurement of the same people |
| Period shocks (2008 recession, pandemic) | M01–M08 windows coincide with a post-2008 decline; M10's estimate relies on changes across 2020 [C10.04] | Plausible confounder | Multiple cohorts and periods |
| Composition and immigration | M11: births are scenario-conditional on immigration [C11.10] | Affects births, not rates | — |

## 7. Limitations

The full register is in `docs/final_limitations_register.md`. The most consequential:
1. **No numeric desired family size** for Generation Z in any source [C09.13].
2. **No completed lifetime fertility** for any Generation Z cohort (the 1995–2002 cohorts are only nearly complete by 2040), and no individual follow-up [C11.07].
3. **The only expectation-outcome test is in an earlier cohort** (1980–84). It is unweighted, and it concerns five-year expectations [C01.12].
4. **M09 is cross-sectional and its age proxy only bounds birth year;** respondents under 18 are excluded [C00.02].
5. **M10 is ecological, associational and short after 2020** [C10.03, C10.06].
6. **M11's intervals are uncalibrated historical-error intervals,** with four independent 15-year windows and backtests on the current data vintage [C11.03].
7. **M11 post-review comparison (finding F21-1, resolved).** The origin-local comparison (1.07–1.17) is concentrated in six early origins (1976–1981), where sparse historical errors and unstable bootstrap selection limit generalization [C11.09].
   - The frozen M11 chapter's wording was corrected by an owner-authorized controlled revision (`docs/m11_freeze_revision_F21-1.md`).
   - No number, forecast, interval or locked selection changed.

## 8. Conclusions

| # | Conclusion | Evidence strength |
|---|---|---|
| 1 | Whether Generation Z will have the families it says it wants cannot be established from these data | Definitive about the limits of the evidence [C00.04] |
| 2 | About 70% of U.S. adults aged about 18–27 wanted a(nother) child in 2022–2023, and about 63% intended one | Strong (design-based) [C09.01, C09.02] |
| 3 | Among those who wanted a child, about 1 in 9 did not intend one, and about 42% of that gap was classified as sterility-linked (not asked; preferences not observed) | Strong (design-based) [C09.03, C09.06] |
| 4 | In an earlier cohort, stated birth expectations ranked outcomes well but were far too extreme; childless women's expectations exceeded their births | Strong for that sample; transfer to Generation Z untested [C01.04, C01.05, C01.08] |
| 5 | The 2040 U.S. TFR forecast is 1.593, with wide, uncalibrated historical-error intervals and no directional signal | Moderate (locked protocol; few independent windows) [C11.01, C11.02, C11.03] |
| 6 | If 2024 rates persist, Generation Z cohorts born 1995–2002 reach 1.48–1.75 births per woman by 2040, nearly complete by historical standards but not completed lifetime fertility; later cohorts are partial | Conditional projection [C11.06, C11.07] |
| 7 | Rental cost burden is not robustly associated with state birth rates at ages 20–29 | Ecological; inconclusive [C10.01, C10.02, C10.04] |

## 9. Future research requirements

1. **A numeric desired or ideal family-size item** for Generation Z, asked of the same respondents as intentions. Any cohort desire–achievement comparison depends on it.
2. **Longitudinal follow-up of Generation Z respondents** from stated desire to completed fertility, at least to age 45.
3. **Custom NLSY97 longitudinal weights** (requires the owner's authorization) to turn the M01–M08 sample-level results into population estimates.
4. **Real-time data vintages and probabilistic forecasts** whose calibration can be tested and that are stable across fertility regimes.
5. **Individual-level or linked administrative data** on housing costs, partnership and births, to test the economic explanations that M10 cannot.
6. **Re-estimation when HFD publishes 2025 and later data,** and after 2040 for the 1995–2002 cohorts' completed fertility.

## 10. Verification summary

`audit/scientific-audit.md` sections 21 and 22 hold the full audit record. In summary:
- every material claim cites a matrix entry whose source values were checked against frozen outputs or frozen text;
- the number scanner confirms token coverage only: every numeric token is represented among verified figures. Semantic correctness was established by reviewing the claims in context, not by the scanner;
- headline figures in each chapter were recomputed independently with separate code;
- all five freeze manifests verify (four chapter manifests and the final synthesis manifest);
- the full test suite passes.

## References

Data sources (local copies, retrieval dates and SHA-256 hashes: `docs/final_sources.md`):
- Bureau of Labor Statistics, U.S. Department of Labor. National Longitudinal Survey of Youth 1997 cohort, public-use data (NLS Investigator extracts).
- National Center for Health Statistics. 2022–2023 National Survey of Family Growth public-use files, codebooks, recode specifications and User's Guide (revised July 2025).
- U.S. Census Bureau. American Community Survey 1-year detailed tables B25070, B25072, B23025 and B19013, 2014–2019 and 2021–2024.
- Centers for Disease Control and Prevention, National Center for Health Statistics. Natality on CDC WONDER (2007–2024 and 2016–2024 expanded).
- National Center for Health Statistics. *Births: Final Data* for 2019, 2023 and 2024 (National Vital Statistics Reports 70-2, 74-1, 75-2); 2025 final births (Data Brief 571; VSRR 43); natality public-use files 2024 and 2025.
- Human Fertility Database. Max Planck Institute for Demographic Research and Vienna Institute of Demography. United States, release of 2 July 2026.
- U.S. Census Bureau. Vintage 2024 and Vintage 2025 population estimates; 2023 National Population Projections.

Methods cited by the chapters:
- Bruine de Bruin, W., Fischhoff, B., Millstein, S. G., & Halpern-Felsher, B. L. (2000). Verbal and numerical expressions of probability: "It's a fifty-fifty chance." *Organizational Behavior and Human Decision Processes*, 81(1), 115–131.
- Korn, E. L., & Graubard, B. I. (1990). Simultaneous testing of regression coefficients with complex survey data. *The American Statistician*, 44(4), 270–276.
- Parker, J. D., et al. (2017). National Center for Health Statistics data presentation standards for proportions. *Vital and Health Statistics*, Series 2, No. 175.
- Nadeau, C., & Bengio, Y. (2003). Inference for the generalization error. *Machine Learning*, 52, 239–281.
- Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics*, 13(3), 253–263.
- Harvey, D., Leybourne, S., & Newbold, P. (1997). Testing the equality of prediction mean squared errors. *International Journal of Forecasting*, 13(2), 281–291.
- Lee, R. D., & Carter, L. R. (1992). Modeling and forecasting U.S. mortality. *Journal of the American Statistical Association*, 87(419), 659–671.
- Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2008). Bootstrap-based improvements for inference with clustered errors. *Review of Economics and Statistics*, 90(3), 414–427.
- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209–212.

**Bibliographic status.** The data sources are checked against local provenance records (`docs/final_sources.md`). Method references are given as cited in the chapters; their bibliographic details were not re-checked online in this session (limitations register, L-SRC-2).

## Figures and evidence tables

- `assets/figures/final_evidence_map.png`: who each chapter observes, by calendar year and birth cohort.
- `assets/figures/final_headline_panels.png`: one panel per chapter, each on its own scale and labelled with its estimand; values must not be compared across panels.
- `data/public/final/final_evidence_table.csv`: the 22 headline estimates with estimand type, population, uncertainty type, source file and locator.
- `data/public/final/final_population_map.csv`: design, population, years, birth cohorts and inference for each chapter.
- Chapter figures remain in `assets/figures/` (`stated_expectation_*`, `nsfg_*`, `m10_*`, `m11_*`).
