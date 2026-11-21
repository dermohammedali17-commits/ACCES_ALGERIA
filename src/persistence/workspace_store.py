from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import duckdb

from src.api.core.config import settings


class WorkspaceStore:
    """Persistent workspace and membership storage backed by DuckDB."""

    ROLES = frozenset({"OWNER", "ADMIN", "ANALYST", "VIEWER"})
    ASSIGNABLE_ROLES = frozenset({"ADMIN", "ANALYST", "VIEWER"})

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = str(db_path or settings.auth_database_path)

        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        self._initialize_schema()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self.db_path)

    def _initialize_schema(self) -> None:
        conn = self._get_connection()

        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL UNIQUE,
                    created_by VARCHAR NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspace_memberships (
                    workspace_id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    role VARCHAR NOT NULL
                        CHECK (role IN ('OWNER', 'ADMIN', 'ANALYST', 'VIEWER')),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (workspace_id, user_id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_workspace_members_user
                ON workspace_memberships(user_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_workspace_members_workspace
                ON workspace_memberships(workspace_id)
            """)

        finally:
            conn.close()

    @staticmethod
    def _fetch_dict(
        conn: duckdb.DuckDBPyConnection,
        row: tuple[Any, ...] | None,
    ) -> dict[str, Any] | None:
        if row is None:
            return None

        columns = [item[0] for item in conn.description]
        return dict(zip(columns, row, strict=True))

    @staticmethod
    def _validate_text(value: str, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string.")
        return value.strip()

    @classmethod
    def _validate_role(cls, role: str) -> str:
        normalized = cls._validate_text(role, "role").upper()

        if normalized not in cls.ROLES:
            raise ValueError("Unsupported workspace role.")

        return normalized

    @staticmethod
    def _bump_permissions_version(
        conn: duckdb.DuckDBPyConnection,
        user_id: str,
    ) -> None:
        conn.execute(
            """
            UPDATE users
            SET permissions_version = permissions_version + 1
            WHERE user_id = ?
            """,
            [user_id],
        )

    def create_workspace(
        self,
        name: str,
        slug: str,
        owner_user_id: str,
    ) -> dict[str, Any]:
        name = self._validate_text(name, "name")
        slug = self._validate_text(slug, "slug").casefold()
        owner_user_id = self._validate_text(
            owner_user_id,
            "owner_user_id",
        )

        if any(char.isspace() for char in slug):
            raise ValueError("Workspace slug cannot contain whitespace.")

        workspace_id = str(uuid.uuid4())
        conn = self._get_connection()

        try:
            conn.execute("BEGIN TRANSACTION")

            user = conn.execute(
                """
                SELECT user_id
                FROM users
                WHERE user_id = ?
                  AND is_active = TRUE
                """,
                [owner_user_id],
            ).fetchone()

            if user is None:
                raise ValueError("Workspace owner is not an active user.")

            conn.execute(
                """
                INSERT INTO workspaces (
                    workspace_id,
                    name,
                    slug,
                    created_by
                )
                VALUES (?, ?, ?, ?)
                """,
                [workspace_id, name, slug, owner_user_id],
            )

            conn.execute(
                """
                INSERT INTO workspace_memberships (
                    workspace_id,
                    user_id,
                    role,
                    is_active
                )
                VALUES (?, ?, 'OWNER', TRUE)
                """,
                [workspace_id, owner_user_id],
            )

            self._bump_permissions_version(conn, owner_user_id)
            conn.execute("COMMIT")

        except Exception:
            conn.execute("ROLLBACK")
            raise

        finally:
            conn.close()

        workspace = self.get_workspace(workspace_id)

        if workspace is None:
            raise RuntimeError("Workspace creation could not be verified.")

        return workspace

    def get_workspace(
        self,
        workspace_id: str,
    ) -> dict[str, Any] | None:
        conn = self._get_connection()

        try:
            row = conn.execute(
                """
                SELECT
                    workspace_id,
                    name,
                    slug,
                    created_by,
                    is_active,
                    created_at
                FROM workspaces
                WHERE workspace_id = ?
                """,
                [workspace_id],
            ).fetchone()

            return self._fetch_dict(conn, row)

        finally:
            conn.close()

    def get_membership(
        self,
        workspace_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        conn = self._get_connection()

        try:
            row = conn.execute(
                """
                SELECT
                    workspace_id,
                    user_id,
                    role,
                    is_active,
                    created_at,
                    updated_at
                FROM workspace_memberships
                WHERE workspace_id = ?
                  AND user_id = ?
                  AND is_active = TRUE
                """,
                [workspace_id, user_id],
            ).fetchone()

            return self._fetch_dict(conn, row)

        finally:
            conn.close()

    def add_member(
        self,
        workspace_id: str,
        user_id: str,
        role: str,
    ) -> dict[str, Any]:
        role = self._validate_role(role)

        if role not in self.ASSIGNABLE_ROLES:
            raise ValueError(
                "OWNER role can only be assigned during workspace creation."
            )

        conn = self._get_connection()

        try:
            conn.execute("BEGIN TRANSACTION")

            workspace = conn.execute(
                """
                SELECT workspace_id
                FROM workspaces
                WHERE workspace_id = ?
                  AND is_active = TRUE
                """,
                [workspace_id],
            ).fetchone()

            if workspace is None:
                raise ValueError("Workspace does not exist or is inactive.")

            user = conn.execute(
                """
                SELECT user_id
                FROM users
                WHERE user_id = ?
                  AND is_active = TRUE
                """,
                [user_id],
            ).fetchone()

            if user is None:
                raise ValueError("Member is not an active user.")

            existing = conn.execute(
                """
                SELECT is_active
                FROM workspace_memberships
                WHERE workspace_id = ?
                  AND user_id = ?
                """,
                [workspace_id, user_id],
            ).fetchone()

            if existing is not None and existing[0]:
                raise ValueError("User is already an active workspace member.")

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO workspace_memberships (
                        workspace_id,
                        user_id,
                        role
                    )
                    VALUES (?, ?, ?)
                    """,
                    [workspace_id, user_id, role],
                )
            else:
                conn.execute(
                    """
                    UPDATE workspace_memberships
                    SET role = ?,
                        is_active = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE workspace_id = ?
                      AND user_id = ?
                    """,
                    [role, workspace_id, user_id],
                )

            self._bump_permissions_version(conn, user_id)
            conn.execute("COMMIT")

        except Exception:
            conn.execute("ROLLBACK")
            raise

        finally:
            conn.close()

        membership = self.get_membership(workspace_id, user_id)

        if membership is None:
            raise RuntimeError("Membership creation could not be verified.")

        return membership

    def update_member_role(
        self,
        workspace_id: str,
        user_id: str,
        new_role: str,
    ) -> None:
        new_role = self._validate_role(new_role)

        if new_role == "OWNER":
            raise ValueError("OWNER role cannot be assigned through role updates.")

        conn = self._get_connection()

        try:
            conn.execute("BEGIN TRANSACTION")

            member = conn.execute(
                """
                SELECT role
                FROM workspace_memberships
                WHERE workspace_id = ?
                  AND user_id = ?
                  AND is_active = TRUE
                """,
                [workspace_id, user_id],
            ).fetchone()

            if member is None:
                raise ValueError("Active workspace membership not found.")

            old_role = member[0]

            if old_role == "OWNER":
                owner_count = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM workspace_memberships
                    WHERE workspace_id = ?
                      AND role = 'OWNER'
                      AND is_active = TRUE
                    """,
                    [workspace_id],
                ).fetchone()[0]

                if owner_count <= 1:
                    raise ValueError("The last workspace owner cannot be demoted.")

            conn.execute(
                """
                UPDATE workspace_memberships
                SET role = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE workspace_id = ?
                  AND user_id = ?
                """,
                [new_role, workspace_id, user_id],
            )

            self._bump_permissions_version(conn, user_id)
            conn.execute("COMMIT")

        except Exception:
            conn.execute("ROLLBACK")
            raise

        finally:
            conn.close()

    def deactivate_member(
        self,
        workspace_id: str,
        user_id: str,
    ) -> None:
        conn = self._get_connection()

        try:
            conn.execute("BEGIN TRANSACTION")

            member = conn.execute(
                """
                SELECT role
                FROM workspace_memberships
                WHERE workspace_id = ?
                  AND user_id = ?
                  AND is_active = TRUE
                """,
                [workspace_id, user_id],
            ).fetchone()

            if member is None:
                raise ValueError("Active workspace membership not found.")

            if member[0] == "OWNER":
                owner_count = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM workspace_memberships
                    WHERE workspace_id = ?
                      AND role = 'OWNER'
                      AND is_active = TRUE
                    """,
                    [workspace_id],
                ).fetchone()[0]

                if owner_count <= 1:
                    raise ValueError("The last workspace owner cannot be deactivated.")

            conn.execute(
                """
                UPDATE workspace_memberships
                SET is_active = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE workspace_id = ?
                  AND user_id = ?
                """,
                [workspace_id, user_id],
            )

            self._bump_permissions_version(conn, user_id)
            conn.execute("COMMIT")

        except Exception:
            conn.execute("ROLLBACK")
            raise

        finally:
            conn.close()

    def list_user_workspaces(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """List active workspaces belonging to an active user."""
        user_id = self._validate_text(user_id, "user_id")
        conn = self._get_connection()

        try:
            rows = conn.execute(
                """
                SELECT
                    w.workspace_id,
                    w.name,
                    w.slug,
                    w.created_by,
                    w.created_at,
                    m.role,
                    m.created_at AS membership_created_at,
                    m.updated_at AS membership_updated_at
                FROM workspace_memberships AS m
                INNER JOIN workspaces AS w
                    ON w.workspace_id = m.workspace_id
                INNER JOIN users AS u
                    ON u.user_id = m.user_id
                WHERE m.user_id = ?
                  AND m.is_active = TRUE
                  AND w.is_active = TRUE
                  AND u.is_active = TRUE
                ORDER BY w.created_at DESC, w.name ASC
                """,
                [user_id],
            ).fetchall()

            columns = [item[0] for item in conn.description]

            return [dict(zip(columns, row, strict=True)) for row in rows]

        finally:
            conn.close()

    def list_workspace_members(
        self,
        workspace_id: str,
    ) -> list[dict[str, Any]]:
        """List active members of a workspace without exposing credentials."""
        conn = self._get_connection()

        try:
            rows = conn.execute(
                """
                SELECT
                    m.workspace_id,
                    m.user_id,
                    u.email,
                    m.role,
                    m.created_at,
                    m.updated_at
                FROM workspace_memberships AS m
                INNER JOIN users AS u
                    ON u.user_id = m.user_id
                WHERE m.workspace_id = ?
                  AND m.is_active = TRUE
                  AND u.is_active = TRUE
                ORDER BY
                    CASE m.role
                        WHEN 'OWNER' THEN 1
                        WHEN 'ADMIN' THEN 2
                        WHEN 'ANALYST' THEN 3
                        WHEN 'VIEWER' THEN 4
                    END,
                    u.email
                """,
                [workspace_id],
            ).fetchall()

            columns = [item[0] for item in conn.description]

            return [dict(zip(columns, row, strict=True)) for row in rows]

        finally:
            conn.close()
