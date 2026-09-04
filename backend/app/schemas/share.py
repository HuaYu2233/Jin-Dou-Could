
# /Users/zero/project/JinDou-Cloud/backend/app/schemas/share.py
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ShareCreateRequest(BaseModel):
    expires_days: int | None = None

class ShareCreateResponse(BaseModel):
    id: UUID
    share_token: str
    extract_code: str
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True

class ShareItemResponse(BaseModel):
    id: UUID
    file_id: UUID
    share_token: str
    extract_code: str
    expires_at: datetime | None
    views: int
    created_at: datetime
    filename: str
    file_size: int

    class Config:
        from_attributes = True

class ShareListResponse(BaseModel):
    items: list[ShareItemResponse]
    total: int

class ShareInfoResponse(BaseModel):
    share_token: str
    filename: str
    file_size: int
    file_type: str
    has_code: bool
    expires_at: datetime | None

class ShareVerifyRequest(BaseModel):
    extract_code: str

class ShareVerifyResponse(BaseModel):
    share_token: str
    filename: str
    file_size: int
    file_type: str