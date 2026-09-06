from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://clouduser:cloudpass123@db:5432/clouddrive"
    REDIS_URL: str = "redis://redis:6379/0"
    
    SECRET_KEY: str = "change-me-in-production"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET: str = "cloud-drive"
    MINIO_DOWNLOAD_EXPIRES: int = 3600

    CORS_ORIGINS: str = "http://localhost:3000"

    DEFAULT_STORAGE_QUOTA: int = 1073741824  # 1GB
    MAX_USERS: int = 0  # 0 = 不限制
    ADMIN_EMAIL: str = ""  # 用此邮箱注册的首个用户自动成为管理员

    class Config:
        env_file = ".env"

@lru_cache
def get_settings(): 
    return Settings()

settings = get_settings()