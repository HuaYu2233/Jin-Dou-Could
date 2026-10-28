# /Users/zero/project/JinDou-Cloud/backend/app/api/v1/endpoints/folders.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, invalidate_user_cache
from app.db.base import get_db
from app.models.user import User
from app.services import folder_service
from app.schemas.folder import (
    FolderCreateRequest,
    FolderRenameRequest,
    FolderResponse,
    FolderListResponse,
    FolderTrashListResponse,
    FolderTrashResponse,
)
from app.schemas.file import FileResponse

router = APIRouter()

@router.post("", response_model=FolderResponse)
async def create_folder(
    body: FolderCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        folder = await folder_service.create_folder(
            db, current_user.id, body.name, body.parent_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return folder

@router.get("", response_model=FolderListResponse)
async def list_folder_contents(
    folder_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await folder_service.list_folder_contents(
        db, current_user.id, folder_id, skip, limit
    )
    return {
        "folders": [FolderResponse.model_validate(f) for f in result["folders"]],
        "files": [FileResponse.model_validate(f) for f in result["files"]],
        "breadcrumbs": result["breadcrumbs"],
        "total_files": result["total_files"],
    }

@router.put("/{folder_id}", response_model=FolderResponse)
async def rename_folder(
    folder_id: UUID,
    body: FolderRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    folder = await folder_service.rename_folder(db, folder_id, current_user.id, body.name)
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    return folder

@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await folder_service.delete_folder(db, folder_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    await invalidate_user_cache(current_user.id)
    return {"message": "文件夹已移入回收站"}

@router.get("/trash", response_model=FolderTrashListResponse)
async def list_trash_folders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    folders, total = await folder_service.list_trash_folders(
        db, current_user.id, skip, limit
    )
    return {
        "items": [FolderTrashResponse.model_validate(f) for f in folders],
        "total": total,
    }

@router.post("/{folder_id}/restore")
async def restore_folder(
    folder_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restored = await folder_service.restore_folder(db, folder_id, current_user.id)
    if not restored:
        raise HTTPException(status_code=404, detail="文件夹不存在或不在回收站")
    await invalidate_user_cache(current_user.id)
    return {"message": "文件夹已恢复"}

@router.delete("/{folder_id}/purge")
async def purge_folder(
    folder_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    purged = await folder_service.purge_folder(db, folder_id, current_user.id)
    if not purged:
        raise HTTPException(status_code=404, detail="文件夹不存在或不在回收站")
    await invalidate_user_cache(current_user.id)
    return {"message": "文件夹已彻底删除"}