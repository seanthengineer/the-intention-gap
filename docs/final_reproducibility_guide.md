# Complete reproducibility guide

**Status:** **FROZEN, final scientific approval, 2026-11-20.** Manifest `docs/final_synthesis_freeze.sha256`; completion record `docs/final_readiness_assessment.md`. Editing this file needs a recorded decision and a new manifest.

**Scope.** This guide reproduces every chapter (M01–M11), the final synthesis and the audit, from the project root.

**Precedence.** The chapter documents remain authoritative for their own commands:
- `docs/methodology.md` section 9;
- `docs/nsfg_m09.md` section 9;
- `docs/m10_housing_fertility.md` section 9;
- `docs/m11_fertility_forecasts.md` section 16.

## 1. Environment

**Platform used for every frozen result and for this audit:**
- Windows 11 (10.0.26200);
- CPython 3.15.2 (64-bit);
- project virtual environment `.venv`.

**Install:**

```
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements-research.txt   # includes requirements.txt; adds svy and polars
```

**Direct dependencies** (pinned exactly):
- `requirements.txt`: altair 6.3.0, matplotlib 3.11.2, numpy 2.5.5, pandas 3.1.1, scikit-learn 1.9.1, scipy 1.18.1, streamlit 1.67.0;
- `requirements-research.txt` adds msgspec 0.22.0, polars 2.1.0, polars-runtime-32 2.1.0, svy 0.37.0, svy-io 0.9.0 and svy_rs 0.21.0.

**Full environment at audit time** (`pip freeze`, a record only; transitive versions are not locked by the requirements files):

```
altair==6.3.0  anyio==4.16.0  attrs==26.1.0  certifi==2026.10.23  charset-normalizer==3.5.2  click==8.5.1
cloudpickle==3.1.2  contourpy==1.4.0  cycler==0.12.1  fonttools==4.68.0  h11==0.16.0  idna==3.20
itsdangerous==2.2.0  Jinja2==3.1.6  joblib==1.6.0  jsonschema==4.26.0  jsonschema-specifications==2025.9.1
kiwisolver==1.5.1  MarkupSafe==3.0.4  matplotlib==3.11.2  msgspec==0.22.0  narwhals==2.29.0  nodeenv==1.12.0
numpy==2.5.5  packaging==26.3  pandas==3.1.1  pillow==13.0.0  polars==2.1.0  polars-runtime-32==2.1.0
protobuf==7.36.2  pyarrow==26.0.1  pydeck==0.9.3  pyparsing==3.3.3  pyright==1.1.414  python-dateutil==4.0.0
python-multipart==0.0.34  referencing==0.37.0  requests==2.34.2  rpds-py==2026.9.1  scikit-learn==1.9.1
scipy==1.18.1  starlette==1.10.0  streamlit==1.67.0  svy==0.37.0  svy-io==0.9.0  svy_rs==0.21.0
threadpoolctl==3.8.0  typing_extensions==4.16.0  tzdata==2026.6  urllib3==2.8.0  uvicorn==0.54.0
watchdog==7.1.0  websockets==17.4
```

**Other tools:**
- Info-ZIP `unzip` is needed to read the NCHS natality public-use zips (Deflate64) in `audit/verify_m11.py`; `--skip-puf` skips that step.
- No statsmodels: all models are implemented with numpy, scipy and scikit-learn.

**Byte identity is platform-specific.** Frozen tables and manifests were written on Windows with CRLF line endings.
- Re-running on Linux or macOS writes LF endings, so byte-identical rerun checks and SHA-256 manifests will report differences that are not scientific.
- Values can be compared after normalising line endings.
- Before any Git commit, line-ending normalisation must be disabled for frozen files (finding F21-4).

## 2. Data placement (local only, never distributed)

| Folder | Contents | How obtained |
|---|---|---|
| `data/raw/intention_gap_nlsy97_v2.*`, `_supplement.*`, `_temporal.*` | NLSY97 extracts (CSV + codebook) | NLS Investigator, variable lists in `docs/extract_manifest.csv` and `docs/temporal_extract_manifest.csv` |
| `data/raw/nsfg_2022_2023/` | NSFG female and male CSVs and CDC documentation | CDC NSFG public-use download |
| `data/raw/acs_b25070/`, `acs_m10_covariates/` | ACS API JSON | `python -m analysis.acs_housing --fetch`, `python -m analysis.m10_covariates --fetch` (need `CENSUS_API_KEY` in the environment; never stored) |
| `data/raw/cdc_natality/`, `nchs_nvsr/` | CDC WONDER exports; NVSR PDFs | Manual export (queries recorded in provenance) |
| `data/raw/hfd_usa/`, `hfd_docs/` | HFD USA files and documentation | HFD account download (`USA.zip`) |
| `data/raw/nchs_2025/`, `nchs_natality_puf/`, `census_popest/`, `census_np2023/` | NCHS 2025 births; Census estimates and projections | Public downloads recorded in each `provenance.json` |

