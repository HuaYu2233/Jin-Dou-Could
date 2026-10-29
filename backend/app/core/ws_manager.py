import json
from datetime import datetime, timezone
from loguru import logger
from fastapi import WebSocket
from app.core.config import settings

_WS_CHANNEL_PREFIX = "ws:user:"


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._pubsub_enabled: bool = settings.WS_PUBSUB_ENABLED
        self._pubsub = None
        self._listen_task = None

    def connect(self, user_id: str, ws: WebSocket):
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(ws)
        logger.bind(log_type="ws").info(
            f"WebSocket 连接: user={user_id}, 当前连接数={len(self._connections[user_id])}"
        )

    def disconnect(self, user_id: str, ws: WebSocket):
        if user_id in self._connections:
            self._connections[user_id] = [w for w in self._connections[user_id] if w is not ws]
            if not self._connections[user_id]:
                del self._connections[user_id]
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
            await redis_client.publish(f"{_WS_CHANNEL_PREFIX}{user_id}", payload)
        except Exception as exc:
            logger.bind(log_type="ws").warning(f"Redis publish 失败: {exc}")

    async def broadcast(self, event: str, data: dict):
        payload = json.dumps({
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        for user_id in list(self._connections.keys()):
            if self._pubsub_enabled:
                await self._publish(user_id, payload)
            await self._send_local(user_id, payload)

    async def start_pubsub(self):
        if not self._pubsub_enabled:
            return
        try:
            from app.core.redis import redis_pubsub
            self._pubsub = redis_pubsub.pubsub()
            await self._pubsub.psubscribe(f"{_WS_CHANNEL_PREFIX}*")
            import asyncio
            self._listen_task = asyncio.create_task(self._listen_loop())
            logger.bind(log_type="ws").info("WebSocket Redis Pub/Sub 已启动")
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
                await self._pubsub.punsubscribe()
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None
        logger.bind(log_type="ws").info("WebSocket Redis Pub/Sub 已停止")

    async def _listen_loop(self):
        try:
            async for message in self._pubsub.listen():
                if message["type"] not in ("pmessage",):
                    continue
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode("utf-8")
                user_id = channel.removeprefix(_WS_CHANNEL_PREFIX)
                payload = message["data"]
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                await self._send_local(user_id, payload)
        except Exception as exc:
            logger.bind(log_type="ws").warning(f"Redis Pub/Sub 监听异常: {exc}")

    @property
    def online_count(self) -> int:
        return len(self._connections)

    def user_online(self, user_id: str) -> bool:
        return user_id in self._connections and len(self._connections[user_id]) > 0


ws_manager = ConnectionManager()