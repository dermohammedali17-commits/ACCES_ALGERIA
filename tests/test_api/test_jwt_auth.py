from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.core.config import settings
from src.persistence.auth_store import AuthStore
from src.security.jwt import SessionAuthService, TokenService

client = TestClient(app)


@pytest.fixture
def auth_store(tmp_path):
    db_file = tmp_path / "jwt_corrective_test.duckdb"
    return AuthStore(db_path=str(db_file))


def test_token_issuance_and_verification(auth_store):
    user = auth_store.create_user(
        "token_test@example.com",
        "SecurePass123!",
    )

    expires_at = (
        datetime.now(UTC) + timedelta(minutes=15)
    ).isoformat()

    sid = auth_store.create_session(user["user_id"], expires_at)

    token, exp = TokenService.create_access_token(
        user["user_id"],
        sid,
        1,
    )

    assert isinstance(token, str)
    assert exp > 0

    payload = TokenService.verify_and_decode_token(token)

    assert payload["sub"] == user["user_id"]
    assert payload["sid"] == sid
    assert payload["ver"] == 1
    assert payload["iss"] == settings.jwt_issuer
    assert payload["aud"] == settings.jwt_audience


def test_token_verification_strict_failure_cases(auth_store):
    user = auth_store.create_user(
        "strict_test@example.com",
        "SecurePass123!",
    )

    expires_at = (
        datetime.now(UTC) + timedelta(minutes=15)
    ).isoformat()

    sid = auth_store.create_session(user["user_id"], expires_at)

    token, _ = TokenService.create_access_token(
        user["user_id"],
        sid,
        1,
    )

    secret = settings.jwt_secret_key.get_secret_value()

    # 1. Wrong audience
    wrong_aud_payload = jwt.decode(
        token,
        options={"verify_signature": False},
    )
    wrong_aud_payload["aud"] = "wrong-audience"

    wrong_aud_token = jwt.encode(
        wrong_aud_payload,
        secret,
        algorithm="HS256",
    )

    with pytest.raises(
        ValueError,
        match="Token validation failed",
    ):
        TokenService.verify_and_decode_token(wrong_aud_token)

    # 2. Invalid algorithm
    payload_clean = jwt.decode(
        token,
        options={"verify_signature": False},
    )

    alt_alg_token = jwt.encode(
        payload_clean,
        "x" * 48,
        algorithm="HS384",
    )

    with pytest.raises(
        ValueError,
        match="Token validation failed",
    ):
        TokenService.verify_and_decode_token(alt_alg_token)

    # 3. Missing required claim
    missing_claim_payload = jwt.decode(
        token,
        options={"verify_signature": False},
    )

    del missing_claim_payload["sid"]

    missing_claim_token = jwt.encode(
        missing_claim_payload,
        secret,
        algorithm="HS256",
    )

    with pytest.raises(
        ValueError,
        match="Token validation failed",
    ):
        TokenService.verify_and_decode_token(missing_claim_token)

    # 4. Boolean permissions version
    bool_ver_payload = jwt.decode(
        token,
        options={"verify_signature": False},
    )

    bool_ver_payload["ver"] = True

    bool_ver_token = jwt.encode(
        bool_ver_payload,
        secret,
        algorithm="HS256",
    )

    with pytest.raises(
        ValueError,
        match="Invalid or missing 'ver' claim",
    ):
        TokenService.verify_and_decode_token(bool_ver_token)

    # 5. Negative permissions version
    neg_ver_payload = jwt.decode(
        token,
        options={"verify_signature": False},
    )

    neg_ver_payload["ver"] = -1

    neg_ver_token = jwt.encode(
        neg_ver_payload,
        secret,
        algorithm="HS256",
    )

    with pytest.raises(
        ValueError,
        match="Invalid or missing 'ver' claim",
    ):
        TokenService.verify_and_decode_token(neg_ver_token)

    # 6. Future-issued token
    future_iat_payload = jwt.decode(
        token,
        options={"verify_signature": False},
    )

    future_iat_payload["iat"] = (
        int(datetime.now(UTC).timestamp()) + 300
    )

    future_iat_token = jwt.encode(
        future_iat_payload,
        secret,
        algorithm="HS256",
    )

    with pytest.raises(
        ValueError,
        match="Token issued in the future",
    ):
        TokenService.verify_and_decode_token(future_iat_token)

    # 7. Malformed token
    with pytest.raises(
        ValueError,
        match="Token validation failed",
    ):
        TokenService.verify_and_decode_token(
            "not.a.valid.jwt.string"
        )


