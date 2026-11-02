import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.deps import (
    USER_CACHE_TTL,
    _deserialize_user,
    _serialize_user,
    get_current_user,
    invalidate_user_cache,
)
from app.core.security import create_access_token, hash_password
from app.models.user import User

SENSITIVE_FIELDS = ("hashed_password", "security_question", "security_answer")
REQUIRED_FIELDS = (
    "id",
    "email",
    "username",
    "is_active",
    "is_admin",
    "avatar_key",
    "storage_quota",
    "used_storage",
    "created_at",
    "updated_at",
)


def _make_user(**overrides) -> User:
    defaults = {
        "id": uuid4(),
        "email": "test@example.com",
        "username": "testuser",
        "hashed_password": hash_password("Test1234"),
        "is_active": True,
        "is_admin": False,
        "avatar_key": "avatars/test.png",
        "security_question": "你的宠物叫什么",
        "security_answer": hash_password("小花"),
        "storage_quota": 3221225472,
        "used_storage": 1024,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    user = User()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


class TestSerializeUser:
    def test_excludes_sensitive_fields(self):
        user = _make_user()
        data = json.loads(_serialize_user(user))
        for field in SENSITIVE_FIELDS:
            assert field not in data, f"敏感字段 {field} 不应出现在序列化结果中"

    def test_keeps_required_fields(self):
        user = _make_user()
        data = json.loads(_serialize_user(user))
        for field in REQUIRED_FIELDS:
            assert field in data, f"必需字段 {field} 应出现在序列化结果中"

    def test_id_is_string(self):
        user = _make_user()
        data = json.loads(_serialize_user(user))
        assert isinstance(data["id"], str)


class TestDeserializeUser:
    def test_sensitive_fields_are_none(self):
        user = _make_user()
        cached = _serialize_user(user)
        restored = _deserialize_user(cached)
        assert restored.hashed_password is None
        assert restored.security_question is None
        assert restored.security_answer is None

    def test_preserves_required_fields(self):
        user = _make_user()
        cached = _serialize_user(user)
        restored = _deserialize_user(cached)
        assert str(restored.id) == str(user.id)
        assert restored.email == user.email
        assert restored.username == user.username
        assert restored.is_active == user.is_active
        assert restored.is_admin == user.is_admin
        assert restored.storage_quota == user.storage_quota
        assert restored.used_storage == user.used_storage

    def test_round_trip_preserves_data(self):
        user = _make_user()
        cached = _serialize_user(user)
        restored = _deserialize_user(cached)
        data1 = json.loads(_serialize_user(restored))
        data2 = json.loads(cached)
        assert data1["email"] == data2["email"]
        assert data1["username"] == data2["username"]


class TestUserCacheTTL:
    def test_ttl_is_positive(self):
        assert USER_CACHE_TTL > 0

    def test_ttl_is_60(self):
        assert USER_CACHE_TTL == 60


class TestInvalidateUserCache:
    @pytest.mark.asyncio
    async def test_calls_redis_delete(self):
        async def _empty_scan(*args, **kwargs):
            for _ in ():
                yield _

        pipe = MagicMock()
        pipe.delete = MagicMock()
        pipe.execute = AsyncMock()

        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.pipeline = MagicMock(return_value=pipe)
            mock_redis.scan_iter = _empty_scan
            uid = uuid4()
            await invalidate_user_cache(uid)

        deleted = [call.args[0] for call in pipe.delete.call_args_list]
        assert f"user:{uid}" in deleted
        assert f"trash_count:{uid}" in deleted
        pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_purges_file_count_keys(self):
        async def _scan(*args, **kwargs):
            for key in (f"file_count:{uid}:all", f"file_count:{uid}:image"):
                yield key

        uid = uuid4()
        pipe = MagicMock()
        pipe.delete = MagicMock()
        pipe.execute = AsyncMock()

        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.pipeline = MagicMock(return_value=pipe)
            mock_redis.scan_iter = _scan
            mock_redis.delete = AsyncMock()
            await invalidate_user_cache(uid)

        mock_redis.delete.assert_awaited_once_with(f"file_count:{uid}:all", f"file_count:{uid}:image")


class TestInactiveUserRejected:
    @pytest.mark.asyncio
    async def test_rejects_inactive_cached_user(self):
        inactive = _make_user(is_active=False)
        request = MagicMock()
        request.method = "GET"
        token = create_access_token({"sub": str(inactive.id)})
        db = AsyncMock()

        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=0)
            mock_redis.get = AsyncMock(return_value=_serialize_user(inactive))
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, token, db)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_inactive_user_from_db(self):
        inactive = _make_user(is_active=False)
        request = MagicMock()
        request.method = "POST"
        token = create_access_token({"sub": str(inactive.id)})

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=inactive)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=0)
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, token, db)

        assert exc_info.value.status_code == 403
