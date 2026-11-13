"""P06 Data Quality Engine for ACCESS ALGERIA.

Enforces data completeness, structural validation, non-zero-filled missing-value
management, duplicate/conflict detection, consistency, and freshness checks across
market intelligence observations and structured records.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.data.mie.models import EvidenceBundle, Observation

P06_ENGINE_VERSION = "1.0.0"
DEFAULT_MAX_AGE_DAYS = 365


class QualityStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    QUARANTINE = "QUARANTINE"


class IssueSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class QualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: IssueSeverity
    field: str | None = None
    record_index: int | None = None
    message: str


class DataQualityRecord(BaseModel):
    """Canonical record contract validated by P06."""

    model_config = ConfigDict(extra="allow", frozen=True)

    source_id: str = Field(min_length=1)
    indicator_id: str = Field(min_length=1)
    value: float | int | str | None = None
    unit: str = Field(min_length=1)
    geography: str = Field(min_length=1)
    period: str = Field(min_length=1)
    source_mode: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    retrieved_at: datetime
    classification: str = Field(default="FACT", min_length=1)
    validation_status: str = Field(default="UNVERIFIED", min_length=1)
    confidence_level: str | None = None

    @field_validator("retrieved_at", mode="before")
    @classmethod
    def _parse_retrieved_at(cls, raw: Any) -> datetime:
        if isinstance(raw, datetime):
            if raw.tzinfo is None:
                raise ValueError("retrieved_at must be timezone-aware")
            return raw.astimezone(UTC)
        if isinstance(raw, str) and raw.strip():
            parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("retrieved_at must be timezone-aware")
            return parsed.astimezone(UTC)
        raise ValueError("retrieved_at must be a valid timezone-aware ISO timestamp")

    @field_validator("value")
    @classmethod
    def _validate_finite_numeric(cls, val: Any) -> Any:
        if isinstance(val, float) and not math.isfinite(val):
            raise ValueError("Numeric value must be finite (NaN/Inf rejected)")
        return val

    @property
    def composite_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.source_id.strip(),
            self.indicator_id.strip(),
            self.geography.strip(),
            self.period.strip(),
            self.source_mode.strip(),
        )


class DataQualityReport(BaseModel):
    """Audit-ready P06 quality evaluation report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_version: str = P06_ENGINE_VERSION
    evaluated_at: datetime
    status: QualityStatus
    total_records: int
    valid_records_count: int
    quarantined_records_count: int
    missing_values_count: int
    duplicate_records_count: int
    conflicting_duplicates_count: int
    stale_records_count: int
    completeness_ratio: float
    issues: tuple[QualityIssue, ...] = ()
    valid_records: tuple[DataQualityRecord, ...] = ()


def _coerce_input_record(item: Observation | DataQualityRecord | dict[str, Any]) -> dict[str, Any]:
    if isinstance(item, DataQualityRecord):
        return item.model_dump()
    if isinstance(item, Observation):
        return {
            "source_id": item.source_id,
            "indicator_id": item.indicator_id,
            "value": item.value,
            "unit": item.unit,
            "geography": item.geography,
            "period": item.period,
            "source_mode": item.source_mode,
            "source_url": item.source_url,
            "retrieved_at": item.retrieved_at,
            "classification": item.classification,
            "validation_status": item.validation_status,
            "confidence_level": item.confidence_level,
        }
    if isinstance(item, dict):
        return dict(item)
    raise TypeError(f"Unsupported record type for P06 evaluation: {type(item).__name__}")


