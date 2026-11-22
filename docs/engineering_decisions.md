# Engineering decisions: how the project was built

I organized the research from 17 to 20 November 2026 as a sequence of numbered assignments (M01–M11), reviewing each before authorizing the next. Here I document the decisions that shaped the work using the audit log ([`audit/scientific-audit.md`](../audit/scientific-audit.md)) and the chapter records. I include mistakes and corrections because several useful checks emerged from problems discovered during development.

For each decision, I record the problem, its importance, the alternatives, the approach adopted, its verification and its remaining limitations.

---

### 1. Turning inconsistent birth rosters into a five-year outcome (M01–M04)

- **Problem.** NLSY97 records each child's birth month in rosters that are re-reported every round. Dates and counts sometimes disagree between rounds, and some births fall in the boundary months of the five-year window.
- **Why it mattered.** Every result in the first chapter depends on knowing who had a birth within five years of the 2009–10 interview.
- **Options.** Trust the latest roster; match children across rounds by exact date; or reconcile by count, with explicit rules for conflicts.
- **Choice.** A conservative outcome: rosters are reconciled across the 2009, 2015 and 2017 rounds, and ambiguous or incomplete histories are labelled *unknown* rather than guessed (3,404 of 3,660 eligible women labelled).
- **Verification.** An independent re-implementation, `audit/verify_outcomes.py`, initially produced **11 extra unknowns**. They came from matching children by exact date, whereas the written rule reconciles by count. With the rule implemented as written, all 3,660 labels agreed. The strict date rule became a sensitivity scenario rather than being discarded.
- **Trade-off.** 7% of outcomes are unknown, mostly through attrition. They are handled by bounds, not imputation (entry 4).

### 2. Pregnancy at the time of the answer (M04.1–M04.3)

- **Problem.** The audit first concluded that current pregnancy was not observed. That was wrong: the self-administered section asks "Are you pregnant now?" (YSAQ2-315).
- **Why it mattered.** Women who were already pregnant could state high chances and then have a birth, inflating apparent accuracy.
- **Choice.** A supplementary extract was requested. 187 women (5.1%) reported a pregnancy. Results were re-estimated among women who were not pregnant, and the earlier statements were corrected in the README and dashboard.
- **Verification.** Among non-pregnant women, the answers ranked outcomes less well (AUC 0.694 against 0.726) and were still too extreme.
- **Trade-off.** The headline figures still include pregnant women, labelled as such, because the original analysis was defined that way.

### 3. Preventing leakage between related respondents (M02)

- **Problem.** NLSY97 includes siblings from the same household.
- **Why it mattered.** A random split would place siblings in both training and test sets and overstate out-of-sample accuracy.
- **Choice.** A household-grouped held-out split (fixed seed), grouped cross-validation, and household-cluster bootstrap intervals.
- **Trade-off.** One split is noisy. Repeated grouped cross-validation was added and labelled **exploratory**, because it was introduced after the held-out results were known.

### 4. Survey weights and missing outcomes without restricted weights (M05–M07.1)

