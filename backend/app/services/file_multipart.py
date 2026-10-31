import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.user import User
from app.core.config import settings
from app.core.exceptions import NotFound, PayloadTooLarge, ValidationFailed
from app.core.redis import redis_client
from app.core.storage import (
    create_multipart,
    upload_part,
    complete_multipart,
)
from app.services import storage_accounting
from app.services.file_validation import categorize_file_type, sanitize_filename

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
        raise NotFound("上传会话不存在或已过期，请重新初始化上传")

    if state.get("storage_key") != storage_key:
        raise ValidationFailed("storage_key 与上传会话不匹配")

    max_part_size = settings.UPLOAD_PART_SIZE * 2
    if len(data) > max_part_size:
        raise PayloadTooLarge(f"分片大小超过限制（最大 {max_part_size // (1024*1024)}MB）")

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
            raise NotFound("上传会话不存在或已过期")
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
        raise ValidationFailed("没有已上传的分片")

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

    storage_accounting.add(owner, total_size)
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
        raise ValidationFailed("storage_key 与上传会话不匹配")
    await redis_client.delete(state_key)