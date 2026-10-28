import json
import urllib.request
from loguru import logger
from app.core.celery_app import celery_app
from app.core.config import settings


@celery_app.task(
    name="tasks.send_alert_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def send_alert_webhook(self, text: str) -> None:
    if not settings.ALERT_WEBHOOK_URL:
        return

    wtype = settings.ALERT_WEBHOOK_TYPE
    if wtype == "dingtalk":
        payload = {"msgtype": "text", "text": {"content": text}}
    elif wtype == "feishu":
        payload = {"msg_type": "text", "content": {"text": text}}
    elif wtype == "wechat":
        payload = {"msgtype": "text", "text": {"content": text}}
    else:
        payload = {"text": text, "level": "error", "source": "jindou-cloud"}

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        settings.ALERT_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as exc:
        logger.bind(log_type="alert").error(f"Webhook 告警发送失败: {exc}")
        raise self.retry(exc=exc)