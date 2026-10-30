import secrets
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_CSRF_COOKIE_NAME = "csrf_token"
_CSRF_HEADER_NAME = "x-csrf-token"
_API_PREFIX = "/api/"


def _get_cookie_from_scope(scope: Scope, name: str) -> str | None:
    headers = dict(scope.get("headers", []))
    cookie_header = headers.get(b"cookie")
    if not cookie_header:
        return None
    cookie_str = cookie_header.decode("latin-1")
    for part in cookie_str.split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            return part[len(name) + 1:]
    return None


def _get_header_from_scope(scope: Scope, name: str) -> str | None:
    headers = dict(scope.get("headers", []))
    value = headers.get(name.encode("latin-1"))
    if value:
        return value.decode("latin-1")
    return None


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

        cookie_token = _get_cookie_from_scope(scope, _CSRF_COOKIE_NAME)
        needs_cookie = not cookie_token
        new_token = secrets.token_urlsafe(32) if needs_cookie else None

        method = scope.get("method", "")
        path = scope.get("path", "")

        if method in _SAFE_METHODS:
            if needs_cookie:
                await self._run_with_cookie(scope, receive, send, new_token)
            else:
                await self.app(scope, receive, send)
            return

        if not path.startswith(_API_PREFIX):
            if needs_cookie:
                await self._run_with_cookie(scope, receive, send, new_token)
            else:
                await self.app(scope, receive, send)
            return

        header_token = _get_header_from_scope(scope, _CSRF_HEADER_NAME)

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