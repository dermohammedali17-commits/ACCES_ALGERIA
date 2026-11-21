
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.core.config import settings
from src.persistence.auth_store import AuthStore
from src.persistence.workspace_store import WorkspaceStore

client = TestClient(app)


@pytest.fixture
def workspace_api(monkeypatch, tmp_path):
    db_file = str(tmp_path / "workspace_api.duckdb")

    auth_store = AuthStore(db_path=db_file)
    workspace_store = WorkspaceStore(db_path=db_file)

    owner = auth_store.create_user(
        "owner_api@example.com",
        "Strong-Owner-Password-123!",
    )
    admin = auth_store.create_user(
        "admin_api@example.com",
        "Strong-Admin-Password-123!",
    )
    analyst = auth_store.create_user(
        "analyst_api@example.com",
        "Strong-Analyst-Password-123!",
    )
    viewer = auth_store.create_user(
        "viewer_api@example.com",
        "Strong-Viewer-Password-123!",
    )
    outsider = auth_store.create_user(
        "outsider_api@example.com",
        "Strong-Outsider-Password-123!",
    )

    workspace = workspace_store.create_workspace(
        "API Test Workspace",
        "api-test-workspace",
        owner["user_id"],
    )

    workspace_id = workspace["workspace_id"]

    workspace_store.add_member(
        workspace_id,
        admin["user_id"],
        "ADMIN",
    )
    workspace_store.add_member(
        workspace_id,
        analyst["user_id"],
        "ANALYST",
    )
    workspace_store.add_member(
        workspace_id,
        viewer["user_id"],
        "VIEWER",
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
        "src.api.routers.workspaces.WorkspaceStore",
        lambda db_path=None: workspace_store,
    )
    monkeypatch.setattr(
        settings,
        "rate_limiting_enabled",
        False,
    )

    def login(email: str, password: str) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )
        assert response.status_code == 200, response.text

        return {
            "Authorization": (
                f"Bearer {response.json()['access_token']}"
            )
        }

    return {
        "auth_store": auth_store,
        "workspace_store": workspace_store,
        "workspace": workspace,
        "owner": owner,
        "admin": admin,
        "analyst": analyst,
        "viewer": viewer,
        "outsider": outsider,
        "owner_headers": login(
            "owner_api@example.com",
            "Strong-Owner-Password-123!",
        ),
        "admin_headers": login(
            "admin_api@example.com",
            "Strong-Admin-Password-123!",
        ),
        "analyst_headers": login(
            "analyst_api@example.com",
            "Strong-Analyst-Password-123!",
        ),
        "viewer_headers": login(
            "viewer_api@example.com",
            "Strong-Viewer-Password-123!",
        ),
        "outsider_headers": login(
            "outsider_api@example.com",
            "Strong-Outsider-Password-123!",
        ),
    }


def workspace_headers(context, role: str) -> dict[str, str]:
    headers = dict(context[f"{role}_headers"])
    headers["X-Workspace-ID"] = (
        context["workspace"]["workspace_id"]
    )
    return headers


def test_workspace_list_requires_authentication():
    response = client.get("/api/v1/workspaces")

    assert response.status_code == 401


def test_member_can_list_own_workspaces(workspace_api):
    response = client.get(
        "/api/v1/workspaces",
        headers=workspace_headers(workspace_api, "analyst"),
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert (
        response.json()["items"][0]["workspace_id"]
        == workspace_api["workspace"]["workspace_id"]
    )


def test_workspace_creation_creates_owner_membership(workspace_api):
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Second Workspace",
            "slug": "second-workspace",
        },
        headers=workspace_api["owner_headers"],
    )

    assert response.status_code == 201, response.text

    created = response.json()

    membership = workspace_api["workspace_store"].get_membership(
        created["workspace_id"],
        workspace_api["owner"]["user_id"],
    )

    assert membership is not None
    assert membership["role"] == "OWNER"


def test_duplicate_workspace_slug_returns_conflict(workspace_api):
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Duplicate Workspace",
            "slug": "api-test-workspace",
        },
        headers=workspace_api["owner_headers"],
    )

    assert response.status_code == 409


def test_non_member_cannot_read_workspace(workspace_api):
    response = client.get(
        f"/api/v1/workspaces/{workspace_api['workspace']['workspace_id']}",
        headers=workspace_api["outsider_headers"],
    )

    assert response.status_code == 403


def test_member_can_read_workspace(workspace_api):
    response = client.get(
        f"/api/v1/workspaces/{workspace_api['workspace']['workspace_id']}",
        headers=workspace_headers(workspace_api, "viewer"),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "API Test Workspace"


def test_member_can_list_workspace_members(workspace_api):
    response = client.get(
        f"/api/v1/workspaces/{workspace_api['workspace']['workspace_id']}/members",
        headers=workspace_headers(workspace_api, "viewer"),
    )

    assert response.status_code == 200
    assert response.json()["count"] == 4


def test_owner_can_add_member(workspace_api):
    new_user = workspace_api["auth_store"].create_user(
        "new_member@example.com",
        "Strong-New-Member-Password-123!",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_api['workspace']['workspace_id']}/members",
        json={
            "user_id": new_user["user_id"],
            "role": "ANALYST",
        },
        headers=workspace_headers(workspace_api, "owner"),
    )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "ANALYST"


