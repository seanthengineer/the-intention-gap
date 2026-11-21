# Environment, dependencies and code quality

**Status:** publication preparation, 2026-11-20. Everything below was run locally on the date shown; GitHub-hosted runs have not happened yet.

## 1. Tested platform

| Item | Value |
|---|---|
| Python | CPython **3.15.2** (`.python-version`) |
| Operating system | Windows 11 (10.0.26200), x86-64 |
| Full research environment | 51 packages, all pinned with hashes in `requirements-lock.txt` |
| Development tools | Pyright 1.1.414 (with nodeenv and typing-extensions; `requirements-dev.txt`) |
| Maintenance tool | pip-audit 2.10.1 and 27 dependencies (`requirements-audit.txt`) |
| External programs | Info-ZIP `unzip`, only for the full-data M11 step that reads Deflate64 natality archives (`final_reproducibility_guide.md` §1); Git for publication |
| Not tested | Running the code on Linux or macOS. The lock **resolves** for both under hash checking with binary wheels only (dry run, 51 of 51 packages for `manylinux_2_28_x86_64` and `macosx_14_0_arm64`), but no test was executed there. The prepared CI runs Ubuntu, Windows and macOS once the repository is on GitHub |

Byte-identical reruns of the research outputs are expected only with the same platform and package versions (`final_reproducibility_guide.md` §5).

## 2. Dependency specification

| File | Role | Status |
|---|---|---|
| `requirements.txt` | Direct dependencies of the analysis and the (local, unpublished) prototype dashboard (7 pins) | Unchanged |
| `requirements-research.txt` | Adds the independent survey library `svy` and Polars (frozen under M09) | Unchanged |
| `requirements-lock.txt` | **New.** Every direct and transitive dependency, pinned and hashed | Resolved with pip-tools 7.7.0 from `requirements-research.txt`, constrained to the exact versions of the validated environment. Its 51 pins are identical to the research `.venv` (minus the Pyright tools) |
| `requirements-dev.txt` | **New.** Pyright, pinned and hashed | Separate, so the research install stays minimal |
| `requirements-audit.txt` | **New.** pip-audit, pinned and hashed | Used only by the weekly maintenance workflow |

**Install:**
```
python -m pip install --only-binary=:all: --require-hashes -r requirements-lock.txt
```
Hash checking stops a tampered or substituted download; `--only-binary=:all:` stops code from running at build time.

**Why not Poetry?** Poetry was evaluated and not adopted:
- The project already has working, frozen requirements files, and `requirements-research.txt` is part of the M09 freeze.
- Moving to `pyproject.toml` with Poetry would add a second source of truth for versions, or require editing a frozen file.
- It would not improve reproducibility beyond a hash-locked requirements file, which pip installs natively.
- The smallest reliable change was a generated lock file alongside the existing files.

**Why not upgrade?** The research results were validated with these exact versions. Newer releases are not adopted merely because they exist: Dependabot is configured for GitHub Actions only, and the weekly pip-audit reports vulnerabilities without changing anything.

**Vulnerability audit (2026-11-20):** `pip-audit --require-hashes -r requirements-lock.txt` reported *No known vulnerabilities found*.

## 3. Python version management (pyenv)

- `.python-version` contains `3.15.2`. pyenv and pyenv-win read this file, and GitHub's `setup-python` reads it in the prepared workflows.
- pyenv is **optional**. Any CPython 3.15.2 installation works, from python.org, the Windows Python install manager, or a distribution package:
  ```
  python3.15 -m venv .venv
  .venv/bin/python -m pip install --only-binary=:all: --require-hashes -r requirements-lock.txt   # Windows: .venv\Scripts\python
  ```

## 4. Clean-installation test (2026-11-20)

| Step | Result |
|---|---|
| New virtual environment from the base CPython 3.15.2 interpreter (the research `.venv` untouched) | Created |
| `pip install --require-hashes -r requirements-lock.txt`, then `requirements-dev.txt` | Exit 0; 53 packages installed |
| `pip check` | No broken requirements |
| Source-only copy of the release (no `data/raw`, no `data/processed`) | Staged with `python -m tools.release stage` |
| `python -m tools.release restore-run-record`, then `python -m unittest` in that copy | Final counts: `docs/release_readiness.md` §2 |
| `python audit/verify_freeze.py` in that copy | All five manifests OK |
| `python audit/verify_final_synthesis.py` in that copy | 0 FAIL; checks needing raw data report SKIP |

## 5. Pyright configuration and diagnostics record

`pyrightconfig.json`:
- checks `analysis/`, `audit/`, `tests/` and `tools/` (the local dashboard prototype and its test are excluded);
- runs in `standard` mode for Python 3.15 on all platforms;
- takes the interpreter from whoever runs it (`--pythonpath` in `tools/pyright_baseline.py`).

No rule is switched off globally.

