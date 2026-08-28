from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # ⚠️ 【需修改】如果用 Docker，host 改为 db；本地开发保持 localhost
    DATABASE_URL: str = "postgresql+asyncpg://clouduser:cloudpass123@db:5432/clouddrive"
    
    SECRET_KEY: str = "change-me-in-production"  # ⚠️ 【需修改】生产环境必须换

    class Config:
        env_file = ".env"

@lru_cache
def get_settings(): 
    return Settings()

settings = get_settings()