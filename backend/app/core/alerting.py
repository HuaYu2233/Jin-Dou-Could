import asyncio
import json
import threading
import time
import traceback
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from app.core.config import settings


class AlertManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._cooldowns = {}
        self._cooldown_lock = threading.Lock()

    def _should_alert(self, key):
        now = time.time()
        with self._cooldown_lock:
            last = self._cooldowns.get(key, 0)
            if now - last < settings.ALERT_COOLDOWN_SECONDS:
                return False
            self._cooldowns[key] = now
            return True

    def _build_text(self, record):
        level = record["level"].name
        msg = record["message"]
        name = record["name"]
        func = record["function"]
        line = record["line"]
        time_str = record["time"].strftime("%Y-%m-%d %H:%M:%S")
        text = f"[{level}] {msg}\n时间: {time_str}\n位置: {name}:{func}:{line}"
        if record["exception"]:
            exc = record["exception"]
            text += "\n" + "".join(
                traceback.format_exception(type(exc.value), exc.value, exc.traceback)
            )
        return text

    def notify(self, record):
        if not settings.ALERT_ENABLED:
            return
        key = f"{record['name']}:{record['function']}:{record['line']}:{record['message'][:80]}"
        if not self._should_alert(key):
            return
        text = self._build_text(record)
        subject = f"[云盘告警] {record['level'].name}: {record['message'][:50]}"

        if settings.ALERT_WEBHOOK_URL:
            try:
                from app.tasks.alert_tasks import send_alert_webhook
                send_alert_webhook.delay(text)
            except Exception:
                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(self._async_fallback_webhook(text))
                    task.add_done_callback(self._on_fallback_task_done)
                except RuntimeError:
                    self._fallback_webhook(text)

        if settings.ALERT_EMAIL_ENABLED:
            try:
                from app.tasks.email_tasks import send_alert_email
                send_alert_email.delay(subject, text)
            except Exception:
                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(self._async_fallback_email(subject, text))
                    task.add_done_callback(self._on_fallback_task_done)
                except RuntimeError:
                    self._fallback_email(subject, text)

    async def _async_fallback_webhook(self, text):
        try:
            await asyncio.to_thread(self._fallback_webhook, text)
        except Exception as e:
            logger.bind(log_type="alert").debug(f"异步 Webhook 告警降级发送失败: {e}")

    async def _async_fallback_email(self, subject, text):
        try:
            await asyncio.to_thread(self._fallback_email, subject, text)
        except Exception as e:
            logger.bind(log_type="alert").debug(f"异步邮件告警降级发送失败: {e}")

    @staticmethod
    def _on_fallback_task_done(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.bind(log_type="alert").debug(f"降级告警 task 异常: {exc}")

    def _fallback_webhook(self, text):
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
        except Exception as e:
            logger.bind(log_type="alert").debug(f"Webhook 告警降级发送失败: {e}")

    def _fallback_email(self, subject, text):
        import smtplib

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.ALERT_EMAIL_FROM
            msg["To"] = settings.ALERT_EMAIL_TO
            msg.attach(MIMEText(text, "plain", "utf-8"))
            server = smtplib.SMTP(
                settings.ALERT_EMAIL_SMTP_HOST,
                settings.ALERT_EMAIL_SMTP_PORT,
                timeout=10,
            )
            try:
                if settings.ALERT_EMAIL_USE_TLS:
                    server.starttls()
                if settings.ALERT_EMAIL_SMTP_USER:
                    server.login(
                        settings.ALERT_EMAIL_SMTP_USER,
                        settings.ALERT_EMAIL_SMTP_PASSWORD,
                    )
                server.sendmail(
                    settings.ALERT_EMAIL_FROM,
                    [addr.strip() for addr in settings.ALERT_EMAIL_TO.split(",")],
                    msg.as_string(),
                )
            finally:
                server.quit()
        except Exception as e:
            logger.bind(log_type="alert").debug(f"邮件告警降级发送失败: {e}")


alert_manager = AlertManager()


def alert_sink(message):
    alert_manager.notify(message.record)