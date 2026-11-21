
from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.dependencies import auth as auth_dependencies


class FakeWorkspaceStore:
    def __init__(
        self,
        workspace: dict | None,
        membership: dict | None,
    ) -> None:
        self.workspace = workspace
        self.membership = membership

    def get_workspace(self, workspace_id: str):
        return self.workspace

    def get_membership(self, workspace_id: str, user_id: str):
        return self.membership


@pytest.fixture
def active_membership():
    return {
        "workspace_id": "workspace-1",
        "user_id": "user-1",
        "role": "ANALYST",
        "is_active": True,
    }


def configure_store(
    monkeypatch,
    workspace,
    membership,
):
    fake_store = FakeWorkspaceStore(workspace, membership)

    monkeypatch.setattr(
        auth_dependencies,
        "WorkspaceStore",
        lambda: fake_store,
    )


def test_active_workspace_member_is_authorized(
    monkeypatch,
    active_membership,
):
    configure_store(
        monkeypatch,
        {"workspace_id": "workspace-1", "is_active": True},
        active_membership,
    )

    result = auth_dependencies.get_current_workspace_membership(
        "workspace-1",
        {"user_id": "user-1"},
    )

    assert result == active_membership


@pytest.mark.parametrize(
    "workspace",
    [
        None,
        {"workspace_id": "workspace-1", "is_active": False},
    ],
)
def test_missing_or_inactive_workspace_is_rejected(
    monkeypatch,
    workspace,
):
    configure_store(monkeypatch, workspace, None)

    with pytest.raises(HTTPException) as exc_info:
        auth_dependencies.get_current_workspace_membership(
            "workspace-1",
            {"user_id": "user-1"},
        )

    assert exc_info.value.status_code == 403


def test_non_member_is_rejected(
    monkeypatch,
):
    configure_store(
        monkeypatch,
        {"workspace_id": "workspace-1", "is_active": True},
        None,
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_dependencies.get_current_workspace_membership(
            "workspace-1",
            {"user_id": "user-1"},
        )

    assert exc_info.value.status_code == 403


def test_allowed_workspace_role_is_authorized(
    active_membership,
):
    dependency = auth_dependencies.require_workspace_roles(
        "OWNER",
        "ADMIN",
        "ANALYST",
    )

    result = dependency(active_membership)

    assert result == active_membership


def test_disallowed_workspace_role_is_rejected(
    active_membership,
):
    dependency = auth_dependencies.require_workspace_roles(
        "OWNER",
        "ADMIN",
    )

    with pytest.raises(HTTPException) as exc_info:
        dependency(active_membership)

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "roles",
    [
        (),
        ("SUPERUSER",),
    ],
)
def test_invalid_role_configuration_is_rejected(roles):
    with pytest.raises(ValueError, match="Invalid or missing"):
        auth_dependencies.require_workspace_roles(*roles)
