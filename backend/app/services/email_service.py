import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from app.core.config import settings
from app.core.smtp import resolve_smtp


def send_verification_code(to_email: str, code: str) -> None:
    host, port, user, password, from_email, use_tls = resolve_smtp()
    if not host or not from_email:
        raise ValueError("未配置邮件 SMTP 服务，无法发送验证码")

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

    server = smtplib.SMTP(host, port, timeout=15)
    try:
        if use_tls:
            server.starttls()
        if user:
            server.login(user, password)
        server.sendmail(from_email, [to_email], msg.as_string())
    finally:
        server.quit()


def send_verification_code_async(to_email: str, code: str) -> None:
    from app.tasks.email_tasks import send_verification_email
    send_verification_email.delay(to_email, code)