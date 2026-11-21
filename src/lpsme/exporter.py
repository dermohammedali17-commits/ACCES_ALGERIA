from __future__ import annotations

import json

from src.lpsme.graph import LocalPartnerGraphEngine


class LPSMEGraphExporter:
    """Exports LPSME graph to Cytoscape.js compatible JSON format."""
    def __init__(self, graph: LocalPartnerGraphEngine) -> None:
        self.graph = graph
    def export_cytoscape_json(self) -> str:
        elements = []
        for n in self.graph.nodes:
            elements.append({"data": {"id": n, "label": n}})
        seen_edges = set()
        for edges in self.graph.adjacency_list.values():
            for e in edges:
                if e.relationship_id not in seen_edges:
                    seen_edges.add(e.relationship_id)
                    elements.append({"data": {"id": e.relationship_id, "source": e.source_entity_id, "target": e.target_entity_id, "type": e.relationship_type, "status": e.verification_status}})
        return json.dumps({"elements": elements}, ensure_ascii=False, indent=2)
