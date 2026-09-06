from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.base import get_db
from app.models.user import User
from app.api.deps import get_current_admin
from app.schemas.user import UserListItem, UserUpdate, AdminStats

router = APIRouter()

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True)
    )
    admin_users = await db.scalar(
        select(func.count(User.id)).where(User.is_admin == True)
    )
    total_quota = await db.scalar(select(func.coalesce(func.sum(User.storage_quota), 0)))
    total_used = await db.scalar(select(func.coalesce(func.sum(User.used_storage), 0)))
    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        admin_users=admin_users,
        total_quota=total_quota,
        total_used=total_used,
    )

@router.get("/users", response_model=list[UserListItem])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.patch("/users/{user_id}", response_model=UserListItem)
async def update_user(
    user_id: str,
    data: UserUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    if target.id == current_admin.id and data.is_admin is False:
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")

    if target.is_admin and data.is_admin is False:
        admin_count = await db.scalar(
            select(func.count(User.id)).where(User.is_admin == True)
        )
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="系统至少保留一个管理员")

    if data.username is not None:
        target.username = data.username
    if data.storage_quota is not None:
        target.storage_quota = data.storage_quota
    if data.is_active is not None:
        target.is_active = data.is_active
    if data.is_admin is not None:
        target.is_admin = data.is_admin

    await db.commit()
    await db.refresh(target)
    return target

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    if target.id == current_admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    if target.is_admin:
        admin_count = await db.scalar(
            select(func.count(User.id)).where(User.is_admin == True)
        )
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="系统至少保留一个管理员")

    await db.delete(target)
    await db.commit()
    return {"detail": "用户已删除"}