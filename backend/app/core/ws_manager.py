import json
from datetime import datetime, timezone
from loguru import logger
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    def connect(self, user_id: str, ws: WebSocket):
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(ws)
        logger.bind(log_type="ws").info(f"WebSocket 连接: user={user_id}, 当前连接数={len(self._connections[user_id])}")

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
        dead: list[WebSocket] = []
        targets = self._connections.get(user_id, [])
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def broadcast(self, event: str, data: dict):
        for user_id in list(self._connections.keys()):
            await self.send_to_user(user_id, event, data)

    @property
    def online_count(self) -> int:
        return len(self._connections)

    def user_online(self, user_id: str) -> bool:
        return user_id in self._connections and len(self._connections[user_id]) > 0


ws_manager = ConnectionManager()