import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.request_logging import RequestLoggingMiddleware, request_id_ctx


@pytest.fixture
def logging_app():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    async def _ping():
        return {"request_id": request_id_ctx.get()}

    @app.get("/boom")
    async def _boom():
        raise RuntimeError("boom")

    return app


class TestRequestLoggingMiddleware:
    def test_adds_request_id_header(self, logging_app):
        client = TestClient(logging_app, raise_server_exceptions=False)
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.headers["x-request-id"]
        assert len(resp.headers["x-request-id"]) == 8

    def test_request_id_visible_in_handler_context(self, logging_app):
        client = TestClient(logging_app, raise_server_exceptions=False)
        resp = client.get("/ping")
        assert resp.json()["request_id"] == resp.headers["x-request-id"]

    def test_correlation_id_propagates(self, logging_app):
        client = TestClient(logging_app, raise_server_exceptions=False)
        resp = client.get("/ping", headers={"X-Request-ID": "caller-abc"})
        assert resp.headers["x-correlation-id"] == "caller-abc"
        assert resp.headers["x-request-id"] != "caller-abc"

    def test_error_response_still_carries_request_id(self, logging_app):
        client = TestClient(logging_app, raise_server_exceptions=False)
        resp = client.get("/boom")
        assert resp.status_code == 500
        assert resp.headers["x-request-id"]


class TestMiddlewareIsWired:
    def test_main_app_registers_request_logging(self):
        import app.main as main_module

        names = [m.cls.__name__ for m in main_module.app.user_middleware]
        assert "RequestLoggingMiddleware" in names
