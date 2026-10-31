import asyncio
import re
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.file import File
from app.models.user import User
from app.core.storage import (
    upload_fileobj,
    upload_stream_multipart,
    delete_file,
    get_presigned_download_url,
    get_presigned_preview_url,
    create_multipart,
    upload_part,
    complete_multipart,
    abort_multipart,
)
from app.core.config import settings
from app.core.redis import redis_client

_FILENAME_MAX_LEN = 255
_COUNT_CACHE_TTL = 120
_SEARCH_CACHE_TTL = 60
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_PATH_SEP_RE = re.compile(r"[\\/]+")
_CACHE_HASH_KEY = "file_caches"

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/svg+xml",
    "video/mp4", "video/webm", "video/x-msvideo", "video/quicktime",
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/x-m4a", "audio/flac",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain", "text/csv", "text/html",
    "application/zip", "application/x-rar-compressed", "application/x-7z-compressed",
    "application/octet-stream",
}


def sanitize_filename(name: str) -> str:
    name = _PATH_SEP_RE.sub("_", name)
    name = _CONTROL_CHARS_RE.sub("", name)
    name = name.strip(" .")
    if not name:
        name = "unknown"
    return name[:_FILENAME_MAX_LEN]


async def invalidate_file_caches(owner_id: uuid.UUID) -> None:
    oid = str(owner_id)
    try:
        fields = await redis_client.hkeys(_CACHE_HASH_KEY)
        to_delete = [f for f in fields if f.startswith(f"{oid}:")]
        if to_delete:
            await redis_client.hdel(_CACHE_HASH_KEY, *to_delete)
    except Exception:
        pass


async def detect_real_mime_type(fileobj, declared: str) -> str:
    try:
        import magic
        try:
            if hasattr(fileobj, "seek"):
                fileobj.seek(0)
            head = fileobj.read(2048)
            if hasattr(fileobj, "seek"):
                fileobj.seek(0)
        except Exception:
            head = None
        if head:
            if isinstance(head, str):
                head = head.encode("utf-8")
            detected = await asyncio.to_thread(magic.from_buffer, head, True)
            if detected and detected in ALLOWED_MIME_TYPES:
                return detected
    except Exception:
        pass
    return declared


def validate_mime_type(declared: str, detected: str) -> None:
    if detected not in ALLOWED_MIME_TYPES:
        raise ValueError(f"不允许的文件类型: {detected}")
    if declared and declared in ALLOWED_MIME_TYPES and declared != detected:
        if not _is_compatible_mime(declared, detected):
            raise ValueError(f"文件类型与声明不符: 声明 {declared}, 实际 {detected}")


def _is_compatible_mime(declared: str, detected: str) -> bool:
    if declared == detected:
        return True
    aliases = {
        ("application/octet-stream", detected): True,
        ("audio/mpeg", "audio/mp3"): True,
        ("video/mp4", "application/mp4"): True,
    }
    return aliases.get((declared, detected), False) or aliases.get((detected, declared), False)

