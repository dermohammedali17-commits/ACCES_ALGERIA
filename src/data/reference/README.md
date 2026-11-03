# Country reference data

`countries.csv` is a five-row operational seed for the Algeria trade-data
workflow and current mirror reporter priority. It is not a complete country
catalogue, and its `region`, `is_target_market`, and `is_active` fields are
project configuration rather than authoritative country facts.

## Code checks

Reviewed 2026-11-03 against the following source material:

- The [UN Statistics Division M49 table](https://unstats.un.org/unsd/methodology/m49/)
  supplies country/area names, M49 numeric codes, and ISO alpha codes. Algeria,
  China, Germany, and Türkiye in the seed align with M49 numerically (Algeria's
  `012` is represented as `12` in the Comtrade request) and by ISO codes.
- France is a deliberate service-specific exception: M49 lists France as
  `250`, while the live Comtrade response reviewed for this project returned
  reporter code `251` with reporter name `France`. Keep `251` in the
  `comtrade_code` field for the Comtrade client; do not treat that field as a
  universal M49 code.
- The [World Bank Country API documentation](https://datahelpdesk.worldbank.org/knowledgebase/articles/898590-country-api-queries)
  states that country responses include ISO alpha-2 and alpha-3 codes. The seed's
  World Bank codes match its ISO alpha-3 codes; the live pipeline sample also
  returned country `DZA` / Algeria.

These checks support the current five operational mappings, not the completeness
of the seed or the eligibility of every possible mirror reporter. When adding
countries, retain source URLs, access dates, and evidence for each service's
code mapping.