def test_session_validation_edge_cases(auth_store):
    user = auth_store.create_user(
        "session_edge@example.com",
        "SecurePass123!",
    )

    expires_at = (
        datetime.now(UTC) + timedelta(minutes=15)
    ).isoformat()

    sid = auth_store.create_session(user["user_id"], expires_at)

    token, _ = TokenService.create_access_token(
        user["user_id"],
        sid,
        1,
    )

    auth_service = SessionAuthService(auth_store=auth_store)

    # 1. Inactive user
    conn = auth_store._get_connection()

    try:
        conn.execute(
            "UPDATE users SET is_active = FALSE WHERE user_id = ?",
            [user["user_id"]],
        )
    finally:
        conn.close()

    with pytest.raises(
        ValueError,
        match="User account is inactive",
    ):
        auth_service.authenticate_request(token)

    # Reactivate user
    conn = auth_store._get_connection()

    try:
        conn.execute(
            "UPDATE users SET is_active = TRUE WHERE user_id = ?",
            [user["user_id"]],
        )
    finally:
        conn.close()

    # 2. Missing user
    conn = auth_store._get_connection()

    try:
        conn.execute(
            "DELETE FROM users WHERE user_id = ?",
            [user["user_id"]],
        )
    finally:
        conn.close()

    with pytest.raises(
        ValueError,
        match="User account is inactive or does not exist",
    ):
        auth_service.authenticate_request(token)


def test_api_integration_and_isolation(monkeypatch, tmp_path):
    db_file = tmp_path / "isolated_api.duckdb"
    store = AuthStore(db_path=str(db_file))

    store.create_user(
        "isolated@example.com",
        "SecretPass123!",
    )

    monkeypatch.setattr(
        "src.api.routers.auth.AuthStore",
        lambda db_path=None: store,
    )

    monkeypatch.setattr(
        "src.security.jwt.AuthStore",
        lambda db_path=None: store,
    )

    # 1. Successful login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "isolated@example.com",
            "password": "SecretPass123!",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data

    token = data["access_token"]

    # 2. Invalid credentials
    fail_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "isolated@example.com",
            "password": "WrongPassword",
        },
    )

    assert fail_resp.status_code == 401
    assert fail_resp.json()["detail"] == "Invalid email or password."

    # 3. Successful /me
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "isolated@example.com"

    # 4. Successful logout
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert logout_resp.status_code == 200

    # 5. Rejected token after logout
    after_logout = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert after_logout.status_code == 401
    assert (
        after_logout.json()["detail"]
        == "Could not validate credentials."
    )


