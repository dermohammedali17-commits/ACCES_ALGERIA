"""P07 Conflicting Information Detection & Preservation Module for ACCESS ALGERIA.

Identifies conflicting claims across distinct sources and preserves all original
claims alongside their provenance without silent overwriting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ConflictResolutionStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED_WITH_PRIMARY = "RESOLVED_WITH_PRIMARY"
    UNRESOLVABLE_PRESERVED = "UNRESOLVABLE_PRESERVED"


@dataclass(frozen=True)
class SourceClaimVariant:
    source_id: str
    provenance_id: str
    value: Any
    unit: str
    period: str
    retrieved_at: str
    confidence_level: str | None = None


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: str
    subject_key: str
    detected_at: str
    variants: tuple[SourceClaimVariant, ...]
    status: ConflictResolutionStatus = ConflictResolutionStatus.OPEN
    resolution_notes: str | None = None


class ConflictResolver:
    """Detects and preserves multi-source conflicts without silent overwriting."""

    def __init__(self) -> None:
        self._conflicts: dict[str, ConflictRecord] = {}

    def evaluate_variants(
        self,
        *,
        subject_key: str,
        variants: list[SourceClaimVariant],
    ) -> ConflictRecord | None:
        if len(variants) < 2:
            return None

        distinct_values = {repr(v.value) for v in variants}
        if len(distinct_values) <= 1:
            return None

        now = datetime.now(UTC)
        conflict_id = f"conf-{now.strftime('%Y%m%dT%H%M%S%f')}"

        record = ConflictRecord(
            conflict_id=conflict_id,
            subject_key=subject_key,
            detected_at=now.isoformat(),
            variants=tuple(variants),
            status=ConflictResolutionStatus.OPEN,
        )
        self._conflicts[conflict_id] = record
        return record

    def get_conflict(self, conflict_id: str) -> ConflictRecord | None:
        return self._conflicts.get(conflict_id)

    @property
    def all_conflicts(self) -> tuple[ConflictRecord, ...]:
        return tuple(self._conflicts.values())
