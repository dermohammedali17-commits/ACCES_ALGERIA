from __future__ import annotations

from src.lpsme.models import (
    EvidenceCitation,
    OrganizationRecord,
    RelationshipClaim,
    StakeholderCategory,
    VerificationStatus,
)
from src.lpsme.normalization import normalize_arabic_text, normalize_organization_name
from src.lpsme.resolution import EntityResolutionEngine, ResolutionDecision
from src.lpsme.verification import EvidenceVerificationGate


def test_multilingual_normalization_and_entity_resolution_quarantine() -> None:
    assert normalize_organization_name("SARL ABC AUTOMOTIVE ALGERIE") == "abc automotive"
    assert normalize_organization_name("ABC Automotive SARL") == "abc automotive"
    assert normalize_arabic_text("شركة الأمل للسيارات") == "شركه الامل للسيارات"
    cit_caci = EvidenceCitation(citation_id="C1", source_code="CACI_ELMOUCHIR", source_reference="CACI-101", extraction_method="DIRECTORY_EXPORT", extracted_excerpt="ABC Automotive listing", confidence=0.88)
    cit_cnrc = EvidenceCitation(citation_id="C2", source_code="CNRC_SIDJILCOM", source_reference="RC-16/00-1122334B20", extraction_method="OFFICIAL_REGISTRY_LOOKUP", extracted_excerpt="CNRC legal record", confidence=0.98)
    org_a = OrganizationRecord(org_id="O1", legal_name="SARL ABC AUTOMOTIVE ALGERIE", wilaya="Alger", stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, citations=[cit_caci])
    org_b = OrganizationRecord(org_id="O2", legal_name="ABC Automotive SARL", wilaya="Alger", stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, citations=[cit_caci])
    org_c = OrganizationRecord(org_id="O3", legal_name="ABC Auto Distribution", rc_number="16/00-1122334B20", stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, citations=[cit_cnrc])
    org_d = OrganizationRecord(org_id="O4", legal_name="ABC Auto Parts", rc_number="16/00-1122334B20", stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, citations=[cit_cnrc])
    resolver = EntityResolutionEngine()
    fuzzy_res = resolver.compare_organizations(org_a, org_b)
    assert fuzzy_res.decision == ResolutionDecision.QUARANTINE_HUMAN_REVIEW
    assert fuzzy_res.resulting_status == VerificationStatus.MATCHING_REVIEW
    exact_res = resolver.compare_organizations(org_c, org_d)
    assert exact_res.decision == ResolutionDecision.EXACT_IDENTIFIER_MATCH

def test_evidence_verification_gate_blocks_unverified_ai_claims() -> None:
    cit_ai = EvidenceCitation(citation_id="C-AI", source_code="CORPORATE_WEB", source_reference="https://example.dz", extraction_method="AI_EXTRACTION", extracted_excerpt="Inferred partnership", confidence=0.92)
    cit_cnrc = EvidenceCitation(citation_id="C-CNRC", source_code="CNRC_SIDJILCOM", source_reference="RC-16/00-1122334B20", extraction_method="OFFICIAL_REGISTRY_LOOKUP", extracted_excerpt="Official CNRC extract", confidence=0.97)
    org_unverified = OrganizationRecord(org_id="O-UNV", legal_name="SARL Test", stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, citations=[cit_ai])
    org_verified = OrganizationRecord(org_id="O-VER", legal_name="SARL Test", rc_number="16/00-1122334B20", stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, citations=[cit_cnrc])
    rel_ai = RelationshipClaim(relationship_id="R-AI", source_entity_id="O-VER", target_entity_id="INST-AAPI", relationship_type="PARTNER", citations=[cit_ai])
    gate = EvidenceVerificationGate()
    assert gate.evaluate_organization(org_unverified).approved_status == VerificationStatus.EVIDENCE_REVIEW
    assert gate.evaluate_organization(org_verified).approved_status == VerificationStatus.VERIFIED
    assert gate.evaluate_relationship(rel_ai).approved_status == VerificationStatus.EVIDENCE_REVIEW
def test_unqualified_high_confidence_citation_cannot_verify_organization() -> None:
    cit_cnrc = EvidenceCitation(
        citation_id="C-CNRC-LOW",
        source_code="CNRC_SIDJILCOM",
        source_reference="RC-16/00-1122334B20",
        extraction_method="OFFICIAL_REGISTRY_LOOKUP",
        extracted_excerpt="CNRC registry reference",
        confidence=0.50,
    )

    cit_caci = EvidenceCitation(
        citation_id="C-CACI-HIGH",
        source_code="CACI_ELMOUCHIR",
        source_reference="CACI-101",
        extraction_method="DIRECTORY_EXPORT",
        extracted_excerpt="Company directory listing",
        confidence=0.99,
    )

    org = OrganizationRecord(
        org_id="O-MIXED",
        legal_name="SARL Mixed Evidence",
        rc_number="16/00-1122334B20",
        stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER,
        citations=[cit_cnrc, cit_caci],
    )

    outcome = EvidenceVerificationGate().evaluate_organization(org)

    assert outcome.approved_status == VerificationStatus.EVIDENCE_REVIEW
    assert outcome.has_legal_identity_source is True
    assert outcome.max_confidence == 0.50


def test_official_source_with_mismatched_identifier_cannot_verify() -> None:
    citation = EvidenceCitation(
        citation_id="C-CNRC-MISMATCH",
        source_code="CNRC_SIDJILCOM",
        source_reference="RC-16/00-9999999A99",
        extraction_method="OFFICIAL_REGISTRY_LOOKUP",
        extracted_excerpt="CNRC registry reference",
        confidence=0.99,
    )

    org = OrganizationRecord(
        org_id="O-MISMATCH",
        legal_name="SARL Mismatched Identity",
        rc_number="16/00-1122334B20",
        stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER,
        citations=[citation],
    )

    outcome = EvidenceVerificationGate().evaluate_organization(org)

    assert outcome.approved_status == VerificationStatus.EVIDENCE_REVIEW
    assert outcome.has_legal_identity_source is False
    assert outcome.max_confidence == 0.0


def test_user_submission_cannot_verify_organization() -> None:
    citation = EvidenceCitation(
        citation_id="C-USER-001",
        source_code="USER_SUBMISSION",
        source_reference="API-SUBMISSION:001",
        extraction_method="USER_SUBMISSION",
        extracted_excerpt="Information submitted by an authenticated user.",
        confidence=0.0,
    )

    org = OrganizationRecord(
        org_id="O-USER",
        legal_name="SARL User Submission",
        rc_number="16/00-1122334B20",
        stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER,
        verification_status=VerificationStatus.DISCOVERED,
        citations=[citation],
    )

    outcome = EvidenceVerificationGate().evaluate_organization(org)

    assert outcome.approved_status == VerificationStatus.EVIDENCE_REVIEW
    assert outcome.has_legal_identity_source is False