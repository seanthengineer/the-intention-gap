# Release checklist and publication-readiness report

**Current publication update (November 2026).** I merged the completed V2.1–V2.4 website, housing atlas and documentation into `main`. I made the repository public, enabled branch protection with five required checks, and published [the research website](https://seanthengineer.github.io/the-intention-gap/) through a manual GitHub Pages deployment. The scientific CI and Website checks passed. The site remains `noindex, nofollow` until I decide whether to allow indexing. I have not created an official GitHub Release or release tag. The preparation steps and earlier test totals below remain as historical records. I record the current release decisions in [my publication record](publication_plan.md) and the browser verification in the [website release report](../website/RELEASE.md).

**Historical preparation status, recorded before launch:** publication engineering was complete; the repository was initialized and pushed to a **private** GitHub repository on 2026-11-21. CI source-only jobs passed on Ubuntu and Windows; the integrity workflow passed after a YAML correction. The weekly maintenance workflow has not yet been run. **Not publicly released:** no public visibility, tag or GitHub Release. The Streamlit dashboard is out of scope.

**Historical pre-launch decision: REVIEWABLE WITH NONBLOCKING LIMITATIONS.** Author and project licenses were approved on 2026-11-21. Final visual review, protection settings and public-release authorization remain pending.

## 1. Deliverables

| Deliverable | Where |
|---|---|
| Portfolio README | [`README.md`](../README.md); header images in `assets/readme/`, generated from frozen HFD values by `tools/readme_header.py` |
| Visual research atlas | [`visual_atlas.md`](visual_atlas.md) (all 21 figures) |
| Research pipeline, walkthrough and architecture diagram | [`research_pipeline.md`](research_pipeline.md) |
| Engineering decisions and development narrative | [`engineering_decisions.md`](engineering_decisions.md) |
| Technical walkthrough, verified stack and contribution statement | [`technical_walkthrough.md`](technical_walkthrough.md) |
| Licensing and attribution register; authorized project licensing structure | [`licensing_and_attribution.md`](licensing_and_attribution.md); HFD terms archived in [`source_terms/`](source_terms/hfd_user_agreement_2026-11-20.md) |
| Citation audit and consolidated bibliography | [`bibliography.md`](bibliography.md); [`../CITATION.cff`](../CITATION.cff) (validated against CFF 1.2.0) |
| Publication errata | [`publication_errata.md`](publication_errata.md) |
| Security and disclosure audit; release inventory and exclusion register | [`security_and_disclosure_audit.md`](security_and_disclosure_audit.md); [`release_inventory.csv`](release_inventory.csv) |
| Git configuration | [`../.gitattributes`](../.gitattributes), [`../.gitignore`](../.gitignore); test results in section 4 |
| Dependency specifications | `requirements-lock.txt`, `requirements-dev.txt`, `requirements-audit.txt`, `.python-version` ([`environment_and_code_quality.md`](environment_and_code_quality.md)) |
| Pyright configuration and diagnostics record | `pyrightconfig.json`, `tools/pyright_baseline.json`; record in `environment_and_code_quality.md` §5 |
| GitHub Actions workflows | `.github/workflows/ci.yml`, `integrity.yml`, `maintenance.yml`; `.github/dependabot.yml` (section 5) |
| Contributor and security guidance | [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`../SECURITY.md`](../SECURITY.md) |
| Local pre-publication review archive | Section 7 |

## 2. Final verification (local, 2026-11-20)

Every row below was executed; nothing here reports a GitHub-hosted run. The local runs below include the 18 tests of the local Streamlit prototype; after the prototype was excluded from the repository on 2026-11-21, the repository carries 392 tests.

**Full-data checks in the research environment (Windows, CPython 3.15.2):**

| Check | Result |
|---|---|
| Freeze manifests (`audit/verify_freeze.py`), before and after all reruns | 5 manifests OK: M01–M08 34, M09 39, M10 30, M11 103, final synthesis 15 = **221 files**. Manifest files unchanged; live M11 run record identical to its frozen copy |
| Full unit suite (`python -m unittest`) | **410 tests, OK, 0 skipped**. Five warnings, all known: three `RuntimeWarning`/`RankWarning` from M05 synthetic test inputs (diagnosed in audit section 21.5) and two Streamlit "bare mode" notices |
| NSFG Stage 3 validation (`--require-data`) | 18 PASS, 1 WARN (documented Check 03 routing exceptions), 0 FAIL |
| `audit/verify_nsfg_m09.py --require-data` | 110 PASS, 0 FAIL |
| `python -m audit.verify_outcomes` | 3,660 of 3,660 labels agree with the pipeline |
| `python -m audit.verify_models` | Reproduces the frozen statistics; the cross-validation fold counts (49/50 and 47/50) match the specification sensitivity recorded as V4 in audit section 4 |
| `python -m audit.verify_temporal` | 3,484 of 3,484 labels identical; largest forecast difference 1.1e-16 |
| `audit/verify_m10.py` | 79 PASS, 0 FAIL (60 independent, 2 rerun, 17 reconciliation) |
| `audit/verify_m11.py` | 33 PASS, 0 FAIL |
| `audit/verify_m11_forecast.py` (full rerun) | 46 PASS, 0 FAIL (32 independent, 2 reproducibility, 12 reconciliation); rerun byte-identical |
| `audit/verify_final_synthesis.py --require-data` | 46 PASS, 0 FAIL (26 independent, 19 reconciliation, 1 reproducibility); all 155 claim-matrix checks |
| Release checks (`python -m tools.release check`) | All five PASS: inventory, frozen hashes, content scan, links and anchors, Git attributes |
| Pyright policy (`python -m tools.pyright_baseline`) | PASS: 1,872 errors, equal to the recorded baseline; publication tooling 0 |
| README header (`python -m tools.readme_header --check`) | Current |
| Workflow lint (actionlint 1.7.12) and `CITATION.cff` validation (cffconvert) | Pass |
| Dependency audit (pip-audit 2.10.1) | No known vulnerabilities |

**Source-only checks on the staged release (clean virtual environment, no `data/raw` or `data/processed`):**

| Check | Result |
|---|---|
| Clean install from `requirements-lock.txt` and `requirements-dev.txt` | 53 packages, `pip check` clean |
| Freeze manifests | 5 OK, 221 files |
| Release checks; README header | All PASS; current |
| `python -m tools.release restore-run-record`, then `python -m unittest` | **410 tests, OK, 38 skipped** (tests that need restricted data) |
| `audit/verify_final_synthesis.py` | 10 PASS, 0 FAIL, 5 SKIP (inputs absent) |
| `audit/verify_final_synthesis.py --require-data` | 10 PASS, 5 FAIL, as intended: strict mode fails without data |
| `audit/nsfg_stage3_checks.py` (no data) | 19 SKIP, 0 FAIL |
| Pyright policy in the clean environment | PASS (same 1,872 baseline) |
| Lock resolution for other platforms (dry run, binary wheels, hash checking) | Linux x86-64 and macOS arm64: 51 of 51 packages; audit tool lock resolves on Linux |

**No accepted scientific finding changed.**
- All 221 frozen files match their manifest hashes after every rerun.
- The full M11 rerun reproduced its 53 tables byte for byte.
- The independent recomputations agree as recorded at the freeze.

## 3. Independent reviews

| Review | Verdict | Disposition |
|---|---|---|
| Security review: workflows, tooling, ignore rules, lock files | No blocking findings | Nine nonblocking findings fixed (scanner patterns, mirroring `.gitignore`, symlinks, PNG metadata, checks before staging, binary-only hashed installs); branch protection and pre-push checks are owner actions (section 6) |
| Python review of the publication tooling | No blocking findings | Fourteen findings fixed or recorded (`environment_and_code_quality.md` §6) |
| Open-source sanitization of the release set | PASS WITH WARNINGS | No secrets, personal data, dangerous files or respondent-level data. Warning: frozen audit records mention local review archives (`../intention-gap-review-source-*.zip`) that are **not** published; these mentions are historical and harmless |
| Accessibility of the README, atlas, pipeline document and header | No blocking findings | Header text enlarged (contrast 6.2:1 to 16.2:1); README H1, table headers, units, expanded abbreviations and linked captions added; alt texts shortened; text versions of the diagrams given as lists |

Frozen figures cannot be edited. Their accessibility relies on the text descriptions in the atlas.

## 4. Git byte-preservation test

Run in disposable repositories outside the project with Git 2.56 on Windows. The release set was committed under each `core.autocrlf` setting and cloned under four checkout settings.

| `.gitattributes` | Commit setting | Committed blobs matching the manifests | Checkout settings | Frozen files byte-identical after checkout |
|---|---|---|---|---|
| Present | autocrlf false / true / input | 221 / 221 in each case | autocrlf false, true, input; `core.eol=crlf` | **221 / 221 in all 12 combinations** |
| Absent (control) | autocrlf false | 221 / 221 | autocrlf true or `eol=crlf` | 158 / 221 |
| Absent (control) | autocrlf true or input | 86 / 221 | any | 86–157 / 221 |

Also confirmed:
- `git check-attr` reports `text`, `eol`, `filter`, `ident` and `working-tree-encoding` as *unset* on frozen files;
- `python audit/verify_freeze.py` passes in the protected clone;
- `git ls-files` equals the release inventory (plus the inventory itself);
- the project's `.gitignore`, applied to the real working tree from an external Git directory, yields exactly the same set.

**Limitation.** Linux and macOS Git were not tested. The attributes are platform-independent, and the prepared CI checks out on Ubuntu, Windows (where GitHub runners set `core.autocrlf=true`) and macOS, then runs `verify_freeze.py`.

## 5. Continuous integration (GitHub CI and integrity checks exercised)

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push, pull request, manual | On Ubuntu and Windows: hash-locked install, freeze manifests, release checks, README header check, restore of the run record, full unit suite (skips counted in the job summary), synthesis verifier in source-only mode, NSFG checks without data. Pyright policy on Ubuntu |
| `integrity.yml` | daily 06:17 UTC, manual | Freeze manifests, release checks, freeze and release tests |
| `maintenance.yml` | weekly, Monday 05:41 UTC, manual | Clean install on Linux, Windows and macOS without cache; source-only suite; `pip-audit` of the lock file |
| `dependabot.yml` | weekly | Pull requests updating the SHA-pinned actions only |

**Security of the workflows.**
- `contents: read` everywhere; no secrets; `persist-credentials: false`.
- Actions are pinned to commit SHAs: checkout v7.0.1 and setup-python v7.1.0, confirmed with `git ls-remote`.
- No artifact uploads; nothing modifies research outputs.

**Validation.**
- actionlint 1.7.12 and a YAML parse pass.
- The commands were executed locally on Windows (section 2).
- On GitHub, source-only CI completed successfully on Ubuntu and Windows with Python 3.15.2; the Pyright baseline check also passed. The corrected daily integrity workflow passed a manual run. Weekly maintenance including macOS remains untested. The first integrity and Dependabot runs failed to parse the original workflow YAML; a correction commit fixed that issue.

**Limitations.** GitHub disables scheduled workflows in public repositories after 60 days without repository activity, and scheduled runs can be delayed. A failed scheduled run reports a problem; it never changes anything.

## 6. Release checklist

**My publication decisions:**
- [x] Approve the licences and copyright notice: MIT for original code, CC BY 4.0 for original research writing and presentation; copyright © 2026 Sean Nathaniel M. (`LICENSE`, `LICENSE-docs.md`).
- [x] Update `CITATION.cff` with the publishing name, software license and repository URL. Do not add a public release date before publication.
- [x] Confirm and correct the author contribution statement, including independently selected data sources informed by recommendations and Claude Code implementation assistance.
- [x] Choose the repository name and initial private visibility: `seanthengineer/the-intention-gap`.
- [x] Authorize and complete initial Git initialization and GitHub push.

**Before the first commit (commands in section 8):**
- [ ] `python -m tools.release check`: all PASS.
- [ ] `python audit/verify_freeze.py`: five manifests OK.
- [ ] `python -m tools.release inventory --write`: no change.
- [ ] `git status` shows only files in `docs/release_inventory.csv`; nothing under `data/raw` or `data/processed`; no `CLAUDE.md`, `.env` or archives.

**My GitHub tasks after the first push:**
- [ ] Enable secret scanning, push protection and private vulnerability reporting.
- [ ] Protect `main`: require the CI workflow and a review for changes to `tools/`, `.github/` and `docs/*_freeze.sha256`.
- [x] Confirm the first CI source-only run passed on Ubuntu and Windows (392 tests, 37 data-dependent skips); the integrity workflow also passed on a subsequent manual run.
- [ ] Check that the README renders correctly in light and dark mode, including the Mermaid diagrams and images.
- [ ] Tag the release (`v1.0.0`).

## 7. Local pre-publication review archive

| Item | Value |
|---|---|
| Location | `../intention-gap-public-release-candidate.zip`, outside the repository and **not published** |
| Purpose | Pre-publication review of exactly what would be pushed to GitHub. It is distinct from the authoritative frozen research archive, `../intention-gap-review-source-final.zip`, which is unchanged |
| Contents | Every file in `docs/release_inventory.csv` plus the inventory, under a top-level `the-intention-gap/` folder, with an `ARCHIVE_MANIFEST.sha256` of every file |
| Built by | `python -m tools.release stage <empty folder outside the repository> --archive ../intention-gap-public-release-candidate.zip`. Staging refuses to run if any release check fails. The ZIP is deterministic: fixed order, timestamps, permissions and creating system |
| Archive hash | Recorded beside the archive in `intention-gap-public-release-candidate.zip.sha256`, because an archive cannot contain its own hash |
| Checks on the archive | The frozen safety scan `audit/verify_final_synthesis.check_archive`: every frozen file present with its manifest hash, internal manifest consistent, and no restricted paths, respondent columns or credentials. The same files were also tested as a source-only checkout and in Git (sections 2 and 4) |

## 8. Initial Git commands (historical instructions, already completed)

The initial Git initialization, private remote and push were completed on 2026-11-21; **do not rerun these initialization commands** in the existing repository. The commands below are preserved as reproducibility notes, not as instructions to reinitialize or publish publicly.

```
cd "<path to>/the-intention-gap"

# Pre-commit verification
python audit/verify_freeze.py
python -m tools.release check
python -m tools.release inventory --write        # must leave docs/release_inventory.csv unchanged

# Initialise; core.autocrlf=false is recommended, though .gitattributes already prevents conversion
git init -b main
git config core.autocrlf false
git config user.name  "<author name>"
git config user.email "<GitHub noreply address>"

# Stage and check what will be committed
git add -A
git status --short
git ls-files | wc -l                               # equals the inventory rows + 1
git ls-files | grep -E "^data/(raw|processed)/|CLAUDE.md|\.env|\.zip$" || echo "no restricted paths"

# Optional local guard: run the release checks before every push
printf '#!/bin/sh\npython -m tools.release check\n' > .git/hooks/pre-push && chmod +x .git/hooks/pre-push

# First commit and publication
git commit -m "Initial public release of The Intention Gap research project"
git remote add origin https://github.com/<owner>/<repository>.git
git push -u origin main
git tag -a v1.0.0 -m "The Intention Gap: frozen research and publication release"
git push origin v1.0.0

# Verify a fresh clone (byte-identical frozen files)
git clone https://github.com/<owner>/<repository>.git /tmp/intention-gap-check
cd /tmp/intention-gap-check && python audit/verify_freeze.py
```

The history starts at the publication commit and is not backdated; the research timeline is documented in `audit/scientific-audit.md`.

## 9. Remaining blockers and limitations

**Material blockers to engineering: none.**

**My decisions completed:** original-code MIT license, original-documentation CC BY 4.0 license, copyright name Sean Nathaniel M., citation metadata, contribution statement, and private GitHub setup. **Still pending:** final visual and security-setting review, explicit authorization to make the repository public, and a public release tag.

**Nonblocking limitations:**
- GitHub CI ran successfully on Ubuntu and Windows, including Pyright. Weekly maintenance and the macOS job have not yet run.
- Python 3.15.2 is the only tested interpreter.
- Public users cannot run the full-data verifiers without obtaining the source data themselves; five of them stop with an error, rather than SKIP, when data are absent (errata E-11).
- In a fresh clone, one frozen test needs `python -m tools.release restore-run-record` first (errata E-10).
- Frozen figures cannot be edited for accessibility or NSFG footers; the atlas captions supply both.
- 1,872 recorded Pyright errors in frozen and dashboard code remain (library type inference; `environment_and_code_quality.md` §5).
- One method reference, the NSFG Variance Estimation Report, was not retrieved for verification.
- Small residual-category denominators (2–4 respondents) are shown for suppressed NSFG rows; they were reviewed and are not identifying.
