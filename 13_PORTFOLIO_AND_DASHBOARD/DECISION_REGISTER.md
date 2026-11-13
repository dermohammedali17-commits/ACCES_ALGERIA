# ACCESS ALGERIA
# DECISION REGISTER

> Central record of significant strategic and operational decisions.

---

# 1. PURPOSE

The Decision Register records major decisions that influence Access Algeria strategy, projects, opportunities or execution.

---

# 2. DECISION RECORD

Each significant decision should include:

- Decision ID
- Date
- Decision
- Context
- Evidence
- Options Considered
- Decision Maker
- Rationale
- Consequence
- Next Action
- Review Date

---

# 3. DECISION STATUS

- PENDING
- APPROVED
- APPROVED WITH CONDITIONS
- REJECTED
- REVISIT REQUIRED
- CLOSED

---

# 4. DECISION REGISTER

| ID | Date | Decision | Project | Status | Review Date |
|---|---|---|---|---|---|
| DEC-001 | | | | | |
| DEC-002 | | | | | |
| DEC-003 | | | | | |
| DEC-P04-001 | 2026-11-11 | Canonical Model B, roadmap weights, evidence-backed eligibility gates, and separate validation/policy quarantine | ACCESS ALGERIA P04 | APPROVED | 2027-11-11 |

---

# 5. DECISION REVIEW

## ACCESS ALGERIA P04 — Strategic Opportunity Scoring Engine

**Decision ID:** DEC-P04-001  
**Decision date:** 2026-11-11  
**Decision maker:** Founder / Access Algeria System Owner (instruction in this task)  
**Status:** APPROVED  
**Review date:** 2027-11-11

**Decision:** Model B is the single canonical P04 model: nine named dimensions scored 0–10, fixed weights of `20/15/15/15/10/10/5/5/5` in dimension order, normalized to 0–100. Missing dimensions remain missing and are reported using score lower/upper bounds; evidence confidence remains independent of score magnitude. P04 v1 confidence reliability values are HIGH=1.0, MEDIUM=0.6, LOW=0.3; more than 25% missing weight forces LOW, otherwise HIGH starts at 0.75 and MEDIUM at 0.50.

**Eligibility:** Require exactly one evidence-backed determination for each policy gate: `legal_admissibility`, `market_authorization_path`, and `restricted_party_clearance`. `FAIL` yields `INELIGIBLE`, blocks scoring, and creates a policy-quarantine record. `UNKNOWN` yields `REVIEW_REQUIRED` and blocks scoring. If there are no failures or unknowns, any `CONDITIONAL` yields `CONDITIONALLY_ELIGIBLE` and may be scored with the conditions carried forward; all `PASS` yields `ELIGIBLE`. Structural validation failures are isolated separately. The system records reviewer determinations and does not itself decide legal admissibility or perform restricted-party screening.

**Context and evidence:** The P04 roadmap specifies the canonical weight vector. The repository methodology, named scorer, compatibility scorer, and README previously disagreed. The master methodology already establishes staged decision gates and explicitly permits pause, research, watchlist, and stop outcomes. Existing code supports evidence-aware named Model B scoring but did not implement P04 eligibility or decision packages.

**Options considered:** Retain the older repository weights; select the roadmap vector; keep parallel canonical models. Select sector-specific hard-coded eligibility thresholds; or implement evidence-backed review outcomes without inventing legal facts or commercial thresholds.

**Rationale:** The roadmap is the P04 authority. Fixed weights protect comparability. Gates test admissibility and authorization path; regulatory-feasibility scoring rates the burden of an admissible path. Separating those roles prevents the same issue from being counted twice. Unknown facts require review, not a fabricated pass or failure.

**Consequence:** P04 uses the roadmap vector throughout. New integrations use `src/scoring/p04_engine.py`; legacy scorer classes remain for compatibility only. Policy ineligibility and malformed input are recorded as separate quarantine types. No final business decision is automated from the score alone.

**Next action:** Use the P04 JSON CLI for local assessments. Add a web/API interface only when ACCESS ALGERIA has a real assessment application and service backend. No legal conclusions are embedded in code.

## ACCESS ALGERIA Task 03 — Market Intelligence Engine

| ID | Decision | Status | Review Date |
|---|---|---|---|
| DEC-MIE-001 | Nine dimensions rated 0–10 as future Model B reference; no scorer integration or changes to weights/methodology | APPROVED | 2027-02-04 |
| DEC-MIE-002 | Pilot uses HS 8703/8704; direct Algeria imports and mirror exports remain separate and are never added or substituted | APPROVED | 2027-02-04 |
| DEC-MIE-003 | Weighted mean tariff is PENDING_VALIDATION and excluded from conclusions pending geography, definition and scope verification | APPROVED WITH CONDITIONS | 2027-02-04 |
| DEC-MIE-004 | Normalized data 24 months; bundles/manifests 5 years; raw transient by default; quarterly WB/Comtrade refresh; existing cache unchanged | APPROVED | 2027-02-04 |
| DEC-MIE-005 | Founder / Access Algeria System Owner holds accountability for MIE data and archive custody; may delegate storage tasks to repository maintainer | APPROVED | 2027-02-04 |

**Decision maker:** Founder (decisions supplied in Task 03 handoff).
**Evidence:** Existing World Bank and Comtrade adapters and repository reliability notes.
**Options considered:** Broad HS 87; combined direct/mirror series; unvalidated tariff conclusions; persistent raw API payloads.
**Rationale:** Vehicle-specific data must preserve reporter distinctions; the tariff proxy's scope is not verified; retention and refresh are bounded by the handoff.
**Consequence:** MIE provides evidence without scoring, retains provenance/coverage, defaults raw payloads to transient, and leaves existing cache behavior unchanged.
**Next action:** Confirm archive access/backup before the first recurring run; validate tariff metadata before conclusions use it.
**Review date:** 2027-02-04.

A decision should be reconsidered when:

- New evidence appears
- A critical assumption changes
- Regulations change
- Market conditions change
- Execution becomes materially different from expectations

---

# 6. CORE PRINCIPLE

Decisions should be documented so that Access Algeria can understand not only what was decided, but why it was decided.

---

# DOCUMENT CONTROL

**Document:** Decision Register

**Version:** 1.0

**Status:** Active

**Classification:** Internal

**System Owner:** Access Algeria