def test_password_hash_is_upgraded_after_successful_verification(
    auth_store,
):
    email = "rehash_test@example.com"
    password = "SecurePass123!"

    user = auth_store.create_user(email, password)

    old_hasher = PasswordHasher(
        time_cost=1,
        memory_cost=8192,
        parallelism=1,
    )

    old_hash = old_hasher.hash(password)

    conn = auth_store._get_connection()

    try:
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE user_id = ?
            """,
            [old_hash, user["user_id"]],
        )
    finally:
        conn.close()

    assert auth_store._password_hasher.check_needs_rehash(old_hash)

    assert auth_store.verify_user_password(email, password) is True

    conn = auth_store._get_connection()

    try:
        updated_hash = conn.execute(
            """
            SELECT password_hash
            FROM users
            WHERE user_id = ?
            """,
            [user["user_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert updated_hash != old_hash

    assert not auth_store._password_hasher.check_needs_rehash(
        updated_hash
    )

    assert auth_store.verify_user_password(email, password) is True


def test_nonexistent_user_uses_dummy_password_verification(
    auth_store,
    monkeypatch,
):
    original_dummy_verify = auth_store._verify_dummy_password
    verification_calls = []

    def tracked_dummy_verify(password):
        verification_calls.append(password)
        original_dummy_verify(password)

    monkeypatch.setattr(
        auth_store,
        "_verify_dummy_password",
        tracked_dummy_verify,
    )

    result = auth_store.verify_user_password(
        "missing@example.com",
        "SomePassword123!",
    )

    assert result is False
    assert verification_calls == ["SomePassword123!"]


def test_wrong_password_does_not_upgrade_password_hash(auth_store):
    email = "wrong_password_rehash@example.com"
    password = "SecurePass123!"

    user = auth_store.create_user(email, password)

    conn = auth_store._get_connection()

    try:
        original_hash = conn.execute(
            """
            SELECT password_hash
            FROM users
            WHERE user_id = ?
            """,
            [user["user_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert (
        auth_store.verify_user_password(
            email,
            "WrongPassword123!",
        )
        is False
    )

    conn = auth_store._get_connection()

    try:
        current_hash = conn.execute(
            """
            SELECT password_hash
            FROM users
            WHERE user_id = ?
            """,
            [user["user_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert current_hash == original_hash


def test_api_nonexistent_user_triggers_dummy_password_verification(
    monkeypatch,
    tmp_path,
):
    store = AuthStore(
        db_path=str(tmp_path / "dummy_api_test.duckdb")
    )

    verification_calls = []
    original_verify = store._verify_dummy_password

    def tracked_verify(password):
        verification_calls.append(password)
        original_verify(password)

    monkeypatch.setattr(
        store,
        "_verify_dummy_password",
        tracked_verify,
    )

    monkeypatch.setattr(
        "src.api.routers.auth.AuthStore",
        lambda db_path=None: store,
    )

    submitted_password = "SomePassword123!"

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "missing_api@example.com",
            "password": submitted_password,
        },
    )

    assert response.status_code == 401

    assert response.json()["detail"] == "Invalid email or password."

    assert verification_calls == [submitted_password]


# A5 — Additional JWT and session security tests


def test_expired_jwt_is_rejected():
    now = datetime.now(UTC)

    expired_payload = {
        "sub": "test-user",
        "sid": "test-session",
        "ver": 1,
        "iat": now - timedelta(minutes=10),
        "exp": now - timedelta(minutes=5),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }

    token = jwt.encode(
        expired_payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(
        ValueError,
        match="Token validation failed",
    ):
        TokenService.verify_and_decode_token(token)


def test_expired_session_is_rejected(auth_store):
    user = auth_store.create_user(
        "expired_session@example.com",
        "SecurePass123!",
    )

    expires_at = (
        datetime.now(UTC) - timedelta(minutes=5)
    ).isoformat()

    session_id = auth_store.create_session(
        user["user_id"],
        expires_at,
    )

    token, _ = TokenService.create_access_token(
        user["user_id"],
        session_id,
        1,
    )

    auth_service = SessionAuthService(auth_store=auth_store)

    with pytest.raises(
        ValueError,
        match="Session has expired",
    ):
        auth_service.authenticate_request(token)


def test_permissions_version_mismatch_is_rejected(auth_store):
    user = auth_store.create_user(
        "permissions_version@example.com",
        "SecurePass123!",
    )

    expires_at = (
        datetime.now(UTC) + timedelta(minutes=15)
    ).isoformat()

    session_id = auth_store.create_session(
        user["user_id"],
        expires_at,
    )

    token, _ = TokenService.create_access_token(
        user["user_id"],
        session_id,
        1,
    )

    auth_store.update_permissions_version(
        user["user_id"],
        2,
    )

    auth_service = SessionAuthService(auth_store=auth_store)

    with pytest.raises(
        ValueError,
        match="User permissions have changed",
    ):
        auth_service.authenticate_request(token)


def test_session_user_mismatch_is_rejected(auth_store):
    user_one = auth_store.create_user(
        "session_owner@example.com",
        "SecurePass123!",
    )

    user_two = auth_store.create_user(
        "different_user@example.com",
        "SecurePass123!",
    )

    expires_at = (
        datetime.now(UTC) + timedelta(minutes=15)
    ).isoformat()

    session_id = auth_store.create_session(
        user_one["user_id"],
        expires_at,
    )

    token, _ = TokenService.create_access_token(
        user_two["user_id"],
        session_id,
        1,
    )

    auth_service = SessionAuthService(auth_store=auth_store)

    with pytest.raises(
        ValueError,
        match="Session does not belong to this user",
    ):
        auth_service.authenticate_request(token)