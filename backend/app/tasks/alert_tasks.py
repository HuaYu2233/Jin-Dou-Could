import urllib.request
from loguru import logger
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.webhook import build_webhook_payload


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

    data = build_webhook_payload(text)
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