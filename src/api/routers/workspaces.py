
from __future__ import annotations

from typing import Any

import duckdb
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies.auth import get_current_user
from src.persistence.workspace_store import WorkspaceStore

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(
        min_length=2,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )


class MemberCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    role: str = Field(pattern=r"^(ADMIN|ANALYST|VIEWER)$")


class MemberRoleUpdateRequest(BaseModel):
    role: str = Field(pattern=r"^(ADMIN|ANALYST|VIEWER)$")


def _get_store() -> WorkspaceStore:
    return WorkspaceStore()


def _require_membership(
    store: WorkspaceStore,
    workspace_id: str,
    user_id: str,
) -> dict[str, Any]:
    workspace = store.get_workspace(workspace_id)

    if workspace is None or not workspace["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    membership = store.get_membership(workspace_id, user_id)

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this workspace is not permitted.",
        )

    return membership


def _require_manager(
    membership: dict[str, Any],
    allowed_roles: set[str],
) -> None:
    if membership["role"] not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient workspace permissions.",
        )


def _require_admin_target(
    actor_role: str,
    target_membership: dict[str, Any] | None,
    new_role: str | None = None,
) -> None:
    """Prevent ADMIN users from managing OWNER or ADMIN memberships."""
    if actor_role == "OWNER":
        return

    if actor_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient workspace permissions.",
        )

    if target_membership is not None:
        if target_membership["role"] not in {"ANALYST", "VIEWER"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ADMIN cannot manage OWNER or ADMIN memberships.",
            )

    if new_role == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ADMIN cannot assign the ADMIN role.",
        )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    store: WorkspaceStore = Depends(_get_store),
) -> dict[str, Any]:
    try:
        return store.create_workspace(
            name=payload.name,
            slug=payload.slug,
            owner_user_id=current_user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except duckdb.ConstraintException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace slug already exists or violates a database constraint.",
        ) from exc


@router.get("")
def list_workspaces(
    current_user: dict[str, Any] = Depends(get_current_user),
    store: WorkspaceStore = Depends(_get_store),
) -> dict[str, Any]:
    workspaces = store.list_user_workspaces(current_user["user_id"])

    return {
        "items": workspaces,
        "count": len(workspaces),
    }


@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    store: WorkspaceStore = Depends(_get_store),
) -> dict[str, Any]:
    _require_membership(
        store,
        workspace_id,
        current_user["user_id"],
    )

    workspace = store.get_workspace(workspace_id)

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    return workspace


@router.get("/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    store: WorkspaceStore = Depends(_get_store),
) -> dict[str, Any]:
    _require_membership(
        store,
        workspace_id,
        current_user["user_id"],
    )

    members = store.list_workspace_members(workspace_id)

    return {
        "items": members,
        "count": len(members),
    }


@router.post(
    "/{workspace_id}/members",
    status_code=status.HTTP_201_CREATED,
)
def add_workspace_member(
    workspace_id: str,
    payload: MemberCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    store: WorkspaceStore = Depends(_get_store),
) -> dict[str, Any]:
    actor = _require_membership(
        store,
        workspace_id,
        current_user["user_id"],
    )

    _require_manager(actor, {"OWNER", "ADMIN"})
    _require_admin_target(
        actor["role"],
        target_membership=None,
        new_role=payload.role,
    )

    try:
        return store.add_member(
            workspace_id=workspace_id,
            user_id=payload.user_id,
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except duckdb.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership could not be created.",
        ) from exc


@router.patch("/{workspace_id}/members/{user_id}")
def update_workspace_member_role(
    workspace_id: str,
    user_id: str,
    payload: MemberRoleUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    store: WorkspaceStore = Depends(_get_store),
) -> dict[str, str]:
    actor = _require_membership(
        store,
        workspace_id,
        current_user["user_id"],
    )

    _require_manager(actor, {"OWNER", "ADMIN"})

    target = store.get_membership(workspace_id, user_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workspace membership not found.",
        )

    _require_admin_target(
        actor["role"],
        target_membership=target,
        new_role=payload.role,
    )

    try:
        store.update_member_role(
            workspace_id,
            user_id,
            payload.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return {"message": "Workspace member role updated."}


@router.delete("/{workspace_id}/members/{user_id}")
def deactivate_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    store: WorkspaceStore = Depends(_get_store),
) -> dict[str, str]:
    actor = _require_membership(
        store,
        workspace_id,
        current_user["user_id"],
    )

    _require_manager(actor, {"OWNER", "ADMIN"})

    target = store.get_membership(workspace_id, user_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workspace membership not found.",
        )

    _require_admin_target(
        actor["role"],
        target_membership=target,
    )

    try:
        store.deactivate_member(workspace_id, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return {"message": "Workspace member deactivated."}
