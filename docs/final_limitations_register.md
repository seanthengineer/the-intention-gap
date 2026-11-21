# Consolidated limitations register

**Status:** **FROZEN, final scientific approval, 2026-11-20.** Manifest `docs/final_synthesis_freeze.sha256`; completion record `docs/final_readiness_assessment.md`. Editing this file needs a recorded decision and a new manifest.

**Scope.** This register collects:
- the limitations of the four frozen chapters;
- the limitations of the synthesis;
- the findings of this audit (`audit/scientific-audit.md` section 21).

**Severity:**
- **Blocking:** prevents research completion until resolved.
- **Material:** a claim must be qualified, or an owner decision is needed.
- **Nonblocking:** documented and accepted.

**Claim column:** affected claims refer to `docs/final_claim_evidence_matrix.csv`.

## A. Limits on answering the research question

| ID | Limitation | Affected claims | Severity | Consequence | What would remove it |
|---|---|---|---|---|---|
| L-Q-1 | No numeric desired or ideal family size for Generation Z in any source; desire is yes/no (NSFG RWANT) | [C09.13], [C00.04] | Material (scope) | A desired-versus-achieved family-size gap cannot be computed and is not reported | A numeric desired family-size item |
| L-Q-2 | No completed lifetime fertility for Generation Z; the 1995–2002 cohorts are only nearly complete by 2040 and later cohorts are substantially incomplete | [C11.07] | Material (scope) | Projections to 2040 are partial cumulative fertility, not completed family size | Observation to about age 45 |
| L-Q-3 | No source follows the same Generation Z individuals from desire to outcome (linked longitudinal data are required for individual fulfilment, beyond what a population-average comparison would need) | [C00.03] | Material (scope) | Individual fulfilment cannot be measured; averages cannot reveal it | Longitudinal panel of Generation Z |
| L-Q-4 | Chapters observe different populations, units and periods: NLSY97 cohort 1980–84; NSFG ages 18–27 in 2022–23; state-year age groups; national rates | [C00.02] | Nonblocking (handled) | Results are not combined numerically; agreements are qualitative | — |

## B. M01–M08 (NLSY97 expectations and outcomes)

