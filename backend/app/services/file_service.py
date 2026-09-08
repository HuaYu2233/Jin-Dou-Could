import uuid
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.file import File
from app.models.user import User
from app.core.storage import upload_fileobj, delete_file, get_object_stream

def categorize_file_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("text/"):
        return "document"
    if mime_type in (
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ):
        return "document"
    if mime_type in (
        "application/zip",
        "application/x-rar-compressed",
        "application/x-7z-compressed",
    ):
        return "archive"
    return "other"

async def create_file(
    db: AsyncSession,
    owner: User,
    filename: str,
    fileobj,
    mime_type: str,
    size: int,
    folder_id: uuid.UUID | None = None,
) -> File:
    if owner.used_storage + size > owner.storage_quota:
        raise ValueError("存储空间不足")

    file_id = uuid.uuid4()
    file = File(
        id=file_id,
        owner_id=owner.id,
        folder_id=folder_id,
        filename=filename,
        storage_key=f"{owner.id}/{file_id}",
        size=size,
        mime_type=mime_type,
        file_type=categorize_file_type(mime_type),
    )

    await run_in_threadpool(upload_fileobj, file.storage_key, fileobj, mime_type, size)

    owner.used_storage += size
    db.add(file)
    await db.commit()
    await db.refresh(file)
    return file

async def get_file(
    db: AsyncSession, file_id: uuid.UUID, owner_id: uuid.UUID
) -> File | None:
    result = await db.execute(
        select(File).where(File.id == file_id, File.owner_id == owner_id)
    )
    return result.scalar_one_or_none()

async def list_files(
    db: AsyncSession,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    file_type: str | None = None,
    folder_id: uuid.UUID | None = None,
) -> tuple[list[File], int]:
    filters = [File.owner_id == owner_id, File.deleted_at.is_(None)]
    if file_type:
        filters.append(File.file_type == file_type)
    if folder_id is not None:
        filters.append(File.folder_id == folder_id)
    else:
        filters.append(File.folder_id.is_(None))

    result = await db.execute(
        select(File)
        .where(*filters)
        .order_by(File.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    files = list(result.scalars().all())

    count_result = await db.execute(
        select(func.count()).select_from(File).where(*filters)
    )
    total = count_result.scalar_one()
    return files, total

async def search_files(
    db: AsyncSession,
    owner_id: uuid.UUID,
    keyword: str,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[File], int]:
    filters = [
        File.owner_id == owner_id,
        File.deleted_at.is_(None),
        File.filename.ilike(f"%{keyword}%"),
    ]
    result = await db.execute(
        select(File)
        .where(*filters)
        .order_by(File.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    files = list(result.scalars().all())
    count_result = await db.execute(
        select(func.count()).select_from(File).where(*filters)
    )
    total = count_result.scalar_one()
    return files, total

async def move_files(
    db: AsyncSession,
    owner_id: uuid.UUID,
    file_ids: list[uuid.UUID],
    target_folder_id: uuid.UUID | None,
) -> int:
    result = await db.execute(
        select(File).where(
            File.id.in_(file_ids),
            File.owner_id == owner_id,
            File.deleted_at.is_(None),
        )
    )
    files = list(result.scalars().all())
    for file in files:
        file.folder_id = target_folder_id
    await db.commit()
    return len(files)

async def list_trash_files(
    db: AsyncSession,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[File], int]:
    filters = [File.owner_id == owner_id, File.deleted_at.is_not(None)]

    result = await db.execute(
        select(File)
        .where(*filters)
        .order_by(File.deleted_at.desc())
        .offset(skip)
        .limit(limit)
    )
    files = list(result.scalars().all())

    count_result = await db.execute(
        select(func.count()).select_from(File).where(*filters)
    )
    total = count_result.scalar_one()
    return files, total

async def soft_delete_file(
    db: AsyncSession, file_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    file = await get_file(db, file_id, owner_id)
    if not file:
        return False
    file.deleted_at = func.now()
    await db.commit()
    return True

async def restore_file(
    db: AsyncSession, file_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(File).where(
            File.id == file_id,
            File.owner_id == owner_id,
            File.deleted_at.is_not(None),
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        return False
    file.deleted_at = None
    await db.commit()
    return True

async def purge_file(
    db: AsyncSession, file_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(File).where(
            File.id == file_id,
            File.owner_id == owner_id,
            File.deleted_at.is_not(None),
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        return False

    await run_in_threadpool(delete_file, file.storage_key)

    owner_result = await db.execute(select(User).where(User.id == owner_id))
    owner = owner_result.scalar_one()
    owner.used_storage -= file.size

    await db.delete(file)
    await db.commit()
    return True

def get_download_stream(file: File):
    from app.core.storage import stream_object
    return {
        "stream": stream_object(file.storage_key),
        "mime_type": file.mime_type,
        "filename": file.filename,
        "size": file.size,
    }