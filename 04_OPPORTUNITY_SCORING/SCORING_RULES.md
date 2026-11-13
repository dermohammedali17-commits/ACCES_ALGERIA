# ACCESS ALGERIA
# OPPORTUNITY SCORING RULES

> Rules for maintaining consistency, transparency and comparability in opportunity scoring.

---

# 1. SCORE THE EVIDENCE, NOT THE EXCITEMENT

Scores must reflect available evidence, not personal enthusiasm toward a brand or project.

---

# 2. DO NOT INVENT PRECISION

If reliable information is unavailable, use:

- LOW CONFIDENCE
- Additional research required

Do not create artificial certainty.

---

# 3. DOCUMENT THE REASON

Every unusually high or low score should have a short explanation.

---

# 4. UPDATE SCORES WHEN CONDITIONS CHANGE

Scores may change when:

- Regulations change
- New competitors enter
- Demand changes
- A partner becomes available
- Brand strategy changes
- New evidence becomes available

---

# 5. SEPARATE FACTS FROM JUDGMENT

A score should be based on:

FACTS
↓
EVIDENCE
↓
ASSESSMENT
↓
SCORE

---

# 6. A SCORE IS NOT A DECISION

The scoring system supports decision-making.

It does not replace:

- Strategic judgment
- Due diligence
- Legal review
- Financial analysis
- Executive decision-making

---

# 7. SCORE COMPARABILITY

The same scoring methodology should be used when comparing opportunities within the same strategic category.

Major changes to the methodology must be documented.

---

# 8. REVIEW STANDARD

Priority opportunities should be reviewed when significant new information becomes available.

---

# 9. P04 ELIGIBILITY POLICY

The policy version is `1.0.0`. The required gates are:

| Gate ID | Question to resolve | Evidence expectation |
|---|---|---|
| `legal_admissibility` | Is the proposed activity legally admissible in the target market under the applicable current rules? | Current primary legal or regulator evidence, reviewed by a qualified person. |
| `market_authorization_path` | Is there a known authorization, import, licensing, or certification route for the offered product/service? | Current regulator or official process evidence; identify unresolved approvals as conditions. |
| `restricted_party_clearance` | Have relevant parties been screened against applicable restrictions, and is there a clear result? | Dated screening record and scope of parties checked. |

The system records reviewer determinations, reviewer identity, and a
timezone-aware assessment timestamp; it does not fetch law, interpret it, or
certify screening. Every gate must be supplied exactly once:

- `PASS` requires evidence and means the reviewer found no gate blocker.
- `CONDITIONAL` requires evidence plus specific conditions; it can proceed to
  scoring, but those conditions remain visible in the decision package.
- `FAIL` requires evidence and blocks scoring. The opportunity is marked
  `INELIGIBLE` and returned as a policy-quarantine record.
- `UNKNOWN` blocks scoring and yields `REVIEW_REQUIRED`; obtain evidence or
  qualified review before retrying.

`FAIL` takes precedence over `UNKNOWN`; both take precedence over
`CONDITIONAL`. All `PASS` outcomes yield `ELIGIBLE`. Structural schema errors
are returned as `STRUCTURAL_VALIDATION_FAILURE`, separate from policy outcomes.
Quarantine persistence is append-only JSONL when the caller passes a store
configured with an explicit path to `process_opportunity`. Without that store,
the typed quarantine record is returned in memory. Raw input is never written.

Eligibility asks whether a viable legal and authorization path can be pursued.
The regulatory-feasibility score dimension measures the burden and uncertainty
of that path; it does not repeat the pass/fail decision. No sector-specific
thresholds or legal conclusions are hard-coded.

Use `FAIL` only when current evidence affirmatively establishes a blocker or
that no viable route exists. A missing source, unresolved interpretation, or
uncompleted review is `UNKNOWN`, never `FAIL`. A known route that depends on a
specified approval or condition is `CONDITIONAL`.

For restricted-party clearance, the reviewer records the parties screened,
scope, screening date, result, and evidence reference. If a relevant party was
not screened or the result cannot be verified, use `UNKNOWN`; never infer
clearance from missing data.

## Confidence calculation

P04 v1 records evidence reliability as `HIGH = 1.0`, `MEDIUM = 0.6`, or
`LOW = 0.3`. The confidence index is the sum of each evidenced dimension's
reliability value multiplied by its fixed Model B weight. Missing dimensions
do not contribute to the index. If the missing dimensions account for more
than 25% of total weight, confidence is `LOW`; otherwise the index maps to
`HIGH` at 0.75 or above, `MEDIUM` at 0.50 or above, and `LOW` below 0.50.
Confidence is separate from score and priority and changes only through a
versioned methodology decision.

---

# DOCUMENT CONTROL

**Document:** Scoring Rules

**Version:** 2.0

**Status:** Active

**Classification:** Internal

**System Owner:** Access Algeria
