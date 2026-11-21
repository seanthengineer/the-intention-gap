# M11 controlled freeze revision F21-1

**Date:** 2026-11-20 (17:45 UTC).

**Authorization:** the owner, in the directive "Final Synthesis | Controlled M11 Revision and Review Handoff". It authorizes a narrow M11 freeze revision for the interpretation of the historical cohort backtest only.

**Finding:** F21-1 (`audit/scientific-audit.md` sections 21.4 and 21.8).

**Scope:** wording only. No number, model configuration, forecast, interval, selection, table, figure or code changed.

## Reason for the revision

The frozen chapter said, in four places, that the fixed-strategy cohort backtest is optimistic by about 7–17% relative to origin-local selection. That statement generalizes beyond what the post-review analysis supports.

## Evidence

- **Where the strategies differ.** The origin-local and fixed strategies make different choices only at the six origins 1976–1981. There converge30 was chosen; at the other 27 eligible origins both use no change (`data/public/m11/forecast/m11_pr_origin_local_choices.csv`; `m11_pr_summary.json` `tfr_choices`).
- **Sparse errors at those origins.** At origins 1976–1981 only 10 to 15 no-change errors were available at h = 15 (column `tfr_errors_h15_available`). From 1982, 16 or more were available, and no change was chosen at every origin.
- **A degenerate bootstrap.** `analysis/m11_backtest.block_indices` draws circular blocks of length h. When the number of errors n is at most h, each replicate is a rotation of the full series, so its mean never varies. Checked in the final audit:
  - replicate-mean SD 6e-17 at n = 10;
  - 1.4e-16 at n = 15;
  - 0.023 at n = 16 (block 15, 2,000 replicates).

  The h = 15 component of condition 3 (bootstrap 90th percentile below 1) therefore had no variance at exactly the six origins where the strategies differ.
- **Monte Carlo sensitivity.** The 1981 choice was already documented as sensitive: the bound ranged 0.998–1.011 across 10 seeds.
- **What the averages mean.** The all-ages error ratios (1.16, 1.17, 1.09 and 1.07 at h = 5, 10, 15 and 16) average over 33 origins, of which 27 are identical across strategies. The difference is concentrated in six early origins, where sparse historical errors and unstable bootstrap selection limit generalization.

## Wording changed (`docs/m11_fertility_forecasts.md`)

| Location | Original wording | Revised wording |
|---|---|---|
| Summary B, last bullet | "The cohort intervals come from historical errors and are not calibrated. A post-review test that chose the strategy using only information available at each origin gave 7–17% larger backtest errors than the fixed strategy, so the fixed-strategy backtest is somewhat optimistic (section 13)." | "The cohort intervals come from historical errors and are not calibrated. A post-review test that chose the strategy using only information available at each origin gave 7–17% larger average backtest errors than the fixed strategy. That difference is concentrated in six early origins (1976–1981), where sparse historical errors and unstable bootstrap selection limit generalization, so it does not show that the fixed-strategy backtest is generally optimistic (section 13)." |
| Section 11 | "**The fixed-strategy cohort backtest is optimistic.** A strategy chosen only from information available at each origin had 7–17% larger cohort errors (post-review, section 13)." | "**The post-review origin-local comparison does not generalize.** A strategy chosen only from information available at each origin had 7–17% larger average cohort errors, but the difference is concentrated in six early origins (1976–1981), where sparse historical errors and unstable bootstrap selection limit generalization (post-review, section 13)." |
| Section 13.2, Interpretation, second bullet | "So the locked fixed-strategy backtest is **somewhat optimistic about a fully prospective procedure, by about 7–17% in cohort error**. Its errors should be read as the historical performance of the selected strategy, not of a procedure that would have chosen it in real time." | "So the 7–17% average difference describes this analysis as implemented, not a general optimism of the locked fixed-strategy backtest. At the six origins only 10–15 no-change errors were available at 15 years, no more than the 15-year bootstrap block, so the 15-year part of the bootstrap condition had no variance, and the 1981 choice was Monte Carlo-sensitive. Sparse historical errors and unstable bootstrap selection at these early origins limit generalization (controlled revision F21-1, `docs/m11_freeze_revision_F21-1.md`). The fixed-strategy errors should be read as the historical performance of the selected strategy, not of a procedure that would have chosen it in real time." |
| Section 17, accepted conclusion 3, last sentence | "The fixed-strategy cohort backtest is optimistic by about 7–17% relative to origin-local selection." | "A post-review origin-local comparison found 7–17% larger average cohort errors than the fixed strategy; the difference is concentrated in six early origins (1976–1981), where sparse historical errors and unstable bootstrap selection limit generalization, so it is not a general measure of backtest optimism (controlled revision F21-1)." |
| End of section 17 | — | Added note "**Controlled revision F21-1 (2026-11-20).** …" pointing to this record |

