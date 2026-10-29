import secrets
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_CSRF_COOKIE_NAME = "csrf_token"
_CSRF_HEADER_NAME = "x-csrf-token"
_API_PREFIX = "/api/"


class CSRFMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not settings.CSRF_ENABLED:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        if request.method in _SAFE_METHODS:
            await self._inject_cookie(scope, receive, send)
            return

        if not request.url.path.startswith(_API_PREFIX):
            await self.app(scope, receive, send)
            return

        cookie_token = request.cookies.get(_CSRF_COOKIE_NAME)
        header_token = request.headers.get(_CSRF_HEADER_NAME)

        if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
            response = Response(
                '{"detail":"CSRF token mismatch"}',
                status_code=403,
                media_type="application/json",
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _inject_cookie(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope)

        if request.cookies.get(_CSRF_COOKIE_NAME):
            await self.app(scope, receive, send)
            return

        token = secrets.token_urlsafe(32)
        inner_send = send

        async def send_with_cookie(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                cookie = (
                    f"{_CSRF_COOKIE_NAME}={token}; "
                    f"Path=/; SameSite=Lax; HttpOnly"
                )
                if settings.ENVIRONMENT == "production":
                    cookie += "; Secure"
                headers[b"set-cookie"] = cookie.encode("latin-1")
                message["headers"] = list(headers.items())
            await inner_send(message)

        await self.app(scope, receive, send_with_cookie)