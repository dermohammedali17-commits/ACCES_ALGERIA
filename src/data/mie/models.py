"""Versioned contracts for evidence gathered by the MIE."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class SourceMetadata:
    source_id: str
    provider: str
    definition: str
    unit: str
    geography: str
    temporal_granularity: str
    query_defaults: dict[str, Any]
    limitations: tuple[str, ...]
    retrieval_semantics: str
    version: str = "1.0"
    status: str = "ACTIVE"


@dataclass(frozen=True)
class Observation:
    source_id: str
    indicator_id: str
    value: float | int | str | None
    unit: str
    geography: str
    period: str
    source_mode: str
    source_url: str
    retrieved_at: str
    classification: str = "FACT"
    validation_status: str = "UNVERIFIED"
    confidence_level: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Retrieval:
    retrieval_id: str
    source_id: str
    status: str
    requested_periods: tuple[str, ...]
    retrieved_periods: tuple[str, ...]
    missing_periods: tuple[str, ...]
    source_mode: str
    record_count: int
    warnings: tuple[str, ...] = ()
    error: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    retrieved_at: str
    parameters: dict[str, Any]
    observations: tuple[Observation, ...]
    retrievals: tuple[Retrieval, ...]
    schema_version: str = SCHEMA_VERSION
    interpretations: tuple[dict[str, str], ...] = ()

    @classmethod
    def create(
        cls,
        *,
        parameters: dict[str, Any],
        observations: list[Observation],
        retrievals: list[Retrieval],
        interpretations: tuple[dict[str, str], ...] = (),
    ) -> EvidenceBundle:
        now = datetime.now(UTC).isoformat()
        return cls(
            bundle_id=f"mie-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
            retrieved_at=now,
            parameters=parameters,
            observations=tuple(observations),
            retrievals=tuple(retrievals),
            interpretations=interpretations,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