**Unchanged in the chapter:**
- every number;
- the rest of the first sentence of accepted conclusion 3 (1.75 for the 1995 cohort, 0.62 for 2012, historical-error intervals);
- the required sentence;
- the 13.2 results tables.

**Decision log.** `docs/m11_decision_log.md` gained one appended section, "Controlled freeze revision", with one entry. No earlier entry was edited.

## Hashes (SHA-256)

| File | Original (frozen 2026-11-20) | Replacement |
|---|---|---|
| `docs/m11_fertility_forecasts.md` | `36d26dc0ca39e66eb583bcdcf71180619f9d798d9ca93a8d65e6495d6680b418` | `a6ca9901cc9351bcb688c6c702bd632d31e89f476e984be6b03d220af124ec19` |
| `docs/m11_decision_log.md` | `a30a193c946bf6e115ef955b575b99675083517a80214c44b94fbb28fc83b38c` | `d9c89b1acb7745d65770cbd049810bb78a08832f500e536fc4abff75d3849f64` |
| `docs/m11_freeze.sha256` | `404599f04d1ca3085f8c9fa1abdd7d8f61128c1fce913987e269e86fca60a134` | Recorded in `audit/scientific-audit.md` section 21.8 (it lists this record's hash, so it cannot be stated here) |
| `docs/m11_freeze_revision_F21-1.md` (this record) | — (new) | Listed in the revised manifest |

## Procedure

The established controlled revision procedure was followed: a recorded decision and a new manifest.

1. The owner authorized the revision in writing (directive above).
2. **The original review archive was preserved.** `intention-gap-review-source-M11.zip` (SHA-256 `45a165dc70753c7308ad08e142eacc5566e1a8677fa9fc980d280ee40bebf146`) was copied unchanged to `intention-gap-review-source-M11-original-freeze.zip`, outside the repository.
3. **The wording was edited at byte level,** preserving each file's line endings. Each replacement had to match exactly once. A diff against the original archive shows exactly 4 lines replaced and the revision note added in the chapter, and only appended lines in the decision log.
4. **The manifest was updated** in `docs/m11_freeze.sha256`:
   - two hashes replaced (chapter, decision log);
   - one entry added (this record);
   - the other 100 entries unchanged;
   - line endings preserved.
5. **The M11 review archive was regenerated** under its original name, so that the frozen checkers can still compare files against it. These checkers are `audit/verify_m11_forecast.py` (`check_archive`) and `tests/test_m11_freeze.py`; neither was edited. The regenerated archive contains the original archive's entries with only the three revised or added files replaced, plus the revised manifest.
6. **Verification:** `audit/verify_freeze.py`, the M11 tests, `audit/verify_m11_forecast.py` (including its byte-identical rerun of all 53 tables and summaries), `audit/verify_m11.py`, the synthesis verifier and the full test suite (results in `audit/scientific-audit.md` section 21.8).

**Files not changed:**
- all M11 code, verifiers and tests;
- the protocol and its lock;
- the frozen run record;
- every public table and figure;
- the M01–M08, M09 and M10 manifests and their files.
