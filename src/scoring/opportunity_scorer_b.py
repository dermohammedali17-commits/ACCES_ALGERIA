"""ACCESS ALGERIA - Opportunity Scoring Model B (deterministic engine).

Source of truth for dimensions, weights and bands:
    04_OPPORTUNITY_SCORING/SCORING_METHODOLOGY.md   (v1.0)
    04_OPPORTUNITY_SCORING/SCORING_RULES.md         (v1.0)

Design rules (from the project blueprint):
  * Pure Python, no I/O, no LLM calls. Same input -> same output.
  * LLMs/agents may *propose* dimension inputs with evidence; they never set the total.
  * Missing evidence is never invented: it is reported as missing, and the confidence
    level is lowered accordingly ("do not invent precision").

NOTE - weights: the PDF blueprint lists the multiset 20/15/15/15/10/10/5/5/5 in a different
order than the repository methodology. This module follows the repository (A-I below).
Both sum to 100. Weights stay a parameter so the owner can lock them in explicitly.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Static framework definition
# ---------------------------------------------------------------------------

DIMENSIONS: tuple[str, ...] = (
    "market_attractiveness",   # A
    "brand_market_fit",        # B
    "demand_potential",        # C
    "competitive_gap",         # D
    "regulatory_feasibility",  # E
    "entry_complexity",        # F  (already inverted: harder entry => LOWER score)
    "partner_availability",    # G
    "economic_potential",      # H
    "strategic_timing",        # I
)

DEFAULT_WEIGHTS: Mapping[str, float] = {
    "market_attractiveness": 0.20,
    "brand_market_fit": 0.15,
    "demand_potential": 0.15,
    "competitive_gap": 0.10,
    "regulatory_feasibility": 0.15,
    "entry_complexity": 0.05,
    "partner_availability": 0.10,
    "economic_potential": 0.05,
    "strategic_timing": 0.05,
}

SCALE_MIN = 0.0
SCALE_MAX = 10.0


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Priority(str, Enum):
    A = "A"                    # 85-100 exceptional
    B = "B"                    # 70-84  strong
    C = "C"                    # 55-69  potential
    WATCHLIST = "WATCHLIST"    # 40-54
    LOW_PRIORITY = "LOW PRIORITY"  # 0-39


# Evidence reliability -> numeric reliability used for the confidence index.
# ASSUMPTION (flagged for owner approval): these cut-offs are engineering defaults,
# the methodology only defines the three labels, not the thresholds.
RELIABILITY_VALUE: Mapping[Confidence, float] = {
    Confidence.HIGH: 1.0,
    Confidence.MEDIUM: 0.6,
    Confidence.LOW: 0.3,
}
CONFIDENCE_HIGH_AT = 0.75
CONFIDENCE_MEDIUM_AT = 0.50
MISSING_WEIGHT_FORCES_LOW = 0.25  # if > 25% of total weight has no evidence -> LOW


# ---------------------------------------------------------------------------
# Input / output models
# ---------------------------------------------------------------------------


class DimensionInput(BaseModel):
    """One scored dimension. `score=None` means NO evidence (missing)."""

    score: Optional[float] = Field(default=None, description="0-10, or None if missing")
    reliability: Confidence = Field(
        default=Confidence.LOW, description="Quality of the evidence behind this score"
    )
    reason: str = Field(default="", description="Short justification (required for extremes)")
    sources: list[str] = Field(default_factory=list, description="Evidence references")

    @field_validator("score")
    @classmethod
    def _range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (SCALE_MIN <= v <= SCALE_MAX):
            raise ValueError(f"score must be between {SCALE_MIN} and {SCALE_MAX}, got {v}")
        return v


class OpportunityInput(BaseModel):
    name: str
    dimensions: dict[str, DimensionInput]

    @model_validator(mode="after")
    def _known_dimensions(self) -> "OpportunityInput":
        unknown = set(self.dimensions) - set(DIMENSIONS)
        if unknown:
            raise ValueError(f"unknown dimension(s): {sorted(unknown)}")
        return self


class ScoreResult(BaseModel):
    name: str
    score: float                 # missing dimensions counted as 0  (conservative lower bound)
    score_max: float             # missing dimensions counted as 10 (optimistic upper bound)
    priority: Priority           # based on `score`
    confidence: Confidence
    confidence_index: float
    coverage: float              # share of total weight that has evidence (0-1)
    missing: list[str]
    flags: list[str]
    breakdown: dict[str, float]  # weighted points per dimension (0-100 scale contribution)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def validate_weights(weights: Mapping[str, float]) -> None:
    if set(weights) != set(DIMENSIONS):
        raise ValueError("weights must define exactly the nine Model B dimensions")
    if any(w < 0 for w in weights.values()):
        raise ValueError("weights must be non-negative")
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"weights must sum to 1.0, got {total}")


def classify_priority(score: float) -> Priority:
    """Bands from SCORING_METHODOLOGY.md section 4 (lower bound inclusive)."""
    if score >= 85:
        return Priority.A
    if score >= 70:
        return Priority.B
    if score >= 55:
        return Priority.C
    if score >= 40:
        return Priority.WATCHLIST
    return Priority.LOW_PRIORITY


def _confidence_from_index(index: float, missing_weight: float) -> Confidence:
    if missing_weight > MISSING_WEIGHT_FORCES_LOW:
        return Confidence.LOW
    if index >= CONFIDENCE_HIGH_AT:
        return Confidence.HIGH
    if index >= CONFIDENCE_MEDIUM_AT:
        return Confidence.MEDIUM
    return Confidence.LOW


def score_opportunity(
    opportunity: OpportunityInput,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
) -> ScoreResult:
    """Compute the Model B score. Deterministic and side-effect free."""
    validate_weights(weights)

    points = 0.0          # 0-100 scale, missing = 0
    points_max = 0.0      # missing = 10
    conf_index = 0.0
    missing: list[str] = []
    breakdown: dict[str, float] = {}
    flags: list[str] = []

    for dim in DIMENSIONS:
        w = weights[dim]
        item = opportunity.dimensions.get(dim)
        if item is None or item.score is None:
            missing.append(dim)
            breakdown[dim] = 0.0
            points_max += w * SCALE_MAX * 10
            continue
        contribution = item.score * w * 10  # score(0-10) * weight(0-1) * 10 -> 0-100 scale
        breakdown[dim] = round(contribution, 4)
        points += contribution
        points_max += contribution
        conf_index += w * RELIABILITY_VALUE[item.reliability]
        # Rule 3: document the reason for unusually high/low scores
        if (item.score >= 9 or item.score <= 1) and not item.reason.strip():
            flags.append(f"REASON_REQUIRED:{dim}")

    missing_weight = sum(weights[d] for d in missing)
    coverage = 1.0 - missing_weight
    confidence = _confidence_from_index(conf_index, missing_weight)
    score = round(points, 2)
    priority = classify_priority(score)

    if missing:
        flags.append("INCOMPLETE_EVIDENCE")
    # Core rule: a high score with low confidence must not be treated as a strong one.
    if priority in (Priority.A, Priority.B) and confidence == Confidence.LOW:
        flags.append("REQUIRES_VALIDATION")

    return ScoreResult(
        name=opportunity.name,
        score=score,
        score_max=round(points_max, 2),
        priority=priority,
        confidence=confidence,
        confidence_index=round(conf_index, 4),
        coverage=round(coverage, 4),
        missing=missing,
        flags=flags,
        breakdown=breakdown,
    )


def score_from_dict(name: str, scores: Mapping[str, Optional[float]],
                    reliability: Confidence = Confidence.MEDIUM) -> ScoreResult:
    """Convenience: build an opportunity from a plain {dimension: 0-10 or None} mapping."""
    dims = {d: DimensionInput(score=s, reliability=reliability) for d, s in scores.items()}
    return score_opportunity(OpportunityInput(name=name, dimensions=dims))
