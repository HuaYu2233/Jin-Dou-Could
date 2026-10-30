import time
import uuid
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger
from app.core.security import decode_token
from app.core.config import settings

SLOW_REQUEST_THRESHOLD_MS = 3000


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        user_id = None
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode("latin-1")
        if auth.startswith("Bearer "):
            try:
                payload = decode_token(auth[7:])
                if payload:
                    user_id = payload.get("sub")
            except Exception:
                pass

        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else None

        status_code_holder = [500]
        exc_holder = [None]

        async def send_with_logging(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_code_holder[0] = message.get("status", 500)
                headers_list = list(message.get("headers", []))
                headers_list.append((b"X-Request-ID", request_id.encode("latin-1")))
                message["headers"] = headers_list
            await send(message)

        try:
            await self.app(scope, receive, send_with_logging)
        except Exception as exc:
            exc_holder[0] = exc
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.bind(
                log_type="access",
                request_id=request_id,
                method=method,
                path=path,
                status_code=500,
                duration_ms=duration_ms,
                user_id=user_id,
                client_ip=client_ip,
            ).exception(f"{method} {path} 500 {duration_ms}ms")
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = status_code_holder[0]
        bind_data = dict(
            log_type="access",
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            client_ip=client_ip,
        )

        if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
            logger.bind(**bind_data).warning(
                f"SLOW {method} {path} {status_code} {duration_ms}ms"
            )
        else:
            logger.bind(**bind_data).info(
                f"{method} {path} {status_code} {duration_ms}ms"
            )