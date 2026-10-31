import uuid
from contextlib import suppress
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import PayloadTooLarge
from app.core.redis import redis_client
from app.core.storage import (
    delete_file,
    get_presigned_download_url,
    get_presigned_preview_url,
    upload_fileobj,
    upload_stream_multipart,
)
from app.models.file import File
from app.models.user import User
from app.services import storage_accounting
from app.services.file_validation import (
    categorize_file_type,
    detect_real_mime_type,
    sanitize_filename,
    validate_mime_type,
)

_COUNT_CACHE_TTL = 120
_SEARCH_CACHE_TTL = 60
_CACHE_HASH_KEY = "file_caches"


async def invalidate_file_caches(owner_id: uuid.UUID) -> None:
    oid = str(owner_id)
    try:
        fields = await redis_client.hkeys(_CACHE_HASH_KEY)
        to_delete = [f for f in fields if f.startswith(f"{oid}:")]
        if to_delete:
            await redis_client.hdel(_CACHE_HASH_KEY, *to_delete)
    except Exception:
        pass


async def create_file(
    db: AsyncSession,
    owner: User,
    filename: str,
    fileobj,
    mime_type: str,
    size: int | None,
    folder_id: uuid.UUID | None = None,
) -> File:
    if size is not None:
        storage_accounting.ensure_quota(owner, size)

    filename = sanitize_filename(filename)
    real_mime = await detect_real_mime_type(fileobj, mime_type)
    validate_mime_type(mime_type, real_mime)
    mime_type = real_mime

    if hasattr(fileobj, "seek"):
        fileobj.seek(0)

    file_id = uuid.uuid4()
    storage_key = f"{owner.id}/{file_id}"

    if size is None:
        actual_size = await upload_stream_multipart(
            storage_key, fileobj, mime_type, max_size=settings.MAX_UPLOAD_SIZE
        )
        if not storage_accounting.has_room(owner, actual_size):
            await delete_file(storage_key)
            storage_accounting.ensure_quota(owner, actual_size)
        size = actual_size
    elif size >= settings.MULTIPART_THRESHOLD:
        await upload_stream_multipart(storage_key, fileobj, mime_type, size)
    else:
        await upload_fileobj(storage_key, fileobj, mime_type)

    file = File(
        id=file_id,
        owner_id=owner.id,
        folder_id=folder_id,
        filename=filename,
        storage_key=storage_key,
        size=size,
        mime_type=mime_type,
        file_type=categorize_file_type(mime_type),
    )

    storage_accounting.add(owner, size)
    db.add(file)
    await db.commit()
    await db.refresh(file)

    if file.file_type == "image":
        try:
            from app.tasks.thumbnail_tasks import generate_thumbnail
            generate_thumbnail.delay(storage_key, str(file_id))
        except Exception:
            pass

    return file

async def get_file(
    db: AsyncSession, file_id: uuid.UUID, owner_id: uuid.UUID
) -> File | None:
    result = await db.execute(
        select(File).where(File.id == file_id, File.owner_id == owner_id)
    )
    return result.scalar_one_or_none()

async def list_files(
    db: AsyncSession,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    file_type: str | None = None,
    folder_id: uuid.UUID | None = None,
    cursor: str | None = None,
) -> tuple[list[File], int, str | None]:
    filters = [File.owner_id == owner_id, File.deleted_at.is_(None)]
    if file_type:
        filters.append(File.file_type == file_type)
    if folder_id is not None:
        filters.append(File.folder_id == folder_id)
    else:
        filters.append(File.folder_id.is_(None))

    next_cursor = None

    cache_field = f"{owner_id}:count:{file_type or ''}:{folder_id or 'root'}"
    cached_total = await redis_client.hget(_CACHE_HASH_KEY, cache_field)
    if cached_total is not None:
        total = int(cached_total)
    else:
        count_result = await db.execute(select(func.count()).select_from(File).where(*filters))
        total = count_result.scalar_one()
        await redis_client.hset(_CACHE_HASH_KEY, cache_field, str(total))
        await redis_client.expire(_CACHE_HASH_KEY, _COUNT_CACHE_TTL)

    if cursor:
        cursor_dt = datetime.fromisoformat(cursor).replace(tzinfo=timezone.utc)
        query = (
            select(File)
            .where(*filters, File.created_at < cursor_dt)
            .order_by(File.created_at.desc())
            .limit(limit)
        )
    elif skip > 0:
        sub = (
            select(File.created_at)
            .where(*filters)
            .order_by(File.created_at.desc())
            .offset(skip - 1)
            .limit(1)
            .correlate(None)
            .subquery()
        )
        query = (
            select(File)
            .where(*filters, File.created_at <= sub.c.created_at)
            .order_by(File.created_at.desc())
            .limit(limit)
        )
    else:
        query = (
            select(File)
            .where(*filters)
            .order_by(File.created_at.desc())
            .limit(limit)
        )

    result = await db.execute(query)
    files = list(result.scalars().all())

    if files:
        last_created = files[-1].created_at
        if total > skip + len(files):
            next_cursor = last_created.isoformat()

    return files, total, next_cursor

