from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://clouduser:cloudpass123@db:5432/clouddrive"
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_PASSWORD: str = ""
    
    SECRET_KEY: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    ENVIRONMENT: str = "development"
    MAX_UPLOAD_SIZE: int = 104857600

    BACKEND_WORKERS: int = 4
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    SECURITY_HEADERS_ENABLED: bool = True
    HTTPS_REDIRECT: bool = False

    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300
    LOGIN_RATE_LIMIT_LOCK_SECONDS: int = 900

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "cloud-drive"
    MINIO_SECURE: bool = False
    MINIO_DOWNLOAD_EXPIRES: int = 3600
    UPLOAD_CHUNK_SIZE: int = 8 * 1024 * 1024
    MULTIPART_THRESHOLD: int = 16 * 1024 * 1024

    CORS_ORIGINS: str = "http://localhost:3000"

    DEFAULT_STORAGE_QUOTA: int = 1073741824  # 1GB
    MAX_USERS: int = 0  # 0 = 不限制
    ADMIN_EMAIL: str = ""  # 用此邮箱注册的首个用户自动成为管理员

    # 备份
    BACKUP_DIR: str = "/backups"
    BACKUP_TRIGGER_CMD: str = ""

    # 找回密码
    RESET_PASSWORD_SMTP_HOST: str = ""
    RESET_PASSWORD_SMTP_PORT: int = 465
    RESET_PASSWORD_SMTP_USER: str = ""
    RESET_PASSWORD_SMTP_PASSWORD: str = ""
    RESET_PASSWORD_FROM_EMAIL: str = ""
    RESET_PASSWORD_FROM_NAME: str = "金斗云盘"
    RESET_PASSWORD_CODE_EXPIRE_SECONDS: int = 600
    RESET_PASSWORD_CODE_LENGTH: int = 6

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_RETENTION_DAYS: int = 30

    # 告警
    ALERT_ENABLED: bool = False
    ALERT_MIN_LEVEL: str = "ERROR"
    ALERT_COOLDOWN_SECONDS: int = 300
    ALERT_WEBHOOK_URL: str = ""
    ALERT_WEBHOOK_TYPE: str = "generic"
    ALERT_EMAIL_ENABLED: bool = False
    ALERT_EMAIL_SMTP_HOST: str = ""
    ALERT_EMAIL_SMTP_PORT: int = 587
    ALERT_EMAIL_SMTP_USER: str = ""
    ALERT_EMAIL_SMTP_PASSWORD: str = ""
    ALERT_EMAIL_FROM: str = ""
    ALERT_EMAIL_TO: str = ""
    ALERT_EMAIL_USE_TLS: bool = True

    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND_URL: str = ""
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # CSRF
    CSRF_ENABLED: bool = True

    # WebSocket
    WS_PUBSUB_ENABLED: bool = True

    # Prometheus
    PROMETHEUS_ENABLED: bool = False

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        weak = {
            "change-me-in-production",
            "your-super-secret-key-change-this-in-production",
            "change-this-to-a-random-secret-key",
        }
        if not v or v in weak or len(v) < 32:
            raise ValueError("SECRET_KEY 必须设置为不少于 32 字符的强随机值")
        return v

    class Config:
        env_file = ".env"

@lru_cache
def get_settings(): 
    return Settings()

settings = get_settings()