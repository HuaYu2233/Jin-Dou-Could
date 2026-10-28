from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.core.security import hash_password, verify_password, revoke_token
from app.core.config import settings
from app.core.storage import upload_file, get_presigned_download_url
from app.schemas.user import UserCreate

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise ValueError("Email already registered")

    if settings.MAX_USERS > 0:
        count_result = await db.execute(select(func.count(User.id)))
        total_users = count_result.scalar()
        if total_users >= settings.MAX_USERS:
            raise ValueError("已达到最大注册用户数限制")

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


async def upload_avatar(
    db: AsyncSession, user: User, content: bytes, mime_type: str
) -> User:
    if len(content) > MAX_AVATAR_SIZE:
        raise ValueError("头像大小不能超过 2MB")
    if mime_type not in ALLOWED_AVATAR_TYPES:
        raise ValueError("仅支持 JPG/PNG/WEBP/GIF 格式")

    storage_key = f"avatars/{user.id}"
    await upload_file(storage_key, content, mime_type, len(content))

    user.avatar_key = storage_key
    await db.commit()
    await db.refresh(user)
    return user


async def get_avatar_url(user: User) -> str | None:
    if not user.avatar_key:
        return None
    return await get_presigned_download_url(user.avatar_key, 300)


async def update_profile(db: AsyncSession, user: User, username: str | None) -> User:
    if username is not None:
        if len(username.strip()) < 2:
            raise ValueError("用户名至少 2 个字符")
        user.username = username.strip()
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession, user: User, old_password: str, new_password: str, access_token: str | None = None
) -> User:
    if not verify_password(old_password, user.hashed_password):
        raise ValueError("原密码错误")
    user.hashed_password = hash_password(new_password)
    await db.commit()
    await db.refresh(user)
    if access_token:
        await revoke_token(access_token)
    return user


async def update_security_question(
    db: AsyncSession, user: User, question: str, answer: str
) -> User:
    if len(question.strip()) < 2:
        raise ValueError("密保问题至少 2 个字符")
    if len(answer.strip()) < 1:
        raise ValueError("密保答案不能为空")
    user.security_question = question.strip()
    user.security_answer = hash_password(answer.strip().lower())
    await db.commit()
    await db.refresh(user)
    return user