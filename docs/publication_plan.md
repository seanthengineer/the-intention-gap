# My publication plan

I published [The Intention Gap](https://seanthengineer.github.io/the-intention-gap/) using GitHub Pages from the same repository as my research. I kept the research results frozen and the website layout unchanged. I approved the public repository and the manual deployment. I approved search indexing and added a canonical URL and sitemap. I still need to redeploy the change and decide on the official GitHub Release.

The checklist below records how I prepared publication. Some steps describe the actions I planned before the launch.

## What I have prepared

- I merged the completed research website, geographic atlas and documentation into `main`.
- I verified that the latest research CI and both website build variants pass.
- I kept the 221 frozen research files and their five SHA-256 manifests unchanged.
- I added a manual GitHub Pages workflow at [`.github/workflows/pages.yml`](../.github/workflows/pages.yml). It cannot deploy while the repository is private, cannot deploy from a branch other than `main`, and requires me to select the publishing confirmation.
- I arranged for [the Website workflow](../.github/workflows/website.yml) to check every pull request, so I can require its checks before a merge.
- I reviewed the public file inventory and the 18 recent commit and branch snapshots available during preparation. None of their file paths suggested raw surveys, private-key files or local credentials. The existing release scan checks the current tracked content and disclosure safeguards. This does not replace scanning all previous file contents for secrets.

## GitHub settings I still need to apply

These settings live in my GitHub account. I will confirm them before publication.

### 1. Remove obsolete branches

I will keep `main` and retain `feat/intention-gap-v2` as a release fallback until I verify the live website. I can safely delete these older merged branches from [the branches page](https://github.com/seanthengineer/the-intention-gap/branches):

- `chore/license-and-author-credit`
- `docs/author-voice-and-attribution`
- `chore/pre-publication-tidy`

Deleting a branch does not erase its commits, pull requests or history. I do not need to rewrite the research history or delete workflow files to tidy the repository.

### 2. Protect `main`

In [Settings, Branches](https://github.com/seanthengineer/the-intention-gap/settings/branches), I will create a protection rule or ruleset targeting `main` and:

- Require pull requests before merging.
- Require the successful CI checks for Ubuntu, Windows and Pyright.
- Require the two Website checks, `Install and build the website (build)` and `Install and build the website (build:pages)`. The Website workflow now runs on every pull request.
- Require conversations to be resolved before merging, and block force pushes and branch deletion.
- Preserve a workable solo-developer review process. Requiring another person's approval when I am the only contributor could block my own releases.

If GitHub does not offer branch protection for my account's current plan while the repository is private, I will enable it when the plan or repository visibility permits it. I will not claim a rule is active until GitHub confirms it.

### 3. Confirm repository security

In [Settings, Code security](https://github.com/seanthengineer/the-intention-gap/settings/security_analysis), I will enable secret scanning, push protection and private vulnerability reporting where GitHub makes those features available. I will keep the default Actions permission read-only. The manual publishing job receives the limited Pages permission it needs only when I approve a release.

I will also review the full commit history for credentials before changing repository visibility. The current release checks, [security audit](security_and_disclosure_audit.md) and [licensing register](licensing_and_attribution.md) are my evidence for the present release, not a guarantee about every historical revision.

### 4. Configure Pages without publishing

At [Settings, Pages](https://github.com/seanthengineer/the-intention-gap/settings/pages), I will select **GitHub Actions** as the publishing source when GitHub allows it.

The site will use `https://seanthengineer.github.io/the-intention-gap/`. The [manual publishing workflow](../.github/workflows/pages.yml) builds the existing site with `npm run build:pages` and uploads only `website/dist/`. It never publishes on a push or pull request.

The [normal Website checks](../.github/workflows/website.yml) already test the production build and the `/the-intention-gap/` base path. The website keeps its `noindex, nofollow` directive until I approve public indexing.

### 5. Prepare the public repository details

I will use the following settings in the repository's About section at publication.

**Repository description**

> Independent U.S. demographic research into Generation Z's fertility intentions, housing costs and future births, backed by four verified studies.

**Suggested topics**

`demography`, `fertility`, `generation-z`, `data-science`, `machine-learning`, `forecasting`, `reproducible-research`, `astro`, `d3`

**Website address after launch**

`https://seanthengineer.github.io/the-intention-gap/`

For the social preview, I can use the existing [website overview image](../assets/readme/website-overview.png), subject to checking that the preview crop looks correct. I will keep the existing research title and citation name. I will not claim a DOI, journal publication or peer review.

## My publication decision

I approved public access to the research repository and deployed the website with the manual Publish website workflow on `main`. GitHub reported a successful build and deployment, and I reviewed the live site.

I have linked the published site in the [main README](../README.md). I set the GitHub repository homepage and approved removing `noindex, nofollow`. I am preparing the next manual deployment. After it succeeds, I can verify the canonical URL and sitemap and request indexing in Google Search Console. I still need to decide when to issue a tagged GitHub Release. I will not claim a DOI or peer review.

**Current status:** The repository and website are public. I have approved search indexing and prepared the website changes, but they are not live until I redeploy. No GitHub Release has been published.
