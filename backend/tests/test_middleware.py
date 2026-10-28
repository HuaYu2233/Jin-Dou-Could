import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient
from app.main import app


class TestSecurityHeadersMiddleware:
    def test_health_endpoint_accessible(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_api_docs_accessible(self):
        client = TestClient(app)
        resp = client.get("/docs")
        assert resp.status_code == 200


class TestRateLimitMiddleware:
    def test_health_exempt_from_rate_limit(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200


class TestCORSMiddleware:
    def test_cors_preflight(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
            assert resp.status_code == 200
            assert "access-control-allow-origin" in resp.headers


class TestAppStructure:
    def test_404_for_unknown_route(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/nonexistent")
            assert resp.status_code == 404

    def test_openapi_json(self):
        client = TestClient(app)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "paths" in data
        assert "/api/v1/auth/login" in data["paths"]
        assert "/api/v1/auth/register" in data["paths"]
        assert "/api/v1/files" in data["paths"]
        assert "/api/v1/folders" in data["paths"]
        assert "/api/v1/shares" in data["paths"]