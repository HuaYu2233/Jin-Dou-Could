import os
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RoomContext, get_current_user, get_room_context
from app.core.client_ip import get_client_ip
from app.core.exceptions import ValidationFailed
from app.core.storage import open_object_stream
from app.db.base import get_db
from app.models.transfer_room import TransferRoom
from app.models.user import User
from app.schemas.transfer_room import (
    RoomAttachDriveFilesRequest,
    RoomAttachDriveFilesResponse,
    RoomCreateRequest,
    RoomFileItem,
    RoomFileListResponse,
    RoomJoinRequest,
    RoomJoinResponse,
    RoomMultipartCompleteRequest,
    RoomMultipartInitRequest,
    RoomMultipartInitResponse,
    RoomMultipartPartResponse,
    RoomResponse,
)
from app.services import lan_transfer_service

router = APIRouter()

LIST_RATE_LIMIT = 60
UPLOAD_RATE_LIMIT = 300
DOWNLOAD_RATE_LIMIT = 60
DELETE_RATE_LIMIT = 30


def _room_payload(room: TransferRoom, used_size: int, file_count: int, join_url: str) -> RoomResponse:
    return RoomResponse(
        room_id=room.id,
        code=room.code,
        join_url=join_url,
        title=room.title,
        has_password=bool(room.password_hash),
        max_file_size=room.max_file_size,
        max_total_size=room.max_total_size,
        used_size=used_size,
        file_count=file_count,
        expires_at=room.expires_at,
        closed_at=room.closed_at,
    )


def _file_item(record, uploader: str | None) -> RoomFileItem:
    return RoomFileItem(
        id=record.id,
        filename=record.filename,
        size=record.size,
        mime_type=record.mime_type,
        file_type=record.file_type,
        uploader=uploader or "匿名",
        created_at=record.created_at,
    )


def _upload_size(file: UploadFile) -> int:
    if file.size is not None:
        return int(file.size)
    try:
        return int(os.fstat(file.file.fileno()).st_size)
    except OSError as exc:
        raise ValidationFailed("无法确定上传文件大小") from exc


