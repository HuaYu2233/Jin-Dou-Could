# /Users/zero/project/JinDou-Cloud/backend/app/services/folder_service.py
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from app.models.folder import Folder
from app.models.file import File
from app.models.user import User
from app.core.storage import delete_file as s3_delete_file


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


async def _get_trashed_folder(
    db: AsyncSession, folder_id: uuid.UUID, owner_id: uuid.UUID
) -> Folder | None:
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.owner_id == owner_id,
            Folder.deleted_at.is_not(None),
        )
    )
    return result.scalar_one_or_none()


async def _collect_subfolder_ids(
    db: AsyncSession, folder_id: uuid.UUID, owner_id: uuid.UUID
) -> list[uuid.UUID]:
    cte = (
        select(Folder.id, Folder.parent_id)
        .where(Folder.id == folder_id, Folder.owner_id == owner_id)
        .cte(name="subfolder_tree", recursive=True)
    )
    children = (
        select(Folder.id, Folder.parent_id)
        .where(Folder.parent_id == cte.c.id, Folder.owner_id == owner_id)
    )
    cte = cte.union_all(children)
    result = await db.execute(select(cte.c.id))
    return [row[0] for row in result.all()]


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

    now = datetime.now(timezone.utc)
    all_folder_ids = await _collect_subfolder_ids(db, folder_id, owner_id)

    await db.execute(
        update(Folder)
        .where(Folder.id.in_(all_folder_ids), Folder.deleted_at.is_(None))
        .values(deleted_at=now)
    )
    await db.execute(
        update(File)
        .where(File.folder_id.in_(all_folder_ids), File.deleted_at.is_(None))
        .values(deleted_at=now)
    )

    await db.commit()
    return True


async def list_trash_folders(
    db: AsyncSession,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Folder], int]:
    count_result = await db.execute(
        select(func.count()).select_from(Folder).where(
            Folder.owner_id == owner_id,
            Folder.deleted_at.is_not(None),
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Folder)
        .where(Folder.owner_id == owner_id, Folder.deleted_at.is_not(None))
        .order_by(Folder.deleted_at.desc())
        .offset(skip)
        .limit(limit)
    )
    folders = list(result.scalars().all())
    return folders, total


async def restore_folder(
    db: AsyncSession, folder_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    folder = await _get_trashed_folder(db, folder_id, owner_id)
    if not folder:
        return False

    if folder.parent_id is not None:
        parent_result = await db.execute(
            select(Folder).where(
                Folder.id == folder.parent_id,
                Folder.owner_id == owner_id,
                Folder.deleted_at.is_(None),
            )
        )
        if parent_result.scalar_one_or_none() is None:
            return False

    all_folder_ids = await _collect_subfolder_ids(db, folder_id, owner_id)

    await db.execute(
        update(Folder)
        .where(Folder.id.in_(all_folder_ids), Folder.deleted_at.is_not(None))
        .values(deleted_at=None)
    )
    await db.execute(
        update(File)
        .where(File.folder_id.in_(all_folder_ids), File.deleted_at.is_not(None))
        .values(deleted_at=None)
    )

    await db.commit()
    return True


async def purge_folder(
    db: AsyncSession, folder_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    folder = await _get_trashed_folder(db, folder_id, owner_id)
    if not folder:
        return False

    all_folder_ids = await _collect_subfolder_ids(db, folder_id, owner_id)

    files_result = await db.execute(
        select(File).where(
            File.folder_id.in_(all_folder_ids),
            File.deleted_at.is_not(None),
        )
    )
    files_to_purge = list(files_result.scalars().all())

    total_size = 0
    for file in files_to_purge:
        try:
            await s3_delete_file(file.storage_key)
        except Exception:
            pass
        total_size += file.size

    for file in files_to_purge:
        await db.delete(file)

    subfolders_result = await db.execute(
        select(Folder).where(
            Folder.id.in_(all_folder_ids),
            Folder.id != folder_id,
        )
    )
    for subfolder in subfolders_result.scalars().all():
        await db.delete(subfolder)

    await db.delete(folder)

    if total_size > 0:
        owner_result = await db.execute(select(User).where(User.id == owner_id))
        owner = owner_result.scalar_one_or_none()
        if owner:
            owner.used_storage = max(0, owner.used_storage - total_size)

    await db.commit()
    return True


async def list_folder_contents(
    db: AsyncSession,
    owner_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> dict:
    folder_filter = (
        Folder.parent_id == folder_id if folder_id is not None else Folder.parent_id.is_(None)
    )
    file_filter = (
        File.folder_id == folder_id if folder_id is not None else File.folder_id.is_(None)
    )

    folders_result = await db.execute(
        select(Folder).where(
            Folder.owner_id == owner_id,
            folder_filter,
            Folder.deleted_at.is_(None),
        ).order_by(Folder.name.asc())
    )
    folders = folders_result.scalars().all()

    files_query = (
        select(File, func.count().over().label("total"))
        .where(
            File.owner_id == owner_id,
            file_filter,
            File.deleted_at.is_(None),
        )
        .order_by(File.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    files_result = await db.execute(files_query)
    rows = files_result.all()
    total_files = rows[0].total if rows else 0
    files = [row[0] for row in rows]

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