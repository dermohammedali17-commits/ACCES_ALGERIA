"""Comprehensive unit tests for P07 Evidence & Source Intelligence modules."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.evidence.conflict_resolver import (
    ConflictResolver,
    SourceClaimVariant,
)
from src.evidence.fact_classifier import (
    FactClassifier,
    InformationClassification,
    VerificationLevel,
)
from src.evidence.provenance import ProvenanceTracker
from src.evidence.source_registry import (
    SourceCategory,
    SourceMetadataRecord,
    SourceRegistry,
    SourceStatus,
)


def test_source_registry_defaults() -> None:
    registry = SourceRegistry()
    comtrade = registry.get_source("COMTRADE_API")
    assert comtrade is not None
    assert comtrade.source_name == "UN Comtrade Database"
    assert comtrade.category == SourceCategory.TRADE_DATABASE


def test_provenance_tracker_valid_source() -> None:
    registry = SourceRegistry()
    tracker = ProvenanceTracker(registry)
    record = tracker.register_provenance(
        source_id="COMTRADE_API",
        record_key="DZ-2023-HS87",
        source_url="https://comtradeapi.un.org/data/v1/test",
        validation_status="UNVERIFIED",
        confidence_level="MEDIUM",
    )
    assert record.source_id == "COMTRADE_API"
    assert record.confidence_level == "MEDIUM"


def test_provenance_tracker_invalid_source() -> None:
    tracker = ProvenanceTracker()
    with pytest.raises(ValueError, match="not registered"):
        tracker.register_provenance(
            source_id="UNKNOWN_SOURCE",
            record_key="TEST-KEY",
            source_url="https://example.com",
        )


def test_fact_classifier_valid_claim() -> None:
    claim = FactClassifier.classify_claim(
        claim_id="CLM-01",
        statement="Algeria imported specific goods in 2023.",
        classification=InformationClassification.FACT,
        verification_status=VerificationLevel.VERIFIED,
        justification="Cross-checked against official direct UN Comtrade declarations.",
    )
    assert claim.classification == InformationClassification.FACT
    assert claim.verification_status == VerificationLevel.VERIFIED


def test_fact_classifier_invalid_verified_fact() -> None:
    with pytest.raises(ValueError, match="rigorous"):
        FactClassifier.classify_claim(
            claim_id="CLM-02",
            statement="Unverified statement.",
            classification=InformationClassification.FACT,
            verification_status=VerificationLevel.VERIFIED,
            justification="short",  # Too short justification
        )


def test_conflict_resolver_variants() -> None:
    resolver = ConflictResolver()
    v1 = SourceClaimVariant(
        source_id="SRC_A",
        provenance_id="prov-a-1",
        value=150.0,
        unit="USD",
        period="2023",
        retrieved_at=datetime.now(UTC).isoformat(),
    )
    v2 = SourceClaimVariant(
        source_id="SRC_B",
        provenance_id="prov-b-1",
        value=180.0,  # Conflicting value
        unit="USD",
        period="2023",
        retrieved_at=datetime.now(UTC).isoformat(),
    )
    conflict = resolver.evaluate_variants(subject_key="DZ-GDP-2023", variants=[v1, v2])
    assert conflict is not None
    assert len(conflict.variants) == 2
    assert conflict.subject_key == "DZ-GDP-2023"
