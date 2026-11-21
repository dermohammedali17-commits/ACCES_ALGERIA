from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.data.mie.engine import MarketIntelligenceEngine
from src.data.quality_engine import evaluate_evidence_bundle
from src.scoring.p04_engine import (
    P04Opportunity,
    evaluate_opportunity,
)
from src.services.decision_models import (
    DecisionReadiness,
    EngineExecutionRecord,
    EngineStatus,
    ExecutiveDecisionPackage,
    IntelligenceClassification,
    IntelligenceFinding,
)

QualityEvaluator = Callable[..., Any]
P04Evaluator = Callable[[P04Opportunity], Any]


class DecisionOrchestrator:
    """
    Coordinates the core Access Algeria decision workflow.

    MIE -> P06 -> P04 -> Executive Decision Package

    P04 remains the sole opportunity scoring authority.
    """

    REQUIRED_ENGINES = ("MIE", "P06", "P04")

    def __init__(
        self,
        *,
        mie: MarketIntelligenceEngine,
        quality_evaluator: QualityEvaluator = evaluate_evidence_bundle,
        p04_evaluator: P04Evaluator = evaluate_opportunity,
    ) -> None:
        self._mie = mie
        self._quality_evaluator = quality_evaluator
        self._p04_evaluator = p04_evaluator

    @staticmethod
    def _serialize(value: Any) -> dict[str, Any]:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")

        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")

        raise TypeError(f"Unsupported result type: {type(value).__name__}")

    @staticmethod
    def _quality_status(report: Any) -> str:
        status = report.status
        return status.value if hasattr(status, "value") else str(status)

    @staticmethod
    def _mie_status(retrievals: Any) -> tuple[EngineStatus, str]:
        if not retrievals:
            return (
                EngineStatus.FAILED,
                "MIE returned no retrieval records; collection cannot be verified.",
            )

        statuses = [
            (
                item.status.value if hasattr(item.status, "value") else str(item.status)
            ).upper()
            for item in retrievals
        ]

        if all(status == "SUCCESS" for status in statuses):
            return (
                EngineStatus.COMPLETED,
                "All MIE retrieval operations completed successfully.",
            )

        if all(status == "FAILED" for status in statuses):
            return (
                EngineStatus.FAILED,
                "All MIE retrieval operations failed.",
            )

        if any(status in {"SUCCESS", "PARTIAL"} for status in statuses):
            return (
                EngineStatus.PARTIAL,
                "MIE collection was incomplete; one or more retrievals "
                "were partial or unsuccessful.",
            )

        return (
            EngineStatus.PARTIAL,
            "MIE retrievals produced no fully verified collection; "
            "review NO_DATA, UNCONFIRMED_EMPTY, and PENDING_VALIDATION results.",
        )
        status = report.status
        return status.value if hasattr(status, "value") else str(status)

    def execute(
        self,
        *,
        opportunity: P04Opportunity,
        start_year: int,
        end_year: int,
        reference_time: datetime | None = None,
    ) -> ExecutiveDecisionPackage:
        if start_year > end_year:
            raise ValueError("start_year cannot exceed end_year")

        executions: list[EngineExecutionRecord] = []
        findings: list[IntelligenceFinding] = []
        missing_information: list[str] = []
        blockers: list[str] = []

        mie_summary: dict[str, Any] | None = None
        p04_decision: dict[str, Any] | None = None

        evidence_bundle = None
        quality_report = None

        # -------------------------------------------------
        # 1. MARKET INTELLIGENCE ENGINE
        # -------------------------------------------------

        try:
            evidence_bundle = self._mie.collect(
                start_year=start_year,
                end_year=end_year,
            )

            observations = evidence_bundle.observations
            retrievals = evidence_bundle.retrievals

            mie_summary = {
                "bundle_id": evidence_bundle.bundle_id,
                "schema_version": evidence_bundle.schema_version,
                "observation_count": len(observations),
                "retrieval_count": len(retrievals),
                "retrieval_statuses": [
                    (
                        item.status.value
                        if hasattr(item.status, "value")
                        else str(item.status)
                    )
                    for item in retrievals
                ],
            }

            mie_status, mie_reason = self._mie_status(retrievals)

            executions.append(
                EngineExecutionRecord(
                    engine_name="MIE",
                    status=mie_status,
                    reason=mie_reason,
                    output_reference=evidence_bundle.bundle_id,
                )
            )

            if mie_status != EngineStatus.COMPLETED:
                missing_information.append(
                    "MIE collection is incomplete or could not be verified. "
                    "Review retrieval statuses before relying on market evidence."
                )

                findings.append(
                    IntelligenceFinding(
                        finding_id="MIE-INCOMPLETE-COLLECTION",
                        classification=IntelligenceClassification.MISSING_DATA,
                        description=mie_reason,
                    )
                )

        except Exception as exc:  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001 as exc:  # noqa: BLE001 as exc:  # noqa: BLE001 as exc:  # noqa: BLE001 as exc:
            executions.append(
                EngineExecutionRecord(
                    engine_name="MIE",
                    status=EngineStatus.FAILED,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            )

            missing_information.append(
                "Market Intelligence evidence collection failed."
            )

            executions.extend(
                [
                    EngineExecutionRecord(
                        engine_name="P06",
                        status=EngineStatus.NOT_RUN,
                        reason="MIE did not produce an evidence bundle.",
                    ),
                    EngineExecutionRecord(
                        engine_name="P04",
                        status=EngineStatus.NOT_RUN,
                        reason="Evidence collection failed.",
                    ),
                ]
            )

            return ExecutiveDecisionPackage(
                opportunity_id=opportunity.opportunity_id,
                opportunity_name=opportunity.name,
                required_engines=list(self.REQUIRED_ENGINES),
                engine_executions=executions,
                findings=findings,
                missing_information=missing_information,
                critical_blockers=blockers,
                mie_evidence_summary=mie_summary,
                recommended_next_action=("INVESTIGATE_MIE_FAILURE_AND_RETRY"),
            )

        # -------------------------------------------------
        # 2. DATA QUALITY ENGINE
        # -------------------------------------------------

        try:
            quality_report = self._quality_evaluator(
                evidence_bundle,
                reference_time=reference_time,
            )

            quality_status = self._quality_status(quality_report)

            mie_summary["quality_report"] = self._serialize(quality_report)

            if quality_status == "QUARANTINE":
                executions.append(
                    EngineExecutionRecord(
                        engine_name="P06",
                        status=EngineStatus.COMPLETED,
                        reason=(
                            "Quality evaluation completed; evidence bundle quarantined."
                        ),
                    )
                )

                findings.append(
                    IntelligenceFinding(
                        finding_id="P06-QUARANTINE",
                        classification=(IntelligenceClassification.MISSING_DATA),
                        description=(
                            "P06 quarantined the evidence bundle. "
                            "P04 evaluation was not executed."
                        ),
                    )
                )

                blockers.append(
                    "Evidence quality quarantine prevents downstream P04 evaluation."
                )

                executions.append(
                    EngineExecutionRecord(
                        engine_name="P04",
                        status=EngineStatus.NOT_RUN,
                        reason="P06 returned QUARANTINE.",
                    )
                )

                return ExecutiveDecisionPackage(
                    opportunity_id=opportunity.opportunity_id,
                    opportunity_name=opportunity.name,
                    required_engines=list(self.REQUIRED_ENGINES),
                    engine_executions=executions,
                    findings=findings,
                    missing_information=missing_information,
                    critical_blockers=blockers,
                    mie_evidence_summary=mie_summary,
                    recommended_next_action=(
                        "REVIEW_QUARANTINED_EVIDENCE_AND_RESOLVE_QUALITY_ISSUES"
                    ),
                )

            if quality_status not in ("PASS", "PASS_WITH_WARNINGS"):
                raise ValueError(f"Unsupported P06 status: {quality_status}")

            executions.append(
                EngineExecutionRecord(
                    engine_name="P06",
                    status=(
                        EngineStatus.PARTIAL
                        if quality_status == "PASS_WITH_WARNINGS"
                        else EngineStatus.COMPLETED
                    ),
                    reason=f"P06 status: {quality_status}",
                )
            )

            if quality_status == "PASS_WITH_WARNINGS":
                findings.append(
                    IntelligenceFinding(
                        finding_id="P06-WARNINGS",
                        classification=(IntelligenceClassification.UNVERIFIED),
                        description=(
                            "P06 completed with warnings. "
                            "Review quality issues before relying on the evidence."
                        ),
                    )
                )

        except Exception as exc:  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001 as exc:  # noqa: BLE001 as exc:  # noqa: BLE001 as exc:
            executions.append(
                EngineExecutionRecord(
                    engine_name="P06",
                    status=EngineStatus.FAILED,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            )

            missing_information.append("Evidence quality assessment failed.")

            executions.append(
                EngineExecutionRecord(
                    engine_name="P04",
                    status=EngineStatus.NOT_RUN,
                    reason="P06 assessment failed.",
                )
            )

            return ExecutiveDecisionPackage(
                opportunity_id=opportunity.opportunity_id,
                opportunity_name=opportunity.name,
                required_engines=list(self.REQUIRED_ENGINES),
                engine_executions=executions,
                findings=findings,
                missing_information=missing_information,
                critical_blockers=blockers,
                mie_evidence_summary=mie_summary,
                recommended_next_action=("INVESTIGATE_P06_FAILURE"),
            )

        # -------------------------------------------------
        # 3. P04 MODEL B
        # -------------------------------------------------

        try:
            decision = self._p04_evaluator(opportunity)
            p04_decision = self._serialize(decision)

            state = (
                decision.state.value
                if hasattr(decision.state, "value")
                else str(decision.state)
            )

            executions.append(
                EngineExecutionRecord(
                    engine_name="P04",
                    status=EngineStatus.COMPLETED,
                    reason=f"P04 evaluation state: {state}",
                    output_reference=opportunity.opportunity_id,
                )
            )

            if state == "INELIGIBLE":
                blockers.append("P04 determined the opportunity to be INELIGIBLE.")

            elif state == "REVIEW_REQUIRED":
                missing_information.append(
                    "P04 requires additional evidence or gate resolution."
                )

            elif state == "CONDITIONALLY_ELIGIBLE":
                missing_information.extend(decision.conditions_to_resolve)

            if getattr(decision, "quarantine_record", None) is not None:
                findings.append(
                    IntelligenceFinding(
                        finding_id="P04-QUARANTINE",
                        classification=(IntelligenceClassification.ASSESSMENT),
                        description=(
                            "P04 produced a quarantine record. "
                            "Review its policy and audit details."
                        ),
                    )
                )

        except Exception as exc:  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001  # noqa: BLE001 as exc:  # noqa: BLE001 as exc:  # noqa: BLE001 as exc:
            executions.append(
                EngineExecutionRecord(
                    engine_name="P04",
                    status=EngineStatus.FAILED,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            )

            missing_information.append("P04 opportunity assessment failed.")

        # -------------------------------------------------
        # 4. EXECUTIVE DECISION PACKAGE
        # -------------------------------------------------

        package = ExecutiveDecisionPackage(
            opportunity_id=opportunity.opportunity_id,
            opportunity_name=opportunity.name,
            required_engines=list(self.REQUIRED_ENGINES),
            engine_executions=executions,
            findings=findings,
            missing_information=missing_information,
            critical_blockers=blockers,
            p04_decision=p04_decision,
            mie_evidence_summary=mie_summary,
            recommended_next_action=(
                "PROCEED_TO_HUMAN_REVIEW"
                if p04_decision
                and p04_decision.get("state") == "ELIGIBLE"
                and all(item.status == EngineStatus.COMPLETED for item in executions)
                else "RESOLVE_OUTSTANDING_ISSUES_BEFORE_HUMAN_REVIEW"
            ),
        )

        return package
