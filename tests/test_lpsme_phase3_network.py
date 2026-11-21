from __future__ import annotations

from src.lpsme.graph import LocalPartnerGraphEngine
from src.lpsme.models import EvidenceCitation, RelationshipClaim, VerificationStatus
from src.lpsme.network import LPSMENetworkIntelligence


def test_lpsme_network_intelligence() -> None:
    cit = EvidenceCitation(citation_id="C1", source_code="CNRC_SIDJILCOM", source_reference="REF-1", extraction_method="DIRECT", extracted_excerpt="Edge", confidence=0.95)
    rel = RelationshipClaim(relationship_id="R1", source_entity_id="ORG-HUB", target_entity_id="ORG-PARTNER-1", relationship_type="PARTNER", verification_status=VerificationStatus.VERIFIED, citations=[cit])
    g = LocalPartnerGraphEngine()
    g.add_relationship(rel)
    net = LPSMENetworkIntelligence(g)
    metrics = net.analyze_entity("ORG-HUB")
    assert metrics.degree == 1
    assert "ORG-PARTNER-1" in metrics.connected_partners
    assert metrics.centrality_score > 0.0
