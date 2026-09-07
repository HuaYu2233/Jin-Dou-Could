import redis.asyncio as redis
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def ping_redis() -> bool:
    try:
        return await redis_client.ping()
    except Exception:
        return False
