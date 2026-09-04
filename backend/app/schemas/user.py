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
    created_at: datetime
    storage_quota: int
    used_storage: int

    class Config:
        from_attributes = True  # Pydantic v2 读取 ORM 对象