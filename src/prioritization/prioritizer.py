"""P08 Opportunity Prioritization Engine for ACCESS ALGERIA.

Transforms evaluated and evidence-supported opportunities into explainable,
traceable, and operationally useful priority classifications.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PriorityClassification(str, Enum):
    HIGH_PRIORITY = "HIGH_PRIORITY"
    MEDIUM_PRIORITY = "MEDIUM_PRIORITY"
    LOW_PRIORITY = "LOW_PRIORITY"
    REQUIRES_FURTHER_EVIDENCE = "REQUIRES_FURTHER_EVIDENCE"
    MONITOR = "MONITOR"
    UNDER_REVIEW = "UNDER_REVIEW"


class PrioritizedOpportunityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_id: str = Field(min_length=1)
    prioritization_id: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=100.0)
    data_quality_score: float = Field(ge=0.0, le=100.0)
    evidence_verified: bool
    has_conflicts: bool
    priority: PriorityClassification
    explanation: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class PrioritizationEngine:
    """Engine for classifying and prioritizing investment opportunities."""

    @staticmethod
    def prioritize_opportunity(
        *,
        opportunity_id: str,
        prioritization_id: str,
        score: float,
        data_quality_score: float,
        evidence_verified: bool,
        has_conflicts: bool,
        manual_override: PriorityClassification | None = None,
    ) -> PrioritizedOpportunityRecord:
        if manual_override is not None:
            return PrioritizedOpportunityRecord(
                opportunity_id=opportunity_id,
                prioritization_id=prioritization_id,
                score=score,
                data_quality_score=data_quality_score,
                evidence_verified=evidence_verified,
                has_conflicts=has_conflicts,
                priority=manual_override,
                explanation=f"Priority assigned via governance manual override: {manual_override.value}.",
                recommended_action="Proceed according to approved governance review protocol.",
            )

        # Rule 1: Evidence gaps or conflicts override high numerical scores
        if has_conflicts or not evidence_verified:
            if score >= 70.0:
                priority = PriorityClassification.REQUIRES_FURTHER_EVIDENCE
                explanation = (
                    f"Opportunity score is strong ({score:.1f}), but unresolved "
                    "evidence conflicts or unverified status require additional intelligence."
                )
                recommended_action = "Initiate P07 evidence verification and conflict resolution review."
            else:
                priority = PriorityClassification.LOW_PRIORITY
                explanation = f"Low score ({score:.1f}) combined with evidence limitations."
                recommended_action = "Retain in portfolio registry without active allocation."
        elif data_quality_score < 60.0:
            priority = PriorityClassification.MONITOR
            explanation = f"Moderate score ({score:.1f}) limited by data quality score ({data_quality_score:.1f})."
            recommended_action = "Monitor data pipeline updates via P06 before operational deployment."
        elif score >= 80.0:
            priority = PriorityClassification.HIGH_PRIORITY
            explanation = f"High opportunity score ({score:.1f}) backed by verified evidence and solid data quality."
            recommended_action = "Advance to executive decision package and strategic partner outreach."
        elif score >= 50.0:
            priority = PriorityClassification.MEDIUM_PRIORITY
            explanation = f"Balanced opportunity score ({score:.1f}) with solid supporting fundamentals."
            recommended_action = "Schedule secondary review in upcoming operational cycle."
        else:
            priority = PriorityClassification.LOW_PRIORITY
            explanation = f"Opportunity score ({score:.1f}) falls below primary operational threshold."
            recommended_action = "Archive record for historical tracking."

        return PrioritizedOpportunityRecord(
            opportunity_id=opportunity_id,
            prioritization_id=prioritization_id,
            score=score,
            data_quality_score=data_quality_score,
            evidence_verified=evidence_verified,
            has_conflicts=has_conflicts,
            priority=priority,
            explanation=explanation,
            recommended_action=recommended_action,
        )
