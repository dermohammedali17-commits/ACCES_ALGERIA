# ACCESS ALGERIA
# OPPORTUNITY SCORING SYSTEM

> A structured decision-support system for evaluating market-entry opportunities.

---

# 1. PURPOSE

The Opportunity Scoring System helps Access Algeria compare potential market-entry opportunities using a consistent framework.

The system is designed to reduce subjective decision-making and prioritize opportunities according to strategic and commercial potential.

---

# 2. CORE QUESTION

The system answers:

> Which opportunities deserve the highest level of Access Algeria resources, research and strategic attention?

---

# 3. SCORING PROCESS

OPPORTUNITY
↓
ASSESS
↓
SCORE
↓
INTERPRET
↓
PRIORITIZE
↓
DECIDE

---

# 4. CORE PRINCIPLE

A high score does not automatically mean that an opportunity should be pursued.

The score is a decision-support tool.

Final decisions must also consider:

- Evidence
- Timing
- Strategic context
- Risk
- Resources
- Execution capability

---

# 5. SCORING OUTPUT

Each opportunity should receive:

- Overall Score
- Dimension Scores
- Confidence Level
- Strategic Priority
- Key Strengths
- Key Weaknesses
- Recommended Action

## Python implementation

`src/scoring/engine.py` exposes two explicit implementations:

- `OpportunityScorerA` follows the published methodology: dimension inputs are
  0–10, the documented weights are applied, and a complete result is returned
  on a 0–100 scale. The caller must provide an evidence-based confidence
  assessment; the scorer does not infer evidence quality from score values.
- `OpportunityScorerB` preserves the earlier 0–100 input model and its own
  weights for compatibility. Its confidence value measures dimension
  completeness only, so it must not be interpreted as evidence confidence.

Use Model A for comparisons governed by this document. Model B results are not
directly comparable with Model A results. Results carry a `model` field
(`A_PUBLISHED` or `B_LEGACY`) so downstream reports can preserve that
distinction.

---

# DOCUMENT CONTROL

**Document:** Opportunity Scoring System

**Version:** 1.0

**Status:** Active Framework

**Classification:** Internal

**System Owner:** Access Algeria
