from __future__ import annotations

import math
import re
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from src.lpsme.models import (
    OrganizationRecord,
    RelationshipClaim,
    VerificationStatus,
)
from src.lpsme.sources import (
    ALGERIAN_OFFICIAL_SOURCES,
    SourceAuthorityTier,
)


class VerificationOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    previous_status: VerificationStatus
    approved_status: VerificationStatus
    has_legal_identity_source: bool
    max_confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)


class EvidenceVerificationGate:
    """Enforce evidence-backed verification before promoting organizations."""

    IDENTIFIER_SOURCE_MAP: ClassVar[dict[str, tuple[str, ...]]] = {
        "CNRC_SIDJILCOM": ("rc_number", "nif_number"),
        "GLEIF_LEI": ("lei_code",),
    }

    APPROVED_REGISTRY_METHODS: ClassVar[frozenset[str]] = frozenset({
        "OFFICIAL_REGISTRY_LOOKUP",
    })

    def __init__(self, min_confidence: float = 0.85) -> None:
        if (
            isinstance(min_confidence, bool)
            or not isinstance(min_confidence, (int, float))
            or not math.isfinite(min_confidence)
            or not 0.0 <= min_confidence <= 1.0
        ):
            raise ValueError("min_confidence must be between 0.0 and 1.0.")

        self.min_confidence = float(min_confidence)

    @staticmethod
    def _normalize_identifier(value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    def _matches_registered_identifier(
        self,
        org: OrganizationRecord,
        source_code: str,
        source_reference: str,
    ) -> bool:
        identifier_fields = self.IDENTIFIER_SOURCE_MAP.get(source_code, ())
        normalized_reference = self._normalize_identifier(source_reference)

        if not normalized_reference:
            return False

        for field_name in identifier_fields:
            identifier = getattr(org, field_name)

            if not identifier:
                continue

            normalized_identifier = self._normalize_identifier(identifier)

            if (
                normalized_reference == normalized_identifier
                or normalized_reference.endswith(normalized_identifier)
            ):
                return True

        return False

    def _qualifying_legal_citations(
        self,
        org: OrganizationRecord,
    ) -> list:
        qualifying = []

        for citation in org.citations:
            source = ALGERIAN_OFFICIAL_SOURCES.get(citation.source_code)

            if source is None:
                continue

            if not source.establishes_legal_identity:
                continue

            if source.tier not in {
                SourceAuthorityTier.OFFICIAL_ALGERIAN_PRIMARY,
                SourceAuthorityTier.INTERNATIONAL_REGISTRY,
            }:
                continue

            if citation.extraction_method not in self.APPROVED_REGISTRY_METHODS:
                continue

            if not self._matches_registered_identifier(
                org,
                citation.source_code,
                citation.source_reference,
            ):
                continue

            qualifying.append(citation)

        return qualifying

    def evaluate_organization(
        self,
        org: OrganizationRecord,
        *,
        has_unresolved_conflicts: bool = False,
    ) -> VerificationOutcome:
        qualifying_citations = self._qualifying_legal_citations(org)

        max_confidence = max(
            (citation.confidence for citation in qualifying_citations),
            default=0.0,
        )

        has_legal_source = bool(qualifying_citations)

        if org.verification_status == VerificationStatus.REJECTED:
            return VerificationOutcome(
                entity_id=org.org_id,
                previous_status=org.verification_status,
                approved_status=VerificationStatus.REJECTED,
                has_legal_identity_source=has_legal_source,
                max_confidence=max_confidence,
                reason="Rejected organizations cannot be automatically promoted.",
            )

        if has_unresolved_conflicts:
            return VerificationOutcome(
                entity_id=org.org_id,
                previous_status=org.verification_status,
                approved_status=VerificationStatus.EVIDENCE_REVIEW,
                has_legal_identity_source=has_legal_source,
                max_confidence=max_confidence,
                reason="Unresolved source conflict requires human evidence review.",
            )

        if has_legal_source and max_confidence >= self.min_confidence:
            return VerificationOutcome(
                entity_id=org.org_id,
                previous_status=org.verification_status,
                approved_status=VerificationStatus.VERIFIED,
                has_legal_identity_source=True,
                max_confidence=max_confidence,
                reason=(
                    "Legal identity evidence passed source authority, "
                    "extraction method, identifier matching, and confidence checks."
                ),
            )

        return VerificationOutcome(
            entity_id=org.org_id,
            previous_status=org.verification_status,
            approved_status=VerificationStatus.EVIDENCE_REVIEW,
            has_legal_identity_source=has_legal_source,
            max_confidence=max_confidence,
            reason=(
                "Insufficient qualifying legal identity evidence; "
                "the organization remains under evidence review."
            ),
        )

    def evaluate_relationship(
        self,
        rel: RelationshipClaim,
    ) -> VerificationOutcome:
        qualifying_citations = []

        for citation in rel.citations:
            source = ALGERIAN_OFFICIAL_SOURCES.get(citation.source_code)

            if source is None:
                continue

            if source.tier == SourceAuthorityTier.SECONDARY_DIRECTORY:
                continue

            if citation.extraction_method in {
                "AI_EXTRACTION",
                "USER_SUBMISSION",
            }:
                continue

            qualifying_citations.append(citation)

        max_confidence = max(
            (citation.confidence for citation in qualifying_citations),
            default=0.0,
        )

        verified = (
            bool(qualifying_citations)
            and max_confidence >= self.min_confidence
        )

        return VerificationOutcome(
            entity_id=rel.relationship_id,
            previous_status=rel.verification_status,
            approved_status=(
                VerificationStatus.VERIFIED
                if verified
                else VerificationStatus.EVIDENCE_REVIEW
            ),
            # Relationship evidence does not establish legal identity.
            has_legal_identity_source=False,
            max_confidence=max_confidence,
            reason=(
                "Relationship supported by qualifying documentary evidence."
                if verified
                else "Relationship evidence is insufficient or unqualified."
            ),
        )