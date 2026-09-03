from uuid import UUID
from urllib.parse import quote
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.services import file_service
from app.schemas.file import (
    FileResponse,
    FileListResponse,
    FileUploadResponse,
)

router = APIRouter()

@router.post("", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"
    try:
        file_record = await file_service.create_file(
            db, current_user, filename, content, mime_type
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return file_record

@router.get("", response_model=FileListResponse)
async def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    file_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files, total = await file_service.list_files(db, current_user.id, skip, limit, file_type)
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
    deleted = await file_service.delete_file_record(db, file_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {"message": "删除成功"}