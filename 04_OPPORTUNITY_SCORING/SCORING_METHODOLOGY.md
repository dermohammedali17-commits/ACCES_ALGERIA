# ACCESS ALGERIA
# OPPORTUNITY SCORING METHODOLOGY

> A weighted framework for evaluating market-entry opportunities.

---

# 1. SCORING SCALE

Each dimension is scored from:

0 to 10

Where:

0 = No evidence / extremely weak

5 = Moderate

10 = Exceptional

---

# 2. WEIGHTED DIMENSIONS

## A. MARKET ATTRACTIVENESS — 20%

Evaluate:

- Market size
- Growth
- Demand
- Customer potential
- Strategic market conditions

---

## B. BRAND-MARKET FIT — 15%

Evaluate:

- Brand relevance
- Product-market fit
- Positioning
- Customer alignment

---

## C. DEMAND POTENTIAL — 15%

Evaluate:

- Target customer availability
- Purchasing power
- Evidence of demand
- Unmet demand

---

## D. COMPETITIVE GAP — 15%

Evaluate:

- Existing competitors
- Market saturation
- Market gaps
- Differentiation potential

---

## E. REGULATORY FEASIBILITY — 10%

Evaluate:

- Entry requirements
- Regulatory complexity
- Licensing
- Import conditions
- Compliance requirements

---

## F. ENTRY COMPLEXITY — 10%

Evaluate:

- Capital requirements
- Operational complexity
- Time required
- Infrastructure needs

Score this dimension inversely: greater entry difficulty reduces the score. Do not penalize the same condition twice as both a gate failure and a dimension penalty. A gate asks whether a path is admissible; this dimension rates the burden of an admissible path.

---

## G. PARTNER AVAILABILITY — 5%

Evaluate:

- Availability of qualified local partners
- Strategic fit
- Financial capacity
- Operational capability

---

## H. ECONOMIC POTENTIAL — 5%

Evaluate:

- Revenue potential
- Investment potential
- Long-term commercial value

---

## I. STRATEGIC TIMING — 5%

Evaluate:

- Market timing
- Brand expansion timing
- Regulatory timing
- Competitive timing

---

# 3. WEIGHTED SCORE

The overall score is calculated as:

Dimension Score × Weight

The final score is normalized to:

0–100

When dimensions are missing, report `score` as the conservative lower bound
(missing values contribute no points) and `score_max` as the optimistic upper
bound (missing values could contribute their maximum). The missing value is
not a factual zero. The priority band is calculated from the lower bound; when
coverage is incomplete, it is a provisional screening label only.

---

# 4. PRIORITY CLASSIFICATION

## A — 85–100

Exceptional opportunity.

Immediate strategic attention.

---

## B — 70–84

Strong opportunity.

Requires structured validation and prioritization.

---

## C — 55–69

Potential opportunity.

Further research required.

---

## WATCHLIST — 40–54

Monitor but do not allocate significant resources.

---

## LOW PRIORITY — 0–39

Insufficient strategic attractiveness under current conditions.

---

# 5. CONFIDENCE LEVEL

Each score should also receive:

HIGH
MEDIUM
LOW

Confidence reflects the quality and completeness of the evidence behind the score.

---

# 6. ELIGIBILITY GATES

Eligibility is evaluated before weighted scoring. The P04 gate catalogue is defined in `SCORING_RULES.md` and implemented in `src/scoring/p04_engine.py`. Gate outcomes must be supported by evidence; the software does not make legal determinations or infer a gate from a score.

- Any evidenced `FAIL` makes the opportunity `INELIGIBLE`; it is not scored and is returned with a policy-quarantine record.
- Any `UNKNOWN` makes the opportunity `REVIEW_REQUIRED`; it is not scored until the missing determination is resolved.
- If every gate passes, the opportunity is `ELIGIBLE`.
- If there are no failures or unknowns and one or more gates are conditional, it is `CONDITIONALLY_ELIGIBLE`; it may be scored, with conditions surfaced.
- Structural input errors are isolated separately from policy ineligibility.

The gate evaluator requires every catalogue gate exactly once. A reviewer owns the factual gate determination and evidence references. `CONDITIONAL` requires explicit conditions; `PASS`, `FAIL`, and `CONDITIONAL` require evidence refs.

# 7. CORE RULE

A high score with low confidence should not be treated the same way as a high score supported by strong evidence.

---

# DOCUMENT CONTROL

**Document:** Scoring Methodology

**Version:** 2.0

**Status:** Active Framework

**Classification:** Internal

**System Owner:** Access Algeria