`python audit/verify_final_synthesis.py` re-hashes every file recorded in a `provenance.json`.

## 3. Reproduction order

**M01–M08 (NLSY97):**

```
python -m analysis.birth_history_audit
python -m analysis.build_outcomes
python -m analysis.analyze_calibration
python -m analysis.robustness_analysis
python -m analysis.export_dashboard_data
python -m analysis.supplement_extract
python -m analysis.pregnancy_status
python -m analysis.expanded_histories
python -m analysis.population_validity
python -m analysis.temporal_validation
python -m analysis.survey_design
```

**M09 (NSFG):**

```
python audit/nsfg_stage3_checks.py --require-data
python -m analysis.nsfg_descriptive
python -m analysis.nsfg_models                # about 3 minutes
```

**M10 (housing):**

```
python -m analysis.acs_housing
python -m analysis.m10_covariates
python -m analysis.cdc_natality
python -m analysis.m10_panel
python -m analysis.m10_models                 # refuses to run if the protocol changed
python -m analysis.m10_descriptive
```

**M11 (forecasts):**

```
python -m analysis.m11_protocol --status
python -m analysis.hfd
python -m analysis.m11_feasibility
python -m analysis.m11_forecast               # about 2 minutes; rewrites the live run record (not frozen)
python -m analysis.m11_origin_local
python -m analysis.m11_figures
```

**Final synthesis** (reads only frozen public outputs; writes `data/public/final/` and `assets/figures/final_*.png`):

```
python -m analysis.final_synthesis
```

Running the chapter pipelines rewrites their outputs. With the pinned environment on the same platform, every frozen output is reproduced byte for byte. This was checked for M11 by the verifier's full rerun (53 files) and for M01–M08 in M03. If a frozen output changes, stop: that is a finding, not an update.

## 4. Verification

| Command | What it checks | Result at audit (2026-11-20) |
|---|---|---|
| `python audit/verify_freeze.py` | All five freeze manifests | 34 + 39 + 30 + 103 + 15 files OK (M01–M08, M09, M10, M11, final synthesis) |
| `python -m unittest` | Full test suite | See audit section 21 for the final count; 0 failures, 0 skipped with data present |
| `python -m audit.verify_outcomes` | NLSY97 labels, independent | Pass |
| `python -m audit.verify_models` | NLSY97 statistics, independent | Pass |
| `python -m audit.verify_temporal` | 2015–16 validation, independent | Pass |
| `python audit/nsfg_stage3_checks.py --require-data` | 19 NSFG checks | 18 PASS, 1 WARN (documented) |
| `python audit/verify_nsfg_m09.py --require-data` | M09 verification | 110 PASS |
| `python audit/verify_m10.py` | M10 verification | 79 PASS |
| `python audit/verify_m11.py` | M11 data stage | 33 PASS |
| `python audit/verify_m11_forecast.py` | M11 forecasting, with full rerun (about 4.5 minutes) | 46 PASS; rerun byte-identical; run record restored |
| `python audit/verify_final_synthesis.py --require-data --archive ..\intention-gap-review-source-final.zip` | Claim matrix (values against frozen sources); numeric-token coverage (every number in the synthesis documents is represented among verified matrix figures; this is not a check of semantic correctness); independent recomputation; provenance and freeze hashes; archive safety | 47 PASS with full data: 26 independent, 20 reconciliation, 1 reproducibility (audit section 22) |
| `python audit/verify_final_synthesis.py` (source-only package, no `--require-data`) | As above. Inputs absent from a source-only package are reported as SKIP ("inputs not present"); a provenance hash that differs from a present file is always FAIL | Expected: 11 PASS, 14 SKIP (10 provenance, 4 independent recomputation), 0 FAIL; with `--require-data` the 14 become FAIL |

**Without the restricted data:**
- Tests and verifiers that need respondent-level or raw files skip, or with `--require-data` fail.
- A clean checkout therefore verifies the aggregate outputs, the claim matrix and the freeze manifests, not the data-dependent paths (finding F21-6).

## 5. Seeds and determinism

| Seed | Use |
|---|---|
| 1997 | NLSY97 held-out split |
| 2009 | NLSY97 bootstrap |
| 101–110 | NLSY97 cross-validation |
| 211 | NLSY97 cross-fitting |
| 2015 | 2015–16 temporal bootstrap |
| 2023 | NSFG models |
| 20261120 | M11 |

- No unseeded randomness was found.
- Wall-clock timestamps appear only in run records and validation JSON. These are excluded from frozen manifests, or restored by the verifiers.

## 6. Building the review archive

The source-only archive is built outside the repository, from files that are under version control in principle:
- it excludes `data/raw/`, `data/processed/`, `.venv/`, caches, `CLAUDE.md`, `.claude/`, the owner's scripts, logs and existing archives;
- the inclusion list and the per-file SHA-256 are recorded inside the archive (`ARCHIVE_MANIFEST.sha256`);
- `audit/verify_final_synthesis.py --archive <path>` scans it for restricted paths, respondent-level columns and credentials.
