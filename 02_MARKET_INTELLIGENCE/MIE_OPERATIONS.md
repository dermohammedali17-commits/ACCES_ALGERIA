# MIE Task 03 — Operations and readiness

## Purpose and boundary

The Market Intelligence Engine (`src/data/mie/`) gathers and presents evidence
from the existing World Bank and UN Comtrade adapters. It does not compute,
change, or call opportunity scoring. The nine-dimension, 0–10 Model B is only
the founder-approved future reference; scoring integration remains out of scope.

## Approved pilot and safeguards

- Comtrade codes: HS 8703 and HS 8704.
- Direct Algeria imports (`flow=M`, reporter 12) and selected reporters' mirror
  exports (`flow=X`, Algeria partner 12) are distinct retrievals. Never sum,
  substitute, or label mirror values as Algeria declarations.
- Tariff indicator `TM.TAX.MRCH.WM.AR.ZS` is `PENDING_VALIDATION`, is not queried
  by the pilot, and must not support conclusions until geography, definition,
  and scope are verified.
- Missing observations remain null/absent. A successful API response is not a
  completeness claim. Preview caps and mirror reporter coverage remain caveats.
- Observation validation is `UNVERIFIED` by default; confidence is null until
  separately assessed. Neither field is a proxy for period/query coverage.

## Retention and refresh

Normalized data: 24 months. Evidence bundles and retrieval manifests: 5 years.
Raw provider payloads are transient by default. World Bank and Comtrade refresh
quarterly. The existing Comtrade cache is unchanged and its expiration is not
managed by MIE. This implementation does not add an automated deletion job or
scheduler; the designated operator must apply the retention periods in the
approved storage environment and document deletion activity. No live calls are
made by tests.

## Roles and release gate

| Role | Responsibility | Assignment |
|---|---|---|
| MIE data owner | Approves query years/reporters, reviews coverage and signs off the quarterly evidence bundle | Founder / Access Algeria System Owner |
| Storage custodian | Applies archive access, backup, and retention/deletion controls | Founder / Access Algeria System Owner; may delegate to the repository maintainer |
| Evidence reviewer | Checks source, units, missing periods, direct/mirror labels, and any interpretation | Data owner or reviewer named by the data owner for each run |

Both accountabilities are assigned to the Founder / Access Algeria System
Owner. The repository does not identify that person by name. The founder may
delegate day-to-day storage custody to the repository maintainer while retaining
accountability. Confirm archive access/backup before the first recurring run.

## Quarterly run procedure

1. The data owner opens a run record below and confirms the reporting years and
   the existing cache policy. Do not change cache settings for this task.
2. Run `MarketIntelligenceEngine.collect(start_year, end_year)` manually.
   A default run queries the two active World Bank indicators and five separate
   Comtrade queries for direct imports and configured mirror reporters. It
   records the tariff indicator as pending and does not query it.
3. Save the returned bundle with `save_bundle`. Save it and its rendered view
   under the approved evidence archive, not an unreviewed personal folder.
4. Inspect each `Retrieval`: status, requested/retrieved/missing periods, mode,
   record count, warnings, and failure type. Check that any NO_DATA,
   UNCONFIRMED_EMPTY, or FAILED result remains missing and has not become zero.
5. Inspect each Comtrade retrieval's `diagnostics` alongside reporter, flow,
   partner, period and HS code. Diagnostics record safe query parameters,
   access mode, response state, row count, and—when exposed by the client—HTTP
   status, provider error payload/message, total count and pagination fields.
   API keys, authorization values and other credential fields are excluded or
   redacted. The current `comtradeapicall` DataFrame wrapper does not expose
   HTTP status or response headers/count metadata, so these fields may be
   absent; their absence is not evidence of complete coverage. DataFrame `attrs`
   metadata is recorded when a wrapper supplies it. Inspect Comtrade reporter,
   flow and HS code for each observation. Keep
   `algeria_direct_imports` apart from
   `selected_reporter_mirror_exports`; never total them together. The EU
   aggregate reporter 97 is kept as one reporter and is not combined with EU
   member reporters. The current provider wrapper may omit pagination,
   total-count, or per-commodity completeness metadata; period coverage means at least one
   valid observation for that year, not complete coverage of both HS codes.
6. Review units, source references, validation status (`UNVERIFIED`) and
   confidence (`null`). Label any human analysis as interpretation and record
   its author. Do not publish a conclusion from the tariff indicator.
7. Evidence reviewer signs the run record. Storage custodian archives the
   bundle/manifest and records the next retention review date.
