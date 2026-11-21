from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from src.api.core.config import settings
from src.api.dependencies.auth import get_current_user
from src.persistence.auth_store import AuthStore
from src.security.jwt import SessionAuthService, TokenService

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int
    user_id: str
    email: str


class LogoutResponse(BaseModel):
    message: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> dict[str, Any]:
    """Authenticate user credentials, create a persistent session, and issue a session-bound JWT."""
    auth_store = AuthStore()
    norm_email = auth_store.normalize_email(payload.email)

    generic_err = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )

    password_valid = auth_store.verify_user_password(
        norm_email,
        payload.password,
    )

    user = auth_store.get_user_by_email(norm_email)

    if not password_valid or not user or not user["is_active"]:
        raise generic_err

    # Unified UTC expiration calculation shared between session and JWT
    now_utc = datetime.now(UTC)
    expire_delta_mins = settings.jwt_access_token_expire_minutes
    expires_dt = now_utc + timedelta(minutes=expire_delta_mins)

    session_id = auth_store.create_session(user["user_id"], expires_dt.isoformat())

    token, exp_epoch = TokenService.create_access_token(
        user_id=user["user_id"],
        session_id=session_id,
        permissions_version=user["permissions_version"],
        expires_at_dt=expires_dt,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": exp_epoch,
        "user_id": user["user_id"],
        "email": user["email"],
    }


@router.post("/logout", response_model=LogoutResponse)
def logout(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, str]:
    """Revoke the current persisted session, immediately invalidating the associated JWT."""
    auth_store = AuthStore()
    session_id = current_user["session_id"]
    auth_store.revoke_session(session_id)
    return {"message": "Successfully logged out."}


@router.get("/me")
def get_current_user_profile(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return profile details for the authenticated user session."""
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "session_id": current_user["session_id"],
    }
