
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.persistence.workspace_store import WorkspaceStore
from src.security.jwt import SessionAuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Authenticate the current user using a Bearer access token."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return SessionAuthService().authenticate_request(
            credentials.credentials
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_workspace_membership(
    workspace_id: str = Header(..., alias="X-Workspace-ID"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Require active membership in the requested workspace."""

    workspace_store = WorkspaceStore()

    workspace = workspace_store.get_workspace(workspace_id)

    if workspace is None or not workspace["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this workspace is not permitted.",
        )

    membership = workspace_store.get_membership(
        workspace_id,
        current_user["user_id"],
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this workspace is not permitted.",
        )

    return membership


def require_workspace_roles(
    *allowed_roles: str,
) -> Callable[..., dict[str, Any]]:
    """Create a dependency that restricts access to specified roles."""

    normalized_roles = {
        role.strip().upper()
        for role in allowed_roles
        if isinstance(role, str) and role.strip()
    }

    valid_roles = WorkspaceStore.ROLES

    if not normalized_roles or not normalized_roles.issubset(valid_roles):
        raise ValueError("Invalid or missing workspace roles.")

    def role_dependency(
        membership: dict[str, Any] = Depends(
            get_current_workspace_membership
        ),
    ) -> dict[str, Any]:
        if membership["role"] not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient workspace permissions.",
            )

        return membership

    return role_dependency
