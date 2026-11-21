from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from src.api.middleware.rate_limiter import (
    LoginRateLimiter,
    LoginRateLimitMiddleware,
)


@dataclass
class FakeClock:
    current: float = 0.0

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


@dataclass
class FakeSettings:
    api_v1_prefix: str = "/api/v1"
    rate_limiting_enabled: bool = True
    trusted_proxy_ips: list[str] = field(
        default_factory=lambda: ["127.0.0.1", "::1"]
    )


class DummyApp:
    def __init__(self) -> None:
        self.called = False

    async def __call__(self, scope, receive, send) -> None:
        self.called = True


def make_scope(
    *,
    method: str = "POST",
    path: str = "/api/v1/auth/login",
    client: tuple[str, int] = ("192.0.2.10", 50000),
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "client": client,
        "headers": headers or [],
    }


def test_rate_limiter_allows_attempts_under_limit():
    limiter = LoginRateLimiter(max_attempts=3)

    assert limiter.check("192.0.2.1") == (True, 0)
    assert limiter.check("192.0.2.1") == (True, 0)
    assert limiter.check("192.0.2.1") == (True, 0)


def test_rate_limiter_blocks_attempt_after_limit():
    limiter = LoginRateLimiter(max_attempts=2, window_seconds=60)

    assert limiter.check("192.0.2.1") == (True, 0)
    assert limiter.check("192.0.2.1") == (True, 0)

    allowed, retry_after = limiter.check("192.0.2.1")

    assert allowed is False
    assert retry_after == 60


def test_rate_limiter_expires_attempts_after_window():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_attempts=2,
        window_seconds=60,
        clock=clock,
    )

    assert limiter.check("192.0.2.1") == (True, 0)
    assert limiter.check("192.0.2.1") == (True, 0)

    clock.advance(60)

    assert limiter.check("192.0.2.1") == (True, 0)


def test_rate_limiter_calculates_retry_after():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_attempts=1,
        window_seconds=60,
        clock=clock,
    )

    limiter.check("192.0.2.1")
    clock.advance(15)

    allowed, retry_after = limiter.check("192.0.2.1")

    assert allowed is False
    assert retry_after == 45


def test_rate_limiter_isolates_clients():
    limiter = LoginRateLimiter(max_attempts=1)

    assert limiter.check("192.0.2.1") == (True, 0)
    assert limiter.check("192.0.2.2") == (True, 0)


def test_rate_limiter_rejects_invalid_configuration():
    import pytest

    with pytest.raises(ValueError):
        LoginRateLimiter(max_attempts=0)

    with pytest.raises(ValueError):
        LoginRateLimiter(window_seconds=0)

    with pytest.raises(ValueError):
        LoginRateLimiter(max_clients=0)


def test_rate_limiter_enforces_client_capacity():
    limiter = LoginRateLimiter(max_clients=1)

    assert limiter.check("192.0.2.1") == (True, 0)

    allowed, retry_after = limiter.check("192.0.2.2")

    assert allowed is False
    assert retry_after == 60
    assert limiter.client_count() == 1


def test_rate_limiter_recovers_capacity_after_cleanup():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_clients=1,
        window_seconds=60,
        clock=clock,
    )

    assert limiter.check("192.0.2.1") == (True, 0)

    clock.advance(60)

    assert limiter.check("192.0.2.2") == (True, 0)
    assert limiter.client_count() == 1


def test_rate_limiter_is_thread_safe():
    limiter = LoginRateLimiter(max_attempts=5, window_seconds=60)

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(
            executor.map(
                limiter.check,
                ["192.0.2.1"] * 10,
            )
        )

    allowed_count = sum(allowed for allowed, _ in results)

    assert allowed_count == 5


def test_untrusted_peer_cannot_spoof_forwarded_header():
    middleware = LoginRateLimitMiddleware(
        DummyApp(),
        settings=FakeSettings(),
    )

    scope = make_scope(
        client=("192.0.2.10", 50000),
        headers=[
            (b"x-forwarded-for", b"198.51.100.99"),
        ],
    )

    assert middleware._resolve_client_ip(scope) == "192.0.2.10"


def test_trusted_proxy_resolves_original_client():
    settings = FakeSettings(
        trusted_proxy_ips=["10.0.0.1", "10.0.0.2"]
    )

    middleware = LoginRateLimitMiddleware(
        DummyApp(),
        settings=settings,
    )

    scope = make_scope(
        client=("10.0.0.2", 50000),
        headers=[
            (
                b"x-forwarded-for",
                b"198.51.100.7, 10.0.0.1",
            ),
        ],
    )

    assert middleware._resolve_client_ip(scope) == "198.51.100.7"


def test_invalid_forwarded_header_falls_back_to_peer():
    middleware = LoginRateLimitMiddleware(
        DummyApp(),
        settings=FakeSettings(
            trusted_proxy_ips=["10.0.0.1"]
        ),
    )

    scope = make_scope(
        client=("10.0.0.1", 50000),
        headers=[
            (b"x-forwarded-for", b"invalid-ip"),
        ],
    )

    assert middleware._resolve_client_ip(scope) == "10.0.0.1"


def test_middleware_skips_non_login_requests():
    app = DummyApp()
    limiter = LoginRateLimiter(max_attempts=1)

    middleware = LoginRateLimitMiddleware(
        app,
        settings=FakeSettings(),
        limiter=limiter,
    )

    scope = make_scope(path="/api/v1/other")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        pass

    asyncio.run(middleware(scope, receive, send))

    assert app.called is True
    assert limiter.client_count() == 0


def test_middleware_returns_429_when_limit_is_exceeded():
    app = DummyApp()
    limiter = LoginRateLimiter(max_attempts=1)

    middleware = LoginRateLimitMiddleware(
        app,
        settings=FakeSettings(),
        limiter=limiter,
    )

    scope = make_scope()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    messages = []

    async def send(message):
        messages.append(message)

    asyncio.run(middleware(scope, receive, send))

    assert app.called is True

    app.called = False
    asyncio.run(middleware(scope, receive, send))

    assert app.called is False

    response_start = next(
        message
        for message in messages
        if message["type"] == "http.response.start"
    )

    assert response_start["status"] == 429

    headers = dict(response_start["headers"])

    assert headers[b"retry-after"] == b"60"
    assert headers[b"cache-control"] == b"no-store"


def test_disabled_rate_limiting_bypasses_limiter():
    app = DummyApp()
    limiter = LoginRateLimiter(max_attempts=1)

    settings = FakeSettings(rate_limiting_enabled=False)

    middleware = LoginRateLimitMiddleware(
        app,
        settings=settings,
        limiter=limiter,
    )

    scope = make_scope()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        pass

    asyncio.run(middleware(scope, receive, send))

    assert app.called is True
    assert limiter.client_count() == 0