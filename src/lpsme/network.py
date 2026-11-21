from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.lpsme.graph import LocalPartnerGraphEngine


class NetworkMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    entity_id: str = Field(min_length=1)
    degree: int = Field(ge=0)
    centrality_score: float = Field(ge=0.0, le=1.0)
    connected_partners: list[str] = Field(default_factory=list)

class LPSMENetworkIntelligence:
    """Analyzes stakeholder connectivity, clustering, and network centrality for LPSME."""
    def __init__(self, graph: LocalPartnerGraphEngine) -> None:
        self.graph = graph
    def analyze_entity(self, entity_id: str) -> NetworkMetrics:
        neighbors = self.graph.get_neighbors(entity_id)
        centrality_dict = self.graph.compute_degree_centrality()
        cent_score = centrality_dict.get(entity_id, 0.0)
        return NetworkMetrics(entity_id=entity_id, degree=len(neighbors), centrality_score=cent_score, connected_partners=neighbors)
