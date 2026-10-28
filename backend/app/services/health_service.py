import asyncio
import time
from sqlalchemy import text
from app.db.base import engine
from app.core.storage import get_s3_client
from app.core.redis import ping_redis


async def check_postgres() -> dict:
    start = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_minio() -> dict:
    start = time.perf_counter()
    try:
        async with get_s3_client() as client:
            await client.list_buckets()
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_redis() -> dict:
    start = time.perf_counter()
    try:
        ok = await ping_redis()
        if ok:
            return {
                "status": "ok",
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
        return {"status": "error", "error": "ping returned false"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_health() -> dict:
    pg_result, minio_result, redis_result = await asyncio.gather(
        check_postgres(),
        check_minio(),
        check_redis(),
    )

    checks = {
        "postgres": pg_result,
        "minio": minio_result,
        "redis": redis_result,
    }

    overall = all(c["status"] == "ok" for c in checks.values())

    return {
        "status": "ok" if overall else "degraded",
        "checks": checks,
    }