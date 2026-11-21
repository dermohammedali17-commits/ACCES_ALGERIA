from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.lpsme.models import OrganizationRecord
from src.lpsme.network import NetworkMetrics
from src.lpsme.regulatory import RegulatoryGateAssessment
from src.lpsme.scoring import PartnerScoreCard


class PartnerIntelligenceDossier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    organization: OrganizationRecord
    scorecard: PartnerScoreCard
    regulatory_assessment: RegulatoryGateAssessment
    network_metrics: NetworkMetrics
    executive_summary: str = Field(min_length=1)

class LPSMEDossierBuilder:
    """Constructs comprehensive, evidence-backed partner intelligence dossiers for ACCESS ALGERIA."""
    def build_dossier(self, org: OrganizationRecord, scorecard: PartnerScoreCard, regulatory: RegulatoryGateAssessment, network: NetworkMetrics) -> PartnerIntelligenceDossier:
        wilaya_str = org.wilaya if org.wilaya else "N/A"
        summary = f"Dossier for {org.legal_name} (Wilaya: {wilaya_str}): Composite Score={scorecard.composite_score}, Regulatory Gate Decision={regulatory.decision.value}, Network Degree={network.degree}."
        return PartnerIntelligenceDossier(organization=org, scorecard=scorecard, regulatory_assessment=regulatory, network_metrics=network, executive_summary=summary)
