import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.core.security import ROOM_TOKEN_TYPE, decode_token
from app.db.base import get_db
from app.models.transfer_room import TransferRoom
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

USER_CACHE_TTL = 60


def _serialize_user(user: User) -> str:
    return json.dumps(
        {
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
        }
    )


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
    user._cache_incomplete = True
    return user


async def invalidate_user_cache(user_id: UUID | str) -> None:
    uid = str(user_id)
    await redis_client.delete(f"user:{uid}")
    try:
        from app.services.file_service import invalidate_file_caches

        await invalidate_file_caches(user_id)
    except Exception as exc:
        logger.bind(log_type="cache").warning(f"文件缓存失效失败: user={uid}, {exc}")


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

    user_id = payload["sub"]
    cache_key = f"user:{user_id}"

    if request.method == "GET":
        pipe = redis_client.pipeline(transaction=False)
        pipe.exists(f"token_blacklist:{payload.get('jti') or ''}")
        pipe.get(cache_key)
        bl_exist, cached = await pipe.execute()

        if bl_exist:
            raise HTTPException(status_code=401, detail="Token 已被撤销，请重新登录")
        if cached:
            cached_user = _deserialize_user(cached)
            if not cached_user.is_active:
                raise HTTPException(status_code=403, detail="账号已被禁用")
            return cached_user
    else:
        jti = payload.get("jti")
        if jti and await redis_client.exists(f"token_blacklist:{jti}"):
            raise HTTPException(status_code=401, detail="Token 已被撤销，请重新登录")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

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


@dataclass
class RoomContext:
    room: TransferRoom
    jti: str | None
    role: str
    user_id: UUID | None = None
    user_name: str | None = None


async def get_room_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RoomContext:
    from app.services import lan_transfer_service

    raw_room_id = request.path_params.get("room_id")
    try:
        room_id = UUID(str(raw_room_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail="房间不存在") from exc

    token = request.headers.get("x-room-token")
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="缺少房间令牌")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="房间令牌无效或已过期")

    token_type = payload.get("type")
    if token_type == ROOM_TOKEN_TYPE:
        if payload.get("room_id") != str(room_id):
            raise HTTPException(status_code=403, detail="房间令牌与请求房间不匹配")
        room = await lan_transfer_service.get_room(db, room_id)
        return RoomContext(room=room, jti=payload.get("jti"), role=payload.get("role", "guest"))

    if token_type == "access":
        room = await lan_transfer_service.get_room(db, room_id)
        sub = payload.get("sub")
        if not sub or str(room.owner_id) != str(sub):
            raise HTTPException(status_code=403, detail="仅房间创建者可访问该接口")
        owner = await db.scalar(select(User).where(User.id == room.owner_id))
        if not owner or not owner.is_active:
            raise HTTPException(status_code=403, detail="账号不可用")
        return RoomContext(
            room=room,
            jti=payload.get("jti"),
            role="owner",
            user_id=room.owner_id,
            user_name=owner.username,
        )

    raise HTTPException(status_code=401, detail="房间令牌无效或已过期")
