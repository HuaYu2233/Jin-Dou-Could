from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.services import share_service
from app.schemas.share import (
    ShareCreateRequest,
    ShareCreateResponse,
    ShareListResponse,
    ShareInfoResponse,
    ShareVerifyRequest,
    ShareVerifyResponse,
)
from app.core.ws_manager import ws_manager

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

    await ws_manager.send_to_user(str(current_user.id), "share:created", {
        "share_id": str(share.id),
        "file_id": str(file_id),
        "share_token": share.share_token,
        "extract_code": share.extract_code,
    })

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
    try:
        info = await share_service.verify_share_with_rate_limit(db, token, body.extract_code)
    except ValueError as e:
        if "过多" in str(e):
            raise HTTPException(status_code=429, detail=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    return info


@router.get("/public/{token}/download")
async def download_shared_file(
    token: str,
    extract_code: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        url = await share_service.download_shared_file(db, token, extract_code)
    except ValueError as e:
        if "过多" in str(e):
            raise HTTPException(status_code=429, detail=str(e))
        if "文件不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    return {"url": url}