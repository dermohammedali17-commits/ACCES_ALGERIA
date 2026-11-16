"""Unit tests for P09 Sector Intelligence Engine."""

from __future__ import annotations

import pytest

from src.prioritization.prioritizer import PrioritizationEngine
from src.sector.engine import SectorIntelligenceEngine
from src.sector.models import MarketMaturityLevel, SectorCategory, SectorProfile
from src.sector.regulations import (
    ComplianceImpactLevel,
    RegulatoryRegistry,
    RegulatoryRule,
)


def test_sector_intelligence_luxury_auto_synthesis() -> None:
    registry = RegulatoryRegistry()
    registry.register_rule(
        RegulatoryRule(
            rule_id="REG-AUTO-01",
            sector=SectorCategory.LUXURY_AUTOMOTIVE,
            title="Cahier des charges concessionnaires",
            legal_reference="Decret Executif 22-383",
            impact=ComplianceImpactLevel.HIGH_FRICTION,
            requires_local_partner=True,
            summary="Requires approved dealership infrastructure and after-sales network.",
        )
    )

    profile = SectorProfile(
        sector_id="SEC-LUX-AUTO",
        category=SectorCategory.LUXURY_AUTOMOTIVE,
        name="Luxury & Performance Automotive Algeria",
        maturity=MarketMaturityLevel.REGULATED_TRANSITION,
        estimated_market_size_usd=120_000_000.0,
        annual_growth_rate_pct=None,  # Intentionally missing to test transparency
        local_content_requirement_pct=15.0,
        provenance_reference="PROV-JORADP-2022",
    )

    prioritized = PrioritizationEngine.prioritize_opportunity(
        opportunity_id="OPP-ASTON-01",
        prioritization_id="PRI-001",
        score=86.0,
        data_quality_score=92.0,
        evidence_verified=True,
        has_conflicts=False,
    )

    engine = SectorIntelligenceEngine(registry)
    report = engine.analyze_opportunity_sector(
        report_id="REP-SEC-001",
        profile=profile,
        prioritized_opportunity=prioritized,
    )

    assert report.applicable_rules_count == 1
    assert report.requires_local_partner is True
    assert report.has_regulatory_blockers is False
    assert "annual_growth_rate_pct" in report.missing_macro_indicators
    assert report.upstream_priority == "HIGH_PRIORITY"


def test_duplicate_regulatory_rule_raises_error() -> None:
    registry = RegulatoryRegistry()
    rule = RegulatoryRule(
        rule_id="REG-DUP-01",
        sector=SectorCategory.TOURISM_HOSPITALITY,
        title="Coastal Zone Protection",
        legal_reference="Loi Littoral",
        impact=ComplianceImpactLevel.BLOCKER,
        requires_local_partner=False,
        summary="Strict environmental clearance required.",
    )
    registry.register_rule(rule)
    with pytest.raises(ValueError, match="Duplicate regulatory rule_id"):
        registry.register_rule(rule)
