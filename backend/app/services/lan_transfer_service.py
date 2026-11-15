import io
import ipaddress
import secrets
import shutil
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    Conflict,
    Forbidden,
    Gone,
    InsufficientStorage,
    NotFound,
    PayloadTooLarge,
    QuotaExceeded,
    RateLimited,
    ServiceUnavailable,
    UnsupportedMediaType,
    ValidationFailed,
)
from app.core.redis import redis_client
from app.core.security import create_room_token, hash_password, verify_password
from app.core.storage import (
    abort_multipart,
    batch_delete_files,
    complete_multipart,
    create_multipart,
    delete_file,
    head_object_size,
    upload_fileobj,
    upload_part,
    upload_stream_multipart,
)
from app.models.file import File
from app.models.transfer_room import TransferRoom, TransferRoomFile
from app.models.user import User
from app.services import storage_accounting
from app.services.file_validation import (
    categorize_file_type,
    detect_real_mime_type,
    ensure_mime_allowed,
    sanitize_filename,
    validate_mime_type,
)

ROOM_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_CODE_LEN = 8
_RESERVED_TTL = 3600
_CACHE_TTL = 60


def get_disk_usage() -> tuple[int, int, int]:
    path = settings.LAN_TRANSFER_DISK_PATH
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        logger.bind(log_type="storage").warning(f"磁盘探测路径不可用，回退根目录: {path}")
        usage = shutil.disk_usage("/")
    return usage.total, usage.used, usage.free


def is_feature_available() -> bool:
    if not settings.LAN_TRANSFER_ENABLED:
        return False
    return get_disk_usage()[2] >= settings.LAN_TRANSFER_MIN_FREE_BYTES


def ensure_feature_available() -> None:
    if not settings.LAN_TRANSFER_ENABLED:
        raise Forbidden("局域网快传已关闭")
    if get_disk_usage()[2] < settings.LAN_TRANSFER_MIN_FREE_BYTES:
        raise InsufficientStorage("服务器存储空间不足，快传已暂停")


def _ensure_disk_for(size: int) -> None:
    free = get_disk_usage()[2]
    if free - size < settings.LAN_TRANSFER_MIN_FREE_BYTES:
        raise InsufficientStorage("服务器存储空间不足")


def resolve_limits(user: User) -> tuple[int, int]:
    limit = max(int(user.storage_quota or 0), 0)
    return limit, limit


def _reserved_key(room_id: uuid.UUID | str) -> str:
    return f"lan_room:{room_id}:reserved"


def _used_key(room_id: uuid.UUID | str) -> str:
    return f"lan_room:{room_id}:used"


def _files_key(room_id: uuid.UUID | str) -> str:
    return f"lan_room:{room_id}:files"


async def _invalidate_room_caches(room_id: uuid.UUID | str) -> None:
    with suppress(Exception):
        await redis_client.delete(_used_key(room_id), _files_key(room_id))


async def get_room_used(db: AsyncSession, room_id: uuid.UUID) -> int:
    cached = await redis_client.get(_used_key(room_id))
    if cached is not None:
        return int(cached)
    used = await db.scalar(
        select(func.coalesce(func.sum(TransferRoomFile.size), 0)).where(TransferRoomFile.room_id == room_id)
    )
    used = int(used or 0)
    with suppress(Exception):
        await redis_client.setex(_used_key(room_id), _CACHE_TTL, used)
    return used


async def get_room_file_count(db: AsyncSession, room_id: uuid.UUID) -> int:
    cached = await redis_client.get(_files_key(room_id))
    if cached is not None:
        return int(cached)
    count = await db.scalar(select(func.count(TransferRoomFile.id)).where(TransferRoomFile.room_id == room_id))
    count = int(count or 0)
    with suppress(Exception):
        await redis_client.setex(_files_key(room_id), _CACHE_TTL, count)
    return count


