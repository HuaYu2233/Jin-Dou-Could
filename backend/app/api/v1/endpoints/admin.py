from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.models.user import User
from app.api.deps import get_current_admin, invalidate_user_cache
from app.schemas.user import UserListItem, UserUpdate, AdminStats
from app.services import admin_service

router = APIRouter()


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    stats = await admin_service.get_stats(db)
    return AdminStats(**stats)


@router.get("/users", response_model=list[UserListItem])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_users(db, skip, limit)


@router.patch("/users/{user_id}", response_model=UserListItem)
async def update_user(
    user_id: str,
    data: UserUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        target = await admin_service.update_user(
            db,
            user_id,
            current_admin.id,
            username=data.username,
            storage_quota=data.storage_quota,
            is_active=data.is_active,
            is_admin=data.is_admin,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await invalidate_user_cache(target.id)
    return target


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await admin_service.delete_user(db, user_id, current_admin.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await invalidate_user_cache(user_id)
    return {"detail": "用户已删除"}