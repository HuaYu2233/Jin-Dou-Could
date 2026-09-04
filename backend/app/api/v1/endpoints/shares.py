# /Users/zero/project/JinDou-Cloud/backend/app/api/v1/endpoints/shares.py
from uuid import UUID
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.file import File
from app.services import share_service
from app.services import file_service
from app.schemas.share import (
    ShareCreateRequest,
    ShareCreateResponse,
    ShareListResponse,
    ShareInfoResponse,
    ShareVerifyRequest,
    ShareVerifyResponse,
)

router = APIRouter()

@router.post("/{file_id}", response_model=ShareCreateResponse)
async def create_share(
    file_id: UUID,
    body: ShareCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        share = await share_service.create_share(
            db, file_id, current_user.id, body.expires_days
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return share

@router.get("", response_model=ShareListResponse)
async def list_shares(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = await share_service.list_shares(db, current_user.id, skip, limit)
    return {"items": items, "total": total}

@router.delete("/{share_id}")
async def delete_share(
    share_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await share_service.delete_share(db, share_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="分享不存在")
    return {"message": "已取消分享"}

@router.get("/public/{token}", response_model=ShareInfoResponse)
async def get_share_info(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    info = await share_service.get_share_info(db, token)
    if not info:
        raise HTTPException(status_code=404, detail="分享不存在或已过期")
    return info

@router.post("/public/{token}/verify", response_model=ShareVerifyResponse)
async def verify_share(
    token: str,
    body: ShareVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    info = await share_service.verify_share(db, token, body.extract_code)
    if not info:
        raise HTTPException(status_code=403, detail="提取码错误或分享已过期")
    return info

@router.get("/public/{token}/download")
async def download_shared_file(
    token: str,
    extract_code: str,
    db: AsyncSession = Depends(get_db),
):
    info = await share_service.verify_share(db, token, extract_code)
    if not info:
        raise HTTPException(status_code=403, detail="提取码错误或分享已过期")

    file_result = await db.execute(
        select(File).where(File.storage_key == info["storage_key"])
    )
    file = file_result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")

    stream_info = file_service.get_download_stream(file)
    filename = stream_info["filename"]
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    headers = {
        "Content-Disposition": disposition,
        "Content-Length": str(stream_info["size"]),
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
    }
    return StreamingResponse(
        content=stream_info["stream"],
        media_type=stream_info["mime_type"],
        headers=headers,
    )