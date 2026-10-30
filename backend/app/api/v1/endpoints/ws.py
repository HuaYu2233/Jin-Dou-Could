import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.security import decode_token
from app.core.ws_manager import ws_manager
from loguru import logger

router = APIRouter()

_AUTH_TIMEOUT = 5.0
_MAX_AUTH_MSG_SIZE = 4096


@router.websocket("/connect")
async def ws_connect(ws: WebSocket):
    await ws.accept()

    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=_AUTH_TIMEOUT)
        if len(raw) > _MAX_AUTH_MSG_SIZE:
            await ws.close(code=4001, reason="认证消息过长")
            return
        msg = json.loads(raw)
    except asyncio.TimeoutError:
        await ws.close(code=4001, reason="认证超时")
        return
    except Exception:
        await ws.close(code=4001, reason="认证消息格式错误")
        return

    if msg.get("type") != "auth" or not msg.get("token"):
        await ws.close(code=4001, reason="缺少认证信息")
        return

    payload = decode_token(msg["token"])
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="认证失败")
        return

    user_id = payload.get("sub")
    if not user_id:
        await ws.close(code=4001, reason="无效令牌")
        return

    try:
        await ws.send_json({"event": "auth:ok", "data": {}})
    except Exception:
        await ws.close(code=4001, reason="发送认证确认失败")
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