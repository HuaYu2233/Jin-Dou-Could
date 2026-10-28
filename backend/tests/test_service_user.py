import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.user_service import (
    create_user,
    upload_avatar,
    update_profile,
    change_password,
    update_security_question,
    ALLOWED_AVATAR_TYPES,
    MAX_AVATAR_SIZE,
)
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password, verify_password


def _make_user(**overrides) -> User:
    defaults = {
        "id": uuid4(),
        "email": "test@example.com",
        "username": "testuser",
        "hashed_password": hash_password("Test1234"),
        "is_active": True,
        "is_admin": False,
        "avatar_key": None,
        "security_question": None,
        "security_answer": None,
        "storage_quota": 1073741824,
        "used_storage": 0,
    }
    defaults.update(overrides)
    user = User()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


class TestUploadAvatar:
    @pytest.mark.asyncio
    async def test_rejects_oversized_avatar(self):
        db = AsyncMock()
        user = _make_user()
        big_content = b"x" * (MAX_AVATAR_SIZE + 1)
        with pytest.raises(ValueError, match="2MB"):
            await upload_avatar(db, user, big_content, "image/jpeg")

    @pytest.mark.asyncio
    async def test_rejects_invalid_mime(self):
        db = AsyncMock()
        user = _make_user()
        with pytest.raises(ValueError, match="JPG/PNG/WEBP/GIF"):
            await upload_avatar(db, user, b"img", "text/plain")

    def test_allowed_avatar_types(self):
        assert "image/jpeg" in ALLOWED_AVATAR_TYPES
        assert "image/png" in ALLOWED_AVATAR_TYPES
        assert "image/webp" in ALLOWED_AVATAR_TYPES
        assert "image/gif" in ALLOWED_AVATAR_TYPES
        assert "text/plain" not in ALLOWED_AVATAR_TYPES


class TestUpdateProfile:
    @pytest.mark.asyncio
    async def test_rejects_short_username(self):
        db = AsyncMock()
        user = _make_user()
        with pytest.raises(ValueError, match="2"):
            await update_profile(db, user, "a")

    @pytest.mark.asyncio
    async def test_strips_username(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        user = _make_user()
        result = await update_profile(db, user, "  newname  ")
        assert result.username == "newname"

    @pytest.mark.asyncio
    async def test_none_username_no_change(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        user = _make_user()
        original = user.username
        result = await update_profile(db, user, None)
        assert result.username == original


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_rejects_wrong_old_password(self):
        db = AsyncMock()
        user = _make_user()
        with pytest.raises(ValueError, match="原密码错误"):
            await change_password(db, user, "WrongPass1", "NewPass1234")

    @pytest.mark.asyncio
    async def test_changes_password_correctly(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        user = _make_user()
        old_hash = user.hashed_password
        result = await change_password(db, user, "Test1234", "NewPass1234")
        assert result.hashed_password != old_hash
        assert verify_password("NewPass1234", result.hashed_password)


class TestUpdateSecurityQuestion:
    @pytest.mark.asyncio
    async def test_rejects_short_question(self):
        db = AsyncMock()
        user = _make_user()
        with pytest.raises(ValueError, match="2"):
            await update_security_question(db, user, "a", "answer")

    @pytest.mark.asyncio
    async def test_rejects_empty_answer(self):
        db = AsyncMock()
        user = _make_user()
        with pytest.raises(ValueError, match="不能为空"):
            await update_security_question(db, user, "question", "  ")

    @pytest.mark.asyncio
    async def test_sets_security_question(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        user = _make_user()
        result = await update_security_question(db, user, "你的宠物？", "小花")
        assert result.security_question == "你的宠物？"
        assert result.security_answer is not None