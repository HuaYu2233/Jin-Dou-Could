from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.api.deps import get_current_admin
from app.models.user import User
from app.schemas.backup import BackupInfo, BackupTriggerResponse
from app.services import backup_service

router = APIRouter()

@router.get("", response_model=list[BackupInfo])
async def list_backups(_: User = Depends(get_current_admin)):
    return backup_service.list_backups()

@router.post("/trigger", response_model=BackupTriggerResponse)
async def trigger_backup(_: User = Depends(get_current_admin)):
    await backup_service.trigger_backup()
    return BackupTriggerResponse(detail="备份已触发", timestamp=None)

@router.get("/{timestamp}/download")
async def download_backup(
    timestamp: str,
    file: str,
    _: User = Depends(get_current_admin),
):
    path = backup_service.get_backup_file_path(timestamp, file)
    if not path:
        raise HTTPException(status_code=404, detail="备份文件不存在")
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )

@router.delete("/{timestamp}")
async def delete_backup(
    timestamp: str,
    _: User = Depends(get_current_admin),
):
    if not backup_service.delete_backup(timestamp):
        raise HTTPException(status_code=404, detail="备份不存在")
    return {"detail": "备份已删除"}