# Research completion record and publication-readiness assessment

**Status:** **FROZEN, final scientific approval, 2026-11-20.**

**Approval.** The independent source-package review accepted the scientific synthesis, the frozen research findings, the controlled M11 revision and the project-wide audit. The bounded final corrections (section 3) were then made and verified, and the synthesis was frozen.

**Manifest:** `docs/final_synthesis_freeze.sha256`, checked by `python audit/verify_freeze.py` and `tests/test_final_synthesis_freeze.py`.

**Changes after freezing:** editing any file in the manifest needs a recorded decision and a new manifest.

## 1. Final recommendation

**THE INTENTION GAP — SCIENTIFIC RESEARCH COMPLETE AND FROZEN.** Publication work requires separate authorization (section 6).

## 2. Accepted scientific conclusions

1. **The question cannot be established from the available data:** "Will Generation Z have the families they say they want?"
   - A population-average desired-versus-achieved difference would need a numeric desired family size for Generation Z and the completed lifetime fertility of the same birth cohorts. Neither is available.
   - Individual fulfilment would additionally need linked longitudinal observations of the same people. No source provides them.
2. **Desire and intention among older Generation Z.** In 2022–2023, most U.S. adults aged about 18–27 wanted a(nother) child, and most intended one (design-based estimates). This is the older part of Generation Z, not all of it.
3. **The desire–intention gap.** Among those who wanted a child, about one in nine did not intend one.
   - Roughly two in five of these were respondents the survey classifies as not intending because they or their partner were reported sterile. Their preferences are not observed.
   - The evaluated models using demographic and socioeconomic characteristics failed to demonstrate meaningful out-of-sample improvement in identifying the explicit "no".
4. **Expectations in an earlier cohort (born 1980–84; unweighted sample):**
   - stated five-year birth expectations ranked outcomes well but were far too extreme as forecasts;
   - childless women's expectations exceeded their births under every bound;
   - transfer to Generation Z is untested.
5. **National forecast.** No alternative model satisfied the locked model-selection criteria for replacing the no-change baseline.
   - The 2040 TFR forecast is the 2024 level.
   - Its historical-error intervals are wide, failed the calibration criterion, and are not validated probabilities.
6. **Generation Z cohorts.** If 2024 rates persist, the cohorts born 1995–2002 are nearly complete by historical standards by 2040, but this is not completed lifetime fertility. Later cohorts are partial.
7. **Housing.** Rental cost burden is not robustly associated with state birth rates at ages 20–29. The analysis is ecological, not causal.

All numerical values behind these conclusions are those of the frozen chapters. The claim-to-evidence matrix traces each one. No accepted estimate changed in the synthesis, the controlled M11 revision or the final corrections.

## 3. Final corrections before freezing (2026-11-20)

- **Population.** M09 statements are restricted to U.S. adults aged about 18–27 in 2022–2023 (the older part of Generation Z).
- **Prediction.** "Demographics cannot predict negative intentions" was replaced by "the evaluated models failed to demonstrate meaningful out-of-sample predictive improvement".
- **Completion.** Nearly complete cohort fertility is distinguished from completed lifetime fertility throughout.
- **Data requirements.** The requirements for a population-average desired-versus-achieved difference are distinguished from the stronger requirement of linked longitudinal data for individual fulfilment.
- **Sterility.** Statements about sterility describe the survey classification, not preferences or motivations.
- **Forecasting.** Residual "no method beat the baseline" wording was replaced by "no alternative satisfied the locked model-selection criteria".
- **Verifier coverage.** The number scanner is described as a token-coverage check, not semantic verification. Material claims were reviewed in their textual context (audit section 22).
- **Source-only verification.** Without `--require-data`, inputs absent from a source-only package are reported as SKIP rather than FAIL, while hash mismatches always fail. Strict behaviour under `--require-data` is unchanged, and regression tests were added.

## 4. Deliverables (frozen)

| Deliverable | Location |
|---|---|
| Integrated research manuscript | `docs/final_synthesis_manuscript.md` |
| Executive scientific summary | `docs/final_executive_summary.md` |
| Claim-to-evidence matrix | `docs/final_claim_evidence_matrix.csv` (50 claims, 155 checks; separate `status` and `interpretation_support` columns) |
| Limitations register | `docs/final_limitations_register.md` |
| Citations, source inventory and licensing | `docs/final_sources.md` |
| Reproducibility guide | `docs/final_reproducibility_guide.md` |
| Completion record (this document) | `docs/final_readiness_assessment.md` |
| Evidence tables | `data/public/final/final_evidence_table.csv`, `final_population_map.csv` |
| Figures | `assets/figures/final_evidence_map.png`, `final_headline_panels.png` |
| Code and verification | `analysis/final_synthesis.py`, `audit/verify_final_synthesis.py`, `tests/test_final_synthesis.py`, `tests/test_final_synthesis_freeze.py` |
| Audit record (living log, not hash-frozen) | `audit/scientific-audit.md` sections 21 and 22 |
| Source-only review archive | `../intention-gap-review-source-final.zip` (outside the repository) |

## 5. Verification at freeze

| Check | Result |
|---|---|
| Freeze manifests (`python audit/verify_freeze.py`) | Five manifests: M01–M08 34, M09 39, M10 30, M11 103, final synthesis 15 files; all OK. The 206 previously frozen files are unchanged |
| Full test suite | All tests pass, 0 skipped with full data (count in audit section 22) |
| Synthesis verifier with full data and archive scan | All checks pass (count in audit section 22) |
| Source-only package | Verifier runs with SKIPs for absent inputs and 0 FAIL; `--require-data` fails, as intended |
| Archive | Every file in all five manifests present with its frozen hash; internal manifest matches; safety scan clean |

## 6. Publication-phase requirements (not authorized; carried forward)

| Area | Requirement |
|---|---|
| Dataset licensing and attribution | HFD CC BY 4.0 attribution and licence notice; quote and archive the exact HFD User Agreement; update the outdated local HFD provenance note; confirm the CDC WONDER, NSFG, NLSY97 and Census terms and citation forms (`docs/final_sources.md` section 5) |
| Source and method references | Verify every data citation and method reference (DOIs) online |
| Git line-ending preservation | Frozen files have mixed line endings. Store them without conversion, or manifest hashes will fail on checkout |
| Dependency reproducibility | Lock transitive dependencies or publish the recorded `pip freeze`; state the tested platform; reruns are byte-identical only on the same platform and versions |
| Security and disclosure review | `ecc:security-reviewer` and `ecc:opensource-sanitizer` before release; re-run the archive safety scan on the publication tree |
| Accessibility | `ecc:a11y-architect` review of the documentation and figures |
| Pyright configuration | Add a configuration so type checking uses the project environment |
| GitHub preparation | Repository structure, `.gitignore` review, licence for the project's own code and text, release notes. Git, commit and push need explicit authorization |
| Streamlit development and browser testing | Dashboard work, Context7 API checks and Playwright browser tests only once authorized; the dashboard must display validated outputs from `data/public/` without recalculating them |
