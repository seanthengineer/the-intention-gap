# Executive scientific summary: will Generation Z have the families they say they want?

**Status:** **FROZEN, final scientific approval, 2026-11-20.** Manifest `docs/final_synthesis_freeze.sha256`; completion record `docs/final_readiness_assessment.md`. Editing this file needs a recorded decision and a new manifest.

**Sources:** full argument in `docs/final_synthesis_manuscript.md`. Each bracketed claim ID is traced in `docs/final_claim_evidence_matrix.csv`.

## Answer

**Not establishable from the existing evidence** [C00.04].

Two levels of answer need different data:
- **A population-average desired-versus-achieved difference** needs a numeric desired family size for Generation Z and the completed lifetime fertility of the same birth cohorts.
- **Individual fulfilment** needs, in addition, linked longitudinal observations of the same people.

No source in this project provides either for Generation Z (born 1995–2012):
- the 2022–2023 NSFG measures desire only as yes/no, and covers only adults aged about 18–27 [C09.13];
- completed lifetime fertility lies in the future for every Generation Z cohort; by 2040 the 1995–2002 cohorts are only nearly complete [C11.07].

What the evidence supports is a set of separate, bounded statements. None of them is a measured desire–achievement gap.

## Five findings

| # | Finding | Kind of evidence | Strength |
|---|---|---|---|
| 1 | In 2022–2023, 69.9% of U.S. adults aged about 18–27 (the older part of Generation Z) wanted a(nother) child, and 62.8% intended one [C09.01, C09.02] | Stated desire and intention; weighted, design-based | Strong |
| 2 | Of those who wanted a child, 11.2% did not intend one; about 42% of that gap was classified as sterility-linked (respondents not asked because they or their partner were reported sterile), not a stated "no" [C09.03, C09.06]. Models using demographic characteristics failed to demonstrate meaningful out-of-sample improvement in predicting the "no" (holdout AUC 0.51 against 0.50) [C09.12] | Stated intention | Strong |
| 3 | In an earlier cohort (women born 1980–84), stated chances of a birth within five years ranked outcomes (AUC 0.726) but were far too extreme (linear calibration slope 0.476) [C01.04, C01.05]. Childless women overstated their births under every bound [C01.08] | Stated expectation against observed births; unweighted sample | Strong for that cohort; transfer to Generation Z untested |
| 4 | The 2040 U.S. TFR forecast is the 2024 level, 1.593. Its nominal 80% historical-error interval is 1.05–2.42, which failed its calibration check, so there is no reliable directional signal [C11.01, C11.02, C11.03] | Model prediction (no-change forecast) | Moderate |
| 5 | If 2024 rates persist, women born in 1995 reach about 1.75 births by the end of 2040, which is nearly complete by historical standards but not completed lifetime fertility. Women born in 2012 reach about 0.62, which is partial [C11.06, C11.07] | Projected cumulative cohort fertility | Conditional on persisting rates |

**Housing.** Rent burden was not robustly associated with state birth rates: −2.77 per 10 points at ages 20–24 (95% CI −5.81 to 0.26), and none at 25–29 [C10.01, C10.02]. This is ecological, not causal.

## What must not be inferred

- **No gap can be calculated.** No "gap" between desired and achieved family size can be calculated by subtracting projected cohort fertility (M11) from survey answers (M09). They describe different people, measures and points in time.
- **The forecast intervals are not probabilities.** The forecast intervals are historical-error ranges that failed calibration [C11.03].
- **Projections are not completed fertility.** No cohort projection to 2040 is completed lifetime fertility; those for people born after 2002 are far from complete [C11.07].
- **The housing results are not causal.** M10 gives associations only [C10.06].
- **The NLSY97 results are not population estimates.** They are unweighted sample results for a cohort born 1980–84, not population estimates and not Generation Z results [C01.12].

## Audit outcome in brief

- **Matrix:** every material claim cites a matrix entry whose values were checked against frozen sources. The number scanner confirms token coverage only; the claims themselves were reviewed in context.
- **Independent recomputation:** headline results of all four chapters were recomputed with separate code and agree.
- **Freeze manifests and tests:** all five freeze manifests verify (the four chapters and this synthesis), and the full test suite passes.
- **One material qualification, now resolved (F21-1).** The M11 statement that the fixed-strategy cohort backtest was "optimistic by 7–17%" was over-general [C11.09].
  - The calculation reproduces. But the difference is concentrated in six early origins (1976–1981), where sparse historical errors and unstable bootstrap selection limit generalization.
  - The frozen M11 chapter was corrected by an owner-authorized controlled revision (`docs/m11_freeze_revision_F21-1.md`). No forecast, interval or accepted M11 number changed.
- Details: `audit/scientific-audit.md` section 21 and `docs/final_readiness_assessment.md`.

## What would answer the question

- A numeric desired family-size item for Generation Z.
- Longitudinal follow-up of the same respondents to completed fertility (about age 45).
- Calibrated probabilistic forecasts.