def evaluate_data_quality(
    records: Sequence[Observation | DataQualityRecord | dict[str, Any]],
    *,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    reference_time: datetime | None = None,
    allow_missing_values: bool = True,
    min_completeness_ratio: float = 0.0,
) -> DataQualityReport:
    """Run P06 data quality checks without mutating or zero-filling missing values."""
    if max_age_days <= 0:
        raise ValueError("max_age_days must be positive")
    if not (0.0 <= min_completeness_ratio <= 1.0):
        raise ValueError("min_completeness_ratio must be between 0.0 and 1.0")

    now = (reference_time or datetime.now(UTC)).astimezone(UTC)
    if reference_time is not None and reference_time.tzinfo is None:
        raise ValueError("reference_time must be timezone-aware")

    freshness_cutoff = now - timedelta(days=max_age_days)
    issues: list[QualityIssue] = []
    valid_records: list[DataQualityRecord] = []

    if not records:
        issues.append(
            QualityIssue(
                code="P06_EMPTY_DATASET",
                severity=IssueSeverity.ERROR,
                message="Dataset contains zero records.",
            )
        )
        return DataQualityReport(
            evaluated_at=now,
            status=QualityStatus.QUARANTINE,
            total_records=0,
            valid_records_count=0,
            quarantined_records_count=0,
            missing_values_count=0,
            duplicate_records_count=0,
            conflicting_duplicates_count=0,
            stale_records_count=0,
            completeness_ratio=0.0,
            issues=tuple(issues),
            valid_records=(),
        )

    quarantined_count = 0
    missing_values_count = 0
    duplicate_count = 0
    conflicting_duplicate_count = 0
    stale_count = 0

    seen_keys: dict[tuple[str, str, str, str, str], DataQualityRecord] = {}

    for idx, raw_item in enumerate(records):
        try:
            payload = _coerce_input_record(raw_item)
            record = DataQualityRecord.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            quarantined_count += 1
            issues.append(
                QualityIssue(
                    code="P06_SCHEMA_VALIDATION_FAILED",
                    severity=IssueSeverity.ERROR,
                    record_index=idx,
                    message=str(exc),
                )
            )
            continue

        # Consistency: future retrieval timestamp check
        if record.retrieved_at > now + timedelta(minutes=5):
            quarantined_count += 1
            issues.append(
                QualityIssue(
                    code="P06_FUTURE_TIMESTAMP",
                    severity=IssueSeverity.ERROR,
                    field="retrieved_at",
                    record_index=idx,
                    message=f"retrieved_at ({record.retrieved_at.isoformat()}) is in the future.",
                )
            )
            continue

        # Consistency: source_url scheme check
        if not record.source_url.startswith(("http://", "https://", "urn:", "doc://")):
            quarantined_count += 1
            issues.append(
                QualityIssue(
                    code="P06_INVALID_SOURCE_URL",
                    severity=IssueSeverity.ERROR,
                    field="source_url",
                    record_index=idx,
                    message="source_url must use a valid scheme (http, https, urn, or doc).",
                )
            )
            continue

        # Duplicate & conflict detection
        key = record.composite_key
        if key in seen_keys:
            existing = seen_keys[key]
            duplicate_count += 1
            if existing.value != record.value:
                conflicting_duplicate_count += 1
                quarantined_count += 1
                issues.append(
                    QualityIssue(
                        code="P06_CONFLICTING_DUPLICATE",
                        severity=IssueSeverity.ERROR,
                        field="value",
                        record_index=idx,
                        message=(
                            f"Conflicting duplicate value for key {key}: "
                            f"{existing.value!r} vs {record.value!r}."
                        ),
                    )
                )
            else:
                issues.append(
                    QualityIssue(
                        code="P06_EXACT_DUPLICATE",
                        severity=IssueSeverity.WARNING,
                        record_index=idx,
                        message=f"Exact duplicate record skipped for key {key}.",
                    )
                )
            continue

        seen_keys[key] = record

        # Missing value detection (never zero-filled)
        is_missing = record.value is None or (
            isinstance(record.value, str) and not record.value.strip()
        )
        if is_missing:
            missing_values_count += 1
            issues.append(
                QualityIssue(
                    code="P06_MISSING_VALUE_PRESERVED",
                    severity=(
                        IssueSeverity.WARNING
                        if allow_missing_values
                        else IssueSeverity.ERROR
                    ),
                    field="value",
                    record_index=idx,
                    message="Missing value preserved as null (not zero-filled).",
                )
            )
            if not allow_missing_values:
                quarantined_count += 1
                continue

        # Freshness check
        if record.retrieved_at < freshness_cutoff:
            stale_count += 1
            issues.append(
                QualityIssue(
                    code="P06_STALE_DATA",
                    severity=IssueSeverity.WARNING,
                    field="retrieved_at",
                    record_index=idx,
                    message=(
                        f"Record retrieved at {record.retrieved_at.isoformat()} exceeds "
                        f"max_age_days={max_age_days}."
                    ),
                )
            )

        # Mirror source transparency warning
        if record.source_mode.upper() == "MIRROR" and record.confidence_level == "HIGH":
            quarantined_count += 1
            issues.append(
                QualityIssue(
                    code="P06_MIRROR_HIGH_CONFIDENCE_VIOLATION",
                    severity=IssueSeverity.ERROR,
                    field="confidence_level",
                    record_index=idx,
                    message="Mirror-reported records cannot be assigned HIGH confidence automatically.",
                )
            )
            continue

        valid_records.append(record)

    total = len(records)
    non_missing_valid = sum(
        1
        for r in valid_records
        if r.value is not None and not (isinstance(r.value, str) and not r.value.strip())
    )
    completeness_ratio = round(non_missing_valid / total, 4) if total > 0 else 0.0

    if completeness_ratio < min_completeness_ratio:
        issues.append(
            QualityIssue(
                code="P06_COMPLETENESS_BELOW_THRESHOLD",
                severity=IssueSeverity.ERROR,
                message=(
                    f"Completeness ratio {completeness_ratio:.4f} is below minimum "
                    f"required {min_completeness_ratio:.4f}."
                ),
            )
        )

    has_errors = any(issue.severity == IssueSeverity.ERROR for issue in issues)
    has_warnings = any(issue.severity == IssueSeverity.WARNING for issue in issues)

    if has_errors or not valid_records:
        status = QualityStatus.QUARANTINE
    elif has_warnings:
        status = QualityStatus.PASS_WITH_WARNINGS
    else:
        status = QualityStatus.PASS

    return DataQualityReport(
        evaluated_at=now,
        status=status,
        total_records=total,
        valid_records_count=len(valid_records),
        quarantined_records_count=quarantined_count,
        missing_values_count=missing_values_count,
        duplicate_records_count=duplicate_count,
        conflicting_duplicates_count=conflicting_duplicate_count,
        stale_records_count=stale_count,
        completeness_ratio=completeness_ratio,
        issues=tuple(issues),
        valid_records=tuple(valid_records),
    )


def evaluate_evidence_bundle(
    bundle: EvidenceBundle,
    *,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    reference_time: datetime | None = None,
    allow_missing_values: bool = True,
    min_completeness_ratio: float = 0.0,
) -> DataQualityReport:
    """Validate an MIE EvidenceBundle through the P06 Data Quality Engine."""
    return evaluate_data_quality(
        bundle.observations,
        max_age_days=max_age_days,
        reference_time=reference_time,
        allow_missing_values=allow_missing_values,
        min_completeness_ratio=min_completeness_ratio,
    )