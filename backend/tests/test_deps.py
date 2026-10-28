import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.api.deps import (
    _serialize_user,
    _deserialize_user,
    invalidate_user_cache,
    USER_CACHE_TTL,
)
from app.models.user import User
from app.core.security import hash_password


SENSITIVE_FIELDS = ("hashed_password", "security_question", "security_answer")
REQUIRED_FIELDS = (
    "id", "email", "username", "is_active", "is_admin",
    "avatar_key", "storage_quota", "used_storage",
    "created_at", "updated_at",
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
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
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
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.delete = AsyncMock()
            uid = uuid4()
            await invalidate_user_cache(uid)
            mock_redis.delete.assert_called_once_with(f"user:{uid}")