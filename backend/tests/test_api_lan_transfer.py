import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from starlette.testclient import TestClient

from app.core.security import create_room_token
from app.main import app
from app.services import lan_transfer_service as svc


def _room_token(room_id) -> str:
    return create_room_token(room_id, "guest", "anon:testclient", timedelta(hours=1))


class TestOwnerEndpoints:
    def test_create_room_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post("/api/v1/lan-transfer/rooms", json={})
            assert resp.status_code == 401

    def test_get_room_requires_auth(self):
        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get(f"/api/v1/lan-transfer/rooms/{uuid4()}")
            assert resp.status_code == 401


class TestJoinEndpoint:
    def test_join_returns_403_when_feature_disabled(self):
        with patch.object(svc.settings, "LAN_TRANSFER_ENABLED", False):
            client = TestClient(app)
            resp = client.post("/api/v1/lan-transfer/public/rooms/ABCD1234/join", json={})
            assert resp.status_code == 403
            assert "关闭" in resp.json()["detail"]

    def test_join_returns_403_when_disk_low(self):
        with (
            patch.object(svc.settings, "LAN_TRANSFER_ENABLED", True),
            patch.object(svc.settings, "LAN_TRANSFER_MIN_FREE_BYTES", 100),
            patch.object(svc, "get_disk_usage", return_value=(1000, 950, 50)),
        ):
            client = TestClient(app)
            resp = client.post("/api/v1/lan-transfer/public/rooms/ABCD1234/join", json={})
            assert resp.status_code == 507


class TestRoomTokenGuard:
    def test_files_requires_room_token(self):
        client = TestClient(app)
        resp = client.get(f"/api/v1/lan-transfer/public/rooms/{uuid4()}/files")
        assert resp.status_code == 401
        assert "令牌" in resp.json()["detail"]

    def test_invalid_room_token_rejected(self):
        client = TestClient(app)
        resp = client.get(
            f"/api/v1/lan-transfer/public/rooms/{uuid4()}/files",
            headers={"X-Room-Token": "not-a-token"},
        )
        assert resp.status_code == 401

    def test_token_for_other_room_forbidden(self):
        token = _room_token(uuid4())
        client = TestClient(app)
        resp = client.get(
            f"/api/v1/lan-transfer/public/rooms/{uuid4()}/files",
            headers={"X-Room-Token": token},
        )
        assert resp.status_code == 403
        assert "不匹配" in resp.json()["detail"]

    def test_delete_requires_room_token(self):
        client = TestClient(app)
        resp = client.delete(
            f"/api/v1/lan-transfer/public/rooms/{uuid4()}/files/{uuid4()}",
        )
        assert resp.status_code == 401

    def test_download_requires_room_token(self):
        client = TestClient(app)
        resp = client.get(
            f"/api/v1/lan-transfer/public/rooms/{uuid4()}/files/{uuid4()}/download",
        )
        assert resp.status_code == 401


class TestPublicPrefixMiddleware:
    def test_bad_room_id_returns_404(self):
        client = TestClient(app)
        resp = client.get(
            "/api/v1/lan-transfer/public/rooms/not-a-uuid/files",
            headers={"X-Room-Token": _room_token(uuid4())},
        )
        assert resp.status_code == 404
