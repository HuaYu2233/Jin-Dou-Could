
# /Users/zero/project/JinDou-Cloud/backend/app/services/folder_service.py
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.folder import Folder
from app.models.file import File

async def create_folder(
    db: AsyncSession,
    owner_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None = None,
) -> Folder:
    if parent_id is not None:
        parent = await _get_folder(db, parent_id, owner_id)
        if not parent:
            raise ValueError("父文件夹不存在")

    existing = await db.execute(
        select(Folder).where(
            Folder.owner_id == owner_id,
            Folder.parent_id == parent_id if parent_id is not None else Folder.parent_id.is_(None),
            Folder.name == name,
            Folder.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("同名文件夹已存在")

    folder = Folder(
        id=uuid.uuid4(),
        owner_id=owner_id,
        parent_id=parent_id,
        name=name,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder

async def _get_folder(
    db: AsyncSession, folder_id: uuid.UUID, owner_id: uuid.UUID
) -> Folder | None:
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.owner_id == owner_id,
            Folder.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()

async def rename_folder(
    db: AsyncSession,
    folder_id: uuid.UUID,
    owner_id: uuid.UUID,
    name: str,
) -> Folder | None:
    folder = await _get_folder(db, folder_id, owner_id)
    if not folder:
        return None
    folder.name = name
    await db.commit()
    await db.refresh(folder)
    return folder

async def delete_folder(
    db: AsyncSession, folder_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    folder = await _get_folder(db, folder_id, owner_id)
    if not folder:
        return False
    folder.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return True

async def list_folder_contents(
    db: AsyncSession,
    owner_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> dict:
    folders_result = await db.execute(
        select(Folder).where(
            Folder.owner_id == owner_id,
            Folder.parent_id == folder_id if folder_id is not None else Folder.parent_id.is_(None),
            Folder.deleted_at.is_(None),
        ).order_by(Folder.name.asc())
    )
    folders = folders_result.scalars().all()

    files_result = await db.execute(
        select(File).where(
            File.owner_id == owner_id,
            File.folder_id == folder_id if folder_id is not None else File.folder_id.is_(None),
            File.deleted_at.is_(None),
        ).order_by(File.created_at.desc()).offset(skip).limit(limit)
    )
    files = files_result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(File).where(
            File.owner_id == owner_id,
            File.folder_id == folder_id if folder_id is not None else File.folder_id.is_(None),
            File.deleted_at.is_(None),
        )
    )
    total_files = count_result.scalar_one()

    breadcrumbs = await _get_breadcrumbs(db, folder_id, owner_id)

    return {
        "folders": folders,
        "files": files,
        "breadcrumbs": breadcrumbs,
        "total_files": total_files,
    }

async def _get_breadcrumbs(
    db: AsyncSession, folder_id: uuid.UUID | None, owner_id: uuid.UUID
) -> list:
    breadcrumbs = [{"id": None, "name": "全部文件", "path": "/"}]
    if folder_id is None:
        return breadcrumbs

    current_id = folder_id
    chain = []
    while current_id is not None:
        result = await db.execute(
            select(Folder).where(Folder.id == current_id, Folder.owner_id == owner_id, Folder.deleted_at.is_(None))
        )
        folder = result.scalar_one_or_none()
        if not folder:
            break
        chain.append(folder)
        current_id = folder.parent_id

    chain.reverse()
    for folder in chain:
        breadcrumbs.append({"id": str(folder.id), "name": folder.name, "path": f"/folder/{folder.id}"})
    return breadcrumbs

async def get_folder_path(
    db: AsyncSession, folder_id: uuid.UUID | None, owner_id: uuid.UUID
) -> str:
    if folder_id is None:
        return "/"
    breadcrumbs = await _get_breadcrumbs(db, folder_id, owner_id)
    return "/".join(b["name"] for b in breadcrumbs[1:])