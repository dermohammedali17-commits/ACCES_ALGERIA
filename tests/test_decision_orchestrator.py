from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.scoring.p04_engine import (
    GateAssessment,
    GateDecision,
    GateId,
    P04Opportunity,
    evaluate_opportunity,
)
from src.services.decision_models import DecisionReadiness, EngineStatus
from src.services.decision_orchestrator import DecisionOrchestrator


@pytest.fixture
def opportunity():
    assessed_at = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)

    gates = [
        GateAssessment(
            gate_id=gate_id,
            decision=GateDecision.UNKNOWN,
            assessed_by="test",
            assessed_at=assessed_at,
            rationale="Test fixture: regulatory evidence not supplied.",
            evidence_refs=[],
        )
        for gate_id in GateId
    ]

    return P04Opportunity(
        opportunity_id="TEST-001",
        name="Test Opportunity",
        assessed_by="test",
        assessed_at=assessed_at,
        gates=gates,
        dimensions={},
    )


@pytest.fixture
def evidence_bundle():
    return SimpleNamespace(
        bundle_id="test-bundle",
        schema_version="1.0",
        observations=(),
        retrievals=(
            SimpleNamespace(
                status="SUCCESS",
                requested_periods=("2020",),
                retrieved_periods=("2020",),
                missing_periods=(),
                record_count=1,
            ),
        ),
    )


def make_quality_report(status):
    return SimpleNamespace(
        status=status,
        model_dump=lambda **kwargs: {"status": status},
    )


def make_p04_decision(state):
    return SimpleNamespace(
        state=SimpleNamespace(value=state),
        conditions_to_resolve=[],
        quarantine_record=None,
        model_dump=lambda **kwargs: {"state": state},
    )


def test_successful_core_workflow(opportunity, evidence_bundle):
    mie = Mock()
    mie.collect.return_value = evidence_bundle

    quality = Mock(return_value=make_quality_report("PASS"))
    p04 = Mock(return_value=make_p04_decision("ELIGIBLE"))

    orchestrator = DecisionOrchestrator(
        mie=mie,
        quality_evaluator=quality,
        p04_evaluator=p04,
    )

    result = orchestrator.execute(
        opportunity=opportunity,
        start_year=2020,
        end_year=2025,
    )

    assert result.p04_decision["state"] == "ELIGIBLE"
    assert result.decision_readiness == DecisionReadiness.READY_FOR_HUMAN_REVIEW

    mie.collect.assert_called_once()
    quality.assert_called_once()
    p04.assert_called_once_with(opportunity)


def test_mie_failure_prevents_downstream_execution(opportunity):
    mie = Mock()
    mie.collect.side_effect = RuntimeError("MIE unavailable")

    quality = Mock()
    p04 = Mock()

    orchestrator = DecisionOrchestrator(
        mie=mie,
        quality_evaluator=quality,
        p04_evaluator=p04,
    )

    result = orchestrator.execute(
        opportunity=opportunity,
        start_year=2020,
        end_year=2025,
    )

    assert result.p04_decision is None
    assert result.decision_readiness == DecisionReadiness.INCOMPLETE

    quality.assert_not_called()
    p04.assert_not_called()


def test_p06_quarantine_prevents_p04(opportunity, evidence_bundle):
    mie = Mock()
    mie.collect.return_value = evidence_bundle

    quality = Mock(return_value=make_quality_report("QUARANTINE"))
    p04 = Mock()

    orchestrator = DecisionOrchestrator(
        mie=mie,
        quality_evaluator=quality,
        p04_evaluator=p04,
    )

    result = orchestrator.execute(
        opportunity=opportunity,
        start_year=2020,
        end_year=2025,
    )

    assert result.p04_decision is None
    assert result.critical_blockers
    p04.assert_not_called()


def test_p04_ineligible_blocks_package(opportunity, evidence_bundle):
    mie = Mock()
    mie.collect.return_value = evidence_bundle

    quality = Mock(return_value=make_quality_report("PASS"))
    p04 = Mock(return_value=make_p04_decision("INELIGIBLE"))

    orchestrator = DecisionOrchestrator(
        mie=mie,
        quality_evaluator=quality,
        p04_evaluator=p04,
    )

    result = orchestrator.execute(
        opportunity=opportunity,
        start_year=2020,
        end_year=2025,
    )

    assert result.decision_readiness == DecisionReadiness.BLOCKED


