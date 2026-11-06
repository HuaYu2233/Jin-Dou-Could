import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy import select

from app.core.security import decode_token
from app.core.ws_manager import ws_manager
from app.db.base import AsyncSessionLocal
from app.models.user import User

router = APIRouter()

_AUTH_TIMEOUT = 5.0
_MAX_AUTH_MSG_SIZE = 4096


async def _authenticate(ws: WebSocket):
    token = ws.cookies.get("access_token")
    if not token:
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=_AUTH_TIMEOUT)
            if len(raw) > _MAX_AUTH_MSG_SIZE:
                await ws.close(code=4001, reason="认证消息过长")
                return None
            msg = json.loads(raw)
            if msg.get("type") == "auth" and msg.get("token"):
                token = msg["token"]
        except TimeoutError:
            await ws.close(code=4001, reason="认证超时")
            return None
        except Exception:
            await ws.close(code=4001, reason="认证消息格式错误")
            return None

    if not token:
        await ws.close(code=4001, reason="缺少认证信息")
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="认证失败")
        return None

    user_id = payload.get("sub")
    if not user_id:
        await ws.close(code=4001, reason="无效令牌")
        return None

    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        await ws.close(code=4001, reason="无效令牌")
        return None

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_uuid))
            user = result.scalar_one_or_none()
    except Exception as exc:
        logger.bind(log_type="ws").warning(f"WebSocket 认证查询用户失败: {exc}")
        await ws.close(code=4001, reason="认证失败")
        return None

    if not user or not user.is_active:
        await ws.close(code=4001, reason="账号已被禁用")
        return None

    try:
        await ws.send_json({"event": "auth:ok", "data": {}})
    except Exception:
        await ws.close(code=4001, reason="发送认证确认失败")
        return None

    return user_id


@router.websocket("/connect")
async def ws_connect(ws: WebSocket):
    await ws.accept()

    user_id = await _authenticate(ws)
    if not user_id:
        return

    ws_manager.connect(user_id, ws)

    try:
        while True:
            raw = await ws.receive_text()
            logger.bind(log_type="ws").debug(f"收到消息: user={user_id}, msg={raw[:100]}")
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, ws)
    except Exception as exc:
        logger.bind(log_type="ws").warning(f"WebSocket 异常: user={user_id}, {exc}")
        ws_manager.disconnect(user_id, ws)
