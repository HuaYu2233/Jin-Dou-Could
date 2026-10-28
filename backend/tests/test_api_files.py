import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.models.user import User
from app.core.security import hash_password
from uuid import uuid4


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


MOCK_USER = _make_user()
MOCK_ADMIN = _make_user(is_admin=True, email="admin@example.com", username="admin")


class TestFileEndpoints:
    def test_list_files_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/files")
            assert resp.status_code == 401

    def test_search_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/files/search?keyword=test")
            assert resp.status_code == 401

    def test_trash_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/files/trash")
            assert resp.status_code == 401

    def test_move_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post(
                "/api/v1/files/move",
                json={"file_ids": [str(uuid4())], "target_folder_id": None},
            )
            assert resp.status_code == 401


class TestFolderEndpoints:
    def test_list_folders_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/folders")
            assert resp.status_code == 401

    def test_create_folder_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post("/api/v1/folders", json={"name": "test"})
            assert resp.status_code == 401

    def test_delete_folder_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.delete(f"/api/v1/folders/{uuid4()}")
            assert resp.status_code == 401


class TestShareEndpoints:
    def test_list_shares_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/shares")
            assert resp.status_code == 401

    def test_create_share_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post(f"/api/v1/shares/{uuid4()}", json={})
            assert resp.status_code == 401

    def test_public_share_info_not_found(self):
        with patch("app.api.deps.redis_client") as mock_redis, \
             patch("app.db.base.engine") as mock_engine:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/v1/shares/public/nonexistent-token")
            assert resp.status_code in (404, 500)


class TestAdminEndpoints:
    def test_admin_stats_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/admin/stats")
            assert resp.status_code == 401

    def test_admin_users_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/admin/users")
            assert resp.status_code == 401


class TestUsersEndpoints:
    def test_me_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/users/me")
            assert resp.status_code == 401

    def test_update_profile_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.patch("/api/v1/users/me/profile", json={"username": "test"})
            assert resp.status_code == 401

    def test_change_password_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.patch(
                "/api/v1/users/me/password",
                json={"old_password": "Old12345", "new_password": "NewPass1234"},
            )
            assert resp.status_code == 401


class TestHealthEndpoint:
    def test_health_endpoint(self):
        with patch("app.services.health_service.engine") as mock_engine, \
             patch("app.services.health_service.get_s3_client") as mock_s3, \
             patch("app.services.health_service.ping_redis") as mock_ping:
            mock_ping.return_value = True
            mock_engine.connect = AsyncMock()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_openapi_schema(self):
        client = TestClient(app)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert "paths" in resp.json()