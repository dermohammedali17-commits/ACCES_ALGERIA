"""Tests for the P06 Data Quality Engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.data.quality_engine import (
    DataQualityRecord,
    DataQualityReport,
    QualityStatus,
    evaluate_data_quality,
)


def test_quality_engine_perfect_records() -> None:
    now = datetime.now(UTC)
    records = [
        {
            "source_id": "SRC_01",
            "indicator_id": "IND_01",
            "value": 100.5,
            "unit": "USD",
            "geography": "DZ",
            "period": "2023",
            "source_mode": "DIRECT",
            "source_url": "https://api.example.com/data",
            "retrieved_at": now.isoformat(),
        }
    ]
    report = evaluate_data_quality(records, reference_time=now)
    assert report.status == QualityStatus.PASS
    assert report.total_records == 1
    assert report.valid_records_count == 1
    assert report.quarantined_records_count == 0
    assert report.missing_values_count == 0
    assert report.completeness_ratio == 1.0


def test_quality_engine_missing_values_preserved() -> None:
    now = datetime.now(UTC)
    records = [
        {
            "source_id": "SRC_01",
            "indicator_id": "IND_01",
            "value": None,
            "unit": "USD",
            "geography": "DZ",
            "period": "2023",
            "source_mode": "DIRECT",
            "source_url": "https://api.example.com/data",
            "retrieved_at": now.isoformat(),
        }
    ]
    report = evaluate_data_quality(records, reference_time=now, allow_missing_values=True)
    assert report.status == QualityStatus.PASS_WITH_WARNINGS
    assert report.missing_values_count == 1
    assert report.valid_records_count == 1


def test_quality_engine_conflicting_duplicates() -> None:
    now = datetime.now(UTC)
    records = [
        {
            "source_id": "SRC_01",
            "indicator_id": "IND_01",
            "value": 100.0,
            "unit": "USD",
            "geography": "DZ",
            "period": "2023",
            "source_mode": "DIRECT",
            "source_url": "https://api.example.com/data",
            "retrieved_at": now.isoformat(),
        },
        {
            "source_id": "SRC_01",
            "indicator_id": "IND_01",
            "value": 200.0,
            "unit": "USD",
            "geography": "DZ",
            "period": "2023",
            "source_mode": "DIRECT",
            "source_url": "https://api.example.com/data",
            "retrieved_at": now.isoformat(),
        },
    ]
    report = evaluate_data_quality(records, reference_time=now)
    assert report.status == QualityStatus.QUARANTINE
    assert report.conflicting_duplicates_count == 1
    assert report.quarantined_records_count == 1


def test_quality_engine_stale_data() -> None:
    now = datetime.now(UTC)
    old_time = now - timedelta(days=400)
    records = [
        {
            "source_id": "SRC_01",
            "indicator_id": "IND_01",
            "value": 50.0,
            "unit": "USD",
            "geography": "DZ",
            "period": "2020",
            "source_mode": "DIRECT",
            "source_url": "https://api.example.com/data",
            "retrieved_at": old_time.isoformat(),
        }
    ]
    report = evaluate_data_quality(records, max_age_days=365, reference_time=now)
    assert report.status == QualityStatus.PASS_WITH_WARNINGS
    assert report.stale_records_count == 1
    assert any(issue.code == "P06_STALE_DATA" for issue in report.issues)