"""P04 eligibility, scoring hand-off, explanation, and quarantine contracts.

This module evaluates submitted gate determinations. It does not decide what
Algerian law says; every determination must be made by a qualified reviewer and
supported by evidence. Scoring is deterministic; quarantine persistence is
explicit and opt-in.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from src.scoring.opportunity_scorer_b import (
    DEFAULT_WEIGHTS,
    DIMENSIONS,
    SCORING_MODEL_VERSION,
    DimensionInput,
    OpportunityInput,
    ScoreResult,
    score_opportunity,
)

P04_POLICY_VERSION = "1.0.0"


class GateId(str, Enum):
    LEGAL_ADMISSIBILITY = "legal_admissibility"
    MARKET_AUTHORIZATION_PATH = "market_authorization_path"
    RESTRICTED_PARTY_CLEARANCE = "restricted_party_clearance"


class GateDecision(str, Enum):
    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class EvaluationState(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    CONDITIONALLY_ELIGIBLE = "CONDITIONALLY_ELIGIBLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INELIGIBLE = "INELIGIBLE"


class QuarantineType(str, Enum):
    STRUCTURAL_VALIDATION_FAILURE = "STRUCTURAL_VALIDATION_FAILURE"
    POLICY_INELIGIBLE = "POLICY_INELIGIBLE"


class GateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_id: GateId
    decision: GateDecision
    assessed_by: str = Field(min_length=1, max_length=200)
    assessed_at: datetime
    rationale: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)

    @field_validator("rationale")
    @classmethod
    def rationale_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("gate rationale must not be blank")
        return value

    @field_validator("assessed_by")
    @classmethod
    def assessor_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("assessed_by must not be blank")
        return value

    @field_validator("assessed_at")
    @classmethod
    def assessment_time_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assessed_at must include a timezone")
        return value

    @field_validator("evidence_refs", "conditions")
    @classmethod
    def list_items_not_blank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("evidence refs and conditions must not contain blank values")
        return values

    @model_validator(mode="after")
    def evidence_and_conditions_match_decision(self) -> "GateAssessment":
        if self.decision in (GateDecision.PASS, GateDecision.FAIL, GateDecision.CONDITIONAL) and not self.evidence_refs:
            raise ValueError("PASS, FAIL, and CONDITIONAL gate decisions require evidence references")
        if self.decision == GateDecision.CONDITIONAL and not self.conditions:
            raise ValueError("CONDITIONAL gate decisions require explicit conditions")
        if self.decision != GateDecision.CONDITIONAL and self.conditions:
            raise ValueError("conditions may only be supplied for CONDITIONAL decisions")
        return self


class P04Opportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=300)
    assessed_by: str = Field(min_length=1, max_length=200)
    assessed_at: datetime
    gates: list[GateAssessment]
    dimensions: dict[str, DimensionInput] = Field(default_factory=dict)

    @field_validator("opportunity_id")
    @classmethod
    def stable_id_only(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("opportunity_id must not contain control characters")
        return value

    @field_validator("assessed_by")
    @classmethod
    def opportunity_assessor_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("assessed_by must not be blank")
        return value

    @field_validator("assessed_at")
    @classmethod
    def opportunity_assessment_time_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assessed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def required_gates_once(self) -> "P04Opportunity":
        received = [gate.gate_id for gate in self.gates]
        missing = set(GateId) - set(received)
        duplicates = {gate_id for gate_id in received if received.count(gate_id) > 1}
        if missing or duplicates:
            raise ValueError(
                f"gate set must include each required gate exactly once; missing={sorted(g.value for g in missing)}, "
                f"duplicates={sorted(g.value for g in duplicates)}"
            )
        unknown_dimensions = set(self.dimensions) - set(DIMENSIONS)
        if unknown_dimensions:
            raise ValueError(f"unknown dimensions: {sorted(unknown_dimensions)}")
        unsupported = [
            dimension
            for dimension, item in self.dimensions.items()
            if item.score is not None
            and (
                not item.reason.strip()
                or not item.sources
                or any(not source.strip() for source in item.sources)
            )
        ]
        if unsupported:
            raise ValueError(
                "scored dimensions require a rationale and evidence references: "
                f"{sorted(unsupported)}"
            )
        return self


class QuarantineRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: UUID = Field(default_factory=uuid4)
    schema_version: str = "1.0.0"
    policy_version: str = P04_POLICY_VERSION
    opportunity_id: str | None = None
    record_type: QuarantineType
    reason_codes: list[str]
    details: list[str]
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DecisionPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    policy_version: str = P04_POLICY_VERSION
    scoring_model: str = "MODEL_B"
    scoring_version: str = SCORING_MODEL_VERSION
    opportunity_id: str
    name: str
    assessed_by: str
    assessed_at: datetime
    state: EvaluationState
    gate_assessments: list[GateAssessment]
    score_result: ScoreResult | None = None
    fixed_weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    dimension_explanations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    highest_scoring_dimensions: list[str] = Field(default_factory=list)
    lowest_scoring_dimensions: list[str] = Field(default_factory=list)
    conditions_to_resolve: list[str] = Field(default_factory=list)
    next_action: str
    quarantine_record: QuarantineRecord | None = None


class P04AuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    opportunity_id: str | None = None
    assessed_by: str | None = None
    assessed_at: datetime | None = None
    scoring_model: str = "MODEL_B"
    scoring_version: str = SCORING_MODEL_VERSION
    policy_version: str = P04_POLICY_VERSION
    schema_version: str
    result_type: str
    input_sha256: str
    result_sha256: str
    result_payload: dict[str, Any]
    previous_hash: str | None = None
    event_hash: str = ""


class AuditWriter(Protocol):
    def append(self, input_payload: Any, result: DecisionPackage | QuarantineRecord) -> None: ...


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify_p04_audit_log(path: Path) -> tuple[int, str | None]:
    """Verify event hashes, result digests, and chain order; return count and head."""
    if not path.exists():
        return 0, None

    previous_hash: str | None = None
    count = 0
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise ValueError(f"blank audit event at line {line_number}")
            event = json.loads(line)
            event_hash = event.pop("event_hash", None)
            if event.get("previous_hash") != previous_hash:
                raise ValueError(f"broken audit chain at line {line_number}")
            result_hash = hashlib.sha256(_canonical_json(event["result_payload"]).encode("utf-8")).hexdigest()
            if result_hash != event.get("result_sha256"):
                raise ValueError(f"result digest mismatch at line {line_number}")
            calculated = hashlib.sha256(_canonical_json(event).encode("utf-8")).hexdigest()
            if event_hash != calculated:
                raise ValueError(f"event digest mismatch at line {line_number}")
            previous_hash = event_hash
            count += 1
    return count, previous_hash


class JsonlAuditStore:
    """Append-only, hash-chained local assessment log. Use one writer per file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, input_payload: Any, result: DecisionPackage | QuarantineRecord) -> None:
        if isinstance(input_payload, bytes):
            input_bytes = input_payload
        elif isinstance(input_payload, BaseModel):
            input_bytes = _canonical_json(input_payload.model_dump(mode="json")).encode("utf-8")
        else:
            input_bytes = _canonical_json(input_payload).encode("utf-8")

        result_payload = result.model_dump(mode="json")
        result_hash = hashlib.sha256(_canonical_json(result_payload).encode("utf-8")).hexdigest()
        _count, previous_hash = verify_p04_audit_log(self.path)
        audit_record = P04AuditRecord(
            opportunity_id=getattr(result, "opportunity_id", None),
            assessed_by=getattr(result, "assessed_by", None),
            assessed_at=getattr(result, "assessed_at", None),
            schema_version=getattr(result, "schema_version", "1.0.0"),
            result_type=("QUARANTINE_RECORD" if isinstance(result, QuarantineRecord) else result.state.value),
            input_sha256=hashlib.sha256(input_bytes).hexdigest(),
            result_sha256=result_hash,
            result_payload=result_payload,
            previous_hash=previous_hash,
        )
        event = audit_record.model_dump(mode="json", exclude={"event_hash"})
        event_hash = hashlib.sha256(_canonical_json(event).encode("utf-8")).hexdigest()
        event["event_hash"] = event_hash

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical_json(event) + "\n")
            stream.flush()


