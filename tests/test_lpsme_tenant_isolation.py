
from __future__ import annotations

from pathlib import Path

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
from src.lpsme.storage import LPSMEStorage


def build_records(suffix: str):
    citation = EvidenceCitation(
        citation_id=f"CIT-{suffix}",
        source_code="CNRC_SIDJILCOM",
        source_reference=f"RC-{suffix}",
        extraction_method="OFFICIAL_REGISTRY_LOOKUP",
        extracted_excerpt=f"Official evidence for workspace {suffix}.",
        confidence=0.95,
    )

    org = OrganizationRecord(
        org_id="ORG-SHARED",
        legal_name=f"Company {suffix}",
        rc_number=f"RC-{suffix}",
        partner_types=[
            PartnerType.DISTRIBUTOR,
            PartnerType.OPERATIONAL_PARTNER,
        ],
        stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER,
        strategic_level=StrategicLevel.LEVEL_A_STRATEGIC,
        verification_status=VerificationStatus.VERIFIED,
        citations=[citation],
    )

    institution = InstitutionRecord(
        institution_id="INST-SHARED",
        name=f"Institution {suffix}",
        acronym=f"INST-{suffix}",
        category=StakeholderCategory.INVESTMENT_INSTITUTION,
        mandate_summary=f"Mandate for {suffix}",
        official_portal="https://aapi.dz",
        citations=[citation],
    )

    relationship = RelationshipClaim(
        relationship_id="REL-SHARED",
        source_entity_id="ORG-SHARED",
        target_entity_id="INST-SHARED",
        relationship_type=f"RELATIONSHIP-{suffix}",
        citations=[citation],
    )

    contact = ProfessionalContactRecord(
        contact_id="CONTACT-SHARED",
        org_id="ORG-SHARED",
        role_title=f"Director {suffix}",
        official_channel=f"contact-{suffix}@example.com",
        lawful_basis="Public corporate directory",
        consent_or_public_record_ref=f"RECORD-{suffix}",
    )

    return org, institution, relationship, contact


def test_lpsme_workspace_tenant_isolation(tmp_path: Path) -> None:
    db_path = str(tmp_path / "tenant_isolation.duckdb")

    # Insert records for Workspace A.
    org_a, inst_a, rel_a, contact_a = build_records("A")

    with LPSMEStorage(
        db_path,
        workspace_id="WORKSPACE-A",
    ) as storage_a:
        storage_a.upsert_organization(org_a)
        storage_a.upsert_institution(inst_a)
        storage_a.upsert_relationship(rel_a)
        storage_a.store_restricted_contact(contact_a)

    # Insert records with identical IDs for Workspace B.
    org_b, inst_b, rel_b, contact_b = build_records("B")

    with LPSMEStorage(
        db_path,
        workspace_id="WORKSPACE-B",
    ) as storage_b:
        storage_b.upsert_organization(org_b)
        storage_b.upsert_institution(inst_b)
        storage_b.upsert_relationship(rel_b)
        storage_b.store_restricted_contact(contact_b)

    # Verify Workspace A can only read its own records.
    with LPSMEStorage(
        db_path,
        workspace_id="WORKSPACE-A",
    ) as storage_a:
        loaded_org_a = storage_a.get_organization("ORG-SHARED")
        loaded_inst_a = storage_a.get_institutions()
        loaded_rel_a = storage_a.get_relationships()
        loaded_contact_a = storage_a.get_restricted_contact(
            "CONTACT-SHARED"
        )

        assert loaded_org_a is not None
        assert loaded_org_a.legal_name == "Company A"

        assert len(loaded_inst_a) == 1
        assert loaded_inst_a[0].name == "Institution A"

        assert len(loaded_rel_a) == 1
        assert loaded_rel_a[0].relationship_type == "RELATIONSHIP-A"

        assert loaded_contact_a is not None
        assert loaded_contact_a.official_channel == "contact-A@example.com"

        assert storage_a.count_records() == {
            "organizations": 1,
            "institutions": 1,
            "relationships": 1,
            "restricted_contacts": 1,
        }

    # Verify Workspace B can only read its own records.
    with LPSMEStorage(
        db_path,
        workspace_id="WORKSPACE-B",
    ) as storage_b:
        loaded_org_b = storage_b.get_organization("ORG-SHARED")
        loaded_inst_b = storage_b.get_institutions()
        loaded_rel_b = storage_b.get_relationships()
        loaded_contact_b = storage_b.get_restricted_contact(
            "CONTACT-SHARED"
        )

        assert loaded_org_b is not None
        assert loaded_org_b.legal_name == "Company B"

        assert len(loaded_inst_b) == 1
        assert loaded_inst_b[0].name == "Institution B"

        assert len(loaded_rel_b) == 1
        assert loaded_rel_b[0].relationship_type == "RELATIONSHIP-B"

        assert loaded_contact_b is not None
        assert loaded_contact_b.official_channel == "contact-B@example.com"

        assert storage_b.count_records() == {
            "organizations": 1,
            "institutions": 1,
            "relationships": 1,
            "restricted_contacts": 1,
        }
