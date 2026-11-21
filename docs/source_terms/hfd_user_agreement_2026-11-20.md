# Human Fertility Database: User Agreement and Citation Guidelines (archived copy)

| Item | Value |
|---|---|
| Source | Human Fertility Database (HFD), Max Planck Institute for Demographic Research (Germany) and Vienna Institute of Demography (Austria) |
| User Agreement URL | <https://www.humanfertility.org/Data/UserAgreement> (the same text is served at `/Account/UserAgreement`) |
| Citation Guidelines URL | <https://www.humanfertility.org/Data/CitationGuidelines> |
| Retrieved | 2026-11-20, by an unauthenticated HTTPS request |
| SHA-256 of the retrieved HTML | User Agreement `ce1a51e488c306afd7de1ae3e7f8cc4ab76ff94d5cadc3a24de859b342d35f5e`; Citation Guidelines `c16a91059ea53c26f28d41480b595d9541e8670c8e22519ccce904d8accd8abf` |
| Page footer | © 2026 MPIDR |
| Version | The pages carry no version number or date; the retrieval date identifies this copy |

The text below is the agreement's operative wording, extracted from the retrieved HTML (navigation and buttons removed; wording unchanged). It is archived so that the licensing decisions in [`docs/licensing_and_attribution.md`](../licensing_and_attribution.md) can be checked against what the provider said at the time.

## User Agreement (verbatim)

> The HFD data is licensed under a Creative Commons Attribution 4.0 International License.
>
> The HFD provides original estimates of fertility rates and indicators, exposure-to-risk, and fertility tables as well as the input data that have been used to produce these estimates. The data constructed by the HFD are published under the CC BY 4.0 license. This is not the case for the input data which remains under each provider's distribution license.
>
> In all published work and presentations, please acknowledge the HFD as either the source or the intermediary provider of the data. When downloading data, note the date for future reference. When presenting and publishing the original HFD estimates of exposure-to-risk, death rates, or life tables, please use the following citation:
>
> HFD. Human Fertility Database. Max Planck Institute for Demographic Research (Germany) and Vienna Institute of Demography (Austria). Available at www.humanfertility.org. Data downloaded on [date]
>
> Note that all original data published under “Input Data” on the country pages should not be used for commercial gain or re-published in any form without the explicit permission of the data owners (usually national statistical agencies).
>
> Data sources used for each country are listed on the country page.
>
> We ask that you kindly observe the following:
>
> Since the HFD data are updated on a regular basis (including corrections as needed), the preferable option is not to pass a copy of these data to other users. Instead, refer them to the HFD website, where they may download the data for themselves. This practice helps to prevent multiple outdated or incorrect versions. It also ensures that each user has full access to the information regarding the source and processing of mortality estimates, citation procedures, and any other useful documentation.

## Citation Guidelines (verbatim excerpt)

> If you are presenting or analyzing our original estimates of fertility rates, fertility tables or other parts of the provided data, including data from the Short-Term Fertility Fluctuations (STFF) series, the following citation format should be used:
>
> Human Fertility Database. Max Planck Institute for Demographic Research (Germany) and Vienna Institute of Demography (Austria). Available at www.humanfertility.org (data downloaded on [date]).
>
> If requirements of a publisher or other important reasons force you to choose another citation format, please make sure that this citation includes the full name of the database, full names of the both institutional data providers, and the HFD Internet address.
>
> Please note that some parts of the data available in this collection (especially population exposure data) come from other sources. If you use such data, it is appropriate to cite first the original source and to acknowledge the HFD as the intermediary.

## What this means for this project

- **Licence of what the project uses.** The project used only HFD-constructed estimates (the `USA.zip` country archive: rates, births, exposures, TFR and cohort indicators). These are CC BY 4.0. No HFD "Input Data" file was downloaded or published, so the input-data restriction ("should not be ... re-published in any form") does not apply.
- **Attribution.** Every public table and figure carrying HFD-derived values is covered by the attribution and change notice in `docs/licensing_and_attribution.md` section 3.
- **The non-binding request.** The HFD asks users not to pass on copies of the data. The project therefore does not redistribute the HFD archive or its files; it publishes only the extracts and derived values needed to check its results, and directs readers to the HFD for the data themselves.
- **Underlying U.S. sources.** According to the HFD's U.S. documentation (`USAref`), U.S. birth counts come from the vital statistics published by NCHS and the Census Bureau, and the HFD estimates population exposure from Human Mortality Database data on population size and deaths. Following the Citation Guidelines, the bibliography acknowledges these sources and cites the HFD as the intermediary.
