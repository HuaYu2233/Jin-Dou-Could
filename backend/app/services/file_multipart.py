import io
import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFound, PayloadTooLarge, ValidationFailed
from app.core.redis import redis_client
from app.core.storage import (
    abort_multipart,
    complete_multipart,
    create_multipart,
    delete_file,
    head_object_size,
    upload_part,
)
from app.models.file import File
from app.models.user import User
from app.services import storage_accounting
from app.services.file_validation import (
    categorize_file_type,
    detect_real_mime_type,
    ensure_mime_allowed,
    sanitize_filename,
    validate_mime_type,
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
    ensure_mime_allowed(mime_type)
    if total_size <= 0:
        raise ValidationFailed("文件大小必须大于 0")
    if total_size > settings.MAX_UPLOAD_SIZE:
        raise PayloadTooLarge(f"文件过大，单文件上限 {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB")
    if part_size <= 0:
        raise ValidationFailed("分片大小不合法")
    storage_accounting.ensure_quota(owner, total_size)
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
        raise PayloadTooLarge(f"分片大小超过限制（最大 {max_part_size // (1024 * 1024)}MB）")

    total_parts = int(state.get("total_parts", "0"))
    max_parts = (settings.MAX_UPLOAD_SIZE + settings.UPLOAD_PART_SIZE - 1) // settings.UPLOAD_PART_SIZE
    part_limit = total_parts if total_parts > 0 else max_parts
    if part_number > part_limit:
        raise ValidationFailed(f"分片序号超出范围（共 {part_limit} 片）")

    total_size = int(state.get("total_size", "0"))
    previous_size = int(state.get(f"size_{part_number}", "0"))
    uploaded_bytes = int(state.get("uploaded_bytes", "0")) - previous_size + len(data)
    if total_size > 0 and uploaded_bytes > total_size:
        raise PayloadTooLarge("已上传数据超过声明的文件大小")

    if part_number == 1:
        declared = state.get("mime_type", "")
        real_mime = await detect_real_mime_type(io.BytesIO(data), declared)
        validate_mime_type(declared, real_mime)
        await redis_client.hset(state_key, "real_mime_type", real_mime)

    etag = await upload_part(storage_key, upload_id, part_number, data)

    await redis_client.hset(state_key, mapping={f"part_{part_number}": etag, f"size_{part_number}": str(len(data))})
    await redis_client.hset(state_key, "uploaded_bytes", uploaded_bytes)

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
        raise NotFound("上传会话不存在或已过期")
    if state.get("storage_key") != storage_key:
        raise ValidationFailed("storage_key 与上传会话不匹配")

    file_id = uuid.UUID(state["file_id"])
    storage_key = state["storage_key"]
    filename = state.get("filename", filename)
    real_mime = state.get("real_mime_type")
    if not real_mime:
        raise ValidationFailed("分片上传未完成文件类型校验，请从第 1 片开始上传")
    validate_mime_type(mime_type, real_mime)
    mime_type = real_mime
    total_size = int(state.get("total_size", total_size))
    part_size = int(state.get("part_size", settings.UPLOAD_PART_SIZE))
    total_parts = int(state.get("total_parts", "0"))
    folder_id_str = state.get("folder_id", "")
    folder_id = uuid.UUID(folder_id_str) if folder_id_str else None

    if not parts:
        parts = []
        for i in range(1, total_parts + 1):
            etag = state.get(f"part_{i}")
            if etag:
                parts.append({"PartNumber": i, "ETag": etag})

    if not parts:
        raise ValidationFailed("没有已上传的分片")

    if total_parts > 0:
        if len(parts) != total_parts:
            raise ValidationFailed(f"分片数量不符：声明 {total_parts} 片，实际 {len(parts)} 片")
        part_numbers = {p["PartNumber"] for p in parts}
        if part_numbers != set(range(1, total_parts + 1)):
            raise ValidationFailed("分片序号不连续或重复")

    parts.sort(key=lambda p: p["PartNumber"])
    await complete_multipart(storage_key, upload_id, parts)

    actual_size = await head_object_size(storage_key)
    if actual_size > settings.MAX_UPLOAD_SIZE:
        await delete_file(storage_key)
        raise PayloadTooLarge(f"文件过大，单文件上限 {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB")
    if total_parts > 0 and abs(actual_size - total_size) > part_size:
        await delete_file(storage_key)
        raise ValidationFailed(f"合并后实际大小 {actual_size} 与声明 {total_size} 不符")
    if not storage_accounting.has_room(owner, actual_size):
        await delete_file(storage_key)
        storage_accounting.ensure_quota(owner, actual_size)

    await redis_client.delete(state_key)

    file = File(
        id=file_id,
        owner_id=owner.id,
        folder_id=folder_id,
        filename=filename,
        storage_key=storage_key,
        size=actual_size,
        mime_type=mime_type,
        file_type=categorize_file_type(mime_type),
    )

    storage_accounting.add(owner, actual_size)
    db.add(file)
    await db.commit()
    await db.refresh(file)

    if file.file_type == "image":
        try:
            from app.tasks.thumbnail_tasks import generate_thumbnail

            generate_thumbnail.delay(storage_key, str(file_id))
        except Exception as exc:
            logger.bind(log_type="task").warning(f"缩略图任务入队失败: file={file_id}, {exc}")

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
    await abort_multipart(storage_key, upload_id)
