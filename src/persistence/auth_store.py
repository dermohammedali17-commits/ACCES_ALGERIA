from __future__ import annotations

import secrets
import uuid
from pathlib import Path
from typing import Any

import duckdb
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from src.api.core.config import settings


class AuthStore:
    """Persistent authentication storage backed by DuckDB."""

    _password_hasher = PasswordHasher()
    _dummy_password = secrets.token_urlsafe(32)
    _dummy_password_hash = _password_hasher.hash(_dummy_password)

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
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR PRIMARY KEY,
                    email VARCHAR NOT NULL UNIQUE,
                    password_hash VARCHAR NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    permissions_version INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    revoked_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id
                ON sessions(user_id)
            """)

        finally:
            conn.close()

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().casefold()

    @staticmethod
    def _row_to_dict(
        conn: duckdb.DuckDBPyConnection,
        row: tuple[Any, ...] | None,
    ) -> dict[str, Any] | None:
        if row is None:
            return None

        columns = [item[0] for item in conn.description]
        return dict(zip(columns, row, strict=True))

    def create_user(
        self,
        email: str,
        password: str,
    ) -> dict[str, Any]:
        normalized_email = self.normalize_email(email)

        if not normalized_email:
            raise ValueError("Email cannot be empty.")

        if not password:
            raise ValueError("Password cannot be empty.")

        password_hash = self._password_hasher.hash(password)
        user_id = str(uuid.uuid4())

        conn = self._get_connection()

        try:
            conn.execute(
                """
                INSERT INTO users (
                    user_id,
                    email,
                    password_hash,
                    is_active,
                    permissions_version
                )
                VALUES (?, ?, ?, TRUE, 1)
                """,
                [user_id, normalized_email, password_hash],
            )
        finally:
            conn.close()

        user = self.get_user_by_email(normalized_email)

        if user is None:
            raise RuntimeError("User creation could not be verified.")

        return user

    def get_user_by_email(
        self,
        email: str,
    ) -> dict[str, Any] | None:
        normalized_email = self.normalize_email(email)

        conn = self._get_connection()

        try:
            row = conn.execute(
                """
                SELECT
                    user_id,
                    email,
                    is_active,
                    permissions_version,
                    created_at
                FROM users
                WHERE email = ?
                """,
                [normalized_email],
            ).fetchone()

            return self._row_to_dict(conn, row)

        finally:
            conn.close()

    def get_user_by_id(
        self,
        user_id: str,
    ) -> dict[str, Any] | None:
        conn = self._get_connection()

        try:
            row = conn.execute(
                """
                SELECT
                    user_id,
                    email,
                    is_active,
                    permissions_version,
                    created_at
                FROM users
                WHERE user_id = ?
                """,
                [user_id],
            ).fetchone()

            return self._row_to_dict(conn, row)

        finally:
            conn.close()

    def verify_user_password(
        self,
        email: str,
        password: str,
    ) -> bool:
        normalized_email = self.normalize_email(email)

        conn = self._get_connection()

        try:
            row = conn.execute(
                """
                SELECT password_hash
                FROM users
                WHERE email = ?
                """,
                [normalized_email],
            ).fetchone()

        finally:
            conn.close()

        if row is None:
            self._verify_dummy_password(password)
            return False

        stored_hash = row[0]

        try:
            verified = self._password_hasher.verify(
                stored_hash,
                password,
            )
        except VerifyMismatchError:
            return False
        except (VerificationError, InvalidHashError):
            self._verify_dummy_password(password)
            return False

        if not verified:
            return False

        if self._password_hasher.check_needs_rehash(stored_hash):
            updated_hash = self._password_hasher.hash(password)

            conn = self._get_connection()

            try:
                conn.execute(
                    """
                    UPDATE users
                    SET password_hash = ?
                    WHERE email = ?
                      AND password_hash = ?
                    """,
                    [
                        updated_hash,
                        normalized_email,
                        stored_hash,
                    ],
                )

            finally:
                conn.close()

        return True

    def _verify_dummy_password(self, password: str) -> None:
        try:
            self._password_hasher.verify(
                self._dummy_password_hash,
                password,
            )
        except (
            VerifyMismatchError,
            VerificationError,
            InvalidHashError,
        ):
            pass

    def create_session(
        self,
        user_id: str,
        expires_at: str,
    ) -> str:
        session_id = str(uuid.uuid4())

        conn = self._get_connection()

        try:
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
                raise ValueError("Cannot create session for inactive or missing user.")

            conn.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    user_id,
                    expires_at
                )
                VALUES (?, ?, CAST(? AS TIMESTAMP))
                """,
                [session_id, user_id, expires_at],
            )

        finally:
            conn.close()

        return session_id

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        conn = self._get_connection()

        try:
            row = conn.execute(
                """
                SELECT
                    session_id,
                    user_id,
                    expires_at,
                    revoked_at,
                    created_at
                FROM sessions
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            return self._row_to_dict(conn, row)

        finally:
            conn.close()

    def revoke_session(self, session_id: str) -> None:
        conn = self._get_connection()

        try:
            conn.execute(
                """
                UPDATE sessions
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                  AND revoked_at IS NULL
                """,
                [session_id],
            )

        finally:
            conn.close()

    def update_permissions_version(
        self,
        user_id: str,
        version: int,
    ) -> None:
        if isinstance(version, bool) or version < 1:
            raise ValueError("Permissions version must be a positive integer.")

        conn = self._get_connection()

        try:
            conn.execute(
                """
                UPDATE users
                SET permissions_version = ?
                WHERE user_id = ?
                """,
                [version, user_id],
            )

        finally:
            conn.close()
