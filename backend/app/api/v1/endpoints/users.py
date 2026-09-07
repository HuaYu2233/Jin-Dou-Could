from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import UserResponse, ProfileUpdate, PasswordChange
from app.core.security import hash_password, verify_password
from app.core.storage import upload_file, get_object_stream
import uuid

router = APIRouter()

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

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
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=413, detail="头像大小不能超过 2MB")
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WEBP/GIF 格式")

    storage_key = f"avatars/{current_user.id}"
    upload_file(storage_key, content, mime_type, len(content))

    current_user.avatar_key = storage_key
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.get("/me/avatar")
async def get_avatar(current_user: User = Depends(get_current_user)):
    if not current_user.avatar_key:
        raise HTTPException(status_code=404, detail="未设置头像")
    stream = get_object_stream(current_user.avatar_key)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(stream, media_type="image/octet-stream")

@router.patch("/me/profile", response_model=UserResponse)
async def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.username is not None:
        if len(data.username.strip()) < 2:
            raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
        current_user.username = data.username.strip()
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.patch("/me/password", response_model=UserResponse)
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 个字符")
    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()
    await db.refresh(current_user)
    return current_user