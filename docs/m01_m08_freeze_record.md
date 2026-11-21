# M01–M08 freeze record

**Status:** FROZEN, 2026-11-20 (owner approval). Manifest: `docs/m01_m08_freeze.sha256` (34 files).

M01–M08 had been declared frozen without a checksum manifest. This record documents how the manifest was built and checked. No research file was modified in the process.

## Baseline

- **Source of truth:** the M08 release candidate, `intention-gap-release-candidate-M08.zip`, kept outside the repository. It contains 43 files. Its SHA-256 is `b51935738a84d09e134cc6fcb17662a728552791ce3ae9e2ded3f05822ec21cf`.
- **How the hashes were taken:** every manifest hash comes from the file inside that archive, not from the working copy. The working copy is then checked against the release, so the current state cannot quietly become the baseline.
- **Second piece of evidence:** the M11 review archive (`intention-gap-review-source-M11.zip`) matches the working copy byte for byte.

## Accounting for the 43 released files

| Group | Files | Treatment |
|---|---|---|
| Unchanged since M08, research content | 34 | Frozen in `docs/m01_m08_freeze.sha256`. Covers the M01–M08 analysis modules and audit verifiers, their tests, the methodology, the extract manifests, the frozen model parameters, the dashboard data export and the three research figures. |
| Unchanged since M08, dashboard or configuration | 6 | Not frozen (owner decision 2026-11-20): `streamlit_app.py`, `tests/test_dashboard.py`, `assets/dashboard.png`, `requirements.txt`, `.streamlit/config.toml`, `.gitignore`. |
| Changed since M08: `README.md` | 1 | Not frozen (owner decision 2026-11-20). |
| Changed since M08: `analysis/survey_design.py` | 1 | See Explained differences. Frozen by the M09 manifest. |
| Changed since M08: `audit/scientific-audit.md` | 1 | See Explained differences. Its M08 portion is checked by a test. |

Also left out:
- The owner's own scripts, `inspect_data.py` and `audit_data.py`.
- Respondent-level files in `data/raw/` and `data/processed/`. This follows the M09–M11 precedent: restricted data is never listed in a published manifest.

## Explained differences from the M08 release

1. **`analysis/survey_design.py`**
   - **Hashes:** M08 version `eba617b5…`; current version as recorded in `docs/nsfg_m09_freeze.sha256`.
   - **What changed:** in M09 the body of `linearized_mean` was split into two private helpers, `_mean_scores` and `_psu_variance`, with the same arithmetic. New functions were added for M09: `linearized_domain_difference`, `linearized_domain_covariance` and `adjusted_wald_test`.
   - **Evidence that M07 results are unaffected:** the M07 test file `tests/test_survey_design.py` is byte-identical to M08 and still passes.
   - **Freeze status:** the file is frozen under M09 and is not listed twice.

2. **`audit/scientific-audit.md`**
   - **What changed:** after M08 the file was converted to CRLF line endings, and sections 17–20 (M09–M11) were appended.
   - **What did not change:** with line endings normalized, its first 31,101 bytes (sections 0–16) are identical to the M08 version, whose SHA-256 is `18413daa…`.
   - **How it stays protected:** the file remains the project's living audit log, so it is not hash-frozen as a whole. `tests/test_m01_m08_freeze.py` checks that its M08 portion is unchanged.

## Verification

- `python audit/verify_freeze.py` finds the new manifest automatically because it matches `docs/*_freeze.sha256`. Neither it nor `tests/test_freeze_integrity.py`, both frozen M10 files, was edited.
- `sha256sum -c docs/m01_m08_freeze.sha256` gives the same result.
- `tests/test_m01_m08_freeze.py` (new, not frozen) checks:
  - the manifest's contents;
  - that every M08 release file is accounted for;
  - that each frozen file's hash matches the release archive (when the archive is present);
  - that `survey_design.py` is in the M09 manifest;
  - that the M08 portion of the audit log is unchanged.

The checks reproduce the archived bytes. They are not an independent re-derivation of the M01–M08 findings, which the M04–M07 audit verifiers provide.

## Unresolved discrepancies

None. Every difference between the M08 release and the working copy is explained above.
