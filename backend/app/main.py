from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from app.api.v1.api import api_router
from app.api.v1.endpoints import health
from app.core.storage import init_s3_clients, ensure_bucket, close_s3_clients
from app.core.redis import close_redis, close_redis_pubsub
from app.core.ws_manager import ws_manager
from app.db.base import dispose_engine
from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.csrf import CSRFMiddleware
from loguru import logger


def _check_production_security() -> None:
    errors = []

    if settings.ALGORITHM == "HS256":
        errors.append("JWT 使用 HS256 对称算法，生产环境建议迁移到 RS256（设置 ALGORITHM=RS256 + JWT_PRIVATE_KEY_PATH + JWT_PUBLIC_KEY_PATH）")

    if settings.ALGORITHM == "RS256":
        if not settings.JWT_PRIVATE_KEY_PATH:
            errors.append("RS256 模式下必须设置 JWT_PRIVATE_KEY_PATH")
        if not settings.JWT_PUBLIC_KEY_PATH:
            errors.append("RS256 模式下必须设置 JWT_PUBLIC_KEY_PATH")

    if not settings.HTTPS_REDIRECT:
        errors.append("生产环境未启用 HTTPS 重定向（设置 HTTPS_REDIRECT=true）")

    if not settings.SECURITY_HEADERS_ENABLED:
        errors.append("生产环境未启用安全响应头（设置 SECURITY_HEADERS_ENABLED=true）")

    if not settings.RATE_LIMIT_ENABLED:
        errors.append("生产环境未启用限流（设置 RATE_LIMIT_ENABLED=true）")

    if errors:
        msg = "生产环境安全检查失败:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.warning(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    if settings.ENVIRONMENT == "production":
        _check_production_security()

    await init_s3_clients()
    await ensure_bucket()

    await ws_manager.start_pubsub()

    logger.info(
        f"应用启动完成 | env={settings.ENVIRONMENT} | "
        f"algorithm={settings.ALGORITHM} | "
        f"prometheus={settings.PROMETHEUS_ENABLED} | "
        f"ws_pubsub={settings.WS_PUBSUB_ENABLED} | "
        f"minio_secure={settings.MINIO_SECURE}"
    )

    yield

    await ws_manager.stop_pubsub()
    await close_s3_clients()
    await close_redis()
    await close_redis_pubsub()
    await dispose_engine()
    logger.info("应用关闭完成，所有资源已释放")


app = FastAPI(title="Cloud Drive API", lifespan=lifespan)

if settings.PROMETHEUS_ENABLED:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    logger.info("Prometheus 指标已启用，访问 /metrics")

# HTTPS 重定向（仅生产启用，最外层）
if settings.HTTPS_REDIRECT and settings.ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# 安全响应头（CSP/HSTS/X-Frame-Options 等）
app.add_middleware(SecurityHeadersMiddleware)

# 全局限流（滑动窗口，基于 IP + 路径）
app.add_middleware(RateLimitMiddleware)

# CSRF 双提交 Cookie 防护
app.add_middleware(CSRFMiddleware)

# GZip 压缩（最小 500 字节以上才压缩）
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS（确保错误响应也带 CORS 头）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "Range", "Origin", "X-CSRF-Token"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Range", "Accept-Ranges"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(health.router, tags=["health"])