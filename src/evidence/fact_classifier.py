"""P07 Fact and Claim Classification Module for ACCESS ALGERIA.

Explicitly categorizes intelligence records into Fact, Analysis, Recommendation,
and Uncertainty, ensuring unverified claims are never automatically treated as verified facts.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class InformationClassification(str, Enum):
    FACT = "FACT"
    ANALYSIS = "ANALYSIS"
    RECOMMENDATION = "RECOMMENDATION"
    UNCERTAINTY = "UNCERTAINTY"


class VerificationLevel(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTORY = "CONTRADICTORY"
    OUTDATED = "OUTDATED"
    MISSING = "MISSING"


class ClassifiedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    classification: InformationClassification
    verification_status: VerificationLevel = VerificationLevel.UNVERIFIED
    justification: str = Field(min_length=1)


class FactClassifier:
    """Classifies and validates claims against rigorous evidentiary standards."""

    @staticmethod
    def classify_claim(
        *,
        claim_id: str,
        statement: str,
        classification: InformationClassification,
        verification_status: VerificationLevel = VerificationLevel.UNVERIFIED,
        justification: str,
    ) -> ClassifiedClaim:
        # Rule enforcement: recognized source/website alone does not make a claim VERIFIED
        if classification == InformationClassification.FACT and verification_status == VerificationLevel.VERIFIED:
            if not justification or len(justification.strip()) < 10:
                raise ValueError("Verified facts require rigorous, non-trivial evidentiary justification.")

        return ClassifiedClaim(
            claim_id=claim_id,
            statement=statement,
            classification=classification,
            verification_status=verification_status,
            justification=justification,
        )