def evaluate_opportunity(opportunity: P04Opportunity) -> DecisionPackage:
    """Apply P04 gate precedence, scoring only eligible opportunities."""
    failed = [gate for gate in opportunity.gates if gate.decision == GateDecision.FAIL]
    unknown = [gate for gate in opportunity.gates if gate.decision == GateDecision.UNKNOWN]
    conditional = [gate for gate in opportunity.gates if gate.decision == GateDecision.CONDITIONAL]

    if failed:
        quarantine = QuarantineRecord(
            opportunity_id=opportunity.opportunity_id,
            record_type=QuarantineType.POLICY_INELIGIBLE,
            reason_codes=[f"GATE_FAILED:{gate.gate_id.value}" for gate in failed],
            details=[gate.rationale for gate in failed],
            evidence_refs=[ref for gate in failed for ref in gate.evidence_refs],
        )
        return DecisionPackage(
            opportunity_id=opportunity.opportunity_id,
            name=opportunity.name,
            assessed_by=opportunity.assessed_by,
            assessed_at=opportunity.assessed_at,
            state=EvaluationState.INELIGIBLE,
            gate_assessments=opportunity.gates,
            next_action="STOP_SCORING_AND_RETAIN_IN_POLICY_QUARANTINE",
            quarantine_record=quarantine,
        )

    if unknown:
        return DecisionPackage(
            opportunity_id=opportunity.opportunity_id,
            name=opportunity.name,
            assessed_by=opportunity.assessed_by,
            assessed_at=opportunity.assessed_at,
            state=EvaluationState.REVIEW_REQUIRED,
            gate_assessments=opportunity.gates,
            conditions_to_resolve=[
                condition for gate in conditional for condition in gate.conditions
            ],
            next_action="OBTAIN_EVIDENCE_AND_RESOLVE_UNKNOWN_GATES",
        )

    state = EvaluationState.CONDITIONALLY_ELIGIBLE if conditional else EvaluationState.ELIGIBLE
    score_result = score_opportunity(
        OpportunityInput(name=opportunity.name, dimensions=opportunity.dimensions)
    )
    observed: list[tuple[str, float]] = []
    for dimension, item in opportunity.dimensions.items():
        if item.score is not None:
            observed.append((dimension, item.score))
    ordered = [
        dimension
        for dimension, _score in sorted(
            observed, key=lambda pair: (-pair[1], DIMENSIONS.index(pair[0]))
        )
    ]
    explanation: dict[str, dict[str, Any]] = {}
    for dimension in DIMENSIONS:
        dim_item = opportunity.dimensions.get(dimension)
        explanation[dimension] = {
            "score_0_to_10": item.score if item else None,
            "weight": DEFAULT_WEIGHTS[dimension],
            "weighted_points_0_to_100": score_result.breakdown[dimension],
            "reliability": item.reliability.value if item else None,
            "rationale": item.reason if item else None,
            "evidence_refs": list(item.sources) if item else [],
            "missing_evidence": item is None or item.score is None,
        }
    return DecisionPackage(
        opportunity_id=opportunity.opportunity_id,
        name=opportunity.name,
        assessed_by=opportunity.assessed_by,
        assessed_at=opportunity.assessed_at,
        state=state,
        gate_assessments=opportunity.gates,
        score_result=score_result,
        dimension_explanations=explanation,
        highest_scoring_dimensions=ordered[:3],
        lowest_scoring_dimensions=list(reversed(ordered[-3:])),
        conditions_to_resolve=[condition for gate in conditional for condition in gate.conditions],
        next_action=(
            "RESOLVE_CONDITIONS_THEN_REVIEW_SCORE" if conditional else "REVIEW_SCORE_AND_EVIDENCE"
        ),
    )


