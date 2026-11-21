from __future__ import annotations

from src.lpsme.dossier import LPSMEDossierBuilder
from src.lpsme.exporter import LPSMEGraphExporter
from src.lpsme.graph import LocalPartnerGraphEngine
from src.lpsme.models import (
    EvidenceCitation,
    OrganizationRecord,
    PartnerType,
    RelationshipClaim,
    StakeholderCategory,
    VerificationStatus,
)
from src.lpsme.network import NetworkMetrics
from src.lpsme.regulatory import GateDecision, RegulatoryGateAssessment
from src.lpsme.scoring import PartnerScoreCard


def test_lpsme_phase4_dossier_and_export() -> None:
    cit = EvidenceCitation(citation_id="C1", source_code="CNRC_SIDJILCOM", source_reference="RC-1", extraction_method="OFFICIAL_REGISTRY_LOOKUP", extracted_excerpt="Extract", confidence=0.95)
    org = OrganizationRecord(org_id="ORG-1", legal_name="SPA Test Algeria", rc_number="16/00-111", stakeholder_category=StakeholderCategory.COMMERCIAL_STAKEHOLDER, verification_status=VerificationStatus.VERIFIED, citations=[cit])
    scorecard = PartnerScoreCard(org_id="ORG-1", strategic_fit_score=90.0, operational_capability_score=85.0, evidence_confidence_score=0.95, regulatory_compliance_score=100.0, composite_score=91.5, scoring_rationale="Solid")
    reg = RegulatoryGateAssessment(org_id="ORG-1", sector="Luxury Automotive", decision=GateDecision.ELIGIBLE, passed_checks=["OK"])
    net = NetworkMetrics(entity_id="ORG-1", degree=1, centrality_score=1.0, connected_partners=["ORG-2"])
    builder = LPSMEDossierBuilder()
    dossier = builder.build_dossier(org, scorecard, reg, net)
    assert dossier.scorecard.composite_score == 91.5
    assert "SPA Test Algeria" in dossier.executive_summary
    rel = RelationshipClaim(relationship_id="R1", source_entity_id="ORG-1", target_entity_id="ORG-2", relationship_type="PARTNER", verification_status=VerificationStatus.VERIFIED, citations=[cit])
    g = LocalPartnerGraphEngine()
    g.add_relationship(rel)
    exporter = LPSMEGraphExporter(g)
    js_data = exporter.export_cytoscape_json()
    assert "ORG-1" in js_data
    assert "ORG-2" in js_data