| ID | Limitation | Affected claims | Severity | Consequence |
|---|---|---|---|---|
| L-01-1 | Earlier cohort (born 1980–84), five-year expectations, not lifetime desires | [C01.03], [C01.08] | Material (transfer) | Evidence about the reliability of stated expectations, not about Generation Z |
| L-01-2 | Outcomes unweighted; no custom longitudinal weight (needs the owner's authorization) | [C01.12] | Nonblocking (disclosed) | Sample-level results, not population estimates |
| L-01-3 | 7% (2009) and 8% (2015) of outcomes unknown, mostly attrition; pooled average over-statement depends on them | [C01.09], [C01.13] | Nonblocking (bounded) | Pooled average over-statement fragile; childless over-statement robust |
| L-01-4 | Some women pregnant at interview; answers partly report pregnancies | [C01.10] | Nonblocking (bounded) | Discrimination lower among not-pregnant women; "too extreme" holds |
| L-01-5 | Heaping at 0, 50 and 100%; answers act as categories | [C01.02] | Nonblocking | "Too extreme" applies to reported numbers as forecasts, not to beliefs |
| L-01-6 | Labels not checked against birth records; extract release relative to 2025 roster errata probable, not confirmed | [C01.03] | Nonblocking | Small residual measurement uncertainty |
| L-01-7 | Repeated cross-validation exploratory; Nadeau–Bengio correction approximate for grouped folds; held-out bootstrap holds fitted models fixed | [C01.06] | Nonblocking | Intervals describe test-set sampling only |
| L-01-8 | Age and period confounded in the 2015–16 temporal check (same women, six years older) | [C01.11] | Nonblocking | Calibration drift cannot be attributed to age or period |
| L-01-9 | 2009 recalibration gain lacks worst-case bounds (held-out set drawn from labelled women) | [C01.06] | Nonblocking (disclosed) | Robustness established for 2015–16 only |

## C. M09 (NSFG 2022–2023 desires and intentions)

| ID | Limitation | Affected claims | Severity | Consequence |
|---|---|---|---|---|
| L-09-1 | Cross-sectional: answers at one interview, no outcomes | [C09.01], [C09.02] | Material (scope) | No statement about fulfilment |
| L-09-2 | Age proxy only bounds birth year (born 1995–2005); ages 15–17 excluded | [C00.02] | Nonblocking | Covers older Generation Z only |
| L-09-3 | Joint (partnered) and individual intention items cannot be separated from partnership | [C09.03] | Nonblocking | Partnership differences not interpreted |
| L-09-4 | 98 subgroup and 12 expected-birth estimates fail the NCHS standard and are suppressed | [C09.09] | Nonblocking | Parent subgroups not interpreted |
| L-09-5 | No time-stamped protocol; H1 known before specification; H2–H4 planned, not pre-registered | [C09.09], [C09.12] | Nonblocking (disclosed) | Planned comparisons, not confirmatory tests |
| L-09-6 | Small holdout (28 positives) | [C09.12] | Nonblocking | Wide holdout intervals; repeated CV reported separately |
| L-09-7 | Check 03 WARN: one unexplained routing exception | — | Nonblocking | Affects no estimate |
| L-09-8 | Expected births set to zero after a "no" by CDC rule; men's counts not comparable with women's | [C09.10] | Nonblocking | Expected total reported for women only, as an expectation |

## D. M10 (housing cost burden and state fertility)

| ID | Limitation | Affected claims | Severity | Consequence |
|---|---|---|---|---|
| L-10-1 | Ecological inference; no link between renter households and mothers | [C10.06] | Material (scope) | No individual or causal claim |
| L-10-2 | Time-varying confounding and reverse causality; only unemployment (and income) adjusted | [C10.01] | Nonblocking (disclosed) | Association only |
| L-10-3 | Full-period estimate relies on changes across the 2020 gap (pandemic, population-estimate methods) | [C10.04] | Nonblocking (disclosed) | Primary estimate not robust |
| L-10-4 | ACS sampling error of about 47% of residual burden variance (assumption-dependent); SIMEX exploratory | [C10.01], [C10.07] | Nonblocking | Possible attenuation; no corrected estimate claimed |
| L-10-5 | Short post-2020 window; minimum detectable effect about 2.8 | [C10.03] | Nonblocking | Cannot rule out modest associations |
| L-10-6 | Age groups contain different cohorts each year; not a Generation Z cohort study | [C10.06] | Nonblocking | Age-period description only |
| L-10-7 | Internal protocol lock, not external preregistration | [C10.01] | Nonblocking | — |

## E. M11 (fertility forecasts and Generation Z cohorts)

| ID | Limitation | Affected claims | Severity | Consequence |
|---|---|---|---|---|
| L-11-1 | Historical-error intervals failed the calibration criterion; era-dependent | [C11.02], [C11.03] | Material (interpretation) | Intervals are not probabilities; reported as nominal |
| L-11-2 | Four independent 15-year windows (one since 1977) | [C11.04] | Nonblocking | Weak support for any long-horizon statement |
| L-11-3 | Pseudo-real-time backtests on the current data vintage, not real-time vintages | [C11.04] | Nonblocking | Backtest errors may be optimistic |
| L-11-4 | Univariate methods only; no covariates, Bayesian or expert methods | [C11.01] | Nonblocking | — |
| L-11-5 | Cohort projections assume persisting 2024 period rates and HFD Lexis conventions | [C11.06], [C11.07] | Nonblocking | Postponement changes endpoints by about ±0.1 [C11.11] |
| L-11-6 | 2025 value reconstructed, not HFD or official | [C11.05] | Nonblocking | Secondary only |
| L-11-7 | Births conditional on Census immigration scenarios and rebasing | [C11.10] | Nonblocking | Scenario ranges, not probabilities |
| L-11-8 | **Audit finding F21-1 (resolved by controlled revision).** The post-review origin-local result (1.07–1.17) reproduces, but the difference from the fixed strategy is concentrated in six early origins (1976–1981). There, sparse historical errors (10–15 at h = 15) and unstable bootstrap selection, with a degenerate 15-year bootstrap term, limit generalization | [C11.09] | Material (interpretation); **resolved**: the frozen M11 wording was corrected under an owner-authorized controlled revision (`docs/m11_freeze_revision_F21-1.md`) | Not a general measure of backtest optimism; no number, forecast, interval or locked selection changed |
| L-11-9 | **Audit finding F21-2.** The selection bootstrap resamples horizons independently, so the variance of the averaged ratio is understated | [C11.04] | Nonblocking (disclosed in protocol) | Conservative for retaining no change |
| L-11-10 | Retrospective strategy choice in the fixed-strategy cohort backtest; eight candidates without multiplicity adjustment | [C11.08], [C11.09] | Nonblocking (disclosed) | Backtest describes the selected strategy |

## F. Synthesis, code and publication

| ID | Limitation or finding | Severity | Consequence or action |
|---|---|---|---|
| L-SYN-1 | The synthesis adds no estimates; cross-chapter statements are qualitative | Nonblocking | Avoids combining incompatible estimands |
| L-SRC-1 | Terms of use for CDC WONDER, NSFG, NLSY97 and the Census data were not verified against provider documentation in this session; no licence text is held locally | Nonblocking for scientific review; **required before publication** | Publication-readiness requirements listed in `docs/final_sources.md` section 5 |
| L-SRC-2 | Method references are given as cited; bibliographic details were not re-checked online | Nonblocking | Check before publication |
| L-SRC-4 | Some public M11 tables reproduce HFD-produced estimates verbatim. The owner confirmed that the official HFD User Agreement licenses HFD-produced estimates under a Creative Commons Attribution licence, while input data keep their original providers' licences. The project used HFD-produced estimates only, so redistribution is permitted with attribution and an indication of changes. The local provenance note ("not redistributed") predates this and should be updated | Nonblocking; **attribution and licence notice required at publication** | Table-by-table classification, attribution text and open questions in `docs/final_sources.md` section 5 |
| L-SRC-3 | NSFG and NLSY97 raw files have no `provenance.json` | Nonblocking | NLSY97 raw hash matches the frozen reference; NSFG dimensions match CDC (Stage 3 Check 01) |
| L-REP-1 | **Audit finding F21-4 (wording corrected).** Line endings in frozen files are mixed. All public output files, the M11 manifest, the M11 chapter and the audit log use CRLF; the M01–M08, M09 and M10 manifests and the methodology use LF; the M11 decision log mixes both. Manifest hashes and byte-identical reruns hold only for the exact bytes | Material for publication; nonblocking for review | Before any Git commit, store frozen files without line-ending conversion, or hashes will fail on checkout |
| L-REP-2 | **Audit finding F21-5.** Transitive dependencies not locked; results produced with one interpreter (Python 3.15.2) | Nonblocking | Full `pip freeze` record in `docs/final_reproducibility_guide.md` |
| L-REP-3 | **Audit finding F21-6.** Tests and verifiers that need restricted data skip in a clean checkout | Nonblocking | "Tests pass" in a clean checkout does not cover data-dependent paths |
| L-COD-1 | **Audit finding F21-3.** `population_validity.py` warnings arise only from synthetic test inputs; real data raise none | Nonblocking | No result affected; no change made (frozen file) |
| L-COD-2 | **Audit finding F21-7.** Frozen M01–M08 documents print the held-out recalibration gain as −0.051; the stored point estimate is −0.050494 [C01.06] | Nonblocking (rounding) | Synthesis reports −0.0505 [C01.06] |
| L-COD-3 | Pyright reports many type errors, mostly pandas stub noise, and there is no Pyright configuration | Nonblocking | Not quality evidence either way |
