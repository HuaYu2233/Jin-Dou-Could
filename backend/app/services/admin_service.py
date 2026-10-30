import uuid
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.file import File
from app.core.storage import delete_file as s3_delete_file, batch_delete_files


async def get_stats(db: AsyncSession) -> dict:
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True)
    )
    admin_users = await db.scalar(
        select(func.count(User.id)).where(User.is_admin == True)
    )
    total_quota = await db.scalar(select(func.coalesce(func.sum(User.storage_quota), 0)))
    total_used = await db.scalar(select(func.coalesce(func.sum(User.used_storage), 0)))
    return {
        "total_users": total_users,
        "active_users": active_users,
        "admin_users": admin_users,
        "total_quota": total_quota,
        "total_used": total_used,
    }


async def list_users(
    db: AsyncSession, skip: int = 0, limit: int = 20
) -> list[User]:
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


async def update_user(
    db: AsyncSession,
    target_id: uuid.UUID,
    admin_id: uuid.UUID,
    username: str | None = None,
    storage_quota: int | None = None,
    is_active: bool | None = None,
    is_admin: bool | None = None,
) -> User:
    result = await db.execute(select(User).where(User.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise ValueError("用户不存在")

    if target.id == admin_id and is_admin is False:
        raise ValueError("不能取消自己的管理员权限")

    if target.is_admin and is_admin is False:
        admin_count = await db.scalar(
            select(func.count(User.id)).where(User.is_admin == True)
        )
        if admin_count <= 1:
            raise ValueError("系统至少保留一个管理员")

    if username is not None:
        target.username = username
    if storage_quota is not None:
        target.storage_quota = storage_quota
    if is_active is not None:
        target.is_active = is_active
    if is_admin is not None:
        target.is_admin = is_admin

    await db.commit()
    await db.refresh(target)
    return target


async def delete_user(
    db: AsyncSession, target_id: uuid.UUID, admin_id: uuid.UUID
) -> None:
    result = await db.execute(select(User).where(User.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise ValueError("用户不存在")

    if target.id == admin_id:
        raise ValueError("不能删除自己")

    if target.is_admin:
        admin_count = await db.scalar(
            select(func.count(User.id)).where(User.is_admin == True)
        )
        if admin_count <= 1:
            raise ValueError("系统至少保留一个管理员")

    files_result = await db.execute(select(File.storage_key).where(File.owner_id == target_id))
    storage_keys = [row[0] for row in files_result.all()]

    await db.execute(File.__table__.delete().where(File.owner_id == target_id))
    await db.delete(target)
    await db.commit()

    if storage_keys:
        try:
            await batch_delete_files(storage_keys)
        except Exception as exc:
            logger.bind(log_type="storage").error(f"用户 {target_id} 批量 S3 删除失败，尝试逐个删除: {exc}")
            for key in storage_keys:
                try:
                    await s3_delete_file(key)
                except Exception as e2:
                    logger.bind(log_type="storage").warning(f"孤儿 S3 对象: {key}, 删除失败: {e2}")