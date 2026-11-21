# Contributing

Thank you for your interest. The Intention Gap is a **completed and frozen research project**, so contributions take a particular form.

## What is welcome

- **Reports of errors**: a wrong number, a citation problem, a broken link or a reproducibility failure. Please open an issue with the file, the line or table, and what you expected.
- **Reproduction reports**: whether the source-only checks pass on your platform (Python version and operating system), or whether your full-data rerun reproduced the frozen outputs.
- **Questions about methods**: please point to the section of the chapter or manuscript concerned.

## What cannot be changed by a pull request

- **Frozen files.** 221 files are frozen by SHA-256 manifests (`docs/*_freeze.sha256`). They are corrected only through a documented freeze revision (see `docs/m11_freeze_revision_F21-1.md` for an example) or recorded in `docs/publication_errata.md`. Tests fail if a frozen file changes.
- **Accepted findings.** Results are not re-tuned. New analyses would be a new, separately documented study.
- **Data.** Never commit raw or respondent-level data, provider archives, credentials or `.env` files. `data/raw/` and `data/processed/` are ignored by Git for this reason.

## Before opening a pull request

```
python -m pip install --only-binary=:all: --require-hashes -r requirements-lock.txt
python -m pip install --only-binary=:all: --require-hashes -r requirements-dev.txt
python audit/verify_freeze.py               # all five manifests must be OK
python -m tools.release check               # inventory, frozen hashes, credential and disclosure scan, links
python -m tools.release restore-run-record  # needed once in a fresh clone
python -m unittest                          # tests needing restricted data are skipped
python -m tools.pyright_baseline            # no new type errors; tooling must be clean
```

If you add a file, run `python -m tools.release inventory --write` and commit the updated `docs/release_inventory.csv`.

## Conventions

- Tests use `unittest`.
- Source files carry no tutorial-style comments; explanations belong in `docs/`.
- New publication tooling must pass Pyright with no diagnostics.

## Conduct

Be respectful and specific. Discussions of fertility touch personal topics: keep them about the data and methods, not about individuals.
