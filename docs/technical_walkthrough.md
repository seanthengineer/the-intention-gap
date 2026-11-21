# Technical walkthrough

Short, evidence-linked answers to the questions a technical reviewer, researcher or interviewer is likely to ask. For depth, follow the links; for the full argument, read the [manuscript](final_synthesis_manuscript.md).

## The project

**Why this problem?**
- U.S. fertility has fallen to about 1.6 births per woman (HFD period TFR, 2024).
- Surveys meanwhile report that most young adults want children.
- It is tempting to call the difference an "intention gap" and to project it onto Generation Z. The project asks whether the available evidence can actually support that claim, and builds each piece needed to test it.

**What is distinctive about it?**
- **Integration.** Four research designs answer one question: a longitudinal test of stated expectations, a weighted cross-sectional survey, a state panel and a cohort forecast.
- **Discipline about what the data can say.** The integrated answer is "not establishable from the existing evidence". It is backed by an explicit map of who each data source observes ([evidence map](visual_atlas.md#who-each-chapter-observes)).
- **Verification infrastructure.** Independent recomputation, a claim-to-evidence matrix and hash-frozen results.

The methods themselves are standard and are not claimed to be new.

**What is original?** The research question and its decomposition; the choice and reconciliation of sources; the outcome rules for the NLSY97 rosters; the locked protocols; the verification design; and the synthesis.

## Data

**Why these datasets?** Each is the authoritative public source for one link in the argument:
- **NLSY97:** stated expectations followed by observed births in the same people.
- **NSFG 2022–2023:** the only national survey of Generation Z's wanting and intending.
- **ACS and CDC WONDER:** state housing burden and birth rates.
- **Human Fertility Database:** a consistent long series for forecasting, cross-checked against NCHS and Census figures.

**How were the data acquired and validated?**
- Every raw file is SHA-256-hashed in a `provenance.json` (221 files in 10 records), and the synthesis verifier re-hashes them.
- Each chapter benchmarks against published statistics:
  - the CDC NSFG benchmark (pill use, women 20–24: 18.9586%, SE 2.0226) is reproduced to the published digits;
  - 2024 state birth rates match NVSR 75-2 for 102 of 102 state-age cells;
  - the HFD period TFR agrees with NCHS published values for 2010–2024.

Records: [`m10_data_feasibility.md`](m10_data_feasibility.md), [`m11_data_feasibility.md`](m11_data_feasibility.md), [`nsfg_stage3_validation.md`](nsfg_stage3_validation.md).

**How were incompatible sources reconciled?**
- CDC WONDER's 2007–2024 database lacked rates after 2020, so a second export (2016–2024 expanded) was reconciled cell by cell before it was used. A permanent test guards the seam ([decision 8](engineering_decisions.md#8-incompatible-cdc-natality-denominators-m10)).
- NLSY97 rosters disagree across rounds, so explicit reconciliation rules define the outcome ([decision 1](engineering_decisions.md#1-turning-inconsistent-birth-rosters-into-a-five-year-outcome-m01m04)).

**Missing data and survey weights?**
- **NSFG:** full design-based estimation with weights, strata and clusters, using linearization and Korn–Graubard intervals, with NCHS reliability suppression.
- **NLSY97:** missing outcomes are bounded, not imputed. Weighted analyses use the baseline weights with a delete-one-PSU jackknife. Outcome results stay unweighted because valid longitudinal weights would require submitting respondent IDs ([decision 4](engineering_decisions.md#4-survey-weights-and-missing-outcomes-without-restricted-weights-m05m071)).

## Modelling and evaluation

**How were prediction targets defined?**
- **NLSY97:** at least one biological birth within five years of the 2009–10 interview (`analysis/build_outcomes.py`, [methodology §3](methodology.md#3-five-year-outcome)).
- **NSFG:** an explicit "no" versus a positive intention, among those who want a child (`analysis/nsfg_models.py`).
- **M11:** period TFR and cohort cumulative fertility.

**How was feature leakage prevented?**
- NLSY97 siblings are kept on one side of the split by a household-grouped split.
- The NSFG model uses a feature dictionary with a stated reason for every inclusion, enforced in code (`assert_no_leakage`), and an isolated cluster holdout.
- M11 backtests refit every model using only data up to each origin.

**Why these models, and what were the baselines?** Each model was compared with a simple baseline first:

| Chapter | Baseline | Models |
|---|---|---|
| NLSY97 | Constant rate; the stated answer itself | Logistic recalibration; logistic with covariates |
| NSFG | Class prior | Penalized logistic regression; histogram gradient boosting |
| M10 | — (fixed-effects inference) | State and year fixed effects |
| M11 | No change | Nine methods, including ARIMA and exponential smoothing, implemented directly with NumPy and SciPy |

**What happened when more complex models failed?** They were reported as failing:
- **NSFG classifier:** holdout AUC 0.51 against 0.50 for the dummy.
- **M11:** no forecasting method met the locked replacement rule, so the no-change baseline was kept.
- **M10:** the housing association was not robust.

None of these was tuned further after the result was known.

**How were predictions evaluated?**
- Brier score, ROC AUC, PR-AUC, calibration slope and calibration tables (NLSY97, NSFG).
- MAE ratios against no change at 5, 10 and 15 years, with Diebold–Mariano tests reported as descriptive only (M11).

**Uncertainty and calibration?** Interval types are matched to designs (Wilson, household-cluster bootstrap, design-based, cluster-robust CR1 with wild bootstrap, historical-error). They are labelled by type everywhere. M11's intervals **failed** their pseudo-real-time calibration check and are not presented as probabilities ([decision 13](engineering_decisions.md#13-uncertainty-intervals-that-failed-calibration-m11)).

**Robustness and sensitivity?**
- Outcome-rule scenarios and missing-outcome bounds (NLSY97).
- Alternative cohort definitions and designs (NSFG).
- Lags, periods, weights, measures, trends and leave-one-state-out (M10).
- Training windows, origins, age shapes and cohort conventions (M11).

The full list for each chapter is in [`research_pipeline.md`](research_pipeline.md#2-which-steps-apply-to-which-chapter).

## Verification and testing

**How was independent verification done?** Each chapter has a verifier in `audit/` that recomputes headline results with **separately written code**. Examples:
- the NSFG estimates are re-coded with Polars and re-estimated with the `svy` library;
- M10's fixed effects use alternating projections and a separate CR1 implementation;
- NLSY97 labels are rebuilt from the codebook.

Checks are labelled INDEPENDENT, RECONCILIATION or REPRODUCIBILITY so that a same-code rerun is never presented as independent evidence. The final synthesis verifier checks all 155 claim-matrix entries against frozen outputs.

**What does the test suite demonstrate?** That the code computes what it claims on controlled inputs:
- synthetic-data tests of outcome rules, estimators and survey variance;
- checks of the frozen outputs' internal consistency;
- freeze-integrity tests over all 221 frozen files;
- tests of the publication tooling.

**What does it not demonstrate?** That the science is right. Tests confirm implementation behaviour, not that a design is appropriate or a conclusion valid; that is the job of the protocols, the independent verifiers and the limitations register. In a public clone, tests that need restricted data are **skipped**, and the CI summary reports how many.

**Can someone reproduce the work?**
- **Without restricted data:** anyone can install the hash-locked environment, run the source-only test suite and the freeze checks, and re-derive every figure in the synthesis from the published tables.
- **Full reproduction:** this needs the source data, obtained by the reader from the providers: free public downloads for NLSY97 (NLS Investigator), NSFG, CDC WONDER, NCHS and Census, and a free HFD account. Steps: [`final_reproducibility_guide.md`](final_reproducibility_guide.md).

**What needs restricted data?** Nothing in the project uses restricted-access data. "Restricted" here means not redistributable: respondent-level survey extracts and the HFD archive, which the HFD asks users not to pass on. These stay local; see [`licensing_and_attribution.md`](licensing_and_attribution.md).

## Technology actually used

Verified against the imports in the code and `requirements-lock.txt`. Publication tooling added in this phase is marked *(publication)*.

| Area | Tool or concept | Where |
|---|---|---|
| Language and data | Python 3.15; pandas 3.1; NumPy 2.5 | Throughout `analysis/` |
| Independent survey checks | Polars 2.1; `svy` 0.37 | `audit/verify_nsfg_m09.py`, `audit/nsfg_stage3_checks.py` |
| Statistics | SciPy (distributions, optimisation); own implementations of survey linearization, JKn jackknife, Korn–Graubard intervals, adjusted Wald tests, CR1 cluster-robust variance, wild cluster bootstrap | `analysis/survey_design.py`, `nsfg.py`, `m10_models.py` |
| Machine learning | scikit-learn: `LogisticRegression`, `HistGradientBoostingClassifier`, `DummyClassifier`, grouped splits (`GroupShuffleSplit`, `StratifiedGroupKFold`), pipelines with imputation and encoding; ROC AUC, PR-AUC (average precision), Brier score | `analysis/analyze_calibration.py`, `nsfg_models.py` |
| Forecasting | No-change, drift and mean benchmarks; simple and damped-trend exponential smoothing; AR and ARIMA(p,1,0) by AICc; compositional Lee–Carter age shapes; Lexis-triangle cohort transform; pseudo-real-time backtesting | `analysis/m11_models.py`, `m11_backtest.py`, `m11_cohorts.py` |
| Data acquisition | Census Data API (HTTP, key read from the environment, never stored); file provenance with SHA-256 | `analysis/acs_housing.py`, `m11_sources.py` |
| Figures | matplotlib | `analysis/analyze_calibration.py`, `m11_figures.py`, `final_synthesis.py` |
| Testing | `unittest` (no pytest, by project decision) | `tests/` |
| Integrity | SHA-256 freeze manifests; independent verifiers; claim-to-evidence matrix | `docs/*_freeze.sha256`, `audit/` |
| Static analysis *(publication)* | Pyright 1.1.414 with a recorded baseline | `pyrightconfig.json`, `tools/pyright_baseline.py` |
| Reproducible installs *(publication)* | pip-tools hash-locked requirements | `requirements-lock.txt` |
| CI *(publication)* | GitHub Actions workflows, prepared but **not yet run** on GitHub | `.github/workflows/` |
| Release engineering *(publication)* | Release inventory, credential and disclosure scan, link checker, Git byte-preservation rules | `tools/release.py`, `.gitattributes` |

Not used: statsmodels, PyTorch, Poetry, Docker. A prototype Streamlit dashboard for the first chapter exists locally but is **not in this repository**; Streamlit and Altair remain in the locked environment because the validated research environment includes them. Dashboard development is a separate future phase.

## Author contribution and AI assistance

*Draft for the author to confirm before release.*

- **Research direction and decisions (the author).**
  - Posed the research question, defined Generation Z as the 1995–2012 birth cohorts, and set each chapter's scope.
  - Directed the work as numbered assignments and chose the data sources.
  - Downloaded the data that need a personal account or manual export (NLSY97 extracts, the CDC WONDER natality exports, the HFD archive).
  - Made the governing decisions: authorizing machine learning for one chapter only, not submitting respondent IDs for custom weights, and the controlled M11 revision.
  - Reviewed every assignment, requested corrections, and approved each freeze.
- **Implementation (AI-assisted).** Code, tests, independent verifiers, documentation and figures were written with an AI coding assistant (Anthropic's Claude, through Claude Code) working under the author's direction and review. The engineering decisions document records where that implementation was wrong and how it was caught.
- **Third-party work.** Python libraries are listed in `requirements-lock.txt`. Methods are cited in [`bibliography.md`](bibliography.md). The data belong to their providers ([`licensing_and_attribution.md`](licensing_and_attribution.md)).
- **Status.** An independent research project, **not peer-reviewed** and not affiliated with any data provider.

## What would improve the research

From the manuscript's [section 9](final_synthesis_manuscript.md#9-future-research-requirements):
- a numeric desired-family-size item for Generation Z, asked of the same respondents as intentions;
- longitudinal follow-up of Generation Z respondents to completed fertility (at least age 45);
- custom NLSY97 longitudinal weights, to turn sample-level results into population estimates;
- real-time data vintages and probabilistic forecasts whose calibration can be tested;
- individual-level or linked data on housing costs, partnership and births;
- re-estimation as the HFD publishes 2025 and later data.
