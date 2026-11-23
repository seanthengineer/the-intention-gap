# M10 housing atlas data

The [atlas CSV](../data/public/m10/m10_geography.csv) is an aggregate derivative of the M10 analytical panel. It contains 510 state-year rows for the 50 states and the District of Columbia in 2014–2019 and 2021–2024. The panel has 1,020 state-year-age rows. The Census Bureau issued experimental ACS 1-year estimates for 2020 in place of the standard release, so the atlas skips that year. [M10 data feasibility audit](m10_data_feasibility.md) · [Census Bureau 2020 experimental data](https://www.census.gov/programs-surveys/acs/data/experimental-data.html)

## Data dictionary

| Field | Definition |
| --- | --- |
| `state_fips` | Two-character state FIPS code, including leading zeros |
| `state_name` | Jurisdiction name shared by both sources |
| `year` | Calendar year |
| `burden30_pct` | Percentage of renter-occupied units with computed rent burden spending 30% or more of household income on gross rent |
| `severe50_pct` | Percentage of renter-occupied units with computed rent burden spending 50% or more of household income on gross rent |
| `birth_rate_20_24` | Annual live births per 1,000 women ages 20–24 by mother's state of residence |
| `birth_rate_25_29` | Annual live births per 1,000 women ages 25–29 by mother's state of residence |

The project calculated both rent-burden percentages from Census Bureau ACS 1-year table B25070. The denominator sums categories B25070_002E through B25070_010E. The 30% numerator sums B25070_007E through B25070_010E and the 50% numerator is B25070_010E. Birth rates use the values reported by CDC WONDER Natality, 2007–2024 for 2014–2015 and Natality, 2016–2024 Expanded for the remaining years. [Census table definitions](https://api.census.gov/data/2024/acs/acs1/groups/B25070.html) · [CDC WONDER Natality](https://wonder.cdc.gov/natality.html)

This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau. NCHS is responsible for the initial natality data release. The project's authors are responsible for the analysis, interpretations, and conclusions. [Census API terms](https://www.census.gov/data/developers/about/terms-of-service.html) · [Project licensing and attribution](licensing_and_attribution.md)

The atlas export includes percentages and rates at the analytical panel's stored precision. Its fields exclude births, population denominators, raw source records, and respondent-level data. The exporter requires an available, verified source rate and checks that the underlying event count meets the CDC WONDER publication threshold. The minimum number of underlying births in the verified release was 598 and each state-year-age rate passed the check. [CDC WONDER confidentiality rules](https://wonder.cdc.gov/wonder/help/natality-expanded.html#Assurance%20of%20Confidentiality)

## Reproduction

Obtain and prepare the local ACS and CDC files using the [full research reproduction steps](final_reproducibility_guide.md). For a checkout with the saved source responses, the following commands regenerate the processed inputs with the existing research pipeline and reproduce the atlas.

```sh
python -m analysis.acs_housing
python -m analysis.cdc_natality
python -m analysis.m10_panel
python -m tools.m10_geography --write
python -m tools.m10_geography --verify-source
```

From a source-only checkout, `python -m tools.m10_geography` checks coverage, fields, and agreement with the frozen annual summaries. The website build reads the checked-in CSV, verifies the FIPS join against its rendered geometry and includes a copy of the CSV for download. The atlas describes aggregate levels across places and years. Refer to the [M10 analysis and limitations](m10_housing_fertility.md) for the separate tests of associations.
