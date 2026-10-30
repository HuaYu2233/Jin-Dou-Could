from fastapi import APIRouter
from app.core.redis import ping_redis
from app.services import health_service

router = APIRouter()


@router.get("/health")
async def health():
    try:
        redis_ok = await ping_redis()
    except Exception:
        redis_ok = False
    status = "ok" if redis_ok else "degraded"
    return {"status": status}


@router.get("/health/ready")
async def health_ready():
    return await health_service.get_health()