async def search_files(
    db: AsyncSession,
    owner_id: uuid.UUID,
    keyword: str,
    skip: int = 0,
    limit: int = 20,
    cursor: str | None = None,
) -> tuple[list[File], int, str | None]:
    base_filters = [File.owner_id == owner_id, File.deleted_at.is_(None)]

    try:
        similarity_expr = func.similarity(File.filename, keyword)
        search_filter = similarity_expr > 0.1
        order_cols = [similarity_expr.desc(), File.created_at.desc()]
    except Exception:
        safe_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_filter = File.filename.ilike(f"%{safe_keyword}%", escape="\\")
        order_cols = [File.created_at.desc()]

    filters = base_filters + [search_filter]

    next_cursor = None

    cache_field = f"{owner_id}:search:{keyword}"
    cached_total = await redis_client.hget(_CACHE_HASH_KEY, cache_field)
    if cached_total is not None:
        total = int(cached_total)
    else:
        count_result = await db.execute(select(func.count()).select_from(File).where(*filters))
        total = count_result.scalar_one()
        await redis_client.hset(_CACHE_HASH_KEY, cache_field, str(total))
        await redis_client.expire(_CACHE_HASH_KEY, _SEARCH_CACHE_TTL)

    if cursor:
        cursor_dt = datetime.fromisoformat(cursor).replace(tzinfo=timezone.utc)
        query = (
            select(File)
            .where(*filters, File.created_at < cursor_dt)
            .order_by(*order_cols)
            .limit(limit)
        )
    elif skip > 0:
        sub = (
            select(File.created_at)
            .where(*filters)
            .order_by(*order_cols)
            .offset(skip - 1)
            .limit(1)
            .correlate(None)
            .subquery()
        )
        query = (
            select(File)
            .where(*filters, File.created_at <= sub.c.created_at)
            .order_by(*order_cols)
            .limit(limit)
        )
    else:
        query = (
            select(File)
            .where(*filters)
            .order_by(*order_cols)
            .limit(limit)
        )

    result = await db.execute(query)
    files = list(result.scalars().all())

    if files:
        last_created = files[-1].created_at
        if total > skip + len(files):
            next_cursor = last_created.isoformat()

    return files, total, next_cursor

async def move_files(
    db: AsyncSession,
    owner_id: uuid.UUID,
    file_ids: list[uuid.UUID],
    target_folder_id: uuid.UUID | None,
) -> int:
    result = await db.execute(
        select(File).where(
            File.id.in_(file_ids),
            File.owner_id == owner_id,
            File.deleted_at.is_(None),
        )
    )
    files = list(result.scalars().all())
    for file in files:
        file.folder_id = target_folder_id
    await db.commit()
    return len(files)

async def list_trash_files(
    db: AsyncSession,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    cursor: str | None = None,
) -> tuple[list[File], int, str | None]:
    filters = [File.owner_id == owner_id, File.deleted_at.is_not(None)]

    next_cursor = None

    cache_field = f"{owner_id}:trash"
    cached_total = await redis_client.hget(_CACHE_HASH_KEY, cache_field)
    if cached_total is not None:
        total = int(cached_total)
    else:
        count_result = await db.execute(select(func.count()).select_from(File).where(*filters))
        total = count_result.scalar_one()
        await redis_client.hset(_CACHE_HASH_KEY, cache_field, str(total))
        await redis_client.expire(_CACHE_HASH_KEY, _COUNT_CACHE_TTL)

    if cursor:
        cursor_dt = datetime.fromisoformat(cursor).replace(tzinfo=timezone.utc)
        query = (
            select(File)
            .where(*filters, File.deleted_at < cursor_dt)
            .order_by(File.deleted_at.desc())
            .limit(limit)
        )
    elif skip > 0:
        sub = (
            select(File.deleted_at)
            .where(*filters)
            .order_by(File.deleted_at.desc())
            .offset(skip - 1)
            .limit(1)
            .correlate(None)
            .subquery()
        )
        query = (
            select(File)
            .where(*filters, File.deleted_at <= sub.c.deleted_at)
            .order_by(File.deleted_at.desc())
            .limit(limit)
        )
    else:
        query = (
            select(File)
            .where(*filters)
            .order_by(File.deleted_at.desc())
            .limit(limit)
        )

    result = await db.execute(query)
    files = list(result.scalars().all())

    if files:
        last_deleted = files[-1].deleted_at
        if last_deleted and total > skip + len(files):
            next_cursor = last_deleted.isoformat()

    return files, total, next_cursor

async def soft_delete_file(
    db: AsyncSession, file_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    file = await get_file(db, file_id, owner_id)
    if not file:
        return False
    file.deleted_at = datetime.now(timezone.utc)
    await storage_accounting.adjust(db, owner_id, -file.size)

    await db.commit()
    return True

async def restore_file(
    db: AsyncSession, file_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(File).where(
            File.id == file_id,
            File.owner_id == owner_id,
            File.deleted_at.is_not(None),
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        return False
    file.deleted_at = None
    await storage_accounting.adjust(db, owner_id, file.size, enforce_quota=True)

    await db.commit()
    return True

async def purge_file(
    db: AsyncSession, file_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(File).where(
            File.id == file_id,
            File.owner_id == owner_id,
            File.deleted_at.is_not(None),
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        return False

    with suppress(Exception):
        await delete_file(file.storage_key)

    await db.delete(file)
    await db.commit()
    return True


async def recalculate_used_storage(
    db: AsyncSession, owner_id: uuid.UUID
) -> int:
    return await storage_accounting.recalculate(db, owner_id)


async def prepare_upload(user: User, file_size: int) -> None:
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise PayloadTooLarge("文件过大，单文件上限 100MB")
    storage_accounting.ensure_quota(user, file_size)


async def get_preview_url(file: File) -> str:
    return await get_presigned_preview_url(
        file.storage_key, file.mime_type, file.filename, settings.MINIO_DOWNLOAD_EXPIRES
    )


async def get_thumbnail_url(thumbnail_key: str) -> str:
    return await get_presigned_preview_url(
        thumbnail_key, "image/jpeg", "thumbnail.jpg", settings.MINIO_DOWNLOAD_EXPIRES
    )


async def get_download_url(file: File) -> str:
    return await get_presigned_download_url(
        file.storage_key, settings.MINIO_DOWNLOAD_EXPIRES, file.filename
    )
