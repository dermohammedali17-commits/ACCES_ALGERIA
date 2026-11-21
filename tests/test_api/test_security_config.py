from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from src.api.core.config import Settings


def test_valid_security_config():
    settings = Settings(
        environment="production",
        jwt_secret_key=SecretStr("super-secure-production-jwt-secret-key-2026"),
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=15,
        deployment_workers=1,
        trusted_proxy_ips="127.0.0.1, 10.0.0.1",
        admin_initial_password=SecretStr("SecurePass123!"),
    )
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_token_expire_minutes == 15
    assert settings.deployment_workers == 1
    assert settings.trusted_proxy_ips == ["127.0.0.1", "10.0.0.1"]
    assert isinstance(settings.jwt_secret_key, SecretStr)
    assert isinstance(settings.admin_initial_password, SecretStr)
    assert settings.admin_initial_password.get_secret_value() == "SecurePass123!"
    # Ensure secret is masked in representations
    assert "SecurePass123!" not in repr(settings)


def test_insecure_production_jwt_secret_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            jwt_secret_key=SecretStr("insecure-default-secret-key-change-me"),
            deployment_workers=1,
        )
    assert "Insecure or default JWT_SECRET_KEY" in str(exc_info.value)


def test_invalid_jwt_algorithm_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="test",
            jwt_secret_key=SecretStr("some-random-secret-key-for-testing"),
            jwt_algorithm="RS256",
            deployment_workers=1,
        )
    assert "Unsupported JWT algorithm" in str(exc_info.value)


def test_invalid_token_expiration_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="test",
            jwt_secret_key=SecretStr("some-random-secret-key-for-testing"),
            jwt_access_token_expire_minutes=120,
            deployment_workers=1,
        )
    assert "JWT access token expiration must be between 1 and 60 minutes" in str(exc_info.value)


def test_multi_worker_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="test",
            jwt_secret_key=SecretStr("some-random-secret-key-for-testing"),
            deployment_workers=4,
        )
    assert "strictly requires single-worker deployment" in str(exc_info.value)


def test_trusted_proxy_parsing():
    settings = Settings(
        environment="test",
        jwt_secret_key=SecretStr("some-random-secret-key-for-testing"),
        trusted_proxy_ips=["192.168.1.1", "10.0.0.2"],
        deployment_workers=1,
    )
    assert settings.trusted_proxy_ips == ["192.168.1.1", "10.0.0.2"]

    settings_str = Settings(
        environment="test",
        jwt_secret_key=SecretStr("some-random-secret-key-for-testing"),
        trusted_proxy_ips=" 192.168.1.5 , 10.0.0.9 ",
        deployment_workers=1,
    )
    assert settings_str.trusted_proxy_ips == ["192.168.1.5", "10.0.0.9"]
def test_short_production_jwt_secret_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            jwt_secret_key=SecretStr("short-production-secret"),
            deployment_workers=1,
        )

    assert "JWT_SECRET_KEY must be at least 32 bytes long in production" in str(
        exc_info.value
    )


def test_invalid_trusted_proxy_ip_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="test",
            jwt_secret_key=SecretStr("some-random-secret-key-for-testing"),
            trusted_proxy_ips=["127.0.0.1", "not-an-ip"],
            deployment_workers=1,
        )

    assert "Invalid trusted proxy IP address" in str(exc_info.value)


def test_duplicate_trusted_proxy_ips_normalized():
    settings = Settings(
        environment="test",
        jwt_secret_key=SecretStr("some-random-secret-key-for-testing"),
        trusted_proxy_ips=["127.0.0.1", "127.0.0.1", "::1"],
        deployment_workers=1,
    )

    assert settings.trusted_proxy_ips == ["127.0.0.1", "::1"]