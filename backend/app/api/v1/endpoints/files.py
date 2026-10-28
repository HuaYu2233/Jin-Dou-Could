from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, invalidate_user_cache
from app.db.base import get_db
from app.models.user import User
from app.services import file_service
from app.schemas.file import (
    FileResponse,
    FileListResponse,
    FileUploadResponse,
    FileMoveRequest,
)

router = APIRouter()


@router.post("", response_model=FileUploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    folder_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mime_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"
    declared_size = file.size

    if declared_size is not None:
        try:
            await file_service.prepare_upload(current_user, declared_size, mime_type, filename)
        except ValueError as e:
            if "过大" in str(e) or "不足" in str(e):
                raise HTTPException(status_code=413, detail=str(e))
            raise HTTPException(status_code=400, detail=str(e))

    try:
        file_record = await file_service.create_file(
            db, current_user, filename, file, mime_type, declared_size, folder_id
        )
    except ValueError as e:
        msg = str(e)
        if "过大" in msg or "不足" in msg:
            raise HTTPException(status_code=413, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    await invalidate_user_cache(current_user.id)
    return file_record


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


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = await file_service.get_file(db, file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    url = await file_service.get_download_url(file)
    return {"url": url}


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