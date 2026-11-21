
from __future__ import annotations

import pytest

from src.persistence.auth_store import AuthStore
from src.persistence.workspace_store import WorkspaceStore


@pytest.fixture
def stores(tmp_path):
    db_path = str(tmp_path / "workspace_test.duckdb")

    auth_store = AuthStore(db_path=db_path)
    workspace_store = WorkspaceStore(db_path=db_path)

    owner = auth_store.create_user(
        email="owner@example.com",
        password="Strong-Test-Password-123!",
    )

    yield auth_store, workspace_store, owner["user_id"]


def test_create_workspace_creates_owner_membership(stores):
    _auth, workspaces, owner_id = stores

    workspace = workspaces.create_workspace(
        name="Access Algeria Internal",
        slug="access-algeria-internal",
        owner_user_id=owner_id,
    )

    membership = workspaces.get_membership(
        workspace["workspace_id"],
        owner_id,
    )

    assert workspace["name"] == "Access Algeria Internal"
    assert membership is not None
    assert membership["role"] == "OWNER"


def test_add_member_and_list_workspaces(stores):
    auth, workspaces, owner_id = stores

    member = auth.create_user(
        email="analyst@example.com",
        password="Strong-Test-Password-456!",
    )
    member_id = member["user_id"]

    workspace = workspaces.create_workspace(
        "Access Algeria",
        "access-algeria",
        owner_id,
    )

    membership = workspaces.add_member(
        workspace["workspace_id"],
        member_id,
        "ANALYST",
    )

    assert membership["role"] == "ANALYST"

    user_workspaces = workspaces.list_user_workspaces(member_id)

    assert len(user_workspaces) == 1
    assert user_workspaces[0]["workspace_id"] == workspace["workspace_id"]


def test_user_cannot_be_added_twice(stores):
    auth, workspaces, owner_id = stores

    member = auth.create_user(
        email="duplicate@example.com",
        password="Strong-Test-Password-789!",
    )
    member_id = member["user_id"]

    workspace = workspaces.create_workspace(
        "Access Algeria",
        "access-algeria",
        owner_id,
    )

    workspaces.add_member(
        workspace["workspace_id"],
        member_id,
        "VIEWER",
    )

    with pytest.raises(ValueError, match="already an active"):
        workspaces.add_member(
            workspace["workspace_id"],
            member_id,
            "ANALYST",
        )


def test_owner_cannot_be_assigned_through_role_update(stores):
    auth, workspaces, owner_id = stores

    member = auth.create_user(
        email="member@example.com",
        password="Strong-Test-Password-000!",
    )
    member_id = member["user_id"]

    workspace = workspaces.create_workspace(
        "Access Algeria",
        "access-algeria",
        owner_id,
    )

    workspaces.add_member(
        workspace["workspace_id"],
        member_id,
        "ANALYST",
    )

    with pytest.raises(ValueError, match="OWNER role cannot"):
        workspaces.update_member_role(
            workspace["workspace_id"],
            member_id,
            "OWNER",
        )


def test_last_owner_cannot_be_deactivated(stores):
    _auth, workspaces, owner_id = stores

    workspace = workspaces.create_workspace(
        "Access Algeria",
        "access-algeria",
        owner_id,
    )

    with pytest.raises(ValueError, match="last workspace owner"):
        workspaces.deactivate_member(
            workspace["workspace_id"],
            owner_id,
        )


def test_membership_changes_increment_permissions_version(stores):
    auth, workspaces, owner_id = stores

    member = auth.create_user(
        email="version@example.com",
        password="Strong-Test-Password-999!",
    )
    member_id = member["user_id"]

    before = auth.get_user_by_id(member_id)["permissions_version"]

    workspace = workspaces.create_workspace(
        "Access Algeria",
        "access-algeria",
        owner_id,
    )

    workspaces.add_member(
        workspace["workspace_id"],
        member_id,
        "ANALYST",
    )

    after = auth.get_user_by_id(member_id)["permissions_version"]

    assert after == before + 1
