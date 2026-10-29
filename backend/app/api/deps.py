import json
from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.base import get_db
from app.models.user import User
from app.core.security import decode_token
from app.core.redis import redis_client

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

USER_CACHE_TTL = 60

def _serialize_user(user: User) -> str:
    return json.dumps({
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "avatar_key": user.avatar_key,
        "storage_quota": user.storage_quota,
        "used_storage": user.used_storage,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    })

def _deserialize_user(data: str) -> User:
    d = json.loads(data)
    user = User()
    user.id = UUID(d["id"])
    user.email = d["email"]
    user.username = d["username"]
    user.hashed_password = None
    user.is_active = d["is_active"]
    user.is_admin = d["is_admin"]
    user.avatar_key = d["avatar_key"]
    user.security_question = None
    user.security_answer = None
    user.storage_quota = d["storage_quota"]
    user.used_storage = d["used_storage"]
    user.created_at = datetime.fromisoformat(d["created_at"]) if d["created_at"] else None
    user.updated_at = datetime.fromisoformat(d["updated_at"]) if d["updated_at"] else None
    user._from_cache = True
    return user

async def invalidate_user_cache(user_id: UUID | str) -> None:
    await redis_client.delete(f"user:{user_id}")

async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token 类型错误，请使用 access token")

    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        if exp < datetime.now(timezone.utc).timestamp():
            raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")
        if await redis_client.exists(f"token_blacklist:{jti}"):
            raise HTTPException(status_code=401, detail="Token 已被撤销，请重新登录")

    user_id = payload["sub"]
    cache_key = f"user:{user_id}"

    if request.method == "GET":
        cached = await redis_client.get(cache_key)
        if cached:
            return _deserialize_user(cached)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if request.method == "GET":
        await redis_client.setex(cache_key, USER_CACHE_TTL, _serialize_user(user))
    
    return user


async def get_full_user(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if getattr(user, "_from_cache", False):
        result = await db.execute(select(User).where(User.id == user.id))
        full_user = result.scalar_one_or_none()
        if not full_user:
            raise HTTPException(status_code=401, detail="User not found")
        return full_user
    return user

async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user