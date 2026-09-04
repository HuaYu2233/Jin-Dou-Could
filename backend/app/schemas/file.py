from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class FileResponse(BaseModel):
    id: UUID
    filename: str
    size: int
    mime_type: str
    file_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    class Config:
        from_attributes = True

class FileListResponse(BaseModel):
    items: list[FileResponse]
    total: int

class FileUploadResponse(BaseModel):
    id: UUID
    filename: str
    size: int
    mime_type: str
    file_type: str
    status: str

class FileDownloadResponse(BaseModel):
    url: str
    expires: int

class FileMoveRequest(BaseModel):
    file_ids: list[UUID]
    target_folder_id: UUID | None = None