import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from app.services.share_service import (
    _generate_token,
    _generate_code,
    SHARE_VERIFY_MAX_ATTEMPTS,
    SHARE_VERIFY_LOCK_SECONDS,
)


class TestShareTokenGeneration:
    def test_token_length(self):
        token = _generate_token()
        assert len(token) == 32

    def test_token_uniqueness(self):
        tokens = {_generate_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_code_length(self):
        code = _generate_code()
        assert len(code) == 6

    def test_code_uppercase_digits(self):
        code = _generate_code()
        assert code.isupper() or code.isdigit() or all(c.isupper() or c.isdigit() for c in code)

    def test_code_uniqueness(self):
        codes = {_generate_code() for _ in range(100)}
        assert len(codes) == 100


class TestShareRateLimitConstants:
    def test_max_attempts(self):
        assert SHARE_VERIFY_MAX_ATTEMPTS == 5

    def test_lock_seconds(self):
        assert SHARE_VERIFY_LOCK_SECONDS == 900

    def test_lock_is_15_minutes(self):
        assert SHARE_VERIFY_LOCK_SECONDS == 15 * 60


class TestShareRateLimitLogic:
    @pytest.mark.asyncio
    async def test_check_rate_limit_raises_when_locked(self):
        with patch("app.services.share_service.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=True)
            mock_redis.ttl = AsyncMock(return_value=600)
            from app.services.share_service import check_share_rate_limit
            with pytest.raises(ValueError, match="过多"):
                await check_share_rate_limit("some-token")

    @pytest.mark.asyncio
    async def test_check_rate_limit_passes_when_not_locked(self):
        with patch("app.services.share_service.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=False)
            from app.services.share_service import check_share_rate_limit
            await check_share_rate_limit("some-token")

    @pytest.mark.asyncio
    async def test_record_failure_increments(self):
        with patch("app.services.share_service.redis_client") as mock_redis:
            mock_redis.incr = AsyncMock(return_value=1)
            mock_redis.expire = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis.delete = AsyncMock()
            from app.services.share_service import record_share_verify_failure
            await record_share_verify_failure("some-token")
            mock_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_failure_locks_at_max(self):
        with patch("app.services.share_service.redis_client") as mock_redis:
            mock_redis.incr = AsyncMock(return_value=SHARE_VERIFY_MAX_ATTEMPTS)
            mock_redis.expire = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis.delete = AsyncMock()
            from app.services.share_service import record_share_verify_failure
            await record_share_verify_failure("some-token")
            mock_redis.setex.assert_called_once()
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_attempts(self):
        with patch("app.services.share_service.redis_client") as mock_redis:
            mock_redis.delete = AsyncMock()
            from app.services.share_service import clear_share_verify_attempts
            await clear_share_verify_attempts("some-token")
            mock_redis.delete.assert_called_once()