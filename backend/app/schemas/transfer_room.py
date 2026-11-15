from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoomCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=4, max_length=64)
    ttl_hours: int | None = Field(default=None, ge=1, le=168)


class RoomJoinRequest(BaseModel):
    password: str | None = Field(default=None, max_length=64)


class RoomResponse(BaseModel):
    room_id: UUID
    code: str
    join_url: str
    title: str | None = None
    has_password: bool
    max_file_size: int
    max_total_size: int
    used_size: int
    file_count: int
    expires_at: datetime
    closed_at: datetime | None = None


class RoomJoinResponse(BaseModel):
    room_token: str
    room_id: UUID
    title: str | None = None
    max_file_size: int
    max_total_size: int
    used_size: int
    file_count: int
    expires_at: datetime
    same_subnet_hint: bool = False


class RoomFileItem(BaseModel):
    id: UUID
    filename: str
    size: int
    mime_type: str
    file_type: str
    uploader: str
    created_at: datetime

    class Config:
        from_attributes = True


class RoomFileListResponse(BaseModel):
    items: list[RoomFileItem]
    used_size: int
    max_total_size: int
    file_count: int


class RoomAttachDriveFilesRequest(BaseModel):
    file_ids: list[UUID] = Field(min_length=1, max_length=50)


class RoomAttachDriveFilesResponse(BaseModel):
    items: list[RoomFileItem]
    used_size: int
    file_count: int


class RoomMultipartInitRequest(BaseModel):
    filename: str
    mime_type: str = "application/octet-stream"
    total_size: int = Field(gt=0)
    total_parts: int = Field(default=0, ge=0)


class RoomMultipartInitResponse(BaseModel):
    upload_id: str
    storage_key: str
    part_size: int
    total_parts: int


class RoomMultipartPartResponse(BaseModel):
    etag: str
    part_number: int


class RoomMultipartCompleteRequest(BaseModel):
    upload_id: str
    storage_key: str
    filename: str | None = None
    mime_type: str | None = None
    total_size: int = Field(gt=0)
    parts: list[dict] | None = None
