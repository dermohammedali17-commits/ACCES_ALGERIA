from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.core.config import settings
from src.lpsme.storage import LPSMEStorage
from src.persistence.auth_store import AuthStore
from src.persistence.workspace_store import WorkspaceStore

client = TestClient(app)


def login(email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def workspace_context(monkeypatch, tmp_path):
    db_file = tmp_path / "lpsme_auth_test.duckdb"
    lpsme_db_file = tmp_path / "lpsme_intelligence_test.duckdb"

    monkeypatch.setattr(
        settings,
        "lpsme_database_path",
        str(lpsme_db_file),
    )

    auth_store = AuthStore(db_path=str(db_file))
    workspace_store = WorkspaceStore(db_path=str(db_file))

    owner = auth_store.create_user(
        "lpsme_test@example.com",
        "SecurePass123!",
    )

    workspace = workspace_store.create_workspace(
        name="LPSME Test Workspace",
        slug="lpsme-test-workspace",
        owner_user_id=owner["user_id"],
    )

    monkeypatch.setattr(
        "src.api.routers.auth.AuthStore",
        lambda db_path=None: auth_store,
    )

    monkeypatch.setattr(
        "src.security.jwt.AuthStore",
        lambda db_path=None: auth_store,
    )

    monkeypatch.setattr(
        "src.api.dependencies.auth.WorkspaceStore",
        lambda db_path=None: workspace_store,
    )

    monkeypatch.setattr(settings, "rate_limiting_enabled", False)

    owner_headers = login(
        "lpsme_test@example.com",
        "SecurePass123!",
    )

    owner_headers["X-Workspace-ID"] = workspace["workspace_id"]

    return {
        "auth_store": auth_store,
        "workspace_store": workspace_store,
        "workspace": workspace,
        "owner": owner,
        "owner_headers": owner_headers,
    }


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_lpsme_dossier_requires_authentication(workspace_context):
    payload = {
        "org_id": "ORG-API-1",
        "legal_name": "SARL API Motors",
        "sector": "Luxury Automotive",
        "strategic_fit": 88.0,
        "operational_cap": 90.0,
        "regulatory_score": 100.0,
        "rc_number": "16/00-999999",
    }

    response = client.post(
        "/api/v1/lpsme/dossier",
        json=payload,
        headers={"X-Workspace-ID": workspace_context["workspace"]["workspace_id"]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials."


def test_lpsme_dossier_requires_workspace_header(workspace_context):
    headers = {"Authorization": workspace_context["owner_headers"]["Authorization"]}

    response = client.post(
        "/api/v1/lpsme/dossier",
        json={
            "org_id": "ORG-API-1",
            "legal_name": "SARL API Motors",
            "sector": "Luxury Automotive",
            "strategic_fit": 88.0,
            "operational_cap": 90.0,
            "regulatory_score": 100.0,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_lpsme_dossier_endpoint_owner_access(workspace_context):
    response = client.post(
        "/api/v1/lpsme/dossier",
        json={
            "org_id": "ORG-API-1",
            "legal_name": "SARL API Motors",
            "sector": "Luxury Automotive",
            "strategic_fit": 88.0,
            "operational_cap": 90.0,
            "regulatory_score": 100.0,
            "rc_number": "16/00-999999",
        },
        headers=workspace_context["owner_headers"],
    )

    assert response.status_code == 200

    data = response.json()

    assert data["scorecard"]["composite_score"] > 80.0
    assert data["regulatory_assessment"]["decision"] in (
        "ELIGIBLE",
        "CONDITIONAL",
    )


def test_lpsme_graph_export_requires_authentication(workspace_context):
    response = client.get(
        "/api/v1/lpsme/graph/export",
        headers={"X-Workspace-ID": workspace_context["workspace"]["workspace_id"]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials."


def test_lpsme_graph_export_owner_access(workspace_context):
    response = client.get(
        "/api/v1/lpsme/graph/export",
        headers=workspace_context["owner_headers"],
    )

    assert response.status_code == 200


def test_non_member_cannot_access_workspace(workspace_context):
    auth_store = workspace_context["auth_store"]

    outsider = auth_store.create_user(
        "outsider@example.com",
        "SecurePass123!",
    )

    outsider_headers = login(
        "outsider@example.com",
        "SecurePass123!",
    )
    outsider_headers["X-Workspace-ID"] = workspace_context["workspace"]["workspace_id"]

    response = client.get(
        "/api/v1/lpsme/graph/export",
        headers=outsider_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == ("Access to this workspace is not permitted.")


def test_viewer_cannot_generate_dossier(workspace_context):
    auth_store = workspace_context["auth_store"]
    workspace_store = workspace_context["workspace_store"]
    workspace_id = workspace_context["workspace"]["workspace_id"]

    viewer = auth_store.create_user(
        "viewer@example.com",
        "SecurePass123!",
    )

    workspace_store.add_member(
        workspace_id=workspace_id,
        user_id=viewer["user_id"],
        role="VIEWER",
    )

    viewer_headers = login(
        "viewer@example.com",
        "SecurePass123!",
    )
    viewer_headers["X-Workspace-ID"] = workspace_id

    response = client.post(
        "/api/v1/lpsme/dossier",
        json={
            "org_id": "ORG-VIEWER-1",
            "legal_name": "Viewer Test Company",
            "sector": "Luxury Automotive",
            "strategic_fit": 80.0,
            "operational_cap": 80.0,
            "regulatory_score": 80.0,
        },
        headers=viewer_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == ("Insufficient workspace permissions.")


def test_viewer_cannot_export_graph(workspace_context):
    auth_store = workspace_context["auth_store"]
    workspace_store = workspace_context["workspace_store"]
    workspace_id = workspace_context["workspace"]["workspace_id"]

    viewer = auth_store.create_user(
        "viewer_graph@example.com",
        "SecurePass123!",
    )

    workspace_store.add_member(
        workspace_id=workspace_id,
        user_id=viewer["user_id"],
        role="VIEWER",
    )

    viewer_headers = login(
        "viewer_graph@example.com",
        "SecurePass123!",
    )
    viewer_headers["X-Workspace-ID"] = workspace_id

    response = client.get(
        "/api/v1/lpsme/graph/export",
        headers=viewer_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == ("Insufficient workspace permissions.")


def test_lpsme_dossier_isolated_between_workspaces(workspace_context):
    workspace_store = workspace_context["workspace_store"]
    owner = workspace_context["owner"]
    workspace_a = workspace_context["workspace"]

    workspace_b = workspace_store.create_workspace(
        name="Second LPSME Test Workspace",
        slug="second-lpsme-test-workspace",
        owner_user_id=owner["user_id"],
    )

    fresh_headers = login(
        "lpsme_test@example.com",
        "SecurePass123!",
    )

    headers_a = dict(fresh_headers)
    headers_a["X-Workspace-ID"] = workspace_a["workspace_id"]

    headers_b = dict(fresh_headers)
    headers_b["X-Workspace-ID"] = workspace_b["workspace_id"]

    payload_a = {
        "org_id": "ORG-SHARED-001",
        "legal_name": "Company Alpha",
        "sector": "Luxury Automotive",
        "strategic_fit": 80.0,
        "operational_cap": 85.0,
        "regulatory_score": 90.0,
    }

    payload_b = {
        "org_id": "ORG-SHARED-001",
        "legal_name": "Company Beta",
        "sector": "Luxury Automotive",
        "strategic_fit": 75.0,
        "operational_cap": 80.0,
        "regulatory_score": 85.0,
    }

    response_a = client.post(
        "/api/v1/lpsme/dossier",
        json=payload_a,
        headers=headers_a,
    )

    response_b = client.post(
        "/api/v1/lpsme/dossier",
        json=payload_b,
        headers=headers_b,
    )

    assert response_a.status_code == 200, response_a.text
    assert response_b.status_code == 200, response_b.text

    with LPSMEStorage(
        settings.lpsme_database_path,
        workspace_id=workspace_a["workspace_id"],
    ) as storage_a:
        organization_a = storage_a.get_organization("ORG-SHARED-001")

    with LPSMEStorage(
        settings.lpsme_database_path,
        workspace_id=workspace_b["workspace_id"],
    ) as storage_b:
        organization_b = storage_b.get_organization("ORG-SHARED-001")

    assert organization_a is not None
    assert organization_b is not None

    assert organization_a.legal_name == "Company Alpha"
    assert organization_b.legal_name == "Company Beta"
