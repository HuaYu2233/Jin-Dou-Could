import json
from app.core.config import settings


def build_webhook_payload(text: str) -> bytes:
    wtype = settings.ALERT_WEBHOOK_TYPE
    if wtype == "dingtalk":
        payload = {"msgtype": "text", "text": {"content": text}}
    elif wtype == "feishu":
        payload = {"msg_type": "text", "content": {"text": text}}
    elif wtype == "wechat":
        payload = {"msgtype": "text", "text": {"content": text}}
    else:
        payload = {"text": text, "level": "error", "source": "jindou-cloud"}
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")