8. Interpret Comtrade outcomes as follows: `SUCCESS`/`PARTIAL` mean at least
   one valid observation for some/all requested periods; they do not certify
   both commodities or all pages. `NO_DATA` for an empty frame is used only
   when diagnostics show HTTP 200 and `total_count: 0` (provider-confirmed zero
   rows for this query); it remains missing evidence and is never zero trade.
   `UNCONFIRMED_EMPTY` means no rows arrived without both signals, so
   transport/API failure or incomplete provider metadata remains possible.
   `FAILED` means the client raised after retries; diagnostics preserve any
   exposed status, error type/message, and safe parameters. If a source fails,
   retain the failure record and do not backfill from a
   mirror into direct imports. The current `collect` method reruns the full
   approved query set; it does not yet support selecting only a failed source.
   After checking provider availability and query parameters, rerun the full
   set and preserve both bundle IDs, or leave the retrieval marked FAILED.

To diagnose the unresolved 2023 direct-import result without reading or
writing the local Comtrade cache, run this from the repository root. It prints
only the normalized row count and credential-safe adapter diagnostics:

```python
from src.infrastructure.adapters.comtrade_adapter import ComtradeAdapter

adapter = ComtradeAdapter(use_cache=False, strict_errors=True)
try:
    frame = adapter.fetch_flows("12", "M", [2023], ["8703", "8704"], "0")
    print({"row_count": len(frame), "diagnostics": adapter.last_diagnostics})
except RuntimeError as exc:
    print({"error": type(exc).__name__, "diagnostics": adapter.last_diagnostics})
```

Review `diagnostics.requests` if preview mode split the query by year. An
HTTP/API or transport failure appears as `ERROR` with any exposed status,
payload, or message. A valid empty response requires HTTP 200 and total count
zero. If the provider wrapper omits these fields, keep the result
`UNCONFIRMED_EMPTY`; the cause is unresolved.

### Run and review record template

Copy this block for each quarterly run:

```text
Run ID:
Run date (UTC):
Reporting years:
Data owner:
Evidence reviewer:
Storage custodian:
Bundle path (includes retrieval manifest):
World Bank statuses and missing years:
Direct Comtrade status and missing years:
Mirror reporter statuses and missing years:
Preview/authentication mode evidence or UNKNOWN:
Warnings, provider delays, and reruns:
Direct/mirror separation checked by:
Tariff excluded from conclusions: YES/NO
Interpretation, author, and supporting facts:
Review decision (ACCEPT / ACCEPT WITH LIMITS / RE-RUN):
Next quarterly refresh due:
24-month normalized-data review due:
5-year evidence/manifest review due:
Reviewer sign-off and date:
```

**Accept** only when evidence labels and sources are intact, missing periods
are visible, and direct/mirror streams are separate. **Accept with limits** may
be used when an incomplete source is explicitly disclosed and no conclusion
depends on the missing evidence. **Re-run** when query scope/provenance is
unclear, values fail validation, or a source stream was substituted or merged.

## Local use

From the repository root, in an environment where existing project dependencies
are installed:

```python
from src.data.mie import MarketIntelligenceEngine
from src.data.mie.persistence import save_bundle
from src.data.mie.presentation import render_evidence

bundle = MarketIntelligenceEngine().collect(2020, 2024)
save_bundle(bundle, "data/evidence/mie")
print(render_evidence(bundle))
```

The example performs live provider calls and should only be run by an operator
when a quarterly refresh is due. Tests use fake clients. Bundle writes use a
temporary file and atomic replacement; they do not write raw API responses.
Keep a retrieval manifest with each archived bundle in the approved archive;
the bundle's retrieval entries contain status, requested/retrieved/missing
periods, mode, record count, warnings, sanitized failure type, and safe
diagnostics. Inspect diagnostic parameters to verify reporter 12, partner 0
(World), flow M, periods, and HS 8703/8704 for direct imports. An empty data
list is not a confirmed zero result unless the response also provides a total
count of zero. Never infer zero trade from absent rows.

## Readiness and limits

The contracts, orchestration, serialization, and presentation are offline-tested.
Operational readiness is **conditional**: confirm archive access/backup,
establish an archive/deletion procedure for 24-month and 5-year periods, and
review tariff metadata. No scheduling,
deployment, live acceptance retrieval, database, or cache changes are included.
The Comtrade adapter may not report access mode
through a stable public property, so the MIE marks its mode `CONFIGURED_ADAPTER`
when using that adapter rather than guessing whether its current cache/network
path was authenticated or preview.
