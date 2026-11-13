# ACCESS ALGERIA — Scoring Model Governance Framework

**Framework ID:** GOV-P04-MODEL  
**Version:** 1.0.0  
**Status:** Active  
**Owner:** Founder / ACCESS ALGERIA System Owner  
**Applies to:** P04 Opportunity Scoring Model B, its eligibility policy, input schema, code, and generated decision packages.

## 1. Purpose and governing principles

This framework controls how P04 is approved, changed, executed, reviewed, and
audited. It protects comparability and evidence traceability while allowing
controlled improvements.

1. One canonical model is used for new opportunity assessments.
2. Model output supports decisions; it does not make the final investment,
   engagement, or market-entry decision.
3. No score or gate outcome may be represented as stronger than its evidence.
4. Every output identifies the model and policy versions that produced it.
5. A correction creates a new, linked record; it never overwrites history.

## 2. Model version control

### 2.1 Current governed release

| Item | Current value | Source of truth |
|---|---|---|
| Model | Model B, nine named dimensions, each 0–10 | `04_OPPORTUNITY_SCORING/SCORING_METHODOLOGY.md` |
| Model version | `1.0.0` | `SCORING_MODEL_VERSION` in `src/scoring/opportunity_scorer_b.py` |
| Weight vector | `20/15/15/15/10/10/5/5/5` in D1–D9 order | Immutable `DEFAULT_WEIGHTS` in the scorer |
| Eligibility policy | `1.0.0` | `P04_POLICY_VERSION` and gate definitions in `src/scoring/p04_engine.py` |
| Decision package schema | `1.0.0` | `DecisionPackage.schema_version` |
| Approval | `DEC-P04-001`, 2026-11-11 | `13_PORTFOLIO_AND_DASHBOARD/DECISION_REGISTER.md` |

The P04 roadmap is authoritative for the weight vector. The named Model B
scorer is the only approved scoring implementation for new work. Classes in
`src/scoring/engine.py` are compatibility code; they are not canonical P04
models and their outputs must not be mixed with Model B packages.

### 2.2 Versioning rules

Model and policy versions use `MAJOR.MINOR.PATCH` independently:

- **MAJOR:** Any change that can alter eligibility, score, confidence,
  priority, or interpretation for the same input. Examples: weights, dimensions,
  scale, formula, missing-data treatment, confidence thresholds, priority bands,
  gate catalogue, or gate precedence.
- **MINOR:** Backward-compatible additions to the decision-package schema or
  audit metadata that do not change eligibility or calculated results.
- **PATCH:** Documentation, typo, or internal refactoring changes proven to
  preserve all governed outputs.

If the effect on prior outputs is unknown, treat the change as MAJOR. The model
version identifies scoring behavior; the policy version identifies eligibility
behavior; the schema version identifies payload shape. Never reuse a version
for changed behavior.

Each release must update the model register above, the decision register,
methodology/rules, version constants, code, regression benchmarks, and release
notes together. Historical decision packages retain their original versions.

## 3. Scoring authority

| Role | Authority and responsibility |
|---|---|
| Founder / System Owner | Approves the model, weights, dimensions, confidence policy, priority bands, eligibility gates, and any behavior-changing release. Records approval in the Decision Register. |
| Model maintainer | Implements only approved changes; keeps code, docs, schema, and benchmarks aligned; prepares impact analysis and release notes. |
| Opportunity assessor | Supplies evidence-backed dimension ratings, rationales, source references, reliability labels, and assessment identity/time. Cannot alter weights or calculated totals. |
| Qualified legal / compliance reviewer | Determines legal, authorization-path, and restricted-party gate outcomes with dated evidence. The engine does not make these determinations. |
| AI or automated research assistant | May discover sources, organize evidence, and propose ratings or explanations. It cannot approve a gate, set a final score, change weights, or release a model. A human assessor owns submitted ratings. |
| Executive decision-maker | Makes the final proceed, pause, research, watchlist, engagement, or stop decision using the score alongside evidence, risk, resources, and strategy. |

The engine alone applies the approved formula and priority bands. No caller,
prompt, UI, spreadsheet, or API may supply replacement weights or override the
calculated score.

## 4. Change management

No behavior-changing model or policy edit is released directly from a research
proposal. Use this sequence:

1. **Submit a change request.** Record request ID, owner, problem, current and
   proposed behavior, evidence, affected versions, alternatives, and urgency.
2. **Analyze impact.** Recalculate a fixed benchmark set and a representative
   historical cohort under old and proposed versions. Report score deltas,
   rank changes, priority transitions, confidence changes, missing-data cases,
   and eligibility/quarantine transitions. Explain every material change.
3. **Review.** The model maintainer checks implementation and consistency. A
   qualified domain reviewer checks legal/policy changes. The System Owner
   decides and records approval or rejection in the Decision Register.
