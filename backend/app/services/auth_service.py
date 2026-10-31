from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import RateLimited, Unauthorized
from app.core.redis import redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_token,
    verify_password,
)
from app.models.user import User

_TRUSTED_PROXIES: set[str] | None = None


def _get_trusted_proxies() -> set[str]:
    global _TRUSTED_PROXIES
    if _TRUSTED_PROXIES is None:
        if settings.TRUSTED_PROXIES:
            _TRUSTED_PROXIES = {p.strip() for p in settings.TRUSTED_PROXIES.split(",") if p.strip()}
        else:
            _TRUSTED_PROXIES = set()
    return _TRUSTED_PROXIES


def get_client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else None
    if not direct_ip:
        return "unknown"

    trusted = _get_trusted_proxies()
    if not trusted or direct_ip not in trusted:
        return direct_ip

    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    return direct_ip


async def check_login_rate_limit(client_ip: str, email: str) -> None:
    lock_key = f"login_lock:{client_ip}:{email}"
    if await redis_client.exists(lock_key):
        ttl = await redis_client.ttl(lock_key)
        raise RateLimited(f"登录尝试过于频繁，请 {max(ttl, 1)} 秒后再试")


async def record_login_failure(client_ip: str, email: str) -> None:
    rl_key = f"login_rl:{client_ip}:{email}"
    lock_key = f"login_lock:{client_ip}:{email}"
    attempts = await redis_client.incr(rl_key)
    if attempts == 1:
        await redis_client.expire(rl_key, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    if attempts >= settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
        await redis_client.setex(
            lock_key,
            settings.LOGIN_RATE_LIMIT_LOCK_SECONDS,
            "1",
        )
        await redis_client.delete(rl_key)


async def clear_login_rate_limit(client_ip: str, email: str) -> None:
    rl_key = f"login_rl:{client_ip}:{email}"
    await redis_client.delete(rl_key)


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def set_auth_cookies(response: Response, user: User) -> None:
    import uuid as _uuid
    family = str(_uuid.uuid4())
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id), "family": family})

    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=secure,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        samesite="lax",
        secure=secure,
    )


async def logout(request: Request, response: Response) -> None:
    for name in ("access_token", "refresh_token"):
        token = request.cookies.get(name)
        if token:
            await revoke_token(token)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


async def refresh_access_token(request: Request, response: Response) -> None:
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        raise Unauthorized("无 refresh token")
    payload = decode_token(refresh)
    if not payload or not payload.get("sub"):
        raise Unauthorized("Invalid refresh token")
    if payload.get("type") != "refresh":
        raise Unauthorized("Token 类型错误，请使用 refresh token")
    jti = payload.get("jti")
    if jti and await redis_client.exists(f"token_blacklist:{jti}"):
        raise Unauthorized("Refresh token 已失效")

    family = payload.get("family")
    if family and await redis_client.exists(f"refresh_reuse:{family}"):
        await _revoke_family(family)
        raise Unauthorized("检测到 Refresh Token 重用，该 Token 族已全部撤销，请重新登录")

    if not family:
        family = str(__import__("uuid").uuid4())

    await revoke_token(refresh)

    user_id = payload["sub"]
    access_token = create_access_token({"sub": user_id})
    new_refresh_token = create_refresh_token({"sub": user_id, "family": family})

    family_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    await redis_client.setex(f"refresh_family:{family}", family_ttl, user_id)

    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=secure,
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        samesite="lax",
        secure=secure,
    )


async def _revoke_family(family: str) -> None:
    await redis_client.setex(
        f"refresh_reuse:{family}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        "1",
    )
    user_id = await redis_client.get(f"refresh_family:{family}")
    if user_id:
        await redis_client.delete(f"refresh_family:{family}")
