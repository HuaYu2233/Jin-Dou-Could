import asyncio
import json
import shutil
from pathlib import Path
from app.core.config import settings
from app.schemas.backup import BackupInfo, BackupFile, BackupManifest

def _backup_root() -> Path:
    root = Path(settings.BACKUP_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root

def _dir_size(path: Path) -> int:
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                pass
    return total

def _parse_manifest(dir_path: Path) -> BackupManifest | None:
    manifest_path = dir_path / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BackupManifest(**data)
    except (json.JSONDecodeError, ValueError):
        return None

def list_backups() -> list[BackupInfo]:
    root = _backup_root()
    items: list[BackupInfo] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        manifest = _parse_manifest(entry)
        files: list[BackupFile] = []
        encrypted = False
        created_at = entry.name
        status = "success"
        if manifest:
            created_at = manifest.created_at
            status = manifest.status
            if manifest.postgres:
                encrypted = manifest.postgres.encrypted
                files.append(
                    BackupFile(
                        name=manifest.postgres.file,
                        size=manifest.postgres.size,
                        encrypted=manifest.postgres.encrypted,
                    )
                )
            if manifest.minio:
                files.append(BackupFile(name=f"{manifest.minio.dir}/", size=0))
        else:
            for sub in entry.iterdir():
                if sub.is_file():
                    files.append(BackupFile(name=sub.name, size=sub.stat().st_size))
            status = "unknown"
        items.append(
            BackupInfo(
                timestamp=entry.name,
                created_at=created_at,
                status=status,
                encrypted=encrypted,
                total_size=_dir_size(entry),
                files=files,
            )
        )
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items

def get_backup_dir(timestamp: str) -> Path | None:
    if not timestamp or "/" in timestamp or "\\" in timestamp or ".." in timestamp:
        return None
    dir_path = _backup_root() / timestamp
    if not dir_path.is_dir():
        return None
    return dir_path

def get_backup_file_path(timestamp: str, filename: str) -> Path | None:
    dir_path = get_backup_dir(timestamp)
    if not dir_path:
        return None
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    file_path = dir_path / filename
    if not file_path.is_file():
        return None
    return file_path

async def trigger_backup() -> str:
    if not settings.BACKUP_TRIGGER_CMD:
        raise ValueError("未配置备份触发命令 (BACKUP_TRIGGER_CMD)")
    proc = await asyncio.create_subprocess_shell(
        settings.BACKUP_TRIGGER_CMD,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"备份命令执行失败 (exit={proc.returncode})")
    return "backup triggered"

def delete_backup(timestamp: str) -> bool:
    dir_path = get_backup_dir(timestamp)
    if not dir_path:
        return False
    shutil.rmtree(dir_path, ignore_errors=True)
    return True