from __future__ import annotations

from difflib import SequenceMatcher
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.lpsme.models import OrganizationRecord, VerificationStatus
from src.lpsme.normalization import normalize_organization_name, normalize_registry_code

try:
    from rapidfuzz import fuzz as _rf_fuzz
    def _similarity(a: str, b: str) -> float:
        return float(_rf_fuzz.token_sort_ratio(a, b)) / 100.0
except ImportError:
    def _similarity(a: str, b: str) -> float:
        sa, sb = " ".join(sorted(a.split())), " ".join(sorted(b.split()))
        return SequenceMatcher(None, sa, sb).ratio()

class ResolutionDecision(str, Enum):
    EXACT_IDENTIFIER_MATCH = "EXACT_IDENTIFIER_MATCH"
    QUARANTINE_HUMAN_REVIEW = "QUARANTINE_HUMAN_REVIEW"
    DISTINCT_ENTITIES = "DISTINCT_ENTITIES"

class EntityMatchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    left_org_id: str = Field(min_length=1)
    right_org_id: str = Field(min_length=1)
    similarity_score: float = Field(ge=0.0, le=1.0)
    matched_on: str = Field(min_length=1)
    decision: ResolutionDecision
    resulting_status: VerificationStatus

class EntityResolutionEngine:
    """Deterministic + probabilistic entity resolution with strict no-auto-merge quarantine."""

    def __init__(self, quarantine_threshold: float = 0.78) -> None:
        self.quarantine_threshold = quarantine_threshold

    def compare_organizations(self, left: OrganizationRecord, right: OrganizationRecord) -> EntityMatchCandidate:
        l_rc, r_rc = normalize_registry_code(left.rc_number), normalize_registry_code(right.rc_number)
        if l_rc and r_rc and l_rc == r_rc:
            return EntityMatchCandidate(left_org_id=left.org_id, right_org_id=right.org_id, similarity_score=1.0, matched_on="rc_number", decision=ResolutionDecision.EXACT_IDENTIFIER_MATCH, resulting_status=VerificationStatus.NORMALIZED)
        l_nif, r_nif = normalize_registry_code(left.nif_number), normalize_registry_code(right.nif_number)
        if l_nif and r_nif and l_nif == r_nif:
            return EntityMatchCandidate(left_org_id=left.org_id, right_org_id=right.org_id, similarity_score=1.0, matched_on="nif_number", decision=ResolutionDecision.EXACT_IDENTIFIER_MATCH, resulting_status=VerificationStatus.NORMALIZED)
        l_lei, r_lei = normalize_registry_code(left.lei_code), normalize_registry_code(right.lei_code)
        if l_lei and r_lei and l_lei == r_lei:
            return EntityMatchCandidate(left_org_id=left.org_id, right_org_id=right.org_id, similarity_score=1.0, matched_on="lei_code", decision=ResolutionDecision.EXACT_IDENTIFIER_MATCH, resulting_status=VerificationStatus.NORMALIZED)
        n_left = normalize_organization_name(left.legal_name)
        n_right = normalize_organization_name(right.legal_name)
        score = round(_similarity(n_left, n_right), 4)
        if left.wilaya and right.wilaya and left.wilaya.strip().lower() == right.wilaya.strip().lower():
            score = min(1.0, round(score + 0.05, 4))
        if score >= self.quarantine_threshold:
            return EntityMatchCandidate(left_org_id=left.org_id, right_org_id=right.org_id, similarity_score=score, matched_on="fuzzy_name_wilaya", decision=ResolutionDecision.QUARANTINE_HUMAN_REVIEW, resulting_status=VerificationStatus.MATCHING_REVIEW)
        return EntityMatchCandidate(left_org_id=left.org_id, right_org_id=right.org_id, similarity_score=score, matched_on="fuzzy_name_wilaya", decision=ResolutionDecision.DISTINCT_ENTITIES, resulting_status=VerificationStatus.NORMALIZED)
