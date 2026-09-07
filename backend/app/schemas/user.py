from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str  # 明文入，后端哈希


# 新增：登录专用
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    is_active: bool
    is_admin: bool
    avatar_key: str | None = None
    created_at: datetime
    storage_quota: int
    used_storage: int

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    username: str | None = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class UserUpdate(BaseModel):
    username: str | None = None
    storage_quota: int | None = None
    is_active: bool | None = None
    is_admin: bool | None = None

class UserListItem(BaseModel):
    id: UUID
    email: str
    username: str
    is_active: bool
    is_admin: bool
    storage_quota: int
    used_storage: int
    created_at: datetime

    class Config:
        from_attributes = True

class AdminStats(BaseModel):
    total_users: int
    active_users: int
    admin_users: int
    total_quota: int
    total_used: int