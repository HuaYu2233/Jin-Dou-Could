from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import QuotaExceeded
from app.models.file import File
from app.models.user import User


def has_room(owner: User, size: int) -> bool:
    return owner.used_storage + size <= owner.storage_quota


def ensure_quota(owner: User, size: int) -> None:
    if not has_room(owner, size):
        raise QuotaExceeded("存储空间不足")


def add(owner: User, size: int) -> None:
    owner.used_storage += size


def subtract(owner: User, size: int) -> None:
    owner.used_storage = max(0, owner.used_storage - size)


async def get_owner(db: AsyncSession, owner_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == owner_id))
    return result.scalar_one_or_none()


async def adjust(db: AsyncSession, owner_id: UUID, size: int, *, enforce_quota: bool = False) -> None:
    if size == 0:
        return
    owner = await get_owner(db, owner_id)
    if owner is None:
        return
    if size > 0:
        if enforce_quota:
            ensure_quota(owner, size)
        add(owner, size)
    else:
        subtract(owner, -size)


async def recalculate(db: AsyncSession, owner_id: UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(File.size), 0)).where(
            File.owner_id == owner_id,
            File.deleted_at.is_(None),
        )
    )
    actual = result.scalar_one()

    owner = await get_owner(db, owner_id)
    if owner and owner.used_storage != actual:
        owner.used_storage = actual
        await db.commit()
        await db.refresh(owner)

    return actual