def test_p04_review_required_is_not_ready(opportunity, evidence_bundle):
    mie = Mock()
    mie.collect.return_value = evidence_bundle

    quality = Mock(return_value=make_quality_report("PASS"))
    p04 = Mock(return_value=make_p04_decision("REVIEW_REQUIRED"))

    orchestrator = DecisionOrchestrator(
        mie=mie,
        quality_evaluator=quality,
        p04_evaluator=p04,
    )

    result = orchestrator.execute(
        opportunity=opportunity,
        start_year=2020,
        end_year=2025,
    )

    assert result.decision_readiness == DecisionReadiness.INCOMPLETE


def test_invalid_year_range_raises(opportunity):
    orchestrator = DecisionOrchestrator(mie=Mock())

    with pytest.raises(ValueError):
        orchestrator.execute(
            opportunity=opportunity,
            start_year=2025,
            end_year=2020,
        )


def test_empty_required_engines_is_not_ready():
    from src.services.decision_models import ExecutiveDecisionPackage

    package = ExecutiveDecisionPackage(
        opportunity_id="TEST-001",
        opportunity_name="Test",
        p04_decision={"state": "ELIGIBLE"},
    )

    assert package.decision_readiness == DecisionReadiness.INCOMPLETE


def test_real_p04_unknown_gates_require_review(
    opportunity,
    evidence_bundle,
):
    mie = Mock()
    mie.collect.return_value = evidence_bundle

    quality = Mock(return_value=make_quality_report("PASS"))

    orchestrator = DecisionOrchestrator(
        mie=mie,
        quality_evaluator=quality,
        p04_evaluator=evaluate_opportunity,
    )

    result = orchestrator.execute(
        opportunity=opportunity,
        start_year=2020,
        end_year=2025,
    )

    assert result.p04_decision is not None
    assert result.p04_decision["state"] == "REVIEW_REQUIRED"
    assert result.decision_readiness == DecisionReadiness.INCOMPLETE
    assert result.p04_decision.get("score") is None

    assert any(
        "additional evidence" in item.lower() or "gate resolution" in item.lower()
        for item in result.missing_information
    )


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["SUCCESS", "SUCCESS"], EngineStatus.COMPLETED),
        (["SUCCESS", "FAILED"], EngineStatus.PARTIAL),
        (["FAILED", "FAILED"], EngineStatus.FAILED),
        ([], EngineStatus.FAILED),
    ],
)
def test_mie_status_classification(statuses, expected):
    retrievals = [SimpleNamespace(status=status) for status in statuses]

    actual, reason = DecisionOrchestrator._mie_status(retrievals)

    assert actual == expected
    assert isinstance(reason, str)
    assert reason.strip()


def test_mie_pending_validation_is_not_completed():
    retrievals = [
        SimpleNamespace(status="SUCCESS"),
        SimpleNamespace(status="PENDING_VALIDATION"),
    ]

    status, reason = DecisionOrchestrator._mie_status(retrievals)

    assert status == EngineStatus.PARTIAL
    assert "incomplete" in reason.lower() or "verified" in reason.lower()


def test_mie_unconfirmed_empty_is_not_completed():
    retrievals = [
        SimpleNamespace(status="UNCONFIRMED_EMPTY"),
    ]

    status, _ = DecisionOrchestrator._mie_status(retrievals)

    assert status == EngineStatus.PARTIAL


def test_partial_mie_prevents_ready_for_human_review(opportunity):
    partial_bundle = SimpleNamespace(
        bundle_id="partial-test-bundle",
        schema_version="1.0",
        observations=(),
        retrievals=(
            SimpleNamespace(
                status="SUCCESS",
                requested_periods=("2020", "2021"),
                retrieved_periods=("2020",),
                missing_periods=("2021",),
                record_count=1,
            ),
            SimpleNamespace(
                status="FAILED",
                requested_periods=("2020", "2021"),
                retrieved_periods=(),
                missing_periods=("2020", "2021"),
                record_count=0,
            ),
        ),
    )

    mie = Mock()
    mie.collect.return_value = partial_bundle

    quality = Mock(return_value=make_quality_report("PASS"))
    p04 = Mock(return_value=make_p04_decision("ELIGIBLE"))

    orchestrator = DecisionOrchestrator(
        mie=mie,
        quality_evaluator=quality,
        p04_evaluator=p04,
    )

    result = orchestrator.execute(
        opportunity=opportunity,
        start_year=2020,
        end_year=2021,
    )

    assert result.p04_decision["state"] == "ELIGIBLE"

    assert result.decision_readiness == DecisionReadiness.INCOMPLETE

    mie.collect.assert_called_once()
    quality.assert_called_once()
    p04.assert_called_once_with(opportunity)

    mie_execution = next(
        execution
        for execution in result.engine_executions
        if execution.engine_name == "MIE"
    )

    assert mie_execution.status == EngineStatus.PARTIAL

    assert any(
        "MIE collection is incomplete" in item for item in result.missing_information
    )
