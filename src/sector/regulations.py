"""Regulatory & Compliance Intelligence for Algerian Target Sectors."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.sector.models import SectorCategory


class ComplianceImpactLevel(str, Enum):
    BLOCKER = "BLOCKER"
    HIGH_FRICTION = "HIGH_FRICTION"
    MODERATE = "MODERATE"
    ENABLER = "ENABLER"


class RegulatoryRule(BaseModel):
    """Represents a specific Algerian legal, customs, or licensing requirement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(min_length=1)
    sector: SectorCategory
    title: str = Field(min_length=1)
    legal_reference: str = Field(min_length=1)
    impact: ComplianceImpactLevel
    requires_local_partner: bool = False
    summary: str = Field(min_length=1)


class RegulatoryRegistry:
    """Deterministic store and evaluator for sector regulatory constraints."""

    def __init__(self) -> None:
        self._rules: dict[str, RegulatoryRule] = {}

    def register_rule(self, rule: RegulatoryRule) -> None:
        if rule.rule_id in self._rules:
            raise ValueError(f"Duplicate regulatory rule_id: {rule.rule_id}")
        self._rules[rule.rule_id] = rule

    def get_rules_for_sector(self, sector: SectorCategory) -> list[RegulatoryRule]:
        return sorted(
            [r for r in self._rules.values() if r.sector == sector],
            key=lambda x: x.rule_id,
        )

    def has_blockers(self, sector: SectorCategory) -> bool:
        return any(
            r.impact == ComplianceImpactLevel.BLOCKER
            for r in self.get_rules_for_sector(sector)
        )
