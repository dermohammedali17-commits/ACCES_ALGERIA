"""P07 Evidence Provenance and Traceability Module for ACCESS ALGERIA.

Connects market intelligence observations and opportunity records to their origins,
provenance history, verification status, and data lineage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.evidence.source_registry import SourceRegistry


@dataclass(frozen=True)
class ProvenanceRecord:
    provenance_id: str
    source_id: str
    record_key: str
    retrieved_at: str
    source_url: str
    validation_status: str
    confidence_level: str | None
    lineage_metadata: dict[str, Any] = field(default_factory=dict)


class ProvenanceTracker:
    """Tracks and validates provenance lineage for analytical observations."""

    def __init__(self, registry: SourceRegistry | None = None) -> None:
        self.registry = registry or SourceRegistry()
        self._provenance_store: dict[str, ProvenanceRecord] = {}

    def register_provenance(
        self,
        *,
        source_id: str,
        record_key: str,
        source_url: str,
        validation_status: str = "UNVERIFIED",
        confidence_level: str | None = None,
        lineage_metadata: dict[str, Any] | None = None,
    ) -> ProvenanceRecord:
        source = self.registry.get_source(source_id)
        if source is None:
            raise ValueError(f"Source ID '{source_id}' is not registered in the SourceRegistry.")

        now = datetime.now(UTC).isoformat()
        prov_id = f"prov-{source_id.lower()}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}"

        record = ProvenanceRecord(
            provenance_id=prov_id,
            source_id=source_id,
            record_key=record_key,
            retrieved_at=now,
            source_url=source_url,
            validation_status=validation_status,
            confidence_level=confidence_level,
            lineage_metadata=lineage_metadata or {},
        )
        self._provenance_store[prov_id] = record
        return record

    def get_provenance(self, provenance_id: str) -> ProvenanceRecord | None:
        return self._provenance_store.get(provenance_id)
