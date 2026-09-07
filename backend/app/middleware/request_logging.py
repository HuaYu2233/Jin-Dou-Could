import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger
from app.core.security import decode_token

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        user_id = None
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            payload = decode_token(auth[7:])
            if payload:
                user_id = payload.get("sub")

        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.bind(
                log_type="access",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                user_id=user_id,
                client_ip=request.client.host if request.client else None,
            ).exception(
                f"{request.method} {request.url.path} 500 {duration_ms}ms"
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.bind(
            log_type="access",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            client_ip=request.client.host if request.client else None,
        ).info(
            f"{request.method} {request.url.path} {response.status_code} {duration_ms}ms"
        )

        response.headers["X-Request-ID"] = request_id
        return response