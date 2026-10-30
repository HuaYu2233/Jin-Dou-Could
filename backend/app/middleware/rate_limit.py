import time
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from loguru import logger
from app.core.config import settings
from app.core.redis import redis_client

EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}
LOGIN_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}
LOGIN_RATE_LIMIT = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
_TRUSTED_PROXIES: set[str] | None = None


def _get_trusted_proxies() -> set[str]:
    global _TRUSTED_PROXIES
    if _TRUSTED_PROXIES is None:
        if settings.TRUSTED_PROXIES:
            _TRUSTED_PROXIES = {p.strip() for p in settings.TRUSTED_PROXIES.split(",") if p.strip()}
        else:
            _TRUSTED_PROXIES = set()
    return _TRUSTED_PROXIES


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not settings.RATE_LIMIT_ENABLED:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        client_ip = self._get_client_ip(scope)
        global_key = f"rl:{client_ip}:global"

        try:
            now = time.time()
            window = 60
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(global_key, 0, now - window)
            pipe.zadd(global_key, {str(now): now})
            pipe.zcard(global_key)
            pipe.expire(global_key, window)
            results = await pipe.execute()

            count = results[2]
            if count > settings.RATE_LIMIT_PER_MINUTE:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请稍后再试"},
                )
                await response(scope, receive, send)
                return

            if path in LOGIN_PATHS:
                login_key = f"rl:{client_ip}:login"
                pipe2 = redis_client.pipeline()
                pipe2.zremrangebyscore(login_key, 0, now - window)
                pipe2.zadd(login_key, {str(now): now})
                pipe2.zcard(login_key)
                pipe2.expire(login_key, window)
                login_results = await pipe2.execute()

                login_count = login_results[2]
                if login_count > LOGIN_RATE_LIMIT:
                    response = JSONResponse(
                        status_code=429,
                        content={"detail": "登录尝试过于频繁，请稍后再试"},
                    )
                    await response(scope, receive, send)
                    return
        except Exception as exc:
            logger.bind(log_type="security").warning(f"限流检查失败(Redis不可达?), 放行请求: {exc}")

        await self.app(scope, receive, send)

    @staticmethod
    def _get_client_ip(scope: Scope) -> str:
        client = scope.get("client")
        direct_ip = client[0] if client else None

        if not direct_ip:
            return "unknown"

        trusted = _get_trusted_proxies()
        if not trusted or direct_ip not in trusted:
            return direct_ip

        headers = dict(scope.get("headers", []))
        xff = headers.get(b"x-forwarded-for")
        if xff:
            return xff.decode().split(",")[0].strip()
        x_real_ip = headers.get(b"x-real-ip")
        if x_real_ip:
            return x_real_ip.decode().strip()
        return direct_ip