4. **Version and implement.** Assign the next model, policy, and/or schema
   version before changing runtime behavior. Update all source-of-truth docs,
   code constants, reference examples, and regression benchmarks in one change.
5. **Validate before release.** Confirm formula arithmetic, gate precedence,
   output contracts, deterministic behavior, version stamping, and quarantine
   handling. Keep old and new outputs side by side for approval; do not silently
   recalculate the live portfolio.
6. **Release prospectively.** The new version applies to assessments created
   after its effective date. Existing packages remain valid records under
   their recorded version.
7. **Reassess deliberately.** Re-score an existing opportunity only on request
   or when the approved review policy requires it. Link the new package to the
   package it supersedes and retain both.
8. **Rollback safely.** Restore the previous released version for new work if
   a defect is found. Do not delete, rewrite, or relabel packages produced by
   the defective version; issue corrected successor packages with an incident
   reference.

Pure documentation changes may use PATCH only when they do not change the
interpretation of a rule. Clarifying wording that changes assessor outcomes
requires a MAJOR policy version and approval.

## 5. Audit trail and record integrity

Every completed, review-required, or quarantined assessment must be traceable
to one immutable decision package or quarantine record. The audit record must
contain:

- Stable opportunity ID, assessment event ID, assessment owner, assessor and
  timezone-aware assessment/recorded timestamps.
- Model name/version, policy version, and decision-package schema version.
- A digest of the submitted input and a digest of the result; do not copy raw
  source documents or API payloads into the audit log.
- All nine dimension values or explicit missing values, rationales, evidence
  references, reliability labels, fixed weights, contributions, score bounds,
  coverage, confidence, priority, and flags.
- All gate decisions, reviewer identity/time, rationale, evidence references,
  conditions, and the resulting eligibility state.
- Quarantine type and reason codes, when applicable.
- Any later correction, superseding package ID, change request/incident ID,
  and reviewer/approver.

Audit records are append-only. Corrections append a new event with a link to the
prior event. The local JSONL audit store uses a chained event digest so edits,
deletions, and reordering can be detected during verification. The digest is
tamper-evident, not a substitute for access control, protected backups, or
separation of duties. Restrict write access to the designated operator and
retain backups under the approved repository records policy.

Quarantine is also append-only. Structural validation failure and policy
ineligibility remain distinct record types. Missing evidence is not stored as a
failed gate. Never place credentials or full raw input payloads in audit or
quarantine records.

## 6. Model consistency controls

The following controls are mandatory for every release:

1. **Single source of truth:** `DEFAULT_WEIGHTS` and
   `SCORING_MODEL_VERSION` define runtime model behavior. Decision packages
   receive the model version from that constant and include the fixed weight
   vector. No runtime weight override is permitted.
2. **Documentation parity:** The weight table, dimension order, scales,
   confidence policy, priority bands, gate catalogue, missing-data semantics,
   and version values agree across this framework, methodology, rules,
   scorecard, code, CLI template, and Decision Register.
3. **Arithmetic:** Weights sum to 1.0. Each contribution is
   `dimension score × weight × 10`; complete scores are 0–100. Missing values
   produce lower/upper bounds and never become asserted facts.
4. **Eligibility precedence:** A `FAIL` blocks scoring and is quarantined;
   `UNKNOWN` blocks scoring for review; `CONDITIONAL` may proceed only with no
   fail/unknown; all-pass is eligible. Required gates appear exactly once.
5. **Evidence separation:** Evidence reliability and coverage determine
   confidence independently from score magnitude. A high score with low
   confidence is flagged for validation.
6. **Determinism:** Identical validated inputs under the same model/policy
   versions produce identical calculated scores, bounds, confidence, and
   priority. Timestamps and event IDs are metadata and may differ.
7. **Compatibility boundary:** Legacy scorers are labeled and isolated. Their
   outputs cannot be compared with or substituted for governed Model B results.

The regression benchmark set must include all-zero, all-ten, hand-calculated
mixed values, each priority boundary, every missing-data pattern class,
confidence cutoffs, all gate outcomes and precedence combinations, malformed
input, and quarantine serialization. A release is blocked if any code,
methodology, template, or decision-register value disagrees.

## 7. Exceptions and review

No emergency exception may silently change weights or bypass eligibility
gates. If urgent manual judgment is required, preserve the governed package,
record the exception as a separate executive decision, identify the decision
owner and evidence, and state that the model result was overridden. Review this
framework annually and after any material scoring or eligibility incident.

## Document control

**Related approval:** `DEC-P04-001`  
**Related implementation:** `04_OPPORTUNITY_SCORING/SCORING_METHODOLOGY.md`,
`04_OPPORTUNITY_SCORING/SCORING_RULES.md`, `src/scoring/opportunity_scorer_b.py`,
`src/scoring/p04_engine.py`, and `src/scoring/cli.py`.
