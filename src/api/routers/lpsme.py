
from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.core.config import settings
from src.api.dependencies.auth import require_workspace_roles
from src.lpsme.exporter import LPSMEGraphExporter
from src.lpsme.graph import LocalPartnerGraphEngine
from src.lpsme.models import (
    EvidenceCitation,
    OrganizationRecord,
    StakeholderCategory,
    VerificationStatus,
)
from src.lpsme.storage import LPSMEStorage
from src.services.orchestration import IntelligenceOrchestrator

router = APIRouter(prefix="/lpsme", tags=["LPSME Intelligence"])


class DossierRequest(BaseModel):
    org_id: str = Field(min_length=1)
    legal_name: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    strategic_fit: float = Field(ge=0.0, le=100.0)
    operational_cap: float = Field(ge=0.0, le=100.0)
    regulatory_score: float = Field(ge=0.0, le=100.0)
    rc_number: str | None = None


def _build_workspace_graph(
    storage: LPSMEStorage,
) -> LocalPartnerGraphEngine:
    graph = LocalPartnerGraphEngine()

    for relationship in storage.get_relationships():
        graph.add_relationship(relationship)

    return graph


@router.post("/dossier")
def generate_partner_dossier(
    req: DossierRequest,
    membership: dict[str, Any] = Depends(
        require_workspace_roles("OWNER", "ADMIN", "ANALYST")
    ),
):
    storage = LPSMEStorage(
        settings.lpsme_database_path,
        workspace_id=membership["workspace_id"],
    )

    try:
        graph = _build_workspace_graph(storage)
        orchestrator = IntelligenceOrchestrator(
            graph_engine=graph,
        )

        submission_id = uuid4().hex

        citation = EvidenceCitation(
            citation_id=f"C-USER-{submission_id}",
            source_code="USER_SUBMISSION",
            source_reference=f"API-SUBMISSION:{submission_id}",
            extraction_method="USER_SUBMISSION",
            extracted_excerpt=(
                "Organization information submitted through the authenticated "
                "LPSME API. No independent official registry verification "
                "has been performed."
            ),
            confidence=0.0,
        )

        org = OrganizationRecord(
            org_id=req.org_id,
            legal_name=req.legal_name,
            rc_number=req.rc_number,
            stakeholder_category=(
                StakeholderCategory.COMMERCIAL_STAKEHOLDER
            ),
            verification_status=VerificationStatus.DISCOVERED,
            citations=[citation],
        )

        dossier = orchestrator.process_partner_dossier(
            org,
            req.sector,
            req.strategic_fit,
            req.operational_cap,
            req.regulatory_score,
        )

        storage.upsert_organization(dossier.organization)

        return dossier.model_dump()

    finally:
        storage.close()


@router.get("/graph/export")
def export_graph(
    membership: dict[str, Any] = Depends(
        require_workspace_roles("OWNER", "ADMIN", "ANALYST")
    ),
):
    storage = LPSMEStorage(
        settings.lpsme_database_path,
        workspace_id=membership["workspace_id"],
    )

    try:
        graph = _build_workspace_graph(storage)
        exporter = LPSMEGraphExporter(graph)

        return exporter.export_cytoscape_json()

    finally:
        storage.close()
