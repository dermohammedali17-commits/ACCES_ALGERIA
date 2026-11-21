"""Unit tests for P08 Opportunity Prioritization Engine."""

from __future__ import annotations

import pytest

from src.prioritization.prioritizer import (
    PrioritizationEngine,
    PriorityClassification,
)


def test_prioritize_high_priority() -> None:
    record = PrioritizationEngine.prioritize_opportunity(
        opportunity_id="OPP-ASTON-01",
        prioritization_id="PRI-001",
        score=85.0,
        data_quality_score=90.0,
        evidence_verified=True,
        has_conflicts=False,
    )
    assert record.priority == PriorityClassification.HIGH_PRIORITY
    assert "High opportunity score" in record.explanation


def test_prioritize_requires_evidence_due_to_conflicts() -> None:
    record = PrioritizationEngine.prioritize_opportunity(
        opportunity_id="OPP-LAMBO-02",
        prioritization_id="PRI-002",
        score=82.0,
        data_quality_score=85.0,
        evidence_verified=True,
        has_conflicts=True,  # Conflicts override high score
    )
    assert record.priority == PriorityClassification.REQUIRES_FURTHER_EVIDENCE
    assert "unresolved evidence conflicts" in record.explanation


def test_prioritize_manual_override() -> None:
    record = PrioritizationEngine.prioritize_opportunity(
        opportunity_id="OPP-MCLAREN-03",
        prioritization_id="PRI-003",
        score=45.0,
        data_quality_score=70.0,
        evidence_verified=False,
        has_conflicts=False,
        manual_override=PriorityClassification.UNDER_REVIEW,
    )
    assert record.priority == PriorityClassification.UNDER_REVIEW
    assert "governance manual override" in record.explanation
