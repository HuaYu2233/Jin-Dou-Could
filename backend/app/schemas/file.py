from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FileResponse(BaseModel):
    id: UUID
    filename: str
    size: int
    mime_type: str
    file_type: str
    status: str
    thumbnail_key: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    items: list[FileResponse]
    total: int
    next_cursor: str | None = None


class FileUploadResponse(BaseModel):
    id: UUID
    filename: str
    size: int
    mime_type: str
    file_type: str
    status: str


class FileMoveRequest(BaseModel):
    file_ids: list[UUID]
    target_folder_id: UUID | None = None


class MultipartInitRequest(BaseModel):
    filename: str
    mime_type: str = "application/octet-stream"
    total_size: int
    folder_id: UUID | None = None


class MultipartInitResponse(BaseModel):
    upload_id: str
    storage_key: str
    part_size: int
    total_parts: int


class MultipartPartRequest(BaseModel):
    part_number: int
    etag: str


class MultipartCompleteRequest(BaseModel):
    upload_id: str
    storage_key: str
    filename: str
    mime_type: str
    total_size: int
    folder_id: UUID | None = None
    parts: list[MultipartPartRequest]