async def reserve_capacity(room: TransferRoom, used_size: int, size: int) -> None:
    key = _reserved_key(room.id)
    reserved = await redis_client.incrby(key, size)
    await redis_client.expire(key, _RESERVED_TTL)
    if used_size + reserved > room.max_total_size:
        await redis_client.decrby(key, size)
        raise InsufficientStorage("房间空间不足")


async def release_capacity(room_id: uuid.UUID, size: int) -> None:
    if size <= 0:
        return
    key = _reserved_key(room_id)
    remaining = await redis_client.decrby(key, size)
    if remaining <= 0:
        with suppress(Exception):
            await redis_client.delete(key)


def _owner_reserved_key(owner_id: uuid.UUID | str) -> str:
    return f"lan_owner:{owner_id}:reserved"


async def reserve_owner_capacity(owner_id: uuid.UUID, used_storage: int, quota: int, size: int) -> None:
    if size <= 0:
        return
    key = _owner_reserved_key(owner_id)
    reserved = await redis_client.incrby(key, size)
    await redis_client.expire(key, _RESERVED_TTL)
    if used_storage + reserved > quota:
        await redis_client.decrby(key, size)
        raise QuotaExceeded("存储空间不足，请清理网盘或关闭旧房间")


async def release_owner_capacity(owner_id: uuid.UUID, size: int) -> None:
    if size <= 0:
        return
    key = _owner_reserved_key(owner_id)
    with suppress(Exception):
        remaining = await redis_client.decrby(key, size)
        if remaining <= 0:
            await redis_client.delete(key)


async def check_room_rate_limit(
    room_id: uuid.UUID | str,
    jti: str | None,
    limit: int,
    bucket: str = "default",
) -> None:
    if not jti:
        return
    key = f"lan_rl:{room_id}:{bucket}:{jti}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 60)
        if count > limit:
            raise RateLimited("请求过于频繁，请稍后再试")
    except RateLimited:
        raise
    except Exception as exc:
        logger.bind(log_type="security").warning(f"房间限流检查失败，放行请求: {exc}")


async def _generate_code(db: AsyncSession) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(ROOM_CODE_CHARS) for _ in range(ROOM_CODE_LEN))
        exists = await db.scalar(select(func.count(TransferRoom.id)).where(TransferRoom.code == code))
        if not exists:
            return code
    raise ServiceUnavailable("房间码生成失败，请稍后重试")


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _is_expired(room: TransferRoom) -> bool:
    return _as_aware(room.expires_at) <= _now()


async def _ensure_active_room_slots(db: AsyncSession, owner_id: uuid.UUID) -> None:
    limit = settings.LAN_TRANSFER_MAX_ACTIVE_ROOMS
    if limit <= 0:
        return
    active = await db.scalar(
        select(func.count(TransferRoom.id)).where(
            TransferRoom.owner_id == owner_id,
            TransferRoom.closed_at.is_(None),
            TransferRoom.expires_at > _now(),
        )
    )
    if int(active or 0) >= limit:
        raise Conflict(f"活跃房间数已达上限（{limit} 个），请先关闭旧房间")


