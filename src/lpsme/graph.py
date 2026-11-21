from __future__ import annotations

from dataclasses import dataclass, field

from src.lpsme.models import RelationshipClaim


@dataclass
class GraphEdge:
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    verification_status: str

class LocalPartnerGraphEngine:
    """Pure Python standard library graph engine for LPSME stakeholder networks."""
    def __init__(self) -> None:
        self.adjacency_list: dict[str, list[GraphEdge]] = {}
        self.nodes: set[str] = set()

    def add_relationship(self, rel: RelationshipClaim) -> None:
        edge = GraphEdge(relationship_id=rel.relationship_id, source_entity_id=rel.source_entity_id, target_entity_id=rel.target_entity_id, relationship_type=rel.relationship_type, verification_status=rel.verification_status.value)
        self.nodes.add(rel.source_entity_id)
        self.nodes.add(rel.target_entity_id)
        self.adjacency_list.setdefault(rel.source_entity_id, []).append(edge)
        self.adjacency_list.setdefault(rel.target_entity_id, []).append(edge)

    def get_neighbors(self, node_id: str) -> list[str]:
        edges = self.adjacency_list.get(node_id, [])
        neighbors = set()
        for e in edges:
            if e.source_entity_id == node_id:
                neighbors.add(e.target_entity_id)
            else:
                neighbors.add(e.source_entity_id)
        return sorted(list(neighbors))

    def compute_degree_centrality(self) -> dict[str, float]:
        total_nodes = len(self.nodes)
        if total_nodes <= 1:
            return {n: 1.0 for n in self.nodes}
        centrality = {}
        for n in self.nodes:
            deg = len(self.get_neighbors(n))
            centrality[n] = round(deg / (total_nodes - 1), 4)
        return centrality
