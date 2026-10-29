from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_full_user, invalidate_user_cache
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import UserResponse, ProfileUpdate, PasswordChange, SecurityQuestionUpdate
from app.services import user_service

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    mime_type = file.content_type or ""
    try:
        user = await user_service.upload_avatar(db, current_user, content, mime_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await invalidate_user_cache(current_user.id)
    return user


@router.get("/me/avatar")
async def get_avatar(current_user: User = Depends(get_current_user)):
    url = await user_service.get_avatar_url(current_user)
    if not url:
        raise HTTPException(status_code=404, detail="未设置头像")
    return {"url": url}


@router.patch("/me/profile", response_model=UserResponse)
async def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await user_service.update_profile(db, current_user, data.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await invalidate_user_cache(current_user.id)
    return user


@router.patch("/me/password", response_model=UserResponse)
async def change_password(
    request: Request,
    data: PasswordChange,
    current_user: User = Depends(get_full_user),
    db: AsyncSession = Depends(get_db),
):
    access_token = request.cookies.get("access_token")
    try:
        user = await user_service.change_password(
            db, current_user, data.old_password, data.new_password, access_token
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await invalidate_user_cache(current_user.id)
    return user


@router.patch("/me/security-question", response_model=UserResponse)
async def update_security_question(
    data: SecurityQuestionUpdate,
    current_user: User = Depends(get_full_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await user_service.update_security_question(
            db, current_user, data.security_question, data.security_answer
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await invalidate_user_cache(current_user.id)
    return user