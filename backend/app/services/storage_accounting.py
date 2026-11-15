from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import QuotaExceeded
from app.models.file import File
from app.models.transfer_room import TransferRoom, TransferRoomFile
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
    drive_total = int(result.scalar_one() or 0)

    room_total = await db.scalar(
        select(func.coalesce(func.sum(TransferRoomFile.size), 0))
        .join(TransferRoom, TransferRoom.id == TransferRoomFile.room_id)
        .where(
            TransferRoom.owner_id == owner_id,
            TransferRoom.closed_at.is_(None),
            TransferRoomFile.source_file_id.is_(None),
        )
    )
    actual = drive_total + int(room_total or 0)

    owner = await get_owner(db, owner_id)
    if owner and owner.used_storage != actual:
        owner.used_storage = actual
        await db.commit()
        await db.refresh(owner)

    return actual
