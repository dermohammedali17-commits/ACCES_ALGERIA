# ACCESS ALGERIA — P04 Decision and Implementation

**Decision:** DEC-P04-001, approved by the Founder / System Owner on 2026-11-11.  
**Scoring model:** Model B, fixed 0–10 dimensions, normalized to 0–100.  
**Policy version:** 1.0.0.

## Canonical weights

| Dimension | Weight |
|---|---:|
| Market attractiveness | 20% |
| Brand-market fit | 15% |
| Demand potential | 15% |
| Competitive gap | 15% |
| Regulatory feasibility | 10% |
| Entry complexity | 10% |
| Partner availability | 5% |
| Economic potential | 5% |
| Strategic timing | 5% |
| **Total** | **100%** |

The P04 roadmap is authoritative for these weights. The older methodology
vector was replaced. Legacy scorer classes remain for compatibility and are
not inputs to new P04 workflows.

## Eligibility policy

P04 requires exactly one reviewer determination, reviewer identity, a
timezone-aware assessment timestamp, rationale, and appropriate evidence
reference for each gate:

1. `legal_admissibility`
2. `market_authorization_path`
3. `restricted_party_clearance`

`FAIL` → `INELIGIBLE`, do not score, return policy-quarantine record.  
`UNKNOWN` → `REVIEW_REQUIRED`, do not score.  
`CONDITIONAL` with no failures or unknowns → `CONDITIONALLY_ELIGIBLE`, score
and preserve conditions.  
All `PASS` → `ELIGIBLE`.

Failure takes precedence over unknown; unknown takes precedence over
conditional. Structural input errors produce a separate
`STRUCTURAL_VALIDATION_FAILURE` quarantine record. The system stores reviewer
determinations; it does not determine what law says or perform screening.
Eligibility is a path-admissibility question. The regulatory-feasibility score
rates the burden of an admissible path, avoiding double penalties.

## Implemented components

| Component | Implementation |
|---|---|
| Fixed Model B scorer | `src/scoring/opportunity_scorer_b.py` |
| Gate validation and precedence | `src/scoring/p04_engine.py` |
| Evidence and score explanations | Versioned `DecisionPackage`, including per-dimension source refs, rationale, weight, contribution, bounds, confidence, and conditions |
| Quarantine contract | Typed records distinguish policy ineligibility from structural validation failures, retain failed-gate evidence refs, and do not retain the raw payload |
| Persistence boundary | `process_opportunity` appends quarantine records through `JsonlQuarantineStore` when the caller supplies a path; storage is opt-in |
| Local intake and output | `python -m src.scoring.cli` reads one JSON input and emits a decision package without overwriting an existing output |
| Governance and templates | Methodology, rules, scorecard, README, and Decision Register updated |

## Remaining integration boundary

P04 now has a local file-based workflow. The existing website is still the
default Vite starter rather than an assessment application, so there is no web
form or server endpoint to wire into. P04 does not automatically fetch
authoritative regulatory evidence, screen parties, assign scores from raw
data, or decide whether to pursue an opportunity. Those actions require
qualified review and a later product application/API integration.

Existing local repository changes were preserved. Automated tests were not
run in this implementation pass.
