from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.lpsme.models import (
    EvidenceCitation,
    InstitutionRecord,
    OrganizationRecord,
    PartnerType,
    ProfessionalContactRecord,
    RelationshipClaim,
    StakeholderCategory,
    StrategicLevel,
    VerificationStatus,
)
from src.lpsme.sources import ALGERIAN_OFFICIAL_SOURCES, SourceAuthorityTier
from src.lpsme.storage import LPSMEStorage


def test_lpsme_phase1_models_and_duckdb_persistence() -> None:
    citation = EvidenceCitation(citation_id="CIT-001", source_code="CNRC_SIDJILCOM", source_reference="RC-16/00-0987654B22", extraction_method="OFFICIAL_REGISTRY_LOOKUP", extracted_excerpt="Registered automotive distribution and maintenance entity.", confidence=0.95)
    org = OrganizationRecord(org_id="ORG-DZ-001", legal_name="SPA Maghreb Luxury Motors", arabic_name="شركة المغرب للسيارات الفاخرة", rc_number="16/00-0987654B22", wilaya="Alger", partner_types=[PartnerType.DISTRIBUTOR, PartnerType.OPERATIONAL_PARTNER], stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, strategic_level=StrategicLevel.LEVEL_A_STRATEGIC, verification_status=VerificationStatus.VERIFIED, citations=[citation])
    inst = InstitutionRecord(institution_id="INST-AAPI", name="Agence Algerienne de Promotion de l'Investissement", acronym="AAPI", category=StakeholderCategory.INVESTMENT_INSTITUTION, mandate_summary="National investment promotion and Bourse de Partenariat.", official_portal="https://aapi.dz", citations=[citation])
    rel = RelationshipClaim(relationship_id="REL-001", source_entity_id="ORG-DZ-001", target_entity_id="INST-AAPI", relationship_type="REGISTERED_ON_BOURSE_PARTENARIAT", citations=[citation])
    contact = ProfessionalContactRecord(contact_id="CNT-001", org_id="ORG-DZ-001", role_title="Directeur Developpement", official_channel="contact@maghrebluxury.dz", lawful_basis="Law 25-11 Art. 7 - Public corporate directory", consent_or_public_record_ref="CACI-2026-881")
    storage = LPSMEStorage(
    ":memory:",
    workspace_id="WS-TEST-001",
)
    storage.upsert_organization(org)
    storage.upsert_institution(inst)
    storage.upsert_relationship(rel)
    storage.store_restricted_contact(contact)
    loaded = storage.get_organization("ORG-DZ-001")
    assert loaded is not None and loaded.rc_number == "16/00-0987654B22"
    assert storage.count_records() == {"organizations": 1, "institutions": 1, "relationships": 1, "restricted_contacts": 1}
    storage.close()
def test_lpsme_enforces_mandatory_evidence_and_official_sources() -> None:
    assert ALGERIAN_OFFICIAL_SOURCES["CNRC_SIDJILCOM"].tier == SourceAuthorityTier.OFFICIAL_ALGERIAN_PRIMARY
    assert ALGERIAN_OFFICIAL_SOURCES["AAPI_BOURSE"].establishes_legal_identity is False
    with pytest.raises(ValidationError):
        OrganizationRecord(org_id="ORG-BAD", legal_name="Unverified Ghost Corp", stakeholder_category=StakeholderCategory.CORPORATE_STAKEHOLDER, citations=[])
