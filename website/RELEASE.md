# Website release candidate

I published [The Intention Gap](https://seanthengineer.github.io/the-intention-gap/) from `main` through the manual GitHub Pages workflow. The build and deployment jobs passed, and I reviewed the live website. The repository is public. I still need to decide whether to allow search engines to index the site and whether to create an official GitHub Release.

The V2.3 Housing atlas and V2.4 review build were developed on `feat/intention-gap-v2` and merged into `main` before publication. The measurements and browser checks below document that release candidate.

## Geographic data

The atlas joins 510 state-year observations to the existing U.S. chart geometry. Its four measures are rent burden at 30% and 50% of household income, and births per 1,000 women ages 20–24 and 25–29. The 2020 gap appears in the year controls, tables and trend line. Map color bins stay fixed for each measure across years. State selection persists through measure and year changes.

The [export and validation notes](../docs/m10_geography_export.md) document the measurement units, coverage, reproduction commands and disclosure checks. Rates were verified against the local M10 panel and validated CDC records, and both rent measures were recomputed from the local ACS inputs. The published download contains rates and percentages only, plus the state-year keys. The atlas accompanies Figures 3.1–3.4 as descriptive context.

## Licensing

The [licensing register](../docs/licensing_and_attribution.md) covers the HFD, CDC/NCHS, Census and NLSY97 notices. The two documentary images retain responsive JPEG sizes, captions and source links. The footer now identifies the photographs actually shown.

- David Brossard’s *July Evening in Washington Square* is credited under CC BY-SA 2.0 with a resizing notice. [License verification](https://commons.wikimedia.org/wiki/File:July_Evening_in_Washington_Square.jpg)
- Carol M. Highsmith’s Shepherd Street row houses photograph is credited to the George F. Landegger Collection, Library of Congress. The catalog records no known restrictions on publication. [Library of Congress catalog](https://www.loc.gov/pictures/item/2010641825/marc/)

## Verification

| Check | Result |
| --- | --- |
| Astro production builds and website data and text checks | Passed at `/` and `/the-intention-gap/`. The site reads 51 repository source files and checks 49 against freeze hashes. |
| Freeze and release checks | All 221 frozen files matched all five manifests. The release inventory, credential and disclosure scan, local links and byte-preserving attributes passed. |
| Scientific synthesis | Full-data run had 46 passes, zero failures or skips. Source-only run had 10 passes and five expected skips. |
| NSFG audit | Full-data run had 18 passes and the existing intention-schema warning, with zero failures or skips. Source-only run skipped the 19 data-dependent checks. |
| Python unit tests | The source-only suite ran 400 cases with 39 expected skips. The full-data run exercised 418 cases. Two release cases initially included the untracked V2.1 review folder and passed on rerun with that folder temporarily held outside the checkout. The review files were restored. All six atlas tests passed with local data. |
| Static analysis | Astro type check passed across 38 files with five unused-import hints. Pyright matched 1,840 known diagnostics across frozen research code and had zero tooling regressions. |
| Published content | V2.2 and the candidate match for the 15 original chart IDs, 21 archived image hashes, 17 original captions, 194 existing table rows, 62 controls and 156 in-page research links. The comparison accounts for the added atlas and provenance row. |
| Pages subpath | Edge verified the original charts, anchors, navigation, fonts, images, atlas state selection, CSV contents and archive lightbox. All 26 local asset URLs and 75 repository reference targets resolved. |
| Security | No external script, style or font requests, console errors or local filesystem paths in the production check. npm dependency audit found zero vulnerabilities. The build includes only the static site, public figures, photos, fonts and the public atlas export. |

## Browser and accessibility coverage

Playwright and Edge inspected 1920 × 1080, 1440 × 900, 1280 × 800, 768 × 1024, 390 × 844 and 375 × 667. The six layouts passed the page overflow, photo loading, keyboard navigation and particle transition checks. Reflow at 720 CSS pixels was tested as the layout equivalent of 200% zoom on the 1440-pixel view. The screenshots and machine-readable results are under the local `outputs/v2.4/` directory.

Browser tests exercised all 15 original charts, 23 live controls, keyboard tooltips, pointer entry into the tooltip, Escape dismissal, the archive lightbox and table expansion. The atlas was exercised at all six sizes, including its four measures, all year options, persistent state selection, keyboard and touch input, the 2020 break and both data tables. Reduced motion was checked on desktop and mobile. With JavaScript off, the original figure images, accessible evidence tables, default atlas and downloadable data remain available.

axe-core flagged no automated WCAG 2.1 A/AA violations in desktop and mobile smoke checks. Text over layered backgrounds still needs manual contrast review. Native browser zoom, physical devices and a screen-reader session were outside the test coverage.

## Performance

A clean, unthrottled local Edge 158 desktop run at 1440 × 900 under the Pages subpath recorded largest contentful paint at about 0.66 s, load at 0.91 s and cumulative layout shift of 0.002. The uncompressed totals were 1.17 MB at initial load, 0.66 MB of JavaScript in the artifact and 6.86 MB for the complete artifact including the 21 archive images. The atlas reuses the existing geometry and D3 bundle. The chart tooltip avoids DOM writes when the displayed value stays the same. The responsive photograph variants remain lazy-loaded.

In a scripted desktop scroll through the cover, ASCII-to-map and map-to-forecast stages, each stage had a median frame interval of 16.7 ms. The 95th-percentile interval was 33.4 ms for the cover and ASCII-to-map stages and 16.8 ms for map-to-forecast. These numbers are a local production smoke measurement. Device speed, hosting and compression affect public timings. The chart assets and server-rendered atlas geometry account for a substantial share of the payload. Field data and physical-device performance remain unmeasured.

## GitHub Pages deployment

I built the published site at the `/the-intention-gap/` base path. The [website build guide](README.md) documents both build variants. The Website workflow verifies them; the separate [manual Pages workflow](../.github/workflows/pages.yml) deploys only with my confirmation and never runs automatically on pushes or pull requests. The public site is [here](https://seanthengineer.github.io/the-intention-gap/). I have left search indexing disabled while I decide whether to enable it. My [publication record](../docs/publication_plan.md) tracks the deployment and remaining decisions.
