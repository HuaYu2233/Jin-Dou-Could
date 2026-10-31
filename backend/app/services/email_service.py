def send_verification_code_async(to_email: str, code: str) -> None:
    from app.tasks.email_tasks import send_verification_email

    send_verification_email.delay(to_email, code)
