import secrets
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings

_API_PATHS = ("/api/", "/health", "/docs", "/openapi.json", "/redoc")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if any(path.startswith(p) or path == p for p in _API_PATHS):
            await self.app(scope, receive, send)
            return

        if not settings.SECURITY_HEADERS_ENABLED:
            await self.app(scope, receive, send)
            return

        nonce = secrets.token_urlsafe(16)

        inner_send = send
        started = False
        headers_mutated: dict[bytes, bytes] = {}

        async def send_with_headers(message: dict) -> None:
            nonlocal started, headers_mutated
            if message["type"] == "http.response.start" and not started:
                started = True
                raw = message.get("headers", [])
                hdrs: dict[bytes, bytes] = {}
                for k, v in raw:
                    hdrs[k] = v

                hdrs[b"x-content-type-options"] = b"nosniff"
                hdrs[b"x-frame-options"] = b"DENY"
                hdrs[b"referrer-policy"] = b"strict-origin-when-cross-origin"
                hdrs[b"x-xss-protection"] = b"1; mode=block"
                hdrs[b"permissions-policy"] = b"geolocation=(), microphone=(), camera=()"

                scheme = scope.get("scheme", "http")
                if settings.ENVIRONMENT == "production" and scheme == "https":
                    hdrs[b"strict-transport-security"] = (
                        b"max-age=63072000; includeSubDomains; preload"
                    )

                csp = (
                    f"default-src 'self'; "
                    f"script-src 'self' 'nonce-{nonce}'; "
                    f"style-src 'self' 'nonce-{nonce}'; "
                    f"img-src 'self' data: blob: http: https:; "
                    f"font-src 'self' data:; "
                    f"connect-src 'self' http://localhost:8000 http://localhost:9000; "
                    f"frame-ancestors 'none'; "
                    f"base-uri 'self'; "
                    f"form-action 'self'"
                )
                hdrs[b"content-security-policy"] = csp.encode("utf-8")

                message["headers"] = list(hdrs.items())

            await inner_send(message)

        await self.app(scope, receive, send_with_headers)