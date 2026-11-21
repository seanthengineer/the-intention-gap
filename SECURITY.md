# Security and data-disclosure policy

## Reporting a problem

Please report privately, not in a public issue, if you find:
- a credential or secret in the repository or its history;
- anything that could identify a survey respondent;
- a published statistic that breaks a data provider's disclosure rules (for example, a CDC WONDER statistic based on nine or fewer births);
- a vulnerability in the code or the workflows.

Use GitHub's **private vulnerability reporting** ("Report a vulnerability" on the repository's Security tab). The owner will enable it when the repository is published.

## What the project does to prevent disclosure

- Only aggregate results are published (`data/public/`). Survey microdata, respondent-level files and provider archives stay local and are ignored by Git.
- NSFG estimates that fail the NCHS reliability standard are suppressed. No CDC WONDER statistic is based on fewer than 10 births.
- `python -m tools.release check` scans every published file for credentials, personal paths, e-mail addresses, restricted file types and respondent-identifier columns. CI runs it on every push and daily.
- The only credential the code uses, a Census API key, is read from the environment and never stored.

Details: [`docs/security_and_disclosure_audit.md`](docs/security_and_disclosure_audit.md).

## Supported versions

Only the current default branch is maintained.
