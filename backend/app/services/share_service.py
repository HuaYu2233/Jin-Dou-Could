
# /Users/zero/project/JinDou-Cloud/backend/app/services/share_service.py
import uuid
import secrets
import string
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.share import Share
from app.models.file import File

def _generate_token() -> str:
    return secrets.token_urlsafe(24)[:32]

def _generate_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(6))

async def create_share(
    db: AsyncSession,
    file_id: uuid.UUID,
    owner_id: uuid.UUID,
    expires_days: int | None = None,
) -> Share:
    file_result = await db.execute(
        select(File).where(
            File.id == file_id,
            File.owner_id == owner_id,
            File.deleted_at.is_(None),
        )
    )
    file = file_result.scalar_one_or_none()
    if not file:
        raise ValueError("文件不存在")

    existing = await db.execute(
        select(Share).where(
            Share.file_id == file_id,
            Share.owner_id == owner_id,
        )
    )
    existing_share = existing.scalar_one_or_none()
    if existing_share:
        return existing_share

    expires_at = None
    if expires_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    share = Share(
        id=uuid.uuid4(),
        file_id=file_id,
        owner_id=owner_id,
        share_token=_generate_token(),
        extract_code=_generate_code(),
        expires_at=expires_at,
        views=0,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return share

async def list_shares(
    db: AsyncSession,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list, int]:
    result = await db.execute(
        select(Share, File.filename, File.size)
        .join(File, Share.file_id == File.id)
        .where(Share.owner_id == owner_id)
        .order_by(Share.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()
    items = []
    for share, filename, file_size in rows:
        items.append(
            {
                "id": share.id,
                "file_id": share.file_id,
                "share_token": share.share_token,
                "extract_code": share.extract_code,
                "expires_at": share.expires_at,
                "views": share.views,
                "created_at": share.created_at,
                "filename": filename,
                "file_size": file_size,
            }
        )

    count_result = await db.execute(
        select(func.count()).select_from(Share).where(Share.owner_id == owner_id)
    )
    total = count_result.scalar_one()
    return items, total

async def delete_share(
    db: AsyncSession, share_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(Share).where(Share.id == share_id, Share.owner_id == owner_id)
    )
    share = result.scalar_one_or_none()
    if not share:
        return False
    await db.delete(share)
    await db.commit()
    return True

async def get_share_info(db: AsyncSession, token: str) -> dict | None:
    result = await db.execute(
        select(Share, File.filename, File.size, File.file_type)
        .join(File, Share.file_id == File.id)
        .where(Share.share_token == token)
    )
    row = result.first()
    if not row:
        return None
    share, filename, file_size, file_type = row

    if share.expires_at is not None:
        if share.expires_at < datetime.now(timezone.utc):
            return None

    return {
        "share_token": share.share_token,
        "filename": filename,
        "file_size": file_size,
        "file_type": file_type,
        "has_code": True,
        "expires_at": share.expires_at,
    }

async def verify_share(
    db: AsyncSession, token: str, extract_code: str
) -> dict | None:
    result = await db.execute(
        select(Share, File.filename, File.size, File.file_type, File.mime_type, File.storage_key)
        .join(File, Share.file_id == File.id)
        .where(Share.share_token == token)
    )
    row = result.first()
    if not row:
        return None
    share, filename, file_size, file_type, mime_type, storage_key = row

    if share.expires_at is not None:
        if share.expires_at < datetime.now(timezone.utc):
            return None

    if share.extract_code != extract_code:
        return None

    share.views = share.views + 1
    await db.commit()

    return {
        "share_token": share.share_token,
        "filename": filename,
        "file_size": file_size,
        "file_type": file_type,
        "mime_type": mime_type,
        "storage_key": storage_key,
    }