from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.core.config import Settings
from src.api.middleware.security_headers import SecurityHeadersMiddleware


def create_test_app(security_headers_enabled: bool = True) -> FastAPI:
    test_app = FastAPI()

    test_settings = Settings(
        _env_file=None,
        security_headers_enabled=security_headers_enabled,
    )

    test_app.add_middleware(
        SecurityHeadersMiddleware,
        settings=test_settings,
    )

    @test_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    return test_app


def test_security_headers_are_present_on_http_response() -> None:
    client = TestClient(create_test_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert (
        response.headers["referrer-policy"]
        == "strict-origin-when-cross-origin"
    )
    assert (
        response.headers["permissions-policy"]
        == "camera=(), microphone=(), geolocation=()"
    )


def test_security_headers_are_applied_to_error_responses() -> None:
    client = TestClient(create_test_app())

    response = client.get("/not-found")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_security_headers_can_be_disabled() -> None:
    client = TestClient(create_test_app(security_headers_enabled=False))

    response = client.get("/health")

    assert response.status_code == 200
    assert "x-content-type-options" not in response.headers
    assert "x-frame-options" not in response.headers
    assert "referrer-policy" not in response.headers
    assert "permissions-policy" not in response.headers


def test_security_headers_do_not_enable_hsts_or_csp() -> None:
    client = TestClient(create_test_app())

    response = client.get("/health")

    assert "strict-transport-security" not in response.headers
    assert "content-security-policy" not in response.headers