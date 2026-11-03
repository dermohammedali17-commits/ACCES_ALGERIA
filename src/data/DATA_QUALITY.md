# Data Reliability and Provenance

**Scope:** the UN Comtrade and World Bank API pipeline in `trade_pipeline.py`.
This document records the pipeline's interpretation rules and the live sample
reviewed on 2026-11-03. API values can change when providers revise or publish
observations; this sample is evidence of one retrieval, not a frozen dataset.

## UN Comtrade

The pipeline first requests Algeria's reported imports. If that query returns no
rows, it requests exports reported by selected partner countries with Algeria
as partner. Mirror exports are useful for triangulation, but they are not
Algeria's own import declarations. A mirror-only year is therefore reported as
`PARTIAL` and carries a warning in its year report.

The unauthenticated Preview API may return at most 500 rows, so a successful
response does not prove that the query's result set is complete. Reports expose
the endpoint mode and the record count. Each normalized record's `source_url`
contains the query parameters used for its reporter, partner, year, flow, and
commodity; the subscription key is never included in the URL.

The pipeline preserves the reporter and partner codes, reported/aggregate
flags, source type, source URL, and retrieval time. It also preserves the
`isnetWgtEstimated` flag (and its alternate API spelling). UN Comtrade's
quantity guidance says zero and null quantity/weight values both represent
missing or estimated quantity information. Accordingly, a zero `netWgt` is
normalized to `net_weight_kg = null`; the original estimation flag remains
available when supplied. See the [UN Comtrade quantity guidance](https://uncomtrade.org/docs/how-should-i-interpret-and-use-quantity-data-in-un-comtrade/)
and [Preview/API limits](https://uncomtrade.org/docs/content-of-data/).

The live sample retrieved on 2026-11-03 contained four mirror records for 2023
from reporter codes 156, 792, 251, and 276, and no direct Algerian import rows.
Those rows must not be presented as direct Algerian declarations. The query
used commodity code `87`, a broad HS chapter; retain the API aggregate flag and
do not describe this sample as a detailed vehicle-model breakdown.

## World Bank Indicators

Indicator status meanings:

- `SUCCESS`: every requested year has a valid numeric observation.
- `PARTIAL`: at least one valid observation exists, but one or more requested
  years are missing or invalid.
- `NO_DATA`: the request returned without a transport/response error, but no
  valid numeric observations were available in the requested range.
- `FAILED`: the request or response raised an error.

Missing values are not imputed or carried forward. `retrieved_years` lists
unique years with valid observations; `record_count` counts accepted observation
rows. Each record's `source_url` includes the indicator and requested date range.

The live sample retrieved on 2026-11-03 returned 2023 GDP and manufacturing
observations. The tariff indicator returned a 2023 row with a null value; the
same API response had values for 2020–2022 (10.16, 10.29, and 9.25). The
pipeline therefore reports 2023 as missing/`NO_DATA` for that indicator rather
than treating the successful API response as a transport failure. No 2023 value
is inferred from earlier years.

## Validation and Confidence

`validation_status` and `confidence_level` represent different things.
`validation_status` remains `UNVERIFIED` until a record has been independently
checked against suitable evidence. The current conservative confidence rubric
is:

- `LOW`: mirror-reported trade values used as a proxy for the target country's
  direct declarations.
- `MEDIUM`: values from one official source (direct Comtrade reporter data or
  World Bank observations) that pass structural checks but have not been
  independently corroborated.
- `HIGH`: reserved for observations independently cross-checked against a
  separate authoritative source; the pipeline does not assign this
  automatically.

`confidence_level = null` means no source rule applies or the confidence has not
been assessed. It is not a zero score and must not be interpreted as high
confidence. Confidence does not certify completeness: Preview caps, missing
years, and aggregate commodity levels remain separate limitations.

The pipeline validates requested reporter, partner, period, flow, and commodity
dimensions; rejects non-finite numeric values; filters World Bank observations
to the requested years; and records missing years and retrieval timestamps.
These checks establish format and query consistency, not independent truth of
the reported economic values.

## Country Reference Scope

`reference/countries.csv` is an operational five-country seed for Algeria and
the current mirror reporter priority. It is not a full country catalogue.
Country-code source checks and the France-specific Comtrade/M49 distinction are
documented in [`reference/README.md`](reference/README.md).
