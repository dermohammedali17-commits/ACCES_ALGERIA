from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SourceAuthorityTier(str, Enum):
    OFFICIAL_ALGERIAN_PRIMARY = "OFFICIAL_ALGERIAN_PRIMARY"
    INTERNATIONAL_REGISTRY = "INTERNATIONAL_REGISTRY"
    CORPORATE_PRIMARY = "CORPORATE_PRIMARY"
    SECONDARY_DIRECTORY = "SECONDARY_DIRECTORY"


class OfficialSourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tier: SourceAuthorityTier
    portal_url: str = Field(min_length=1)
    requires_subscription: bool = False
    establishes_legal_identity: bool = False
    notes: str = Field(min_length=1)


ALGERIAN_OFFICIAL_SOURCES: dict[str, OfficialSourceSpec] = {
    "AAPI_BOURSE": OfficialSourceSpec(
        source_code="AAPI_BOURSE",
        name="AAPI Bourse de Partenariat",
        tier=SourceAuthorityTier.OFFICIAL_ALGERIAN_PRIMARY,
        portal_url="https://aapi.dz",
        establishes_legal_identity=False,
        notes="Official partnership matchmaking and investment opportunity channel.",
    ),
    "CNRC_SIDJILCOM": OfficialSourceSpec(
        source_code="CNRC_SIDJILCOM",
        name="CNRC / Sidjilcom Portal",
        tier=SourceAuthorityTier.OFFICIAL_ALGERIAN_PRIMARY,
        portal_url="https://sidjilcom.cnrc.dz",
        requires_subscription=True,
        establishes_legal_identity=True,
        notes="Primary legal identity, NAE activity codes, and commercial registry.",
    ),
    "CACI_ELMOUCHIR": OfficialSourceSpec(
        source_code="CACI_ELMOUCHIR",
        name="CACI El Mouchir Directory",
        tier=SourceAuthorityTier.OFFICIAL_ALGERIAN_PRIMARY,
        portal_url="https://elmouchir.caci.dz",
        requires_subscription=True,
        establishes_legal_identity=False,
        notes="Trilingual (AR/FR/EN) chamber directory covering ~700 activities.",
    ),
    "COSOB_ISSUERS": OfficialSourceSpec(
        source_code="COSOB_ISSUERS",
        name="COSOB Listed Issuers Directory",
        tier=SourceAuthorityTier.OFFICIAL_ALGERIAN_PRIMARY,
        portal_url="https://www.cosob.dz",
        establishes_legal_identity=True,
        notes="Publicly listed Algerian corporate issuers and financial entities.",
    ),
    "JORADP": OfficialSourceSpec(
        source_code="JORADP",
        name="Journal Officiel de la Republique Algerienne",
        tier=SourceAuthorityTier.OFFICIAL_ALGERIAN_PRIMARY,
        portal_url="https://www.joradp.dz",
        establishes_legal_identity=True,
        notes="Official decrees, approvals, and regulatory decisions.",
    ),
    "GLEIF_LEI": OfficialSourceSpec(
        source_code="GLEIF_LEI",
        name="Global Legal Entity Identifier Foundation",
        tier=SourceAuthorityTier.INTERNATIONAL_REGISTRY,
        portal_url="https://api.gleif.org",
        establishes_legal_identity=True,
        notes="International parent-child corporate structure and LEI verification.",
    ),
    "OPENCORPORATES": OfficialSourceSpec(
        source_code="OPENCORPORATES",
        name="OpenCorporates REST API",
        tier=SourceAuthorityTier.INTERNATIONAL_REGISTRY,
        portal_url="https://api.opencorporates.com",
        requires_subscription=True,
        establishes_legal_identity=False,
        notes="Global corporate enrichment; Algerian coverage requires explicit validation.",
    ),
}
