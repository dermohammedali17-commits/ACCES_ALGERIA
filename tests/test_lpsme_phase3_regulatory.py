from __future__ import annotations

from src.lpsme.models import (
    EvidenceCitation,
    OrganizationRecord,
    PartnerType,
    StakeholderCategory,
    VerificationStatus,
)
from src.lpsme.regulatory import GateDecision, RegulatoryEligibilityEngine


def test_regulatory_eligibility_gates() -> None:
    cit = EvidenceCitation(citation_id="C1", source_code="CNRC_SIDJILCOM", source_reference="RC-16/00-9988776B22", extraction_method="OFFICIAL_REGISTRY_LOOKUP", extracted_excerpt="Verified CNRC extract", confidence=0.98)
    eligible_org = OrganizationRecord(org_id="ORG-AUTO-1", legal_name="SPA Atlas Motors", rc_number="16/00-9988776B22", nae_codes=["402101"], partner_types=[PartnerType.DISTRIBUTOR], stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, verification_status=VerificationStatus.VERIFIED, citations=[cit])
    unverified_org = OrganizationRecord(org_id="ORG-AUTO-2", legal_name="SARL Pending Motors", stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, verification_status=VerificationStatus.DISCOVERED, citations=[cit])
    engine = RegulatoryEligibilityEngine()
    res_ok = engine.evaluate_partner(eligible_org, sector="Luxury Automotive", required_nae_prefixes=["402"])
    assert res_ok.decision == GateDecision.ELIGIBLE
    assert "NAE_ACTIVITY_CODE_MATCHED" in res_ok.passed_checks
    res_bad = engine.evaluate_partner(unverified_org, sector="Luxury Automotive", required_nae_prefixes=["402"])
    assert res_bad.decision == GateDecision.INELIGIBLE
    assert len(res_bad.blocking_reasons) >= 2
