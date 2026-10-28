from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import decode_token
from app.core.ws_manager import ws_manager
from loguru import logger

router = APIRouter()


@router.websocket("/connect")
async def ws_connect(ws: WebSocket, token: str = Query(...)):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="认证失败")
        return

    user_id = payload.get("sub")
    if not user_id:
        await ws.close(code=4001, reason="无效令牌")
        return

    await ws.accept()
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