from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # ⚠️ 【需修改】如果用 Docker，host 改为 db；本地开发保持 localhost
    DATABASE_URL: str = "postgresql+asyncpg://clouduser:cloudpass123@db:5432/clouddrive"
    
    SECRET_KEY: str = "change-me-in-production"  # ⚠️ 【需修改】生产环境必须换

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET: str = "cloud-drive"
    MINIO_DOWNLOAD_EXPIRES: int = 3600

    class Config:
        env_file = ".env"

@lru_cache
def get_settings(): 
    return Settings()

settings = get_settings()