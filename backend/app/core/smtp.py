from app.core.config import settings


def resolve_smtp():
    host = settings.RESET_PASSWORD_SMTP_HOST or settings.ALERT_EMAIL_SMTP_HOST
    port = settings.RESET_PASSWORD_SMTP_PORT or settings.ALERT_EMAIL_SMTP_PORT
    user = settings.RESET_PASSWORD_SMTP_USER or settings.ALERT_EMAIL_SMTP_USER
    password = settings.RESET_PASSWORD_SMTP_PASSWORD or settings.ALERT_EMAIL_SMTP_PASSWORD
    from_email = settings.RESET_PASSWORD_FROM_EMAIL or settings.ALERT_EMAIL_FROM
    use_tls = settings.ALERT_EMAIL_USE_TLS
    return host, port, user, password, from_email, use_tls