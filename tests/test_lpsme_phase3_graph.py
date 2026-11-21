from __future__ import annotations

from src.lpsme.graph import LocalPartnerGraphEngine
from src.lpsme.models import EvidenceCitation, RelationshipClaim, VerificationStatus


def test_local_partner_graph_engine() -> None:
    cit = EvidenceCitation(citation_id="C1", source_code="CNRC_SIDJILCOM", source_reference="REF-1", extraction_method="DIRECT", extracted_excerpt="Edge", confidence=0.95)
    rel1 = RelationshipClaim(relationship_id="R1", source_entity_id="ORG-1", target_entity_id="ORG-2", relationship_type="DISTRIBUTOR", verification_status=VerificationStatus.VERIFIED, citations=[cit])
    rel2 = RelationshipClaim(relationship_id="R2", source_entity_id="ORG-1", target_entity_id="INST-AAPI", relationship_type="REGISTERED", verification_status=VerificationStatus.VERIFIED, citations=[cit])
    g = LocalPartnerGraphEngine()
    g.add_relationship(rel1)
    g.add_relationship(rel2)
    assert "ORG-2" in g.get_neighbors("ORG-1")
    assert "INST-AAPI" in g.get_neighbors("ORG-1")
    centrality = g.compute_degree_centrality()
    assert centrality["ORG-1"] == 1.0
