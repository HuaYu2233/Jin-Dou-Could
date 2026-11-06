from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_pool_size = settings.DB_POOL_SIZE
_max_overflow = settings.DB_MAX_OVERFLOW

if settings.ENVIRONMENT == "production":
    _pool_size = max(_pool_size, 5)
    _max_overflow = max(_max_overflow, 3)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
    pool_recycle=settings.DB_POOL_RECYCLE,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
