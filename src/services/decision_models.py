from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class EngineStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_RUN = "NOT_RUN"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class IntelligenceClassification(str, Enum):
    FACT = "FACT"
    VERIFIED_FACT = "VERIFIED_FACT"
    INTERPRETATION = "INTERPRETATION"
    ASSESSMENT = "ASSESSMENT"
    UNVERIFIED = "UNVERIFIED"
    MISSING_DATA = "MISSING_DATA"
    REGULATORY_BLOCKER = "REGULATORY_BLOCKER"


class DecisionReadiness(str, Enum):
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"


class EngineExecutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_name: str = Field(min_length=1)
    status: EngineStatus
    reason: str | None = None
    output_reference: str | None = None


class IntelligenceFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1)
    classification: IntelligenceClassification
    description: str = Field(min_length=1)
    source_references: tuple[str, ...] = ()
    confidence: str | None = None


class ExecutiveDecisionPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.2"

    opportunity_id: str = Field(min_length=1)
    opportunity_name: str = Field(min_length=1)

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    required_engines: list[str] = Field(default_factory=list)

    engine_executions: list[EngineExecutionRecord] = Field(default_factory=list)

    findings: list[IntelligenceFinding] = Field(default_factory=list)

    missing_information: list[str] = Field(default_factory=list)
    critical_blockers: list[str] = Field(default_factory=list)

    p04_decision: dict[str, Any] | None = None
    mie_evidence_summary: dict[str, Any] | None = None
    sector_assessment: dict[str, Any] | None = None

    partner_assessments: list[dict[str, Any]] = Field(default_factory=list)

    recommended_next_action: str | None = None

    @field_validator("generated_at")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_package_consistency(self):
        engine_names = [record.engine_name for record in self.engine_executions]

        if len(engine_names) != len(set(engine_names)):
            raise ValueError("Duplicate engine execution records")

        if len(self.required_engines) != len(set(self.required_engines)):
            raise ValueError("Duplicate required engine names")

        if not set(self.required_engines).issubset(set(engine_names)):
            raise ValueError("Every required engine must have an execution record")

        blocker_findings = [
            finding
            for finding in self.findings
            if finding.classification == IntelligenceClassification.REGULATORY_BLOCKER
        ]

        if blocker_findings and not self.critical_blockers:
            raise ValueError(
                "Regulatory blocker findings must be reflected in critical_blockers"
            )

        return self

    @property
    def decision_readiness(self) -> DecisionReadiness:
        if self.critical_blockers:
            return DecisionReadiness.BLOCKED

        p04_state = self.p04_decision.get("state") if self.p04_decision else None

        if p04_state == "INELIGIBLE":
            return DecisionReadiness.BLOCKED

        if not self.required_engines:
            return DecisionReadiness.INCOMPLETE

        execution_map = {
            record.engine_name: record.status for record in self.engine_executions
        }

        for engine_name in self.required_engines:
            if execution_map.get(engine_name) != EngineStatus.COMPLETED:
                return DecisionReadiness.INCOMPLETE

        if self.missing_information or self.p04_decision is None:
            return DecisionReadiness.INCOMPLETE

        if p04_state != "ELIGIBLE":
            return DecisionReadiness.INCOMPLETE

        return DecisionReadiness.READY_FOR_HUMAN_REVIEW
