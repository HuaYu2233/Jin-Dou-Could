import time
from fastapi import APIRouter
from sqlalchemy import text
from app.db.base import engine
from app.core.storage import minio_client
from app.core.redis import ping_redis

router = APIRouter()

@router.get("/health")
async def health():
    checks = {}
    overall = True

    pg_start = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - pg_start) * 1000, 2),
        }
    except Exception as e:
        checks["postgres"] = {"status": "error", "error": str(e)}
        overall = False

    minio_start = time.perf_counter()
    try:
        minio_client.list_buckets()
        checks["minio"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - minio_start) * 1000, 2),
        }
    except Exception as e:
        checks["minio"] = {"status": "error", "error": str(e)}
        overall = False

    redis_start = time.perf_counter()
    try:
        ok = await ping_redis()
        if ok:
            checks["redis"] = {
                "status": "ok",
                "latency_ms": round((time.perf_counter() - redis_start) * 1000, 2),
            }
        else:
            checks["redis"] = {"status": "error", "error": "ping returned false"}
            overall = False
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}
        overall = False

    return {
        "status": "ok" if overall else "degraded",
        "checks": checks,
    }
