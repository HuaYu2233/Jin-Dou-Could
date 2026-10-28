import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.auth_service import (
    get_client_ip,
    check_login_rate_limit,
    record_login_failure,
    clear_login_rate_limit,
    authenticate_user,
    set_auth_cookies,
)
from app.models.user import User
from app.core.security import hash_password


def _make_user(**overrides) -> User:
    defaults = {
        "id": uuid4(),
        "email": "test@example.com",
        "username": "testuser",
        "hashed_password": hash_password("Test1234"),
        "is_active": True,
        "is_admin": False,
    }
    defaults.update(overrides)
    user = User()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


class TestGetClientIp:
    def test_xff_first(self):
        req = MagicMock()
        req.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        req.client = MagicMock(host="127.0.0.1")
        assert get_client_ip(req) == "1.2.3.4"

    def test_x_real_ip(self):
        req = MagicMock()
        req.headers = {"x-real-ip": "10.0.0.1"}
        req.client = MagicMock(host="127.0.0.1")
        assert get_client_ip(req) == "10.0.0.1"

    def test_fallback_to_client(self):
        req = MagicMock()
        req.headers = {}
        req.client = MagicMock(host="192.168.1.1")
        assert get_client_ip(req) == "192.168.1.1"

    def test_no_client(self):
        req = MagicMock()
        req.headers = {}
        req.client = None
        assert get_client_ip(req) == "unknown"


class TestCheckLoginRateLimit:
    @pytest.mark.asyncio
    async def test_raises_when_locked(self):
        with patch("app.services.auth_service.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=True)
            mock_redis.ttl = AsyncMock(return_value=300)
            with pytest.raises(ValueError, match="频繁"):
                await check_login_rate_limit("1.2.3.4", "test@example.com")

    @pytest.mark.asyncio
    async def test_passes_when_not_locked(self):
        with patch("app.services.auth_service.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=False)
            await check_login_rate_limit("1.2.3.4", "test@example.com")


class TestRecordLoginFailure:
    @pytest.mark.asyncio
    async def test_first_failure(self):
        with patch("app.services.auth_service.redis_client") as mock_redis:
            mock_redis.incr = AsyncMock(return_value=1)
            mock_redis.expire = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis.delete = AsyncMock()
            await record_login_failure("1.2.3.4", "test@example.com")
            mock_redis.incr.assert_called_once()
            mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_at_max_attempts(self):
        from app.core.config import settings
        with patch("app.services.auth_service.redis_client") as mock_redis:
            mock_redis.incr = AsyncMock(return_value=settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS)
            mock_redis.expire = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis.delete = AsyncMock()
            await record_login_failure("1.2.3.4", "test@example.com")
            mock_redis.setex.assert_called_once()
            mock_redis.delete.assert_called_once()


class TestClearLoginRateLimit:
    @pytest.mark.asyncio
    async def test_clears(self):
        with patch("app.services.auth_service.redis_client") as mock_redis:
            mock_redis.delete = AsyncMock()
            await clear_login_rate_limit("1.2.3.4", "test@example.com")
            mock_redis.delete.assert_called_once()


class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_returns_none_for_wrong_password(self):
        db = AsyncMock()
        user = _make_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=user)
        db.execute = AsyncMock(return_value=mock_result)
        result = await authenticate_user(db, "test@example.com", "WrongPass1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_user(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=mock_result)
        result = await authenticate_user(db, "nobody@example.com", "Test1234")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_for_correct_password(self):
        db = AsyncMock()
        user = _make_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=user)
        db.execute = AsyncMock(return_value=mock_result)
        result = await authenticate_user(db, "test@example.com", "Test1234")
        assert result is not None
        assert result.email == "test@example.com"


class TestSetAuthCookies:
    def test_sets_cookies(self):
        response = MagicMock()
        response.set_cookie = MagicMock()
        user = _make_user()
        set_auth_cookies(response, user)
        assert response.set_cookie.call_count == 2
        calls = response.set_cookie.call_args_list
        assert calls[0][1]["key"] == "access_token"
        assert calls[1][1]["key"] == "refresh_token"
        assert calls[0][1]["httponly"] is True
        assert calls[1][1]["httponly"] is True