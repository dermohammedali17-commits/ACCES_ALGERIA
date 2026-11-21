from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from starlette.responses import JSONResponse


class LoginRateLimiter:
    """Thread-safe, bounded-memory sliding-window login rate limiter."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
        max_clients: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive.")

        if window_seconds < 1:
            raise ValueError("window_seconds must be positive.")

        if max_clients < 1:
            raise ValueError("max_clients must be positive.")

        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.clock = clock

        self._attempts: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_cleanup = clock()

    def check(self, client_ip: str) -> tuple[bool, int]:
        """Return whether the request is allowed and the retry delay."""

        now = self.clock()
        cutoff = now - self.window_seconds

        with self._lock:
            self._cleanup_expired(cutoff, now)

            attempts = self._attempts.get(client_ip)

            if attempts is None:
                if len(self._attempts) >= self.max_clients:
                    return False, self.window_seconds

                attempts = deque()
                self._attempts[client_ip] = attempts

            while attempts and attempts[0] <= cutoff:
                attempts.popleft()

            if len(attempts) >= self.max_attempts:
                retry_after = max(
                    1,
                    math.ceil(
                        attempts[0] + self.window_seconds - now
                    ),
                )
                return False, retry_after

            attempts.append(now)
            return True, 0

    def _cleanup_expired(self, cutoff: float, now: float) -> None:
        """Remove expired entries periodically."""

        if now - self._last_cleanup < self.window_seconds:
            return

        expired = [
            client_ip
            for client_ip, timestamps in self._attempts.items()
            if not timestamps or timestamps[-1] <= cutoff
        ]

        for client_ip in expired:
            del self._attempts[client_ip]

        self._last_cleanup = now

    def client_count(self) -> int:
        """Return the current number of tracked clients."""

        with self._lock:
            return len(self._attempts)


class LoginRateLimitMiddleware:
    """Apply login rate limiting at the ASGI boundary."""

    def __init__(
        self,
        app: Any,
        *,
        settings: Any,
        limiter: LoginRateLimiter | None = None,
    ) -> None:
        self.app = app
        self.settings = settings
        self.limiter = limiter or LoginRateLimiter()

        self.login_path = (
            f"{settings.api_v1_prefix.rstrip('/')}/auth/login"
        )

        self.trusted_proxy_ips = {
            str(ipaddress.ip_address(value))
            for value in settings.trusted_proxy_ips
        }

    def _resolve_client_ip(self, scope: dict[str, Any]) -> str:
        """Resolve the client IP using only explicitly trusted proxy hops."""

        client = scope.get("client")

        if not client:
            return "unknown"

        try:
            peer_ip = str(ipaddress.ip_address(str(client[0])))
        except ValueError:
            return "unknown"

        if peer_ip not in self.trusted_proxy_ips:
            return peer_ip

        headers = {
            key.lower(): value
            for key, value in scope.get("headers", [])
        }

        forwarded = headers.get(b"x-forwarded-for")

        if not forwarded:
            return peer_ip

        try:
            forwarded_ips = [
                str(ipaddress.ip_address(item.strip()))
                for item in forwarded.decode("ascii").split(",")
            ]
        except (UnicodeDecodeError, ValueError):
            return peer_ip

        if not forwarded_ips:
            return peer_ip

        chain = forwarded_ips + [peer_ip]

        # Walk from the nearest proxy toward the original client.
        for address in reversed(chain):
            if address not in self.trusted_proxy_ips:
                return address

        return peer_ip

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if not self.settings.rate_limiting_enabled:
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if (
            scope.get("method") != "POST"
            or scope.get("path") != self.login_path
        ):
            await self.app(scope, receive, send)
            return

        client_ip = self._resolve_client_ip(scope)
        allowed, retry_after = self.limiter.check(client_ip)

        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many login attempts. Please try again later."
                },
                headers={
                    "Retry-After": str(retry_after),
                    "Cache-Control": "no-store",
                },
            )

            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)