def test_admin_can_add_analyst(workspace_api):
    new_user = workspace_api["auth_store"].create_user(
        "admin_added@example.com",
        "Strong-Admin-Added-Password-123!",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_api['workspace']['workspace_id']}/members",
        json={
            "user_id": new_user["user_id"],
            "role": "ANALYST",
        },
        headers=workspace_headers(workspace_api, "admin"),
    )

    assert response.status_code == 201, response.text


def test_admin_cannot_assign_admin_role(workspace_api):
    new_user = workspace_api["auth_store"].create_user(
        "admin_role@example.com",
        "Strong-Admin-Role-Password-123!",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_api['workspace']['workspace_id']}/members",
        json={
            "user_id": new_user["user_id"],
            "role": "ADMIN",
        },
        headers=workspace_headers(workspace_api, "admin"),
    )

    assert response.status_code == 403


def test_analyst_cannot_add_members(workspace_api):
    new_user = workspace_api["auth_store"].create_user(
        "analyst_added@example.com",
        "Strong-Analyst-Added-Password-123!",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_api['workspace']['workspace_id']}/members",
        json={
            "user_id": new_user["user_id"],
            "role": "VIEWER",
        },
        headers=workspace_headers(workspace_api, "analyst"),
    )

    assert response.status_code == 403


def test_viewer_cannot_add_members(workspace_api):
    new_user = workspace_api["auth_store"].create_user(
        "viewer_added@example.com",
        "Strong-Viewer-Added-Password-123!",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_api['workspace']['workspace_id']}/members",
        json={
            "user_id": new_user["user_id"],
            "role": "ANALYST",
        },
        headers=workspace_headers(workspace_api, "viewer"),
    )

    assert response.status_code == 403


def test_admin_cannot_change_another_admin(workspace_api):
    response = client.patch(
        (
            f"/api/v1/workspaces/"
            f"{workspace_api['workspace']['workspace_id']}/members/"
            f"{workspace_api['owner']['user_id']}"
        ),
        json={"role": "ANALYST"},
        headers=workspace_headers(workspace_api, "admin"),
    )

    assert response.status_code == 403


def test_owner_can_change_analyst_role(workspace_api):
    response = client.patch(
        (
            f"/api/v1/workspaces/"
            f"{workspace_api['workspace']['workspace_id']}/members/"
            f"{workspace_api['analyst']['user_id']}"
        ),
        json={"role": "VIEWER"},
        headers=workspace_headers(workspace_api, "owner"),
    )

    assert response.status_code == 200

    membership = workspace_api["workspace_store"].get_membership(
        workspace_api["workspace"]["workspace_id"],
        workspace_api["analyst"]["user_id"],
    )

    assert membership["role"] == "VIEWER"


def test_admin_can_change_analyst_role(workspace_api):
    response = client.patch(
        (
            f"/api/v1/workspaces/"
            f"{workspace_api['workspace']['workspace_id']}/members/"
            f"{workspace_api['analyst']['user_id']}"
        ),
        json={"role": "VIEWER"},
        headers=workspace_headers(workspace_api, "admin"),
    )

    assert response.status_code == 200


def test_admin_cannot_deactivate_owner(workspace_api):
    response = client.delete(
        (
            f"/api/v1/workspaces/"
            f"{workspace_api['workspace']['workspace_id']}/members/"
            f"{workspace_api['owner']['user_id']}"
        ),
        headers=workspace_headers(workspace_api, "admin"),
    )

    assert response.status_code == 403


def test_owner_can_deactivate_viewer(workspace_api):
    response = client.delete(
        (
            f"/api/v1/workspaces/"
            f"{workspace_api['workspace']['workspace_id']}/members/"
            f"{workspace_api['viewer']['user_id']}"
        ),
        headers=workspace_headers(workspace_api, "owner"),
    )

    assert response.status_code == 200

    membership = workspace_api["workspace_store"].get_membership(
        workspace_api["workspace"]["workspace_id"],
        workspace_api["viewer"]["user_id"],
    )

    assert membership is None


def test_last_owner_cannot_be_deactivated(workspace_api):
    response = client.delete(
        (
            f"/api/v1/workspaces/"
            f"{workspace_api['workspace']['workspace_id']}/members/"
            f"{workspace_api['owner']['user_id']}"
        ),
        headers=workspace_headers(workspace_api, "owner"),
    )

    assert response.status_code == 409


def test_membership_change_invalidates_old_member_token(workspace_api):
    member = workspace_api["analyst"]
    old_headers = workspace_headers(workspace_api, "analyst")

    workspace_api["workspace_store"].update_member_role(
        workspace_api["workspace"]["workspace_id"],
        member["user_id"],
        "VIEWER",
    )

    response = client.get(
        "/api/v1/workspaces",
        headers=old_headers,
    )

    assert response.status_code == 401
