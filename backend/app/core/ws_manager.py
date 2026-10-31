import json
from datetime import datetime, timezone
from uuid import uuid4
from loguru import logger
from fastapi import WebSocket
from app.core.config import settings

_WS_CHANNEL_PREFIX = "ws:user:"
_INSTANCE_ID = uuid4().hex


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._pubsub_enabled: bool = settings.WS_PUBSUB_ENABLED
        self._pubsub = None
        self._listen_task = None
        self._subscribed_users: set[str] = set()

    def connect(self, user_id: str, ws: WebSocket):
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(ws)
        self._subscribed_users.add(user_id)
        logger.bind(log_type="ws").info(
            f"WebSocket 连接: user={user_id}, 当前连接数={len(self._connections[user_id])}"
        )
        if self._pubsub_enabled and self._pubsub is not None:
            import asyncio
            try:
                asyncio.get_event_loop().create_task(
                    self._subscribe_user(user_id)
                )
            except Exception:
                pass

    def disconnect(self, user_id: str, ws: WebSocket):
        if user_id in self._connections:
            self._connections[user_id] = [w for w in self._connections[user_id] if w is not ws]
            if not self._connections[user_id]:
                del self._connections[user_id]
                self._subscribed_users.discard(user_id)
                if self._pubsub_enabled and self._pubsub is not None:
                    import asyncio
                    try:
                        asyncio.get_event_loop().create_task(
                            self._unsubscribe_user(user_id)
                        )
                    except Exception:
                        pass
            logger.bind(log_type="ws").info(f"WebSocket 断开: user={user_id}")

    async def send_to_user(self, user_id: str, event: str, data: dict):
        payload = json.dumps({
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if self._pubsub_enabled:
            await self._publish(user_id, payload)

        await self._send_local(user_id, payload)

    async def _send_local(self, user_id: str, payload: str):
        dead: list[WebSocket] = []
        targets = self._connections.get(user_id, [])
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def _publish(self, user_id: str, payload: str):
        try:
            from app.core.redis import redis_client
            await redis_client.publish(
                f"{_WS_CHANNEL_PREFIX}{user_id}",
                json.dumps({"origin": _INSTANCE_ID, "payload": payload}),
            )
        except Exception as exc:
            logger.bind(log_type="ws").warning(f"Redis publish 失败: {exc}")

    async def _subscribe_user(self, user_id: str):
        if self._pubsub is None:
            return
        try:
            channel = f"ws:user:{user_id}"
            await self._pubsub.subscribe(channel)
            logger.bind(log_type="ws").debug(f"已订阅频道: {channel}")
        except Exception as exc:
            logger.bind(log_type="ws").warning(f"订阅频道失败: {exc}")

    async def _unsubscribe_user(self, user_id: str):
        if self._pubsub is None:
            return
        try:
            channel = f"ws:user:{user_id}"
            await self._pubsub.unsubscribe(channel)
            logger.bind(log_type="ws").debug(f"已取消订阅频道: {channel}")
        except Exception as exc:
            logger.bind(log_type="ws").warning(f"取消订阅频道失败: {exc}")

    async def start_pubsub(self):
        if not self._pubsub_enabled:
            return
        try:
            from app.core.redis import redis_pubsub
            self._pubsub = redis_pubsub.pubsub()
            import asyncio
            self._listen_task = asyncio.create_task(self._listen_loop())
            logger.bind(log_type="ws").info("WebSocket Redis Pub/Sub 已启动（按需订阅模式）")
        except Exception as exc:
            logger.bind(log_type="ws").warning(f"Redis Pub/Sub 启动失败，回退到单 Worker 模式: {exc}")
            self._pubsub_enabled = False

    async def stop_pubsub(self):
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except Exception:
                pass
            self._listen_task = None
        if self._pubsub is not None:
            try:
                if self._subscribed_users:
                    channels = [f"{_WS_CHANNEL_PREFIX}{uid}" for uid in self._subscribed_users]
                    await self._pubsub.unsubscribe(*channels)
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None
        self._subscribed_users.clear()
        logger.bind(log_type="ws").info("WebSocket Redis Pub/Sub 已停止")

    async def _listen_loop(self):
        try:
            async for message in self._pubsub.listen():
                if message["type"] not in ("message",):
                    continue
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode("utf-8")
                user_id = channel.removeprefix(_WS_CHANNEL_PREFIX)
                raw = message["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                payload = self._unwrap_payload(raw)
                if payload is None:
                    continue
                if user_id in self._connections:
                    await self._send_local(user_id, payload)
        except Exception as exc:
            logger.bind(log_type="ws").warning(f"Redis Pub/Sub 监听异常: {exc}")

    @staticmethod
    def _unwrap_payload(raw: str) -> str | None:
        try:
            envelope = json.loads(raw)
        except (TypeError, ValueError):
            return raw
        if not isinstance(envelope, dict) or "payload" not in envelope:
            return raw
        if envelope.get("origin") == _INSTANCE_ID:
            return None
        payload = envelope["payload"]
        return payload if isinstance(payload, str) else json.dumps(payload)


ws_manager = ConnectionManager()