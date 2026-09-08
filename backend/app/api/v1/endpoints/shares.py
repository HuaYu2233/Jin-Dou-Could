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
from app.core.storage import get_presigned_download_url
from app.core.config import settings
from app.core.redis import redis_client

SHARE_VERIFY_MAX_ATTEMPTS = 5
SHARE_VERIFY_LOCK_SECONDS = 900
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
    lock_key = f"share_lock:{token}"
    if await redis_client.exists(lock_key):
        ttl = await redis_client.ttl(lock_key)
        raise HTTPException(
            status_code=429,
            detail=f"提取码错误次数过多，请 {max(ttl, 1)} 秒后再试",
        )
    info = await share_service.verify_share(db, token, body.extract_code)
    if not info:
        attempts_key = f"share_verify:{token}"
        attempts = await redis_client.incr(attempts_key)
        if attempts == 1:
            await redis_client.expire(attempts_key, SHARE_VERIFY_LOCK_SECONDS)
        if attempts >= SHARE_VERIFY_MAX_ATTEMPTS:
            await redis_client.setex(lock_key, SHARE_VERIFY_LOCK_SECONDS, "1")
            await redis_client.delete(attempts_key)
        raise HTTPException(status_code=403, detail="提取码错误或分享已过期")
    await redis_client.delete(f"share_verify:{token}")
    return info

@router.get("/public/{token}/download")
async def download_shared_file(
    token: str,
    extract_code: str,
    db: AsyncSession = Depends(get_db),
):
    lock_key = f"share_lock:{token}"
    if await redis_client.exists(lock_key):
        ttl = await redis_client.ttl(lock_key)
        raise HTTPException(
            status_code=429,
            detail=f"提取码错误次数过多，请 {max(ttl, 1)} 秒后再试",
        )
    info = await share_service.verify_share(db, token, extract_code)
    if not info:
        attempts_key = f"share_verify:{token}"
        attempts = await redis_client.incr(attempts_key)
        if attempts == 1:
            await redis_client.expire(attempts_key, SHARE_VERIFY_LOCK_SECONDS)
        if attempts >= SHARE_VERIFY_MAX_ATTEMPTS:
            await redis_client.setex(lock_key, SHARE_VERIFY_LOCK_SECONDS, "1")
            await redis_client.delete(attempts_key)
        raise HTTPException(status_code=403, detail="提取码错误或分享已过期")
    await redis_client.delete(f"share_verify:{token}")

    file_result = await db.execute(
        select(File).where(File.storage_key == info["storage_key"])
    )
    file = file_result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")

    url = get_presigned_download_url(
        file.storage_key, settings.MINIO_DOWNLOAD_EXPIRES, file.filename
    )
    return {"url": url}