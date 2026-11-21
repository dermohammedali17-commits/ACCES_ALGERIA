from __future__ import annotations

from datetime import UTC, datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VerificationStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    EXTRACTED = "EXTRACTED"
    NORMALIZED = "NORMALIZED"
    MATCHING_REVIEW = "MATCHING_REVIEW"
    EVIDENCE_REVIEW = "EVIDENCE_REVIEW"
    VERIFIED = "VERIFIED"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    STALE = "STALE"

class PartnerType(str, Enum):
    INVESTOR = "INVESTOR"
    CORPORATE_PARTNER = "CORPORATE_PARTNER"
    DISTRIBUTOR = "DISTRIBUTOR"
    COMMERCIAL_PARTNER = "COMMERCIAL_PARTNER"
    STRATEGIC_PARTNER = "STRATEGIC_PARTNER"
    OPERATIONAL_PARTNER = "OPERATIONAL_PARTNER"
    TECHNOLOGY_PARTNER = "TECHNOLOGY_PARTNER"
    SERVICE_PROVIDER = "SERVICE_PROVIDER"

class StrategicLevel(str, Enum):
    LEVEL_A_STRATEGIC = "LEVEL_A_STRATEGIC"
    LEVEL_B_DEVELOPMENT = "LEVEL_B_DEVELOPMENT"
    LEVEL_C_SUPPORTING = "LEVEL_C_SUPPORTING"
    WATCHLIST = "WATCHLIST"

class StakeholderCategory(str, Enum):
    GOVERNMENT_INSTITUTION = "GOVERNMENT_INSTITUTION"
    INVESTMENT_INSTITUTION = "INVESTMENT_INSTITUTION"
    REGULATORY_INSTITUTION = "REGULATORY_INSTITUTION"
    FINANCIAL_STAKEHOLDER = "FINANCIAL_STAKEHOLDER"
    CORPORATE_STAKEHOLDER = "CORPORATE_STAKEHOLDER"
    INDUSTRIAL_STAKEHOLDER = "INDUSTRIAL_STAKEHOLDER"
    COMMERCIAL_STAKEHOLDER = "COMMERCIAL_STAKEHOLDER"
    PROFESSIONAL_STAKEHOLDER = "PROFESSIONAL_STAKEHOLDER"
    TECHNICAL_STAKEHOLDER = "TECHNICAL_STAKEHOLDER"
    INFRASTRUCTURE_STAKEHOLDER = "INFRASTRUCTURE_STAKEHOLDER"

class EvidenceCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    citation_id: str = Field(min_length=1)
    source_code: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    publication_date: str | None = None
    extraction_method: str = Field(min_length=1)
    extracted_excerpt: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

class OrganizationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    org_id: str = Field(min_length=1)
    legal_name: str = Field(min_length=1)
    commercial_names: list[str] = Field(default_factory=list)
    arabic_name: str | None = None
    rc_number: str | None = None
    nif_number: str | None = None
    lei_code: str | None = None
    nae_codes: list[str] = Field(default_factory=list)
    wilaya: str | None = None
    country: str = Field(default="Algeria", min_length=1)
    partner_types: list[PartnerType] = Field(default_factory=list)
    stakeholder_category: StakeholderCategory
    strategic_level: StrategicLevel = StrategicLevel.WATCHLIST
    verification_status: VerificationStatus = VerificationStatus.DISCOVERED
    citations: list[EvidenceCitation] = Field(min_length=1)

class InstitutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    institution_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    acronym: str | None = None
    arabic_name: str | None = None
    category: StakeholderCategory
    mandate_summary: str = Field(min_length=1)
    official_portal: str | None = None
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    citations: list[EvidenceCitation] = Field(min_length=1)

class RelationshipClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    relationship_id: str = Field(min_length=1)
    source_entity_id: str = Field(min_length=1)
    target_entity_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    verification_status: VerificationStatus = VerificationStatus.EVIDENCE_REVIEW
    citations: list[EvidenceCitation] = Field(min_length=1)

class ProfessionalContactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contact_id: str = Field(min_length=1)
    org_id: str = Field(min_length=1)
    role_title: str = Field(min_length=1)
    official_channel: str = Field(min_length=1)
    lawful_basis: str = Field(min_length=1)
    consent_or_public_record_ref: str = Field(min_length=1)
