from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.core.security import hash_password
from app.core.config import settings
from app.schemas.user import UserCreate

async def create_user(db: AsyncSession, data: UserCreate) -> User:
    # 查重
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise ValueError("Email already registered")

    # 检查用户数量上限（0 表示不限制）
    if settings.MAX_USERS > 0:
        count_result = await db.execute(select(func.count(User.id)))
        total_users = count_result.scalar()
        if total_users >= settings.MAX_USERS:
            raise ValueError("已达到最大注册用户数限制")

    # ADMIN_EMAIL 引导：用此邮箱注册的用户自动成为管理员
    is_admin = bool(settings.ADMIN_EMAIL and data.email == settings.ADMIN_EMAIL)

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        is_admin=is_admin,
        storage_quota=settings.DEFAULT_STORAGE_QUOTA,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user