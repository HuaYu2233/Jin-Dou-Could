import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import ws_manager as ws_module
from app.core.ws_manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, fail: bool = False):
        self.sent = []
        self.fail = fail

    async def send_text(self, payload: str):
        if self.fail:
            raise RuntimeError("连接已断开")
        self.sent.append(payload)


def _make_manager(pubsub_enabled: bool = True) -> ConnectionManager:
    mgr = ConnectionManager()
    mgr._pubsub_enabled = pubsub_enabled
    return mgr


def _register(mgr: ConnectionManager, user_id: str, ws) -> None:
    mgr._connections.setdefault(user_id, []).append(ws)


class TestSendToUser:
    @pytest.mark.asyncio
    async def test_pubsub_disabled_sends_locally_only(self):
        mgr = _make_manager(pubsub_enabled=False)
        ws = FakeWebSocket()
        _register(mgr, "u1", ws)

        await mgr.send_to_user("u1", "upload:complete", {"id": "1"})

        assert len(ws.sent) == 1
        assert json.loads(ws.sent[0])["event"] == "upload:complete"

    @pytest.mark.asyncio
    async def test_pubsub_enabled_publishes_with_instance_envelope(self):
        mgr = _make_manager(pubsub_enabled=True)
        ws = FakeWebSocket()
        _register(mgr, "u1", ws)

        with patch("app.core.redis.redis_client") as mock_redis:
            mock_redis.publish = AsyncMock()
            await mgr.send_to_user("u1", "storage:changed", {"used": 1})

        channel, raw = mock_redis.publish.await_args.args
        assert channel == "ws:user:u1"
        envelope = json.loads(raw)
        assert envelope["origin"] == ws_module._INSTANCE_ID
        assert json.loads(envelope["payload"])["event"] == "storage:changed"
        assert len(ws.sent) == 1

    @pytest.mark.asyncio
    async def test_dead_connection_is_removed(self):
        mgr = _make_manager(pubsub_enabled=False)
        dead = FakeWebSocket(fail=True)
        alive = FakeWebSocket()
        _register(mgr, "u1", dead)
        _register(mgr, "u1", alive)

        await mgr.send_to_user("u1", "ping", {})

        assert mgr._connections["u1"] == [alive]
        assert len(alive.sent) == 1


class TestUnwrapPayload:
    def test_own_message_is_skipped(self):
        raw = json.dumps({"origin": ws_module._INSTANCE_ID, "payload": '{"event":"x"}'})
        assert ConnectionManager._unwrap_payload(raw) is None

    def test_foreign_message_is_unwrapped(self):
        raw = json.dumps({"origin": "other-instance", "payload": '{"event":"x"}'})
        assert ConnectionManager._unwrap_payload(raw) == '{"event":"x"}'

    def test_legacy_plain_payload_passes_through(self):
        assert ConnectionManager._unwrap_payload('{"event":"x"}') == '{"event":"x"}'

    def test_invalid_json_passes_through(self):
        assert ConnectionManager._unwrap_payload("not-json") == "not-json"


class TestListenLoopNoDuplicate:
    @pytest.mark.asyncio
    async def test_same_message_delivered_once(self):
        mgr = _make_manager(pubsub_enabled=True)
        ws = FakeWebSocket()
        _register(mgr, "u1", ws)

        messages = [
            {"type": "subscribe", "channel": "ws:user:u1", "data": 1},
            {
                "type": "message",
                "channel": "ws:user:u1",
                "data": json.dumps({"origin": ws_module._INSTANCE_ID, "payload": "{}"}),
            },
        ]

        async def _fake_listen():
            for m in messages:
                yield m

        mgr._pubsub = MagicMock()
        mgr._pubsub.listen = _fake_listen

        await mgr._listen_loop()

        assert ws.sent == []

    @pytest.mark.asyncio
    async def test_foreign_message_delivered_locally(self):
        mgr = _make_manager(pubsub_enabled=True)
        ws = FakeWebSocket()
        _register(mgr, "u1", ws)

        async def _fake_listen():
            yield {
                "type": "message",
                "channel": b"ws:user:u1",
                "data": json.dumps({"origin": "other", "payload": '{"event":"x"}'}),
            }

        mgr._pubsub = MagicMock()
        mgr._pubsub.listen = _fake_listen

        await mgr._listen_loop()

        assert len(ws.sent) == 1
        assert json.loads(ws.sent[0])["event"] == "x"
