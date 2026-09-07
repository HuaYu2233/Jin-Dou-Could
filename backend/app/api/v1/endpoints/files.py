from uuid import UUID
from urllib.parse import quote
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.services import file_service
from app.core.config import settings
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
    declared = request.headers.get("content-length")
    if declared and int(declared) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="文件过大，单文件上限 100MB")

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，单文件上限 100MB")
        chunks.append(chunk)
    content = b"".join(chunks)
    mime_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    if current_user.used_storage + len(content) > current_user.storage_quota:
        raise HTTPException(
            status_code=413,
            detail="存储空间不足，请联系管理员扩容",
        )

    try:
        file_record = await file_service.create_file(
            db, current_user, filename, content, mime_type, folder_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return file_record

@router.get("", response_model=FileListResponse)
async def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    file_type: str | None = Query(None),
    folder_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files, total = await file_service.list_files(db, current_user.id, skip, limit, file_type, folder_id)
    return {"items": files, "total": total}

@router.get("/search", response_model=FileListResponse)
async def search_files(
    keyword: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files, total = await file_service.search_files(db, current_user.id, keyword, skip, limit)
    return {"items": files, "total": total}

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files, total = await file_service.list_trash_files(db, current_user.id, skip, limit)
    return {"items": files, "total": total}

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
    info = file_service.get_download_stream(file)
    headers = {
        "Content-Length": str(info["size"]),
        "Access-Control-Allow-Origin": "http://localhost:3000",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Credentials": "true",
    }
    return StreamingResponse(
        content=info["stream"],
        media_type=info["mime_type"],
        headers=headers,
    )

@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = await file_service.get_file(db, file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    info = file_service.get_download_stream(file)
    filename = info["filename"]
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    headers = {
        "Content-Disposition": disposition,
        "Content-Length": str(info["size"]),
        "Access-Control-Allow-Origin": "http://localhost:3000",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Credentials": "true",
    }
    return StreamingResponse(
        content=info["stream"],
        media_type=info["mime_type"],
        headers=headers,
    )

@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await file_service.soft_delete_file(db, file_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文件不存在")
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
    return {"message": "已彻底删除"}