_DOCUMENT_MIME_PREFIXES = {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument", "application/vnd.ms-excel", "application/vnd.ms-powerpoint"}
_ARCHIVE_MIME_TYPES = {"application/zip", "application/x-rar-compressed", "application/x-7z-compressed"}

def categorize_file_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("text/"):
        return "document"
    if any(mime_type == p or mime_type.startswith(p + ".") for p in _DOCUMENT_MIME_PREFIXES):
        return "document"
    if mime_type in _ARCHIVE_MIME_TYPES:
        return "archive"
    return "other"

async def create_file(
    db: AsyncSession,
    owner: User,
    filename: str,
    fileobj,
    mime_type: str,
    size: int | None,
    folder_id: uuid.UUID | None = None,
) -> File:
    if size is not None and owner.used_storage + size > owner.storage_quota:
        raise ValueError("存储空间不足")

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
        if owner.used_storage + actual_size > owner.storage_quota:
            from app.core.storage import delete_file as _delete
            await _delete(storage_key)
            raise ValueError("存储空间不足")
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

    owner.used_storage += size
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

    owner_result = await db.execute(select(User).where(User.id == owner_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        owner.used_storage = max(0, owner.used_storage - file.size)

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

    owner_result = await db.execute(select(User).where(User.id == owner_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        owner.used_storage += file.size

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

    try:
        await delete_file(file.storage_key)
    except Exception:
        pass

    await db.delete(file)
    await db.commit()
    return True


async def recalculate_used_storage(
    db: AsyncSession, owner_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(File.size), 0)).where(
            File.owner_id == owner_id,
            File.deleted_at.is_(None),
        )
    )
    actual = result.scalar_one()

    owner_result = await db.execute(select(User).where(User.id == owner_id))
    owner = owner_result.scalar_one_or_none()
    if owner and owner.used_storage != actual:
        owner.used_storage = actual
        await db.commit()
        await db.refresh(owner)

    return actual


async def prepare_upload(
    user: User, file_size: int, declared_mime: str, filename: str
) -> None:
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise ValueError("文件过大，单文件上限 100MB")
    if user.used_storage + file_size > user.storage_quota:
        raise ValueError("存储空间不足，请联系管理员扩容")


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


_UPLOAD_STATE_TTL = 86400


async def init_multipart_upload(
    owner: User,
    filename: str,
    mime_type: str,
    total_size: int,
    folder_id: uuid.UUID | None = None,
    part_size: int = 5 * 1024 * 1024,
    total_parts: int = 0,
) -> dict:
    filename = sanitize_filename(filename)
    file_id = uuid.uuid4()
    storage_key = f"{owner.id}/{file_id}"

    upload_id = await create_multipart(storage_key, mime_type)

    state_key = f"multipart:{owner.id}:{upload_id}"
    state = {
        "file_id": str(file_id),
        "storage_key": storage_key,
        "filename": filename,
        "mime_type": mime_type,
        "total_size": str(total_size),
        "folder_id": str(folder_id) if folder_id else "",
        "part_size": str(part_size),
        "total_parts": str(total_parts),
        "completed_parts": "",
    }
    await redis_client.hset(state_key, mapping=state)
    await redis_client.expire(state_key, _UPLOAD_STATE_TTL)

    return {"upload_id": upload_id, "storage_key": storage_key}


async def upload_multipart_part(
    storage_key: str,
    upload_id: str,
    part_number: int,
    data: bytes,
    owner_id: uuid.UUID,
) -> str:
    state_key = f"multipart:{owner_id}:{upload_id}"
    state = await redis_client.hgetall(state_key)
    if not state:
        raise ValueError("上传会话不存在或已过期，请重新初始化上传")

    if state.get("storage_key") != storage_key:
        raise ValueError("storage_key 与上传会话不匹配")

    max_part_size = settings.UPLOAD_PART_SIZE * 2
    if len(data) > max_part_size:
        raise ValueError(f"分片大小超过限制（最大 {max_part_size // (1024*1024)}MB）")

    etag = await upload_part(storage_key, upload_id, part_number, data)

    await redis_client.hset(state_key, f"part_{part_number}", etag)

    return etag


async def complete_multipart_upload(
    db: AsyncSession,
    owner: User,
    upload_id: str,
    storage_key: str,
    filename: str,
    mime_type: str,
    total_size: int,
    folder_id: uuid.UUID | None = None,
    parts: list[dict] | None = None,
) -> File:
    state_key = f"multipart:{owner.id}:{upload_id}"
    state = await redis_client.hgetall(state_key)

    if not state:
        if not parts:
            raise ValueError("上传会话不存在或已过期")
        file_id = uuid.uuid4()
        storage_key = storage_key or f"{owner.id}/{file_id}"
    else:
        file_id = uuid.UUID(state["file_id"])
        storage_key = state["storage_key"]
        filename = state.get("filename", filename)
        mime_type = state.get("mime_type", mime_type)
        total_size = int(state.get("total_size", total_size))
        folder_id_str = state.get("folder_id", "")
        folder_id = uuid.UUID(folder_id_str) if folder_id_str else None

        if not parts:
            parts = []
            total_parts = int(state.get("total_parts", "0"))
            for i in range(1, total_parts + 1):
                etag = state.get(f"part_{i}")
                if etag:
                    parts.append({"PartNumber": i, "ETag": etag})

    if not parts:
        raise ValueError("没有已上传的分片")

    parts.sort(key=lambda p: p["PartNumber"])
    await complete_multipart(storage_key, upload_id, parts)

    await redis_client.delete(state_key)

    file = File(
        id=file_id,
        owner_id=owner.id,
        folder_id=folder_id,
        filename=filename,
        storage_key=storage_key,
        size=total_size,
        mime_type=mime_type,
        file_type=categorize_file_type(mime_type),
    )

    owner.used_storage += total_size
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


async def abort_multipart_upload(
    storage_key: str,
    upload_id: str,
    owner_id: uuid.UUID,
) -> None:
    state_key = f"multipart:{owner_id}:{upload_id}"
    state = await redis_client.hgetall(state_key)
    if state and state.get("storage_key") != storage_key:
        raise ValueError("storage_key 与上传会话不匹配")
    await redis_client.delete(state_key)
    await abort_multipart(storage_key, upload_id)