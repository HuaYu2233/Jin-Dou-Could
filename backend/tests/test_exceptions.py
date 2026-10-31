import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import (
    AppError,
    Conflict,
    Forbidden,
    NotFound,
    PayloadTooLarge,
    QuotaExceeded,
    RateLimited,
    ServiceUnavailable,
    Unauthorized,
    ValidationFailed,
    register_exception_handlers,
)


class TestAppErrorContract:
    @pytest.mark.parametrize(
        "exc_cls,status,code",
        [
            (ValidationFailed, 400, "validation_failed"),
            (Unauthorized, 401, "unauthorized"),
            (Forbidden, 403, "forbidden"),
            (NotFound, 404, "not_found"),
            (Conflict, 409, "conflict"),
            (PayloadTooLarge, 413, "payload_too_large"),
            (QuotaExceeded, 413, "quota_exceeded"),
            (RateLimited, 429, "rate_limited"),
            (ServiceUnavailable, 503, "service_unavailable"),
        ],
    )
    def test_status_and_code_are_declared_on_class(self, exc_cls, status, code):
        err = exc_cls()
        assert err.status_code == status
        assert err.code == code
        assert err.message == exc_cls.default_message

    def test_custom_message_overrides_default(self):
        err = NotFound("文件不存在")
        assert err.message == "文件不存在"
        assert err.to_payload() == {"detail": "文件不存在", "code": "not_found"}

    def test_details_included_in_payload(self):
        err = ValidationFailed("参数错误", details={"field": "email"})
        assert err.to_payload()["details"] == {"field": "email"}

    def test_default_app_error_is_500(self):
        err = AppError("未知错误")
        assert err.status_code == 500
        assert err.code == "internal_error"


@pytest.fixture
def error_app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/not-found")
    async def _not_found():
        raise NotFound("资源不存在")

    @app.get("/rate-limited")
    async def _rate_limited():
        raise RateLimited("请求过于频繁")

    @app.get("/quota")
    async def _quota():
        raise QuotaExceeded("存储空间不足")

    @app.get("/unauthorized")
    async def _unauthorized():
        raise Unauthorized("Token 已失效")

    return app


class TestExceptionHandler:
    def test_not_found_maps_to_404(self, error_app):
        client = TestClient(error_app, raise_server_exceptions=False)
        resp = client.get("/not-found")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "资源不存在", "code": "not_found"}

    def test_rate_limited_maps_to_429(self, error_app):
        client = TestClient(error_app, raise_server_exceptions=False)
        resp = client.get("/rate-limited")
        assert resp.status_code == 429
        assert resp.json()["code"] == "rate_limited"

    def test_quota_maps_to_413(self, error_app):
        client = TestClient(error_app, raise_server_exceptions=False)
        resp = client.get("/quota")
        assert resp.status_code == 413
        assert resp.json()["code"] == "quota_exceeded"

    def test_unauthorized_maps_to_401(self, error_app):
        client = TestClient(error_app, raise_server_exceptions=False)
        resp = client.get("/unauthorized")
        assert resp.status_code == 401
        assert resp.json()["code"] == "unauthorized"


class TestNoStringMatchingInEndpoints:
    def test_endpoints_do_not_catch_value_error(self):
        import pathlib

        endpoints_dir = (
            pathlib.Path(__file__).resolve().parent.parent / "app" / "api" / "v1" / "endpoints"
        )
        offenders = []
        for path in endpoints_dir.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "except ValueError" in text:
                offenders.append(path.name)
        assert offenders == [], f"端点层仍在用 ValueError 兜底: {offenders}"