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


class Gone(AppError):
    code = "gone"
    status_code = 410
    default_message = "资源已失效"


class Forbidden(AppError):
    code = "forbidden"
    status_code = 403
    default_message = "没有权限执行该操作"


class Conflict(AppError):
    code = "conflict"
    status_code = 409
    default_message = "资源冲突"


class InsufficientStorage(AppError):
    code = "insufficient_storage"
    status_code = 507
    default_message = "存储空间不足"


class UnsupportedMediaType(AppError):
    code = "unsupported_media_type"
    status_code = 415
    default_message = "不支持的文件类型"


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


class DeployDisabled(AppError):
    code = "deploy_disabled"
    status_code = 403
    default_message = "部署控制台未启用"


class DeployInvalidAction(AppError):
    code = "deploy_invalid_action"
    status_code = 400
    default_message = "不支持的动作或目标"


class DeployConfirmRequired(AppError):
    code = "deploy_confirm_required"
    status_code = 403
    default_message = "危险动作需要确认令牌"


class DeployTaskNotFound(AppError):
    code = "deploy_task_not_found"
    status_code = 404
    default_message = "任务不存在"


class DeployBusy(AppError):
    code = "deploy_busy"
    status_code = 409
    default_message = "已有任务执行中"

    def __init__(self, running_task_id: str, message: str | None = None):
        super().__init__(message)
        self.running_task_id = running_task_id

    def to_payload(self) -> dict:
        payload = super().to_payload()
        payload["running_task_id"] = self.running_task_id
        return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.bind(log_type="app").error(f"业务异常 {exc.code}: {exc.message}")
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