- **Problem.** Population-level outcome estimates need custom longitudinal weights. The NLS service produces them only if respondent IDs are submitted.
- **Options.** Request the custom weights; use cross-sectional weights; or report the outcome results as unweighted sample results and bound what weighting and missingness could change.
- **Choice.** I did not submit respondent IDs for custom longitudinal weights, so the outcome figures remain **unweighted and are labelled as sample results**. Design-based standard errors (a delete-one-PSU JKn jackknife over the survey's strata and PSUs) were used where weights were valid: for the baseline answers.
- **Verification and correction.** Bounding initially filled all missing outcomes uniformly. M07.1 showed that uniform fills are **not** worst-case bounds for differences such as a recalibration gain. They were replaced by exact per-respondent bounds; for the 2009 gain, bounds could not be established and this is stated.
- **Trade-off.** No outcome figure from this chapter is a population estimate.

### 5. Questionnaire routing anomalies in the NSFG (M09)

- **Problem.** Check 03 of the NSFG validation found five respondents whose answers did not follow the documented routing.
- **Choice.** Each case was traced through the marital-status, partner-sterility and expected-children variables. Three cohabiting men with missing partner-sterility status are recoded by CDC itself; one woman has a blank questionnaire section; one man has an unexplained blank intention answer. The check stays at **WARN** rather than being forced to pass, and an earlier note claiming a variable was not public was corrected.
- **Trade-off.** One documented WARN in a 19-check validation, rather than a clean but less honest PASS.

### 6. Publishing survey estimates that fail reliability standards (M09 closure)

- **Problem.** The first public tables included subgroup estimates that fail the NCHS presentation standard for proportions. The figures drew them as open markers.
- **Choice.** The estimate, SE, interval, effective n and event count are blanked in 98 subgroup rows and 12 expected-birth rows, and figures no longer draw them. Complete tables stay local in `data/processed/`.
- **Verification.** `tests/test_nsfg_m09.py` checks the public tables for suppressed values; every unsuppressed value was confirmed unchanged (audit section 17.1).

### 7. A machine-learning experiment that did not work (M09)

- **Problem.** Can demographic and socioeconomic characteristics predict who wants a child but explicitly does not intend one?
- **Guardrails.**
  - I limited the machine-learning experiment to this research task.
  - Every feature is in a feature dictionary with a reason for inclusion, and `assert_no_leakage` enforces it in code.
  - Evaluation uses an isolated cluster holdout, so no PSU appears in both training and test.
  - A class-prior dummy model is the baseline.
- **Result.** Holdout ROC AUC 0.51 for logistic regression against 0.50 for the dummy; gradient boosting reached 0.44. Cross-validated AUC was about 0.62, with Brier skill of about 1%.
- **Choice.** Report the negative result plainly. The evaluated models failed to show meaningful out-of-sample improvement. That is not evidence that demographics are unrelated to intentions, and the documents say so.

### 8. Incompatible CDC natality denominators (M10)

- **Problem.** The CDC WONDER "Natality, 2007–2024" export gave births for 2021–2024 but **no rates**: its bridged-race population denominators end in 2020.
- **Options.** Drop 2021–2024; compute rates with another denominator; or re-export from a database with consistent denominators.
- **Choice.** I exported "Natality, 2016–2024 expanded". The series uses 2014–2015 from the original database and 2016–2024 from the expanded one.
- **Verification.**
  - The two exports were reconciled on 918 shared keys: births, populations and rates are identical for 2016–2020, and births are identical for 2021–2024. A permanent test with an independent parser fails on any disagreement.
  - State rates for 2024 match NVSR 75-2 Table 6 at published precision (102 of 102).
- **Trade-off.** Two source databases in one series, documented and tested at the seam.

### 9. Measurement error and an unidentified model (M10)

- **Problem 1.** ACS rent-burden shares are survey estimates. An early calculation said 54% of the remaining within-state variation was sampling noise.
- **Correction.** That calculation ignored the two-way demeaning. Done correctly, the expected share is about 47% (27–74% if the published margins of error are off by ±25%). **No attenuation-corrected effect is claimed**; SIMEX was run as exploratory only.
- **Problem 2.** The stacked two-age-group design was rank-deficient: age-specific year effects together with state-by-age effects.
- **Correction.** The design was rebuilt without the redundant column, and the estimator now **refuses unidentified designs**. Separately, the result tables kept only six significant digits, which caused differences of about 1e-5 against the independent recomputation; they now keep ten.
- **Result.** The primary association at ages 20–24 (−2.77 births per 1,000 women per 10 points, 95% CI −5.81 to 0.26) was **not robust** under the protocol's own rule.

### 10. Locking protocols before fitting (M10, M11)

- **Problem.** With many defensible specifications, results can drift toward whatever looks best.
- **Choice.** M10 and M11 each have a protocol whose SHA-256 is recorded in a lock file before any model is fitted. The analysis code reads its settings from the hashed protocol and **refuses to run if the protocol has changed**. Amendments are recorded: one pre-fit amendment in M10 and none in M11.
- **Limit.** These are internal locks, not external preregistrations, and the documents say so. M09 had no time-stamped protocol, so its comparisons are labelled "planned, not pre-registered".

### 11. A join bug in Human Fertility Database files (M11)

- **Problem.** HFD cohort summaries appeared to disagree with the project's own sums.
- **Cause.** A bug in the project's code, not in the HFD. Exposure files label open age groups as `12` and `55`, while rate files use `12-` and `55+`. Joining on the labels silently dropped 182 cells.
- **Fix.** Explicit open-age handling in `analysis/hfd.py`. All 16 HFD internal-consistency checks pass, and no HFD value changed.

### 12. When no alternative satisfies the locked replacement criteria (M11)

- **Problem.** Nine methods were backtested at 72 historical origins.
- **Locked rule.** An alternative replaces the no-change baseline only if it cuts error by at least 10% (ratio ≤ 0.90), among other conditions.
- **Result.** The best alternative, ARIMA, reached a ratio of 0.942. **No alternative met the criteria, so the baseline was retained**: the 2040 TFR forecast is the 2024 level, 1.593.
- **Check on the rule.** A pseudo-real-time version of the selection rule, using only errors known at each origin, did worse than always choosing no change (1.02–1.06 times its error).
- **How the backtests are described.** They use the 2026 HFD data vintage at every origin, so they are pseudo-real-time, not real-time forecasts.

### 13. Uncertainty intervals that failed calibration (M11)

- **Problem.** Intervals built from all past forecast errors over-covered (80% intervals contained 96% of outcomes), because they carry baby-boom-era errors. Intervals from post-1977 errors under-covered badly at long horizons.
- **Choice.** No interval method passed the prespecified calibration check, so none is presented as a probability. They are labelled "historical-error interval (nominal level) ... not a validated probability interval", in the tables, the data dictionary and the figures.

### 14. Correcting a frozen chapter without rewriting history (F21-1)

- **Problem.** The final audit found that the M11 statement "the fixed-strategy cohort backtest was optimistic by 7–17%" was over-general. The difference was concentrated in six early origins (1976–1981), where few historical errors existed and bootstrap selection was unstable.
- **Choice.**
  - A **controlled freeze revision** that I authorized.
  - The original and revised wording, the evidence, the reason and the hashes are recorded in `docs/m11_freeze_revision_F21-1.md`.
  - Only the affected sentences changed; no forecast, interval or accepted number did.
  - The manifest was updated by the documented procedure, and the original archive was kept.

### 15. Freezing results, and making the freeze survive Git (all chapters, publication)

- **Problem 1.** Results needed to stay exactly as reviewed.
- **Choice.** Five SHA-256 manifests now cover 221 files: code, tests, documents, public tables and figures. `audit/verify_freeze.py` discovers every manifest. New freezes add new manifests and tests; the original checker is never edited.
- **Problem 2.** The frozen files mix LF, CRLF and mixed line endings, so ordinary Git line-ending conversion would change their bytes and break the hashes.
- **Verification.** In disposable repositories, without protection, `core.autocrlf=true` changed up to 135 of the 221 frozen files. With `.gitattributes` unsetting every conversion attribute, all 221 stayed byte-identical in all 12 combinations of commit and checkout settings (`docs/release_readiness.md`).

### 16. Verifying the verifier (final synthesis)

- **Problem.** The synthesis verifier checks that every number in the manuscript is backed by a frozen value, and that check could itself be wrong.
- **What went wrong.** Its regular expressions were first written through shell heredocs, which silently turned `\b` into a backspace and `\1` into a control character. The scanner then missed numbers at the end of sentences.
- **Fix.** Regression tests for each pattern. The scanner's role is also stated precisely: it checks **token coverage**, not whether each statement is semantically correct; claims were reviewed in context separately.
- **Source-only behaviour.** Missing restricted inputs now report SKIP, a hash mismatch always fails, and strict mode (`--require-data`) still fails on missing data.

---

**What these decisions add up to.** The project prefers a documented limitation to an unsupported result. Unknown outcomes are left unknown, the failed model and the failed interval check are reported, the housing association is called "not robust", and the integrated question is answered "not establishable from the existing evidence". Each of those answers is backed by a check that someone else can rerun.
