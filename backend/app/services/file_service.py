import re
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.file import File
from app.models.user import User
from app.core.storage import (
    upload_fileobj,
    upload_stream_multipart,
    delete_file,
    get_object_stream,
    get_presigned_download_url,
    get_presigned_preview_url,
)
from app.core.config import settings
from app.core.redis import redis_client

_FILENAME_MAX_LEN = 255
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_PATH_SEP_RE = re.compile(r"[\\/]+")

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


async def detect_real_mime_type(fileobj, declared: str) -> str:
    try:
        import magic
        try:
            await fileobj.seek(0)
            head = await fileobj.read(2048)
            await fileobj.seek(0)
        except Exception:
            head = None
        if head:
            if isinstance(head, str):
                head = head.encode("utf-8")
            detected = magic.from_buffer(head, mime=True)
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

def categorize_file_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("text/"):
        return "document"
    if mime_type in (
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ):
        return "document"
    if mime_type in (
        "application/zip",
        "application/x-rar-compressed",
        "application/x-7z-compressed",
    ):
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
    real_mime = detect_real_mime_type(fileobj, mime_type)
    validate_mime_type(mime_type, real_mime)
    mime_type = real_mime

    file_id = uuid.uuid4()
    storage_key = f"{owner.id}/{file_id}"

    if size is None:
        actual_size = await stream_upload_unknown_size(storage_key, fileobj, mime_type)
        if owner.used_storage + actual_size > owner.storage_quota:
            from app.core.storage import delete_file as _delete
            await _delete(storage_key)
            raise ValueError("存储空间不足")
        size = actual_size
    elif size >= settings.MULTIPART_THRESHOLD:
        await upload_stream_multipart(storage_key, fileobj, mime_type, size)
    else:
        await upload_fileobj(storage_key, fileobj, mime_type, size)

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

    cache_key = f"file_count:{owner_id}:{file_type or ''}:{folder_id or 'root'}"
    cached_total = await redis_client.get(cache_key)
    if cached_total is not None:
        total = int(cached_total)
    else:
        count_result = await db.execute(select(func.count()).select_from(File).where(*filters))
        total = count_result.scalar_one()
        await redis_client.setex(cache_key, 5, str(total))

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor).replace(tzinfo=timezone.utc)
            query = (
                select(File)
                .where(*filters, File.created_at < cursor_dt)
                .order_by(File.created_at.desc())
                .limit(limit)
            )
        except (ValueError, TypeError):
            query = (
                select(File)
                .where(*filters)
                .order_by(File.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
    else:
        query = (
            select(File)
            .where(*filters)
            .order_by(File.created_at.desc())
            .offset(skip)
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

    cache_key = f"search_count:{owner_id}:{keyword}"
    cached_total = await redis_client.get(cache_key)
    if cached_total is not None:
        total = int(cached_total)
    else:
        count_result = await db.execute(select(func.count()).select_from(File).where(*filters))
        total = count_result.scalar_one()
        await redis_client.setex(cache_key, 5, str(total))

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor).replace(tzinfo=timezone.utc)
            query = (
                select(File)
                .where(*filters, File.created_at < cursor_dt)
                .order_by(*order_cols)
                .limit(limit)
            )
        except (ValueError, TypeError):
            query = (
                select(File)
                .where(*filters)
                .order_by(*order_cols)
                .offset(skip)
                .limit(limit)
            )
    else:
        query = (
            select(File)
            .where(*filters)
            .order_by(*order_cols)
            .offset(skip)
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

    cache_key = f"trash_count:{owner_id}"
    cached_total = await redis_client.get(cache_key)
    if cached_total is not None:
        total = int(cached_total)
    else:
        count_result = await db.execute(select(func.count()).select_from(File).where(*filters))
        total = count_result.scalar_one()
        await redis_client.setex(cache_key, 5, str(total))

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor).replace(tzinfo=timezone.utc)
            query = (
                select(File)
                .where(*filters, File.deleted_at < cursor_dt)
                .order_by(File.deleted_at.desc())
                .limit(limit)
            )
        except (ValueError, TypeError):
            query = (
                select(File)
                .where(*filters)
                .order_by(File.deleted_at.desc())
                .offset(skip)
                .limit(limit)
            )
    else:
        query = (
            select(File)
            .where(*filters)
            .order_by(File.deleted_at.desc())
            .offset(skip)
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
    file.deleted_at = func.now()
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

    await delete_file(file.storage_key)

    owner_result = await db.execute(select(User).where(User.id == owner_id))
    owner = owner_result.scalar_one()
    owner.used_storage -= file.size

    await db.delete(file)
    await db.commit()
    return True

async def get_download_stream(file: File):
    from app.core.storage import stream_object
    return {
        "stream": stream_object(file.storage_key),
        "mime_type": file.mime_type,
        "filename": file.filename,
        "size": file.size,
    }


async def prepare_upload(
    user: User, file_size: int, declared_mime: str, filename: str
) -> None:
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise ValueError("文件过大，单文件上限 100MB")
    if user.used_storage + file_size > user.storage_quota:
        raise ValueError("存储空间不足，请联系管理员扩容")


async def stream_upload_unknown_size(
    storage_key: str, file_obj, mime_type: str
) -> int:
    from app.core.storage import get_s3_client
    total = 0
    async with get_s3_client() as client:
        resp = await client.create_multipart_upload(
            Bucket=settings.MINIO_BUCKET,
            Key=storage_key,
            ContentType=mime_type,
        )
        upload_id = resp["UploadId"]
        parts = []
        part_number = 1
        try:
            while True:
                chunk = await file_obj.read(settings.UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                total += len(chunk)
                if total > settings.MAX_UPLOAD_SIZE:
                    raise ValueError("文件过大，单文件上限 100MB")
                part_resp = await client.upload_part(
                    Bucket=settings.MINIO_BUCKET,
                    Key=storage_key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk,
                )
                parts.append({
                    "PartNumber": part_number,
                    "ETag": part_resp["ETag"],
                })
                part_number += 1

            if not parts:
                await client.put_object(
                    Bucket=settings.MINIO_BUCKET,
                    Key=storage_key,
                    Body=b"",
                    ContentType=mime_type,
                )
            else:
                await client.complete_multipart_upload(
                    Bucket=settings.MINIO_BUCKET,
                    Key=storage_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
        except Exception:
            try:
                await client.abort_multipart_upload(
                    Bucket=settings.MINIO_BUCKET,
                    Key=storage_key,
                    UploadId=upload_id,
                )
            except Exception:
                pass
            raise
    return total


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