@router.post("/rooms", response_model=RoomResponse, status_code=201)
async def create_room(
    request: Request,
    body: RoomCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = await lan_transfer_service.create_room(
        db,
        current_user,
        title=body.title,
        password=body.password,
        ttl_hours=body.ttl_hours,
    )
    join_url = lan_transfer_service.build_join_url(
        room.code,
        request.headers.get("origin"),
        request.headers.get("referer"),
    )
    return _room_payload(room, 0, 0, join_url)


@router.get("/rooms/{room_id}", response_model=RoomResponse)
async def get_room_detail(
    room_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = await lan_transfer_service.get_owned_room(db, room_id, current_user.id)
    used = await lan_transfer_service.get_room_used(db, room.id)
    count = await lan_transfer_service.get_room_file_count(db, room.id)
    join_url = lan_transfer_service.build_join_url(
        room.code,
        request.headers.get("origin"),
        request.headers.get("referer"),
    )
    return _room_payload(room, used, count, join_url)


@router.post("/rooms/{room_id}/close")
async def close_room(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = await lan_transfer_service.get_owned_room(db, room_id, current_user.id)
    if room.closed_at is None:
        await lan_transfer_service.close_room(db, room)
    return {"message": "房间已关闭"}


@router.post("/rooms/{room_id}/send-from-files", response_model=RoomAttachDriveFilesResponse)
async def send_from_drive_files(
    room_id: UUID,
    body: RoomAttachDriveFilesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = await lan_transfer_service.get_owned_room(db, room_id, current_user.id)
    records = await lan_transfer_service.attach_drive_files(db, room, body.file_ids)
    used = await lan_transfer_service.get_room_used(db, room.id)
    count = await lan_transfer_service.get_room_file_count(db, room.id)
    return RoomAttachDriveFilesResponse(
        items=[_file_item(record, current_user.username) for record in records],
        used_size=used,
        file_count=count,
    )


@router.post("/public/rooms/{code}/join", response_model=RoomJoinResponse)
async def join_room(
    request: Request,
    code: str,
    body: RoomJoinRequest,
    db: AsyncSession = Depends(get_db),
):
    room, room_token, hint = await lan_transfer_service.join_room(
        db,
        code,
        body.password,
        get_client_ip(request),
    )
    used = await lan_transfer_service.get_room_used(db, room.id)
    count = await lan_transfer_service.get_room_file_count(db, room.id)
    return RoomJoinResponse(
        room_token=room_token,
        room_id=room.id,
        title=room.title,
        max_file_size=room.max_file_size,
        max_total_size=room.max_total_size,
        used_size=used,
        file_count=count,
        expires_at=room.expires_at,
        same_subnet_hint=hint,
    )


@router.get("/public/rooms/{room_id}/files", response_model=RoomFileListResponse)
async def list_room_files(
    ctx: RoomContext = Depends(get_room_context),
    db: AsyncSession = Depends(get_db),
):
    await lan_transfer_service.check_room_rate_limit(ctx.room.id, ctx.jti, LIST_RATE_LIMIT, bucket="list")
    rows = await lan_transfer_service.list_room_files(db, ctx.room.id)
    used = await lan_transfer_service.get_room_used(db, ctx.room.id)
    count = await lan_transfer_service.get_room_file_count(db, ctx.room.id)
    return RoomFileListResponse(
        items=[_file_item(record, uploader) for record, uploader in rows],
        used_size=used,
        max_total_size=ctx.room.max_total_size,
        file_count=count,
    )


@router.post("/public/rooms/{room_id}/files", response_model=RoomFileItem)
async def upload_room_file(
    file: UploadFile = File(...),
    ctx: RoomContext = Depends(get_room_context),
    db: AsyncSession = Depends(get_db),
):
    await lan_transfer_service.check_room_rate_limit(ctx.room.id, ctx.jti, UPLOAD_RATE_LIMIT, bucket="upload")
    await file.seek(0)
    record = await lan_transfer_service.add_room_file(
        db,
        ctx.room,
        ctx.user_id,
        file.filename or "unknown",
        file.file,
        file.content_type or "application/octet-stream",
        _upload_size(file),
    )
    return _file_item(record, ctx.user_name)


@router.post("/public/rooms/{room_id}/multipart/init", response_model=RoomMultipartInitResponse)
async def init_room_multipart(
    body: RoomMultipartInitRequest,
    ctx: RoomContext = Depends(get_room_context),
    db: AsyncSession = Depends(get_db),
):
    await lan_transfer_service.check_room_rate_limit(ctx.room.id, ctx.jti, UPLOAD_RATE_LIMIT, bucket="upload")
    result = await lan_transfer_service.init_room_multipart(
        db,
        ctx.room,
        body.filename,
        body.mime_type,
        body.total_size,
        body.total_parts,
        uploader_id=ctx.user_id,
    )
    return RoomMultipartInitResponse(**result)


@router.post("/public/rooms/{room_id}/multipart/part", response_model=RoomMultipartPartResponse)
async def upload_room_multipart_part(
    request: Request,
    upload_id: str = Query(...),
    part_number: int = Query(..., ge=1),
    ctx: RoomContext = Depends(get_room_context),
):
    await lan_transfer_service.check_room_rate_limit(ctx.room.id, ctx.jti, UPLOAD_RATE_LIMIT, bucket="upload")
    data = await request.body()
    etag = await lan_transfer_service.upload_room_part(ctx.room, upload_id, part_number, data)
    return RoomMultipartPartResponse(etag=etag, part_number=part_number)


@router.post("/public/rooms/{room_id}/multipart/complete", response_model=RoomFileItem)
async def complete_room_multipart(
    body: RoomMultipartCompleteRequest,
    ctx: RoomContext = Depends(get_room_context),
    db: AsyncSession = Depends(get_db),
):
    await lan_transfer_service.check_room_rate_limit(ctx.room.id, ctx.jti, UPLOAD_RATE_LIMIT, bucket="upload")
    record = await lan_transfer_service.complete_room_multipart(
        db,
        ctx.room,
        body.upload_id,
        body.storage_key,
        body.filename,
        body.mime_type,
        body.total_size,
        body.parts,
    )
    return _file_item(record, ctx.user_name)


@router.post("/public/rooms/{room_id}/multipart/abort")
async def abort_room_multipart(
    upload_id: str = Query(...),
    storage_key: str | None = Query(None),
    ctx: RoomContext = Depends(get_room_context),
):
    await lan_transfer_service.check_room_rate_limit(ctx.room.id, ctx.jti, UPLOAD_RATE_LIMIT, bucket="upload")
    await lan_transfer_service.abort_room_multipart(ctx.room, upload_id, storage_key)
    return {"message": "上传已取消"}


@router.get("/public/rooms/{room_id}/files/{file_id}/download")
async def download_room_file(
    request: Request,
    file_id: UUID,
    ctx: RoomContext = Depends(get_room_context),
    db: AsyncSession = Depends(get_db),
):
    await lan_transfer_service.check_room_rate_limit(ctx.room.id, ctx.jti, DOWNLOAD_RATE_LIMIT, bucket="download")
    record = await lan_transfer_service.get_room_file(db, ctx.room.id, file_id)

    range_header = request.headers.get("range")
    stream_cm = open_object_stream(record.storage_key, range_header)
    try:
        resp = await stream_cm.__aenter__()
    except Exception as exc:
        raise ValidationFailed("文件下载失败，请稍后重试") from exc

    async def _body():
        try:
            async for chunk in resp["Body"].iter_chunks():
                yield chunk
        finally:
            await stream_cm.__aexit__(None, None, None)

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(record.filename, safe='')}",
    }
    if resp.get("ContentLength") is not None:
        headers["Content-Length"] = str(resp["ContentLength"])
    if resp.get("ContentRange"):
        headers["Content-Range"] = resp["ContentRange"]

    status_code = 206 if resp.get("ContentRange") else 200
    return StreamingResponse(
        _body(),
        status_code=status_code,
        media_type=record.mime_type,
        headers=headers,
    )


@router.delete("/public/rooms/{room_id}/files/{file_id}")
async def delete_room_file(
    file_id: UUID,
    ctx: RoomContext = Depends(get_room_context),
    db: AsyncSession = Depends(get_db),
):
    await lan_transfer_service.check_room_rate_limit(ctx.room.id, ctx.jti, DELETE_RATE_LIMIT, bucket="delete")
    await lan_transfer_service.delete_room_file(db, ctx.room, file_id)
    return {"message": "文件已删除"}
