import smtplib
from email.message import Message

from app.core.config import settings


def resolve_smtp():
    host = settings.RESET_PASSWORD_SMTP_HOST or settings.ALERT_EMAIL_SMTP_HOST
    port = settings.RESET_PASSWORD_SMTP_PORT or settings.ALERT_EMAIL_SMTP_PORT
    user = settings.RESET_PASSWORD_SMTP_USER or settings.ALERT_EMAIL_SMTP_USER
    password = settings.RESET_PASSWORD_SMTP_PASSWORD or settings.ALERT_EMAIL_SMTP_PASSWORD
    from_email = settings.RESET_PASSWORD_FROM_EMAIL or settings.ALERT_EMAIL_FROM
    use_tls = settings.ALERT_EMAIL_USE_TLS
    return host, port, user, password, from_email, use_tls


def send_smtp_message(
    message: Message,
    recipients: list[str],
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    from_email: str,
    use_tls: bool,
    timeout: int = 10,
) -> None:
    server = smtplib.SMTP(host, port, timeout=timeout)
    try:
        if use_tls:
            server.starttls()
        if user:
            server.login(user, password)
        server.sendmail(from_email, recipients, message.as_string())
    finally:
        server.quit()
