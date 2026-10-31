from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger


class AppError(Exception):
    code = "internal_error"
    status_code = 500
    default_message = "服务器内部错误"

    def __init__(self, message: str | None = None, *, details: dict | None = None):
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)

    def to_payload(self) -> dict:
        payload = {"detail": self.message, "code": self.code}
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationFailed(AppError):
    code = "validation_failed"
    status_code = 400
    default_message = "请求参数不合法"


class QuotaExceeded(AppError):
    code = "quota_exceeded"
    status_code = 413
    default_message = "存储空间不足"


class PayloadTooLarge(AppError):
    code = "payload_too_large"
    status_code = 413
    default_message = "文件过大"


class NotFound(AppError):
    code = "not_found"
    status_code = 404
    default_message = "资源不存在"


class Forbidden(AppError):
    code = "forbidden"
    status_code = 403
    default_message = "没有权限执行该操作"


class Conflict(AppError):
    code = "conflict"
    status_code = 409
    default_message = "资源冲突"


class Unauthorized(AppError):
    code = "unauthorized"
    status_code = 401
    default_message = "未认证"


class RateLimited(AppError):
    code = "rate_limited"
    status_code = 429
    default_message = "操作过于频繁"


class ServiceUnavailable(AppError):
    code = "service_unavailable"
    status_code = 503
    default_message = "服务暂不可用"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.bind(log_type="app").error(f"业务异常 {exc.code}: {exc.message}")
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
