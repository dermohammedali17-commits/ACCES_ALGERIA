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

P04 uses **Model B** as the sole canonical opportunity scoring model:

- Nine named dimensions scored from 0–10.
- Fixed roadmap weights in `SCORING_METHODOLOGY.md`; the total is shown on a
  0–100 scale.
- Missing dimensions remain visibly missing. The result shows a conservative
  lower bound and an optimistic upper bound; neither means missing evidence is
  a factual zero. Priority is based on the lower bound and is provisional when
  evidence is incomplete.
- Evidence reliability is recorded separately from score magnitude.
- Priority bands classify the score; they do not make a final business decision.

Use `src/scoring/p04_engine.py` to apply required eligibility gates, run the
scorer only for eligible or conditionally eligible opportunities, produce the
explanation package, and return policy rejections for quarantine. Structural
input failures are isolated separately. The append-only JSONL store is an
explicit persistence boundary; callers choose and configure its path.

`src/scoring/engine.py` retains older scorer classes only for compatibility.
Do not use them for new scoring or compare their outputs with P04 packages.

## Run a P04 assessment

Copy `P04_INPUT_TEMPLATE.json`, fill in the opportunity details, reviewer and
timezone-aware assessment timestamps, evidence-backed gate outcomes, and any
dimension scores with their reasons and source references. Then run from the
repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m src.scoring.cli .\path\to\opportunity.json `
  --output .\outputs\opportunity-decision.json `
  --quarantine .\data\quarantine\p04.jsonl
```

The CLI refuses to overwrite an existing decision file. Omit `--output` to
print the package to the terminal; omit `--quarantine` to receive quarantine
records without persisting them. `UNKNOWN` gates produce a review-required
package and do not score. A structural error is returned as a validation
quarantine record. Policy-ineligible packages include the quarantine record;
when a quarantine path is supplied, it is also appended to that JSONL file.

---

# DOCUMENT CONTROL

**Document:** Opportunity Scoring System

**Version:** 2.0

**Status:** Active Framework

**Classification:** Internal

**System Owner:** Access Algeria
