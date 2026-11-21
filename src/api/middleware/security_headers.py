from __future__ import annotations

from typing import Any

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (
        b"permissions-policy",
        b"camera=(), microphone=(), geolocation=()",
    ),
)


class SecurityHeadersMiddleware:
    """Apply baseline security headers to HTTP responses."""

    def __init__(self, app: Any, settings: Any) -> None:
        self.app = app
        self.settings = settings

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not self.settings.security_headers_enabled:
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                existing_headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower()
                    not in {header[0] for header in SECURITY_HEADERS}
                ]

                message["headers"] = existing_headers + list(SECURITY_HEADERS)

            await send(message)

        await self.app(scope, receive, send_with_security_headers)