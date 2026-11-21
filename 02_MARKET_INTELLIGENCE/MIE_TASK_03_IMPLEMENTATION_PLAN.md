# ACCESS ALGERIA Task 03 — MIE Implementation Plan

**Status:** Implemented with founder-approved scope; see MIE_OPERATIONS.md
**Prepared:** 2026-11-04
**Companion:** [MIE Task 03 Decision Package](MIE_TASK_03_DECISION_PACKAGE.md)

The original task gates below are resolved by the founder decisions recorded in the companion decision package. Tasks are implemented within that approved scope. Do not modify scorer code or weights.

## Task 0 — Confirm scope and freeze interface

- **Purpose:** Turn founder decisions into an approved, versioned MIE contract.
- **Files:** This decision package; 13_PORTFOLIO_AND_DASHBOARD/DECISION_REGISTER.md only with owner-approved entries.
- **Dependencies:** Resolved by the founder handoff and recorded in the companion decision package.
- **Checks:** Documentation review against repository; confirm choices are approved or pending and have an owner.
- **Acceptance:** Approved defaults and non-goals recorded; register entries include required fields; no inferred approval.
- **Rollback:** Revert only new MIE documentation; preserve all existing changes and untracked files.

## Task 1 — Define source and indicator metadata contract

- **Purpose:** Specify stable metadata without changing collection behavior.
- **Files:** New src/data/mie/ metadata module(s), focused tests in tests/, optional src/data/mie/README.md.
- **Dependencies:** Task 0; indicator and trade scope approved in the handoff.
- **Tests:** Schema/required fields, stable IDs, URL and credential redaction, units/geography/period, direct/mirror distinctions.
- **Acceptance:** Each enabled source/indicator has provider, definition, unit, geography, temporal granularity, query defaults, limitations, retrieval semantics, and version; no credentials in metadata or URLs.
- **Rollback:** Remove only new metadata and tests; do not remove caches or user data.

## Task 2 — Add narrow MIE orchestration boundary

- **Purpose:** Call existing adapters and return an evidence bundle without duplicating retrieval logic.
- **Files:** New src/data/mie/ orchestration module(s); tests/test_mie_*.py. Read-only integration with current adapters; no edits to them absent separate approval.
- **Dependencies:** Task 1; existing adapter contracts; approved query scope.
- **Tests:** Fake-client success/partial/no-data/failure, indicator years, selected Comtrade query, empty results; no live network.
- **Acceptance:** Output contains normalized observations, provenance, requested/retrieved/missing coverage, source mode, warnings; missing remains null/absent; API success does not imply completeness; direct/mirror identity is preserved.
- **Rollback:** Remove only new orchestration files/tests; never delete existing caches or outputs.

## Task 3 — Persist versioned local evidence bundles

- **Purpose:** Make approved results reviewable and reproducible with existing local-storage conventions.
- **Files:** New persistence module only if needed; focused tests; generated-path documentation. Do not alter existing cache format.
- **Dependencies:** Task 2; approved retention and refresh are documented. Output path remains operator-selected.
- **Tests:** Deterministic serialization, schema version, null/provenance round-trip, safe filenames, no secret serialization, freshness reporting.
- **Acceptance:** Bundle records schema version, retrieval time, parameters, source references, warnings, coverage; retention is explicit/testable; failed writes do not corrupt prior valid output.
- **Rollback:** Disable/remove only new MIE writes; preserve caches and generated files absent separate cleanup approval.

## Task 4 — Expose evidence downstream without scoring

- **Purpose:** Let market-intelligence documents consume evidence without generating or changing scores.
- **Files:** New presentation module(s) and tests; optional reviewed update to 02_MARKET_INTELLIGENCE/README.md. No scorer files.
- **Dependencies:** Task 3; evidence presentation is standalone and does not change scoring.
- **Tests:** Source/date/unit/missing/coverage caveats, direct/mirror distinction, fact/derived/interpretation labels, safe rendering; assert no score output.
- **Acceptance:** Evidence is independently reviewable; facts, derived values, and human interpretation are visibly distinct; no score or weight is computed.
- **Rollback:** Revert presentation additions; leave evidence bundles intact.

## Task 5 — Operational readiness and handoff

- **Purpose:** Establish a controlled recurring workflow only if approved.
- **Files:** Operator documentation and focused tests/fixtures only. No deployment or scheduling without separate authorization.
- **Dependencies:** Tasks 1–4 are implemented. Named operator/storage owner remains a production-readiness action; no schedule is enabled.
- **Tests:** Offline end-to-end fake-provider run, rerun/idempotency, failure report/recovery; relevant non-live tests for touched files.
- **Acceptance:** Operator can run, inspect, and safely rerun; partial coverage and provider delays are visible; no implicit substitutions or undocumented manual edits.
- **Rollback:** Stop new workflow and preserve generated evidence; revert task-sized changes without deleting data.

## Cross-task constraints

- Do not select a canonical Model B by inference.
- Do not edit src/scoring/engine.py, src/scoring/opportunity_scorer_b.py, scoring methodology/rules, or weights under this plan.
- Do not change src/data/trade_pipeline.py behavior or provenance fields as part of MIE; propose separate reviewed work if needed.
- Do not install dependencies, make live provider calls, delete files, stage, commit, or push without explicit approval.
- Preserve existing modifications and untracked work, including the Comtrade adapter and PoC edits, .agents/, website, audit report, lock file, and src/data/trade_pipeline.py.bak.

## Suggested first implementation task for later

Implemented artifacts live in `src/data/mie/` and `tests/test_mie.py`. Operational limits and remaining production readiness are documented in `MIE_OPERATIONS.md`.
