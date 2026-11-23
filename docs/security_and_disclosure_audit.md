# Security, confidentiality and disclosure audit

**Status:** audit of the proposed public release, 2026-11-20. Results are re-run by `python -m tools.release check`, which CI runs on every push.

## 1. What was checked, and how

Files are classified by **content**, not only by name:

| Check | Method | Result |
|---|---|---|
| Credentials | Patterns for API keys, tokens, passwords and secrets in assignments (including quoted JSON/YAML keys), AWS, GitHub, Slack, Google and `sk-`/`sk_live_` keys, JWTs, private-key blocks, and 40-character hex strings (the Census API key format) | None found |
| Personal data | Paths into a user's home directory on Windows (backslash, escaped and forward-slash forms), Linux or macOS, and e-mail addresses, in text files and in PNG metadata | None found |
| Restricted files | Raw-data and binary formats (`.dat`, `.cdb`, `.dct`, `.sas`, `.sps`, `.do`, `.xls(x)`, `.sav`, `.dta`, `.parquet`, `.pdf`, `.zip`, `.gz`, pickles), and any file type not on the allow list | None in the release |
| Respondent-level data | CSV headers checked for identifier columns (PUBID, CASEID, NLSY97 reference numbers such as `R0000100`, household or sampling-unit codes), after removing a byte-order mark and with several delimiters tried; the largest tables were reviewed by hand | None. The six tables with more than 300 rows (459–11,928 rows) hold forecasts, backtest and interval records, rates by age and year, cohort trajectories and subgroup estimates, not people |
| Small cells (CDC WONDER) | WONDER forbids presenting statistics of nine or fewer births, including rates based on them | Smallest state-by-age birth count behind any published rate: 598 |
| Suppression (NSFG) | Estimates failing the NCHS presentation standard for proportions must be blank in `data/public/nsfg_m09/` and absent from figures | Confirmed: suppressed rows have no estimate, SE, interval, effective n or event count; tested in `tests/test_nsfg_m09.py` |
| Disclosure rules (NLSY97) | Published aggregates follow the project's own thresholds (outcome cells ≥ 20, counts ≥ 10; methodology §9) | Unchanged since the M08 release candidate |
| Symbolic links | Not allowed in the release | None |
| Git exclusions | `.gitignore` compared with the release rules by running `git ls-files --others --exclude-standard` against the real project tree, from a Git directory outside the project | Identical file sets |
| Independent reviews | Specialist security review of workflows and tooling; open-source sanitization review of the staged release | Findings and actions in `environment_and_code_quality.md` §6 and `release_readiness.md` §3 |

**Small national values, reviewed and accepted.** One public table, `m11_hfd_nchs_births_2024_by_age.csv`, contains an HFD estimate of 8.94 U.S. births at age 54 in 2024. This is a national HFD-published estimate, not a CDC WONDER statistic and not sub-national, so the WONDER rule does not apply.

## 2. Exclusion register

These local files and folders exist in the working tree and are **not** part of the public release. The rules are in `tools/release.py` and `.gitignore`; `python -m tools.release excluded` lists every excluded path.

| Excluded | Why | Effect on reproducibility |
|---|---|---|
| `data/raw/` | Source data: NLSY97 extracts (respondent-level), NSFG public-use microdata, CDC WONDER exports, NCHS natality files (record-level), the HFD archive (the HFD asks users not to pass on copies), Census files, and their provenance records | Full reproduction needs the reader to download them from the providers (`final_reproducibility_guide.md` §2). Provenance hashes for every file are in the frozen documents |
| `data/processed/` | Respondent-level cohorts, holdout predictions and full unsuppressed NSFG tables | Rebuilt by the pipeline from `data/raw/` |
| Any other folder under `data/` except `data/public/` | Mirrors `.gitignore` | — |
| `data/public/m11/forecast/m11_run_record.json` | Volatile: rewritten by every run | The frozen copy `docs/m11_frozen_run_record.json` is published, and `python -m tools.release restore-run-record` recreates the live file |
| `inspect_data.py`, `audit_data.py` | The owner's local exploratory scripts; they read respondent-level rows | None |
| `CLAUDE.md`, `.claude/` | Local instructions for the AI coding assistant | None |
| `.venv/`, caches, `*.log`, `*.zip`, editor and OS files | Local environment and build artifacts | None |
| `.env`, `.env.*`, `.streamlit/secrets.toml` | Credentials (none exist; excluded defensively) | None |
| `streamlit_app.py`, `tests/test_dashboard.py`, `assets/dashboard.png`, `.streamlit/config.toml` | Streamlit prototype deferred until a dashboard phase is authorized (owner instruction, 2026-11-21). No public test or document depends on them; `tests/test_dashboard.py` tests only the dashboard. `audit/verify_m11_forecast.py` (frozen) checks the local `streamlit_app.py` hash, which runs only in full-data verification | None for the research. `requirements.txt` still lists Streamlit and Altair because the frozen research environment (`requirements-research.txt`) includes it |

**Frozen artifacts excluded from the release: none.** All 221 frozen files are published with their manifest hashes, so the public freeze check covers the same files as the strict local check.

## 3. Release inventory

[`docs/release_inventory.csv`](release_inventory.csv) lists every published file with its category, its freeze manifest (if frozen) and its proposed licence class. `python -m tools.release check` fails if the working tree and the inventory disagree. Counts by category are in `release_readiness.md` §2.

## 4. Credentials in the workflow

- The project uses one credential, a Census Data API key. It is read from the `CENSUS_API_KEY` environment variable and never written to disk; `audit/verify_m10.py` checks that it does not appear in any saved file.
- Public CI needs no secrets: tests and verifiers that require data or keys report SKIP.
- My research, integrity and routine Website workflows remain read-only and do not upload research artifacts. I have prepared a separate manual Pages workflow that uploads only the static `website/dist/` folder. Its deployment job requests `pages: write` and `id-token: write`, but the workflow refuses to publish from a private repository, from a branch other than `main`, or without my explicit release confirmation.

## 5. Owner actions on GitHub (after the repository exists)

- Enable **secret scanning and push protection**.
- Enable **branch protection** on the default branch, requiring the CI workflow and a review for changes to `tools/`, `.github/` and `docs/*_freeze.sha256`.
- Keep the repository's **default workflow permissions** read-only.
