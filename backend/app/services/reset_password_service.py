import secrets
import string
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services.email_service import send_verification_code_async

CODE_KEY = "reset_password_code:{email}"
SEND_LIMIT_KEY = "reset_password_send_limit:{email}"

def _generate_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(settings.RESET_PASSWORD_CODE_LENGTH))

async def send_code(db: AsyncSession, email: str) -> None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return

    limit_key = SEND_LIMIT_KEY.format(email=email)
    if await redis_client.exists(limit_key):
        raise ValueError("请求过于频繁，请稍后再试")
    await redis_client.setex(limit_key, 60, "1")

    code = _generate_code()
    await redis_client.setex(
        CODE_KEY.format(email=email),
        settings.RESET_PASSWORD_CODE_EXPIRE_SECONDS,
        code,
    )
    send_verification_code_async(email, code)

async def reset_password(db: AsyncSession, email: str, code: str, new_password: str) -> None:
    if len(new_password) < 6:
        raise ValueError("新密码至少 6 个字符")

    key = CODE_KEY.format(email=email)
    stored = await redis_client.get(key)
    if not stored or stored != code:
        raise ValueError("验证码错误或已过期")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("用户不存在")

    user.hashed_password = hash_password(new_password)
    await db.commit()
    await redis_client.delete(key)


async def get_security_question(db: AsyncSession, email: str) -> str | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    return user.security_question


async def reset_password_by_security(
    db: AsyncSession, email: str, answer: str, new_password: str
) -> None:
    if len(new_password) < 6:
        raise ValueError("新密码至少 6 个字符")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("用户不存在")
    if not user.security_question or not user.security_answer:
        raise ValueError("未设置密保问题")

    if not verify_password(answer.strip().lower(), user.security_answer):
        raise ValueError("密保答案错误")

    user.hashed_password = hash_password(new_password)
    await db.commit()