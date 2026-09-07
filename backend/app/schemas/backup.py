from pydantic import BaseModel


class BackupPostgresInfo(BaseModel):
    file: str
    size: int = 0
    encrypted: bool = False


class BackupMinioInfo(BaseModel):
    dir: str = "minio"
    bucket: str = "cloud-drive"


class BackupManifest(BaseModel):
    timestamp: str
    created_at: str
    postgres: BackupPostgresInfo | None = None
    minio: BackupMinioInfo | None = None
    status: str = "success"


class BackupFile(BaseModel):
    name: str
    size: int
    encrypted: bool = False


class BackupInfo(BaseModel):
    timestamp: str
    created_at: str
    status: str
    encrypted: bool = False
    total_size: int = 0
    files: list[BackupFile] = []


class BackupTriggerResponse(BaseModel):
    detail: str
    timestamp: str | None = None