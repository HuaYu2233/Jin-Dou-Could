import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.smtp import resolve_smtp


@celery_app.task(
    name="tasks.send_verification_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_verification_email(self, to_email: str, code: str) -> None:
    host, port, user, password, from_email, use_tls = resolve_smtp()
    if not host or not from_email:
        logger.bind(log_type="email").error("未配置邮件 SMTP 服务，无法发送验证码")
        return

    subject = f"【{settings.RESET_PASSWORD_FROM_NAME}】找回密码验证码"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
        <h2 style="color: #1f2937;">找回密码验证码</h2>
        <p style="color: #4b5563; font-size: 14px;">您正在重置 <strong>{settings.RESET_PASSWORD_FROM_NAME}</strong> 账户的密码，验证码为：</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #2563eb;">{code}</span>
        </div>
        <p style="color: #6b7280; font-size: 13px;">
            验证码 {settings.RESET_PASSWORD_CODE_EXPIRE_SECONDS // 60} 分钟内有效，请尽快使用。
        </p>
        <p style="color: #9ca3af; font-size: 12px;">如非本人操作，请忽略此邮件。</p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.RESET_PASSWORD_FROM_NAME} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        server = smtplib.SMTP(host, port, timeout=15)
        try:
            if use_tls:
                server.starttls()
            if user:
                server.login(user, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        finally:
            server.quit()
        logger.bind(log_type="email").info(f"验证码邮件已发送至 {to_email}")
    except Exception as exc:
        logger.bind(log_type="email").error(f"发送验证码邮件失败: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="tasks.send_alert_email",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def send_alert_email(self, subject: str, text: str) -> None:
    if not settings.ALERT_EMAIL_ENABLED:
        return
    if not settings.ALERT_EMAIL_SMTP_HOST or not settings.ALERT_EMAIL_FROM:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.ALERT_EMAIL_FROM
    msg["To"] = settings.ALERT_EMAIL_TO
    msg.attach(MIMEText(text, "plain", "utf-8"))

    try:
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
    except Exception as exc:
        logger.bind(log_type="alert").error(f"邮件告警发送失败: {exc}")
        raise self.retry(exc=exc)