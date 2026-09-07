import json
import smtplib
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

    def _send_webhook(self, text):
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()

    def _send_email(self, subject, text):
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

    def notify(self, record):
        if not settings.ALERT_ENABLED:
            return
        key = f"{record['name']}:{record['function']}:{record['line']}:{record['message'][:80]}"
        if not self._should_alert(key):
            return
        text = self._build_text(record)
        subject = f"[云盘告警] {record['level'].name}: {record['message'][:50]}"
        threading.Thread(
            target=self._safe_send, args=(text, subject), daemon=True
        ).start()

    def _safe_send(self, text, subject):
        if settings.ALERT_WEBHOOK_URL:
            try:
                self._send_webhook(text)
            except Exception as e:
                logger.bind(log_type="alert").debug(f"Webhook 告警发送失败: {e}")
        if settings.ALERT_EMAIL_ENABLED:
            try:
                self._send_email(subject, text)
            except Exception as e:
                logger.bind(log_type="alert").debug(f"邮件告警发送失败: {e}")

alert_manager = AlertManager()

def alert_sink(message):
    alert_manager.notify(message.record)
