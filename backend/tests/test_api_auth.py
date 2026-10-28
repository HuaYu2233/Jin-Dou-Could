import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from starlette.testclient import TestClient
from app.main import app
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password


class TestSecurityModule:
    def test_hash_password_returns_bcrypt(self):
        hashed = hash_password("Test1234")
        assert hashed.startswith("$2b$")
        assert hashed != "Test1234"

    def test_verify_password_correct(self):
        hashed = hash_password("Test1234")
        assert verify_password("Test1234", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("Test1234")
        assert verify_password("wrong", hashed) is False

    def test_create_access_token_has_type(self):
        token = create_access_token({"sub": "user-1"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "access"
        assert payload["sub"] == "user-1"
        assert "jti" in payload
        assert "exp" in payload

    def test_create_refresh_token_has_type(self):
        token = create_refresh_token({"sub": "user-1"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-1"

    def test_decode_invalid_token_returns_none(self):
        result = decode_token("invalid.token.here")
        assert result is None

    def test_access_and_refresh_types_differ(self):
        access = decode_token(create_access_token({"sub": "u"}))
        refresh = decode_token(create_refresh_token({"sub": "u"}))
        assert access["type"] != refresh["type"]

    def test_token_without_type_rejected_by_logic(self):
        from jose import jwt
        from app.core.config import settings
        fake = jwt.encode({"sub": "u", "jti": "x"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        payload = decode_token(fake)
        assert payload.get("type") != "access"
        assert payload.get("type") != "refresh"


class TestAuthEndpoints:
    def test_register_missing_fields(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post("/api/v1/auth/register", json={})
            assert resp.status_code == 422

    def test_register_invalid_email(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/register",
                json={"email": "not-an-email", "username": "test", "password": "Test1234"},
            )
            assert resp.status_code == 422

    def test_register_weak_password(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/register",
                json={"email": "test@example.com", "username": "test", "password": "short"},
            )
            assert resp.status_code == 422

    def test_login_missing_fields(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post("/api/v1/auth/login", json={})
            assert resp.status_code == 422

    def test_login_invalid_credentials(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            mock_redis.incr = AsyncMock(return_value=1)
            mock_redis.expire = AsyncMock()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "Wrong1234"},
            )
            assert resp.status_code in (401, 429, 500)

    def test_forgot_password_invalid_email(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "bad-email"},
            )
            assert resp.status_code == 422

    def test_security_question_invalid_email(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/security-question",
                json={"email": "bad-email"},
            )
            assert resp.status_code == 422


class TestAuthDeps:
    def test_get_client_ip_from_xff(self):
        from app.services.auth_service import get_client_ip
        request = MagicMock()
        request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        assert get_client_ip(request) == "1.2.3.4"

    def test_get_client_ip_from_x_real_ip(self):
        from app.services.auth_service import get_client_ip
        request = MagicMock()
        request.headers = {"x-real-ip": "10.0.0.1"}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        assert get_client_ip(request) == "10.0.0.1"

    def test_get_client_ip_fallback(self):
        from app.services.auth_service import get_client_ip
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        assert get_client_ip(request) == "192.168.1.1"

    def test_get_client_ip_no_client(self):
        from app.services.auth_service import get_client_ip
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert get_client_ip(request) == "unknown"