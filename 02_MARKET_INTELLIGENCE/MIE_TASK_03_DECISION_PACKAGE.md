# ACCESS ALGERIA Task 03 — MIE Decision Package

**Status:** Superseded by founder-approved Task 03 handoff (2026-11-04)
**Prepared:** 2026-11-04

**Later P04 resolution:** The Model B authority and weight question noted below
was resolved by founder-approved decision `DEC-P04-001` on 2026-11-11. MIE's
Task 03 boundary remains unchanged: MIE supplies evidence and does not score
opportunities.

## Executive recommendation

Build MIE as a provenance-aware evidence and data-quality layer that supplies market facts and documented interpretations to existing workflows. It must not create or alter opportunity scores. Use the current World Bank and UN Comtrade retrieval paths initially; do not add a database or dependencies. Retain provenance and coverage distinctions already present. The bounded implementation is authorized by the founder decisions recorded below.

## Evidence and recommended defaults

| Topic | Repository evidence | Recommended default | Status |
|---|---|---|---|
| MIE role | Existing workflows separate data, interpretation, and strategic implication. The data pipeline retrieves observations and emits reports. | MIE supplies evidence; scoring remains downstream and separately governed. | Safe architecture default |
| Model B authority | src/scoring/engine.py contains legacy 0–100 OpportunityScorerB and published-method OpportunityScorerA. src/scoring/opportunity_scorer_b.py contains a named nine-dimension 0–10 input scorer producing 0–100. Weights and missing-data behavior differ. Methodology and tests encode the named model, but code labels and protected-module guidance do not establish authority. | Do not connect MIE to a scorer or name a canonical implementation until the founder resolves the conflict. Do not change code or weights. | **Founder decision pending** |
| World Bank indicators | TradeMacroPipeline.INDICATORS: NY.GDP.MKTP.CD GDP current US$, NV.IND.MANF.ZS manufacturing value added (% GDP), TM.TAX.MRCH.WM.AR.ZS applied weighted-mean tariff (%). src/data/DATA_QUALITY.md records 2023 GDP/manufacturing data and null 2023 tariff in its 2026-11-03 sample. | Keep as technical seed set; label tariff limitations; never treat null as zero or indicators as scores. | Relevance needs founder review |
| Comtrade scope | trade_pipeline.py defaults to HS 87. mirror_trade.py uses HS 8703/8704 and selected reporters over a rolling five-year window ending at the prior year. Mirror downloader is isolated in requirements-comtrade-mirror.txt. | Keep configurations distinct. For initial MIE integration use the existing pipeline path unless founder selects the vehicle PoC. Do not silently merge direct and mirror. | **Founder decision pending** on analytical scope |
| Direct/mirror data | Pipeline marks mirror fallback PARTIAL and retains reporter, partner, source, confidence. PoC compares direct imports with selected partners’ exports. | Keep series distinct; disclose coverage and valuation differences; no invisible substitution. | Safe architecture default |
| Missing data/completeness | Pipeline reports SUCCESS/PARTIAL/NO_DATA/FAILED with requested, retrieved, and missing years; preview is capped at 500 rows. | Missing remains missing. Successful API response is not a completeness claim. Separate coverage, validity, and source confidence. | Safe architecture default |
| Storage/retention | Existing adapters cache Comtrade responses locally; pipeline returns normalized records and retrieval reports. No MIE retention policy exists. | Reuse local behavior initially. Decide raw/normalized retention, refresh, and deletion before recurring production use. Defer database and dependencies. | **Founder decision pending** |
| Source authority | Records carry source, URL, retrieval time; DATA_QUALITY.md separates structural checks from corroboration. No MIE source registry exists. | Versioned source/indicator metadata should include provider, definition, unit, geography, period, access mode, retrieval date, limits, and transformations. Keep separate from human claim verification. | Safe architecture default |

## Safe design decisions for detailed design

1. MIE supplies evidence and provenance; it does not own scoring or change weights.
2. Direct and mirror observations remain distinguishable end to end.
3. Missing or invalid values remain missing; retrieval success does not imply full coverage.
4. Source confidence, record validation, and query/time coverage are separate concepts.
5. Start with existing adapters, local storage, and dependencies; defer broader infrastructure pending an approved use case.

The existing Decision Register requires decision maker, evidence, alternatives, rationale, consequence, next action, and review date, while its summary table has only ID/date/decision/project/status/review date. No completed MIE-specific record exists. These are recorded as design recommendations here, not founder-approved register entries.

## Founder decisions recorded

1. Future Model B reference: nine dimensions, each rated 0–10. This approves the reference description only; no scorer integration, reconciliation, weight changes, or methodology changes are authorized.
2. Comtrade pilot scope: HS 8703 and HS 8704. Direct Algeria imports and mirror exports remain separate and are never added or substituted.
3. The tariff indicator remains `PENDING_VALIDATION` and must not support conclusions until geography, definition, and scope are verified.
4. Normalized data retention: 24 months; evidence bundles and retrieval manifests: 5 years; raw payloads: transient by default. Refresh World Bank and Comtrade quarterly. Existing cache behavior is unchanged.

These decisions authorize the bounded Task 03 implementation. They do not authorize scorer changes, weight changes, live API calls, dependency installation, scheduling, deployment, or changes to existing cache behavior.
