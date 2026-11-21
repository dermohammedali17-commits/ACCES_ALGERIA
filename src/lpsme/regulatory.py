from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.lpsme.models import OrganizationRecord, PartnerType, VerificationStatus


class GateDecision(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    CONDITIONAL = "CONDITIONAL"
    INELIGIBLE = "INELIGIBLE"

class RegulatoryGateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    org_id: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    decision: GateDecision
    passed_checks: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    regulatory_references: list[str] = Field(default_factory=list)

class RegulatoryEligibilityEngine:
    """Deterministic Algerian sectoral and legal eligibility gates for LPSME."""

    def evaluate_partner(self, org: OrganizationRecord, sector: str, required_nae_prefixes: list[str] | None = None) -> RegulatoryGateAssessment:
        passed: list[str] = []
        blocks: list[str] = []
        refs: list[str] = ["Law 22-18 Investment Law", "CNRC Commercial Registry Rules"]
        if org.verification_status in {VerificationStatus.VERIFIED, VerificationStatus.QUALIFIED}:
            passed.append("ENTITY_VERIFICATION_CONFIRMED")
        else:
            blocks.append(f"Entity status {org.verification_status.value} is not VERIFIED or QUALIFIED.")
        if org.country.strip().lower() == "algeria" and not (org.rc_number or org.nif_number):
            blocks.append("Missing Algerian RC or NIF registration identifier.")
        elif org.rc_number or org.nif_number or org.lei_code:
            passed.append("LEGAL_IDENTIFIER_PRESENT")
        sec_lower = sector.strip().lower()
        if "automotive" in sec_lower:
            refs.append("Executive Decree 22-383 (Vehicle Dealerships)")
            allowed_types = {PartnerType.DISTRIBUTOR, PartnerType.COMMERCIAL_PARTNER, PartnerType.STRATEGIC_PARTNER, PartnerType.OPERATIONAL_PARTNER}
            if any(pt in allowed_types for pt in org.partner_types):
                passed.append("AUTOMOTIVE_PARTNER_ROLE_VALID")
            else:
                blocks.append("Automotive sector requires Distributor, Commercial, Operational, or Strategic partner role.")
        elif "tourism" in sec_lower or "hospitality" in sec_lower:
            refs.append("Law 03-02 Coastal & Tourism Zone Regulation")
            passed.append("TOURISM_SECTOR_BASELINE_CHECKED")
        if required_nae_prefixes:
            if any(any(code.startswith(pref) for pref in required_nae_prefixes) for code in org.nae_codes):
                passed.append("NAE_ACTIVITY_CODE_MATCHED")
            else:
                blocks.append(f"Missing required CNRC NAE activity prefix: {required_nae_prefixes}")
        if blocks:
            decision = GateDecision.INELIGIBLE if org.verification_status == VerificationStatus.REJECTED or not (org.rc_number or org.nif_number or org.lei_code) else GateDecision.CONDITIONAL
        else:
            decision = GateDecision.ELIGIBLE
        return RegulatoryGateAssessment(org_id=org.org_id, sector=sector, decision=decision, passed_checks=passed, blocking_reasons=blocks, regulatory_references=refs)
