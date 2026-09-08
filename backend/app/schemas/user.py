import re
from pydantic import BaseModel, EmailStr, field_validator
from uuid import UUID
from datetime import datetime

def _validate_password_complexity(v: str) -> str:
    if len(v) < 8:
        raise ValueError("密码至少 8 个字符")
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("密码必须包含字母")
    if not re.search(r"\d", v):
        raise ValueError("密码必须包含数字")
    return v

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


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
    security_question: str | None = None
    created_at: datetime
    storage_quota: int
    used_storage: int

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    username: str | None = None

class SecurityQuestionUpdate(BaseModel):
    security_question: str
    security_answer: str

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

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