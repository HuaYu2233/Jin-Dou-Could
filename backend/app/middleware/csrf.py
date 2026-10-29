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
        needs_cookie = not request.cookies.get(_CSRF_COOKIE_NAME)
        new_token = secrets.token_urlsafe(32) if needs_cookie else None

        if request.method in _SAFE_METHODS:
            if needs_cookie:
                await self._run_with_cookie(scope, receive, send, new_token)
            else:
                await self.app(scope, receive, send)
            return

        if not request.url.path.startswith(_API_PREFIX):
            if needs_cookie:
                await self._run_with_cookie(scope, receive, send, new_token)
            else:
                await self.app(scope, receive, send)
            return

        cookie_token = request.cookies.get(_CSRF_COOKIE_NAME)
        header_token = request.headers.get(_CSRF_HEADER_NAME)

        if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
            if needs_cookie:
                response = Response(
                    '{"detail":"CSRF token missing, retry after cookie is set"}',
                    status_code=403,
                    media_type="application/json",
                )
                inner_send = send

                async def send_with_cookie(message: dict) -> None:
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        cookie = self._build_cookie(new_token)
                        headers.append((b"set-cookie", cookie.encode("latin-1")))
                        message["headers"] = headers
                    await inner_send(message)

                await response(scope, receive, send_with_cookie)
            else:
                response = Response(
                    '{"detail":"CSRF token mismatch"}',
                    status_code=403,
                    media_type="application/json",
                )
                await response(scope, receive, send)
            return

        if needs_cookie:
            await self._run_with_cookie(scope, receive, send, new_token)
        else:
            await self.app(scope, receive, send)

    def _build_cookie(self, token: str) -> str:
        if settings.ENVIRONMENT == "production":
            cookie = f"{_CSRF_COOKIE_NAME}={token}; Path=/; SameSite=None; Secure"
        else:
            cookie = f"{_CSRF_COOKIE_NAME}={token}; Path=/; SameSite=Lax"
        return cookie

    async def _run_with_cookie(
        self, scope: Scope, receive: Receive, send: Send, token: str
    ) -> None:
        inner_send = send

        async def send_with_cookie(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                cookie = self._build_cookie(token)
                headers.append((b"set-cookie", cookie.encode("latin-1")))
                message["headers"] = headers
            await inner_send(message)

        await self.app(scope, receive, send_with_cookie)