import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.user import User
from app.models.file import File
from app.models.folder import Folder
from app.models.share import Share


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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


@pytest.fixture
def fake_user() -> User:
    return _make_user()


@pytest.fixture
def fake_admin() -> User:
    return _make_user(is_admin=True, email="admin@example.com", username="admin")


@pytest.fixture
def auth_headers(fake_user: User) -> dict:
    token = create_access_token({"sub": str(fake_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(fake_admin: User) -> dict:
    token = create_access_token({"sub": str(fake_admin.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest.fixture
def mock_redis():
    with patch("app.core.redis.redis_client") as mock_client:
        mock_client.get = AsyncMock(return_value=None)
        mock_client.set = AsyncMock()
        mock_client.setex = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_client.exists = AsyncMock(return_value=False)
        mock_client.incr = AsyncMock(return_value=1)
        mock_client.expire = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=900)
        mock_client.pipeline = MagicMock()
        yield mock_client


@pytest.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client