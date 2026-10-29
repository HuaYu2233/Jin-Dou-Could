import redis.asyncio as redis
from app.core.config import settings

redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=50,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True,
)

redis_pubsub = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=10,
    socket_timeout=0,
    socket_connect_timeout=5,
    retry_on_timeout=True,
)


async def ping_redis() -> bool:
    try:
        return await redis_client.ping()
    except Exception:
        return False


async def close_redis() -> None:
    await redis_client.aclose()


async def close_redis_pubsub() -> None:
    await redis_pubsub.aclose()