**Baseline (Pyright 1.1.414, 2026-11-20):** 1,872 errors in 54 files, recorded file by file in `tools/pyright_baseline.json`.

| Where | Files | Errors | Treatment |
|---|---|---|---|
| Frozen research code and tests | 52 | 1,840 | **Recorded, not edited.** Editing frozen files would need a freeze-revision decision, and the diagnostics are not defects (below) |
| `streamlit_app.py`, `tests/test_dashboard.py` (not frozen; local only) | 2 | 32 at the first baseline | **Deferred** with the dashboard; removed from the Pyright scope and the baseline when the prototype was excluded from the repository (2026-11-21) |
| Publication tooling: `tools/`, `tests/test_release_tools.py` | 5 | **0** | Must stay at zero (enforced) |

**What the diagnostics are.**
- 920 `reportArgumentType`: 520 of them are pandas or NumPy scalars passed to `int()` or `float()`, which the stubs type as unions.
- 672 `reportAttributeAccessIssue`: mostly attribute access on values that pandas annotates as `ndarray | Series | scalar` unions.
- 70 `reportIndexIssue`, 77 `reportCallIssue`, 51 `reportReturnType` and 41 `reportGeneralTypeIssues`: the same union-inference pattern.
- 28 "optional" and "possibly unbound" warnings.

**Spot checks.** Three groups of non-library diagnostics were read in the code; none is a defect:
- `m11_sources.py` lines 212 and 214: both branches assign the variable;
- `nsfg_descriptive.py` lines 426 and 429: the loop over two sexes always runs;
- `verify_final_synthesis.py` lines 301–309: `Series.get` with a numeric default;
- the remaining optional-access diagnostics, such as regex matches in `m11_sources.py` lines 269 and 275, were not examined individually.

**Policy.** `python -m tools.pyright_baseline` is a ratchet:
- tooling must be clean;
- every other file must match its baseline exactly, so a new error fails and a fixed one requires lowering the baseline;
- the Pyright version must match.

**A type diagnostic is not evidence of a scientific calculation error.** Every scientific result is checked independently by the verifiers.

## 6. Code review (independent reviews of the publication tooling)

Two specialist reviews were run on the new tooling: a security review, and a Python correctness review. Neither found a blocking defect. Their findings were classified and handled as follows.

| Finding | Class | Action |
|---|---|---|
| Credential pattern missed quoted JSON/YAML keys; no JWT, Google key or `sk_live_` patterns | Nonblocking | Fixed; tests added |
| Personal-path pattern missed escaped and forward-slash Windows paths | Nonblocking | Fixed; tests added |
| Respondent-column check defeated by a byte-order mark, other delimiters or variant names | Nonblocking | Fixed (BOM-safe, multi-delimiter, ID-pattern match); tests added |
| PNG metadata not scanned | Nonblocking | Byte-level scan added; all 22 PNG images clean |
| Symlinks would be followed | Nonblocking | Symlinks are excluded and reported as findings |
| Release rules did not fully mirror `.gitignore` (other `data/` folders, nested `CLAUDE.md`, NLSY97 file patterns) | Nonblocking | Rules aligned; equality tested against `git ls-files` in a disposable repository (247 = 247) |
| `stage` could build from a failing tree | Nonblocking | Staging now runs every check first and refuses on any finding, or on a destination inside the repository |
| Lock installs could build from source distributions; pip-audit was unhashed | Nonblocking | `--only-binary=:all:` in every install; `requirements-audit.txt` hashed |
| Pyright: warnings ignored for tooling; no version check; baseline never ratchets; unfriendly failure without Pyright; `.venv` assumed | Nonblocking | All addressed (section 5) |
| ZIP bytes differed by platform (`create_system`) | Nonblocking | Fixed to Unix; determinism test added |
| Slug and anchor edge cases (emphasis, setext headings, `~~~` fences, reference links, nested images, percent-encoding) | Nonblocking | Implemented; tests added |
| Run-record restore not atomic; unfriendly errors | Nonblocking | Atomic replace and clear errors; tests added |
| Hard-coded count of 221 frozen files would break future freezes | Nonblocking | Test now requires at least 221 and checks coverage |
| Nothing blocks a commit before CI runs | Nonblocking | Release step: run `python -m tools.release check` before every push. Branch protection with required checks is an owner action on GitHub (`docs/release_readiness.md`) |
| `linguist-generated` hid lock-file diffs | Cosmetic | Removed for lock files and manifests |
| GitHub does not read SVG `<title>`/`<desc>` through `<img>`; small text in the header | Cosmetic | The README `alt` text carries the description |

Checked and not a problem:
- workflow permissions are `contents: read`;
- no `pull_request_target`, no untrusted context in `run:` steps, and no caches or artifact uploads;
- actions are pinned to full commit SHAs, matching `git ls-remote` for checkout v7.0.1 and setup-python v7.1.0;
- `persist-credentials: false` is set on every checkout.
