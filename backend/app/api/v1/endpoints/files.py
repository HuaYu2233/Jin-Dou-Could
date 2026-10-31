from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, invalidate_user_cache
from app.db.base import get_db
from app.models.user import User
from app.services import file_service, file_multipart
from app.schemas.file import (
    FileResponse,
    FileListResponse,
    FileUploadResponse,
    FileMoveRequest,
    MultipartInitRequest,
    MultipartInitResponse,
    MultipartCompleteRequest,
)
from app.core.ws_manager import ws_manager
from app.core.config import settings
from app.core.redis import redis_client

router = APIRouter()


async def _acquire_concurrent_slot(user_id: UUID, slot_type: str, max_slots: int) -> str:
    key = f"concurrent:{slot_type}:{user_id}"
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, 3600)
    if current > max_slots:
        await redis_client.decr(key)
        raise HTTPException(
            status_code=429,
            detail=f"并发{slot_type}数超过限制（最多 {max_slots} 个），请稍后再试",
        )
    return key


async def _release_concurrent_slot(key: str) -> None:
    await redis_client.decr(key)


@router.post("", response_model=FileUploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    folder_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slot_key = await _acquire_concurrent_slot(current_user.id, "upload", settings.MAX_CONCURRENT_UPLOADS)
    try:
        mime_type = file.content_type or "application/octet-stream"
        filename = file.filename or "unknown"
        declared_size = file.size

        await file.seek(0)
        fileobj = file.file
        if hasattr(fileobj, "seek"):
            fileobj.seek(0)

        if declared_size is not None:
            await file_service.prepare_upload(current_user, declared_size, mime_type, filename)

        file_record = await file_service.create_file(
            db, current_user, filename, fileobj, mime_type, declared_size, folder_id
        )
        await invalidate_user_cache(current_user.id)

        await ws_manager.send_to_user(str(current_user.id), "upload:complete", {
            "file_id": str(file_record.id),
            "filename": file_record.filename,
            "size": file_record.size,
            "file_type": file_record.file_type,
        })
        await ws_manager.send_to_user(str(current_user.id), "storage:changed", {
            "used_storage": current_user.used_storage,
            "storage_quota": current_user.storage_quota,
        })

        return file_record
    finally:
        await _release_concurrent_slot(slot_key)


@router.get("", response_model=FileListResponse)
async def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    file_type: str | None = Query(None),
    folder_id: UUID | None = Query(None),
    cursor: str | None = Query(None, description="游标分页：上一页最后一条的 created_at ISO 格式"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files, total, next_cursor = await file_service.list_files(db, current_user.id, skip, limit, file_type, folder_id, cursor)
    return {"items": files, "total": total, "next_cursor": next_cursor}


@router.get("/search", response_model=FileListResponse)
async def search_files(
    keyword: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, description="游标分页游标"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files, total, next_cursor = await file_service.search_files(db, current_user.id, keyword, skip, limit, cursor)
    return {"items": files, "total": total, "next_cursor": next_cursor}


@router.post("/move")
async def move_files(
    body: FileMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    moved = await file_service.move_files(db, current_user.id, body.file_ids, body.target_folder_id)
    return {"message": f"已移动 {moved} 个文件", "moved": moved}


@router.get("/trash", response_model=FileListResponse)
async def list_trash(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, description="游标分页游标"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files, total, next_cursor = await file_service.list_trash_files(db, current_user.id, skip, limit, cursor)
    return {"items": files, "total": total, "next_cursor": next_cursor}


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = await file_service.get_file(db, file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    return file


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = await file_service.get_file(db, file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    url = await file_service.get_preview_url(file)
    return {"url": url}


@router.get("/{file_id}/thumbnail")
async def get_thumbnail(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = await file_service.get_file(db, file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    if file.thumbnail_key:
        url = await file_service.get_thumbnail_url(file.thumbnail_key)
        return {"url": url, "has_thumbnail": True}
    url = await file_service.get_preview_url(file)
    return {"url": url, "has_thumbnail": False}


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slot_key = await _acquire_concurrent_slot(current_user.id, "download", settings.MAX_CONCURRENT_DOWNLOADS)
    try:
        file = await file_service.get_file(db, file_id, current_user.id)
        if not file:
            raise HTTPException(status_code=404, detail="文件不存在")
        url = await file_service.get_download_url(file)
        return {"url": url}
    finally:
        await _release_concurrent_slot(slot_key)


@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await file_service.soft_delete_file(db, file_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文件不存在")
    await invalidate_user_cache(current_user.id)

    await ws_manager.send_to_user(str(current_user.id), "storage:changed", {
        "used_storage": current_user.used_storage,
        "storage_quota": current_user.storage_quota,
    })

    return {"message": "已移入回收站"}


@router.post("/{file_id}/restore")
async def restore_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restored = await file_service.restore_file(db, file_id, current_user.id)
    if not restored:
        raise HTTPException(status_code=404, detail="文件不存在或不在回收站")
    await invalidate_user_cache(current_user.id)
    return {"message": "恢复成功"}


@router.delete("/{file_id}/purge")
async def purge_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    purged = await file_service.purge_file(db, file_id, current_user.id)
    if not purged:
        raise HTTPException(status_code=404, detail="文件不存在或不在回收站")
    await invalidate_user_cache(current_user.id)
    return {"message": "已彻底删除"}


@router.post("/multipart/init", response_model=MultipartInitResponse)
async def multipart_init(
    body: MultipartInitRequest,
    current_user: User = Depends(get_current_user),
):
    await _acquire_concurrent_slot(current_user.id, "upload", settings.MAX_CONCURRENT_UPLOADS)

    await file_service.prepare_upload(current_user, body.total_size, body.mime_type, body.filename)

    part_size = settings.UPLOAD_PART_SIZE
    total_parts = (body.total_size + part_size - 1) // part_size

    result = await file_multipart.init_multipart_upload(
        owner=current_user,
        filename=body.filename,
        mime_type=body.mime_type,
        total_size=body.total_size,
        folder_id=body.folder_id,
        part_size=part_size,
        total_parts=total_parts,
    )
    return MultipartInitResponse(
        upload_id=result["upload_id"],
        storage_key=result["storage_key"],
        part_size=part_size,
        total_parts=total_parts,
    )


@router.post("/multipart/part")
async def multipart_upload_part(
    storage_key: str = Query(...),
    upload_id: str = Query(...),
    part_number: int = Query(..., ge=1),
    part: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    data = await part.read()
    etag = await file_multipart.upload_multipart_part(
        storage_key=storage_key,
        upload_id=upload_id,
        part_number=part_number,
        data=data,
        owner_id=current_user.id,
    )
    return {"part_number": part_number, "etag": etag}


@router.post("/multipart/complete", response_model=FileUploadResponse)
async def multipart_complete(
    body: MultipartCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parts = [{"PartNumber": p.part_number, "ETag": p.etag} for p in body.parts]
    file_record = await file_multipart.complete_multipart_upload(
        db=db,
        owner=current_user,
        upload_id=body.upload_id,
        storage_key=body.storage_key,
        filename=body.filename,
        mime_type=body.mime_type,
        total_size=body.total_size,
        folder_id=body.folder_id,
        parts=parts,
    )
    await invalidate_user_cache(current_user.id)

    await ws_manager.send_to_user(str(current_user.id), "upload:complete", {
        "file_id": str(file_record.id),
        "filename": file_record.filename,
        "size": file_record.size,
        "file_type": file_record.file_type,
    })
    await ws_manager.send_to_user(str(current_user.id), "storage:changed", {
        "used_storage": current_user.used_storage,
        "storage_quota": current_user.storage_quota,
    })

    return file_record


@router.post("/multipart/abort")
async def multipart_abort(
    storage_key: str = Query(...),
    upload_id: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    await file_multipart.abort_multipart_upload(
        storage_key=storage_key,
        upload_id=upload_id,
        owner_id=current_user.id,
    )
    return {"message": "上传已取消"}