async def create_room(
    db: AsyncSession,
    owner: User,
    title: str | None = None,
    password: str | None = None,
    ttl_hours: int | None = None,
) -> TransferRoom:
    ensure_feature_available()
    await _ensure_active_room_slots(db, owner.id)
    ttl = ttl_hours or settings.LAN_TRANSFER_ROOM_TTL_HOURS
    ttl = max(1, min(ttl, 168))
    max_file_size, max_total_size = resolve_limits(owner)
    code = await _generate_code(db)
    room = TransferRoom(
        code=code,
        owner_id=owner.id,
        title=(title or "").strip() or None,
        password_hash=hash_password(password) if password else None,
        max_file_size=max_file_size,
        max_total_size=max_total_size,
        expires_at=_now() + timedelta(hours=ttl),
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


async def get_room(db: AsyncSession, room_id: uuid.UUID) -> TransferRoom:
    room = await db.scalar(select(TransferRoom).where(TransferRoom.id == room_id))
    if not room:
        raise NotFound("房间不存在")
    if room.closed_at is not None:
        raise Gone("房间已关闭")
    if _is_expired(room):
        raise Gone("房间已过期")
    return room


async def get_owned_room(db: AsyncSession, room_id: uuid.UUID, owner_id: uuid.UUID) -> TransferRoom:
    room = await db.scalar(select(TransferRoom).where(TransferRoom.id == room_id, TransferRoom.owner_id == owner_id))
    if not room:
        raise NotFound("房间不存在")
    return room


async def _record_join_failure(code: str, client_ip: str) -> None:
    fail_key = f"lan_join_fail:{code}:{client_ip}"
    count = await redis_client.incr(fail_key)
    if count == 1:
        await redis_client.expire(fail_key, settings.LAN_TRANSFER_JOIN_RATE_WINDOW_SECONDS)
    if count >= settings.LAN_TRANSFER_JOIN_RATE_LIMIT:
        await redis_client.setex(
            f"lan_join_lock:{code}:{client_ip}",
            settings.LAN_TRANSFER_JOIN_RATE_WINDOW_SECONDS,
            "1",
        )


def _same_subnet_hint(client_ip: str) -> bool:
    if not settings.LAN_TRANSFER_REQUIRE_SAME_SUBNET:
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return True
    cidrs = [c.strip() for c in settings.LAN_TRANSFER_ALLOWED_CIDRS.split(",") if c.strip()]
    if cidrs:
        try:
            networks = [ipaddress.ip_network(c) for c in cidrs]
        except ValueError:
            return False
        return not any(addr in network for network in networks)
    return not (addr.is_private or addr.is_loopback)


async def join_room(
    db: AsyncSession,
    code: str,
    password: str | None,
    client_ip: str,
) -> tuple[TransferRoom, str, bool]:
    ensure_feature_available()
    normalized = (code or "").strip().upper()
    if await redis_client.exists(f"lan_join_lock:{normalized}:{client_ip}"):
        raise RateLimited("加入尝试过于频繁，请稍后再试")

    room = await db.scalar(select(TransferRoom).where(TransferRoom.code == normalized))
    if not room:
        await _record_join_failure(normalized, client_ip)
        raise NotFound("房间码不存在")
    if room.closed_at is not None:
        raise Gone("房间已关闭")
    if _is_expired(room):
        raise Gone("房间已过期")

    if room.password_hash and (not password or not verify_password(password, room.password_hash)):
        await _record_join_failure(normalized, client_ip)
        raise Forbidden("房间密码错误")

    with suppress(Exception):
        await redis_client.delete(f"lan_join_fail:{normalized}:{client_ip}")

    remaining = int((_as_aware(room.expires_at) - _now()).total_seconds())
    ttl_seconds = min(remaining, settings.LAN_TRANSFER_ROOM_TTL_HOURS * 3600)
    token = create_room_token(
        room.id,
        "guest",
        f"anon:{client_ip}",
        timedelta(seconds=max(60, ttl_seconds)),
    )
    return room, token, _same_subnet_hint(client_ip)


async def list_room_files(db: AsyncSession, room_id: uuid.UUID) -> list[tuple[TransferRoomFile, str | None]]:
    result = await db.execute(
        select(TransferRoomFile, User.username)
        .outerjoin(User, User.id == TransferRoomFile.uploader_id)
        .where(TransferRoomFile.room_id == room_id)
        .order_by(TransferRoomFile.created_at.desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def get_room_file(db: AsyncSession, room_id: uuid.UUID, file_id: uuid.UUID) -> TransferRoomFile:
    record = await db.scalar(
        select(TransferRoomFile).where(TransferRoomFile.id == file_id, TransferRoomFile.room_id == room_id)
    )
    if not record:
        raise NotFound("文件不存在")
    return record


def _validate_mime(declared: str, detected: str) -> None:
    try:
        validate_mime_type(declared, detected)
    except ValidationFailed as exc:
        raise UnsupportedMediaType(exc.message) from exc


async def attach_drive_files(db: AsyncSession, room: TransferRoom, file_ids: list[uuid.UUID]) -> list[TransferRoomFile]:
    ensure_feature_available()
    if room.closed_at is not None:
        raise Gone("房间已关闭")
    if _is_expired(room):
        raise Gone("房间已过期")
    unique_ids = list(dict.fromkeys(file_ids))
    if not unique_ids:
        raise ValidationFailed("请选择要发送的文件")

    files = (
        (
            await db.execute(
                select(File).where(
                    File.id.in_(unique_ids),
                    File.owner_id == room.owner_id,
                    File.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(files) != len(unique_ids):
        raise NotFound("部分文件不存在或不属于当前用户")

    existing_ids = set(
        (
            await db.execute(
                select(TransferRoomFile.source_file_id).where(
                    TransferRoomFile.room_id == room.id,
                    TransferRoomFile.source_file_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    pending = [f for f in files if f.id not in existing_ids]
    if not pending:
        return []

    for f in pending:
        if f.size > room.max_file_size:
            raise PayloadTooLarge(f"文件过大，单文件上限 {room.max_file_size // (1024 * 1024)}MB")
    if await get_room_file_count(db, room.id) + len(pending) > settings.LAN_TRANSFER_MAX_FILES_PER_ROOM:
        raise ValidationFailed(f"房间文件数量已达上限（{settings.LAN_TRANSFER_MAX_FILES_PER_ROOM} 个）")

    used = await get_room_used(db, room.id)
    total = sum(f.size for f in pending)
    if used + total > room.max_total_size:
        raise InsufficientStorage("房间空间不足")

    records = [
        TransferRoomFile(
            id=uuid.uuid4(),
            room_id=room.id,
            uploader_id=room.owner_id,
            source_file_id=f.id,
            filename=f.filename,
            storage_key=f.storage_key,
            size=f.size,
            mime_type=f.mime_type,
            file_type=f.file_type,
        )
        for f in pending
    ]
    db.add_all(records)
    await db.commit()
    for record in records:
        await db.refresh(record)
    await _invalidate_room_caches(room.id)
    return records


async def detach_drive_file(db: AsyncSession, file_id: uuid.UUID) -> None:
    room_ids = set(
        (await db.execute(select(TransferRoomFile.room_id).where(TransferRoomFile.source_file_id == file_id)))
        .scalars()
        .all()
    )
    if not room_ids:
        return
    await db.execute(TransferRoomFile.__table__.delete().where(TransferRoomFile.source_file_id == file_id))
    for room_id in room_ids:
        await _invalidate_room_caches(room_id)


async def _check_size_and_count(db: AsyncSession, room: TransferRoom, size: int) -> None:
    if size <= 0:
        raise ValidationFailed("文件大小必须大于 0")
    if size > room.max_file_size:
        raise PayloadTooLarge(f"文件过大，单文件上限 {room.max_file_size // (1024 * 1024)}MB")
    if await get_room_file_count(db, room.id) >= settings.LAN_TRANSFER_MAX_FILES_PER_ROOM:
        raise ValidationFailed(f"房间文件数量已达上限（{settings.LAN_TRANSFER_MAX_FILES_PER_ROOM} 个）")
    _ensure_disk_for(size)


async def _reserve_room_capacity(db: AsyncSession, room: TransferRoom, size: int) -> None:
    await reserve_capacity(room, await get_room_used(db, room.id), size)
    owner = await db.scalar(select(User).where(User.id == room.owner_id))
    if owner is None:
        return
    try:
        await reserve_owner_capacity(room.owner_id, owner.used_storage, owner.storage_quota, size)
    except Exception:
        with suppress(Exception):
            await release_capacity(room.id, size)
        raise


async def _release_room_capacity(room: TransferRoom, size: int) -> None:
    with suppress(Exception):
        await release_capacity(room.id, size)
    with suppress(Exception):
        await release_owner_capacity(room.owner_id, size)


def _prepare_filename_and_mime(filename: str, mime_type: str) -> tuple[str, str]:
    name = sanitize_filename(filename)
    try:
        ensure_mime_allowed(mime_type)
    except ValidationFailed as exc:
        raise UnsupportedMediaType(exc.message) from exc
    return name, mime_type


async def add_room_file(
    db: AsyncSession,
    room: TransferRoom,
    uploader_id: uuid.UUID | None,
    filename: str,
    fileobj,
    mime_type: str,
    size: int,
) -> TransferRoomFile:
    ensure_feature_available()
    await _check_size_and_count(db, room, size)
    filename, mime_type = _prepare_filename_and_mime(filename, mime_type)

    real_mime = await detect_real_mime_type(fileobj, mime_type)
    _validate_mime(mime_type, real_mime)
    mime_type = real_mime
    if hasattr(fileobj, "seek"):
        fileobj.seek(0)

    await _reserve_room_capacity(db, room, size)
    file_id = uuid.uuid4()
    storage_key = f"lan-transfer/{room.id}/{file_id}"
    written = False
    try:
        if size >= settings.LAN_TRANSFER_CHUNK_THRESHOLD:
            await upload_stream_multipart(storage_key, fileobj, mime_type, size, max_size=room.max_file_size)
        else:
            await upload_fileobj(storage_key, fileobj, mime_type)
        written = True

        record = TransferRoomFile(
            id=file_id,
            room_id=room.id,
            uploader_id=uploader_id,
            filename=filename,
            storage_key=storage_key,
            size=size,
            mime_type=mime_type,
            file_type=categorize_file_type(mime_type),
        )
        db.add(record)
        await storage_accounting.adjust(db, room.owner_id, size)
        await db.commit()
        await db.refresh(record)
    except Exception:
        if written:
            with suppress(Exception):
                await delete_file(storage_key)
        await _release_room_capacity(room, size)
        raise

    await _release_room_capacity(room, size)
    await _invalidate_room_caches(room.id)
    return record


async def init_room_multipart(
    db: AsyncSession,
    room: TransferRoom,
    filename: str,
    mime_type: str,
    total_size: int,
    total_parts: int = 0,
    uploader_id: uuid.UUID | None = None,
) -> dict:
    ensure_feature_available()
    await _check_size_and_count(db, room, total_size)
    filename, mime_type = _prepare_filename_and_mime(filename, mime_type)
    await _reserve_room_capacity(db, room, total_size)

    file_id = uuid.uuid4()
    storage_key = f"lan-transfer/{room.id}/{file_id}"
    try:
        upload_id = await create_multipart(storage_key, mime_type)
    except Exception:
        await _release_room_capacity(room, total_size)
        raise

    part_size = settings.LAN_TRANSFER_PART_SIZE
    state = {
        "room_id": str(room.id),
        "file_id": str(file_id),
        "storage_key": storage_key,
        "filename": filename,
        "mime_type": mime_type,
        "total_size": str(total_size),
        "total_parts": str(total_parts),
        "part_size": str(part_size),
        "uploaded_bytes": "0",
        "completed_parts": "",
        "uploader_id": str(uploader_id) if uploader_id else "",
    }
    state_key = f"lan_mpu:{upload_id}"
    await redis_client.hset(state_key, mapping=state)
    ttl = max(60, int((_as_aware(room.expires_at) - _now()).total_seconds()))
    await redis_client.expire(state_key, ttl)

    return {
        "upload_id": upload_id,
        "storage_key": storage_key,
        "part_size": part_size,
        "total_parts": total_parts,
    }


async def upload_room_part(
    room: TransferRoom,
    upload_id: str,
    part_number: int,
    data: bytes,
) -> str:
    state_key = f"lan_mpu:{upload_id}"
    state = await redis_client.hgetall(state_key)
    if not state:
        raise NotFound("上传会话不存在或已过期，请重新初始化上传")
    if state.get("room_id") != str(room.id):
        raise Forbidden("上传会话不属于当前房间")

    if part_number <= 0:
        raise ValidationFailed("分片序号不合法")
    max_part_size = settings.LAN_TRANSFER_PART_SIZE * 2
    if len(data) > max_part_size:
        raise PayloadTooLarge(f"分片大小超过限制（最大 {max_part_size // (1024 * 1024)}MB）")

    total_size = int(state.get("total_size", "0"))
    previous_size = int(state.get(f"size_{part_number}", "0"))
    uploaded = int(state.get("uploaded_bytes", "0")) - previous_size + len(data)
    if total_size > 0 and uploaded > total_size:
        raise PayloadTooLarge("已上传数据超过声明的文件大小")

    if part_number == 1:
        declared = state.get("mime_type", "")
        real_mime = await detect_real_mime_type(io.BytesIO(data), declared)
        _validate_mime(declared, real_mime)
        await redis_client.hset(state_key, "real_mime_type", real_mime)

    etag = await upload_part(state["storage_key"], upload_id, part_number, data)
    await redis_client.hset(
        state_key,
        mapping={f"part_{part_number}": etag, f"size_{part_number}": str(len(data))},
    )
    await redis_client.hset(state_key, "uploaded_bytes", uploaded)
    return etag


async def complete_room_multipart(
    db: AsyncSession,
    room: TransferRoom,
    upload_id: str,
    storage_key: str,
    filename: str | None,
    mime_type: str | None,
    total_size: int,
    parts: list[dict] | None = None,
) -> TransferRoomFile:
    state_key = f"lan_mpu:{upload_id}"
    state = await redis_client.hgetall(state_key)
    if not state:
        raise NotFound("上传会话不存在或已过期")
    if state.get("room_id") != str(room.id):
        raise Forbidden("上传会话不属于当前房间")
    if state.get("storage_key") != storage_key:
        raise ValidationFailed("storage_key 与上传会话不匹配")

    file_id = uuid.UUID(state["file_id"])
    filename = sanitize_filename(state.get("filename") or filename or "unknown")
    declared = state.get("mime_type") or mime_type or "application/octet-stream"
    real_mime = state.get("real_mime_type")
    if not real_mime:
        raise ValidationFailed("分片上传未完成文件类型校验，请从第 1 片开始上传")
    _validate_mime(declared, real_mime)
    mime_type = real_mime
    total_size = int(state.get("total_size", total_size))

    if not parts:
        parts = []
        for i in range(1, int(state.get("total_parts", "0")) + 1):
            etag = state.get(f"part_{i}")
            if etag:
                parts.append({"PartNumber": i, "ETag": etag})
    if not parts:
        raise ValidationFailed("没有已上传的分片")
    parts.sort(key=lambda p: int(p["PartNumber"]))

    try:
        await complete_multipart(storage_key, upload_id, parts)
        actual_size = await head_object_size(storage_key)
        if actual_size > room.max_file_size:
            await delete_file(storage_key)
            raise PayloadTooLarge(f"文件过大，单文件上限 {room.max_file_size // (1024 * 1024)}MB")
    except Exception:
        await _release_room_capacity(room, total_size)
        with suppress(Exception):
            await redis_client.delete(state_key)
        raise

    record = TransferRoomFile(
        id=file_id,
        room_id=room.id,
        uploader_id=uuid.UUID(state["uploader_id"]) if state.get("uploader_id") else None,
        filename=filename,
        storage_key=storage_key,
        size=actual_size,
        mime_type=mime_type,
        file_type=categorize_file_type(mime_type),
    )
    db.add(record)
    await storage_accounting.adjust(db, room.owner_id, actual_size)
    await db.commit()
    await db.refresh(record)

    with suppress(Exception):
        await redis_client.delete(state_key)
    await _release_room_capacity(room, total_size)
    await _invalidate_room_caches(room.id)
    return record


async def abort_room_multipart(room: TransferRoom, upload_id: str, storage_key: str | None) -> None:
    state_key = f"lan_mpu:{upload_id}"
    state = await redis_client.hgetall(state_key)
    if state and state.get("room_id") != str(room.id):
        raise Forbidden("上传会话不属于当前房间")
    if state and storage_key and state.get("storage_key") != storage_key:
        raise ValidationFailed("storage_key 与上传会话不匹配")

    with suppress(Exception):
        await redis_client.delete(state_key)
    if state:
        with suppress(Exception):
            await abort_multipart(state["storage_key"], upload_id)
        await _release_room_capacity(room, int(state.get("total_size", "0")))
    elif storage_key:
        with suppress(Exception):
            await abort_multipart(storage_key, upload_id)


async def delete_room_file(db: AsyncSession, room: TransferRoom, file_id: uuid.UUID) -> None:
    record = await get_room_file(db, room.id, file_id)
    if record.source_file_id is None:
        with suppress(Exception):
            await delete_file(record.storage_key)
        await storage_accounting.adjust(db, room.owner_id, -record.size)
    await db.delete(record)
    await db.commit()
    await _invalidate_room_caches(room.id)


async def close_room(db: AsyncSession, room: TransferRoom) -> None:
    room.closed_at = _now()
    own_total = await db.scalar(
        select(func.coalesce(func.sum(TransferRoomFile.size), 0)).where(
            TransferRoomFile.room_id == room.id,
            TransferRoomFile.source_file_id.is_(None),
        )
    )
    result = await db.execute(
        select(TransferRoomFile.storage_key).where(
            TransferRoomFile.room_id == room.id,
            TransferRoomFile.source_file_id.is_(None),
        )
    )
    storage_keys = [row[0] for row in result.all()]
    if storage_keys:
        with suppress(Exception):
            await batch_delete_files(storage_keys)
    await db.execute(TransferRoomFile.__table__.delete().where(TransferRoomFile.room_id == room.id))
    await storage_accounting.adjust(db, room.owner_id, -int(own_total or 0))
    await db.commit()
    await _invalidate_room_caches(room.id)


def build_join_url(code: str, origin: str | None, referer: str | None) -> str:
    base = settings.LAN_TRANSFER_PUBLIC_BASE_URL.strip()
    if base:
        return f"{base.rstrip('/')}/transfer/{code}"
    if origin:
        return f"{origin.rstrip('/')}/transfer/{code}"
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/transfer/{code}"
    return f"/transfer/{code}"


async def cleanup_expired_rooms() -> int:
    from app.db.base import AsyncSessionLocal

    cleaned = 0
    async with AsyncSessionLocal() as db:
        rooms = (
            (
                await db.execute(
                    select(TransferRoom)
                    .where(or_(TransferRoom.expires_at <= _now(), TransferRoom.closed_at.is_not(None)))
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        for room in rooms:
            own_total = await db.scalar(
                select(func.coalesce(func.sum(TransferRoomFile.size), 0)).where(
                    TransferRoomFile.room_id == room.id,
                    TransferRoomFile.source_file_id.is_(None),
                )
            )
            result = await db.execute(
                select(TransferRoomFile.storage_key).where(
                    TransferRoomFile.room_id == room.id,
                    TransferRoomFile.source_file_id.is_(None),
                )
            )
            storage_keys = [row[0] for row in result.all()]
            if storage_keys:
                try:
                    await batch_delete_files(storage_keys)
                except Exception as exc:
                    logger.bind(log_type="storage").warning(f"房间对象清理失败: room={room.id}, {exc}")
            await db.execute(TransferRoomFile.__table__.delete().where(TransferRoomFile.room_id == room.id))
            await storage_accounting.adjust(db, room.owner_id, -int(own_total or 0))
            await db.delete(room)
            await db.commit()
            await _invalidate_room_caches(room.id)
            cleaned += 1
    return cleaned
