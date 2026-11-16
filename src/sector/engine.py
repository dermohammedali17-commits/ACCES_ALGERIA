"""Core Sector Intelligence Engine for ACCESS ALGERIA (P09)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.prioritization.prioritizer import PrioritizedOpportunityRecord
from src.sector.models import SectorProfile
from src.sector.regulations import (
    ComplianceImpactLevel,
    RegulatoryRegistry,
    RegulatoryRule,
)


class SectorIntelligenceReport(BaseModel):
    """Explainable, auditable sector intelligence synthesis for an opportunity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str = Field(min_length=1)
    opportunity_id: str = Field(min_length=1)
    sector_id: str = Field(min_length=1)
    sector_name: str = Field(min_length=1)
    upstream_priority: str = Field(min_length=1)
    applicable_rules_count: int = Field(ge=0)
    has_regulatory_blockers: bool
    requires_local_partner: bool
    missing_macro_indicators: list[str]
    sector_brief: str = Field(min_length=1)
    strategic_considerations: list[str]


class SectorIntelligenceEngine:
    """Synthesizes sector profiles and regulatory constraints without altering P04-P08."""

    def __init__(self, registry: RegulatoryRegistry) -> None:
        self._registry = registry

    def analyze_opportunity_sector(
        self,
        *,
        report_id: str,
        profile: SectorProfile,
        prioritized_opportunity: PrioritizedOpportunityRecord,
    ) -> SectorIntelligenceReport:
        rules: list[RegulatoryRule] = self._registry.get_rules_for_sector(profile.category)
        has_blockers = any(r.impact == ComplianceImpactLevel.BLOCKER for r in rules)
        requires_partner = any(r.requires_local_partner for r in rules)

        missing_indicators: list[str] = []
        if profile.estimated_market_size_usd is None:
            missing_indicators.append("estimated_market_size_usd")
        if profile.annual_growth_rate_pct is None:
            missing_indicators.append("annual_growth_rate_pct")

        considerations: list[str] = []
        if has_blockers:
            considerations.append(
                "CRITICAL: Active regulatory blocker detected in target sector; entry halted pending legal clearance."
            )
        if requires_partner:
            considerations.append(
                "Mandatory local Algerian partner or joint-venture structure required under sector regulations."
            )
        if profile.local_content_requirement_pct > 0.0:
            considerations.append(
                f"Minimum local integration target of {profile.local_content_requirement_pct:.1f}% applies."
            )
        if missing_indicators:
            considerations.append(
                f"Transparency notice: Missing macroeconomic fields ({', '.join(missing_indicators)}) not assumed as zero."
            )
        if not considerations:
            considerations.append("Standard sector entry conditions apply with no active regulatory blockers.")

        brief = (
            f"Sector '{profile.name}' ({profile.maturity.value}) evaluated for opportunity "
            f"'{prioritized_opportunity.opportunity_id}' [Priority: {prioritized_opportunity.priority.value}]. "
            f"Identified {len(rules)} applicable regulatory rule(s)."
        )

        return SectorIntelligenceReport(
            report_id=report_id,
            opportunity_id=prioritized_opportunity.opportunity_id,
            sector_id=profile.sector_id,
            sector_name=profile.name,
            upstream_priority=prioritized_opportunity.priority.value,
            applicable_rules_count=len(rules),
            has_regulatory_blockers=has_blockers,
            requires_local_partner=requires_partner,
            missing_macro_indicators=missing_indicators,
            sector_brief=brief,
            strategic_considerations=considerations,
        )
