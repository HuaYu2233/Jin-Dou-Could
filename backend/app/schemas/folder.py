# /Users/zero/project/JinDou-Cloud/backend/app/schemas/folder.py
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.schemas.file import FileResponse

class FolderCreateRequest(BaseModel):
    name: str
    parent_id: UUID | None = None

class FolderRenameRequest(BaseModel):
    name: str

class FolderResponse(BaseModel):
    id: UUID
    owner_id: UUID
    parent_id: UUID | None
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FolderTrashResponse(BaseModel):
    id: UUID
    owner_id: UUID
    parent_id: UUID | None
    name: str
    deleted_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FolderBreadcrumbItem(BaseModel):
    id: str | None = None
    name: str
    path: str

class FolderListResponse(BaseModel):
    folders: list[FolderResponse]
    files: list[FileResponse]
    breadcrumbs: list[FolderBreadcrumbItem]
    total_files: int

class FolderTrashListResponse(BaseModel):
    items: list[FolderTrashResponse]
    total: int