from __future__ import annotations

from src.lpsme.models import (
    EvidenceCitation,
    OrganizationRecord,
    PartnerType,
    StakeholderCategory,
    VerificationStatus,
)
from src.lpsme.scoring import LPSMEIndependentScorer


def test_lpsme_independent_partner_scoring() -> None:
    cit = EvidenceCitation(citation_id="C1", source_code="CNRC_SIDJILCOM", source_reference="RC-16/00-1111222B22", extraction_method="OFFICIAL_REGISTRY_LOOKUP", extracted_excerpt="Verified RC", confidence=0.96)
    org = OrganizationRecord(org_id="ORG-TEST-99", legal_name="SPA Premium Motors Algeria", rc_number="16/00-1111222B22", partner_types=[PartnerType.DISTRIBUTOR], stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, verification_status=VerificationStatus.VERIFIED, citations=[cit])
    scorer = LPSMEIndependentScorer()
    card = scorer.compute_score(org, strategic_fit=90.0, operational_cap=85.0, regulatory_score=100.0)
    assert card.composite_score > 85.0
    assert card.evidence_confidence_score == 0.96
    assert "SPA Premium Motors Algeria" in card.scoring_rationale
