from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import ImmatureSignatureError, InvalidTokenError

from src.api.core.config import settings
from src.persistence.auth_store import AuthStore


class TokenService:
    """Create and validate JWT access tokens."""

    @staticmethod
    def create_access_token(
        user_id: str,
        session_id: str,
        permissions_version: int,
        expires_at_dt: datetime | None = None,
    ) -> tuple[str, int]:
        if not user_id or not isinstance(user_id, str):
            raise ValueError("A valid user_id is required.")

        if not session_id or not isinstance(session_id, str):
            raise ValueError("A valid session_id is required.")

        if (
            isinstance(permissions_version, bool)
            or not isinstance(permissions_version, int)
            or permissions_version < 1
        ):
            raise ValueError("Invalid permissions version.")

        now = datetime.now(UTC)

        expiration = expires_at_dt or (
            now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        )

        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=UTC)
        else:
            expiration = expiration.astimezone(UTC)

        if expiration <= now:
            raise ValueError("Token expiration must be in the future.")

        payload = {
            "sub": user_id,
            "sid": session_id,
            "ver": permissions_version,
            "iat": now,
            "exp": expiration,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }

        token = jwt.encode(
            payload,
            settings.jwt_secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

        return token, int(expiration.timestamp())

    @staticmethod
    def verify_and_decode_token(token: str) -> dict[str, Any]:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Token is missing or invalid.")

        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key.get_secret_value(),
                algorithms=["HS256"],
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                options={
                    "require": [
                        "sub",
                        "sid",
                        "ver",
                        "iat",
                        "exp",
                        "iss",
                        "aud",
                    ],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )

        except ImmatureSignatureError as exc:
            raise ValueError("Token issued in the future.") from exc

        except InvalidTokenError as exc:
            raise ValueError("Token validation failed.") from exc

        user_id = payload.get("sub")
        session_id = payload.get("sid")
        permissions_version = payload.get("ver")

        if not isinstance(user_id, str) or not user_id:
            raise ValueError("Invalid or missing 'sub' claim.")

        if not isinstance(session_id, str) or not session_id:
            raise ValueError("Invalid or missing 'sid' claim.")

        if (
            isinstance(permissions_version, bool)
            or not isinstance(permissions_version, int)
            or permissions_version < 1
        ):
            raise ValueError("Invalid or missing 'ver' claim.")

        return payload


class SessionAuthService:
    """Validate JWT identity against persistent user and session records."""

    def __init__(self, auth_store: AuthStore | None = None) -> None:
        self.auth_store = auth_store or AuthStore()

    @staticmethod
    def _to_utc(value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)

        if not isinstance(value, datetime):
         raise TypeError("Invalid session expiration.")

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    def authenticate_request(self, token: str) -> dict[str, Any]:
        payload = TokenService.verify_and_decode_token(token)

        user_id = payload["sub"]
        session_id = payload["sid"]
        token_version = payload["ver"]

        session = self.auth_store.get_session(session_id)

        if session is None:
            raise ValueError("Session is invalid or does not exist.")

        if session.get("user_id") != user_id:
            raise ValueError("Session does not belong to this user.")

        if session.get("revoked_at") is not None:
            raise ValueError("Session has been revoked.")

        expires_at = self._to_utc(session.get("expires_at"))

        if expires_at <= datetime.now(UTC):
            raise ValueError("Session has expired.")

        user = self.auth_store.get_user_by_id(user_id)

        if user is None or not user.get("is_active"):
            raise ValueError("User account is inactive or does not exist")

        if user["permissions_version"] != token_version:
            raise ValueError("User permissions have changed.")

        return {
            "user_id": user["user_id"],
            "email": user["email"],
            "session_id": session_id,
            "permissions_version": user["permissions_version"],
        }