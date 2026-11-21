from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.lpsme.models import OrganizationRecord


class PartnerScoreCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    org_id: str = Field(min_length=1)
    strategic_fit_score: float = Field(ge=0.0, le=100.0)
    operational_capability_score: float = Field(ge=0.0, le=100.0)
    evidence_confidence_score: float = Field(ge=0.0, le=1.0)
    regulatory_compliance_score: float = Field(ge=0.0, le=100.0)
    composite_score: float = Field(ge=0.0, le=100.0)
    scoring_rationale: str = Field(min_length=1)

class LPSMEIndependentScorer:
    """Decoupled, evidence-driven partner scoring engine for LPSME (Strictly separate from Model B)."""
    def compute_score(self, org: OrganizationRecord, strategic_fit: float, operational_cap: float, regulatory_score: float) -> PartnerScoreCard:
        max_conf = max((c.confidence for c in org.citations), default=0.5)
        composite = round((
            (strategic_fit * 0.35) +
            (operational_cap * 0.30) +
            (regulatory_score * 0.25) +
            (max_conf * 100.0 * 0.10)
        ), 2)
        rationale = f"Score computed for {org.legal_name}: Strategic Fit={strategic_fit}, Operational={operational_cap}, Regulatory={regulatory_score}, Max Evidence Conf={max_conf}"
        return PartnerScoreCard(org_id=org.org_id, strategic_fit_score=float(strategic_fit), operational_capability_score=float(operational_cap), evidence_confidence_score=float(max_conf), regulatory_compliance_score=float(regulatory_score), composite_score=composite, scoring_rationale=rationale)