def evaluate_payload(payload: Any) -> DecisionPackage | QuarantineRecord:
    """Validate a raw record and isolate invalid input without retaining its payload."""
    try:
        opportunity = P04Opportunity.model_validate(payload)
    except ValidationError as exc:
        source_id = payload.get("opportunity_id") if isinstance(payload, dict) else None
        safe_id = (
            source_id
            if isinstance(source_id, str)
            and len(source_id) <= 128
            and not any(ord(char) < 32 for char in source_id)
            else None
        )
        return QuarantineRecord(
            opportunity_id=safe_id,
           record_type=QuarantineType.STRUCTURAL_VALIDATION_FAILURE,
            reason_codes=["P04_SCHEMA_INVALID"],
            details=[f"{error['loc']}: {error['msg']}" for error in exc.errors()],
        )
    return evaluate_opportunity(opportunity)


def process_opportunity(
    payload: Any,
    quarantine_store: JsonlQuarantineStore | None = None,
) -> DecisionPackage | QuarantineRecord:
    """Evaluate input and append quarantine records when a store is supplied."""
    result = evaluate_payload(payload)
    quarantine = result if isinstance(result, QuarantineRecord) else result.quarantine_record
    if quarantine is not None and quarantine_store is not None:
        quarantine_store.append(quarantine)
    return result


class JsonlQuarantineStore:
    """Append-only JSONL persistence boundary; caller supplies the storage path."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: QuarantineRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")
            stream.flush()
