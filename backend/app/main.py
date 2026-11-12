import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from app.api.v1.api import api_router
from app.api.v1.endpoints import health
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.redis import close_redis, close_redis_pubsub, redis_client
from app.core.storage import close_s3_clients, ensure_bucket, init_s3_clients
from app.core.ws_manager import ws_manager
from app.db.base import dispose_engine, engine
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


def _check_production_security() -> None:
    errors = []

    if settings.ALGORITHM == "HS256":
        errors.append(
            "JWT 使用 HS256 对称算法，生产环境建议迁移到 RS256（设置 ALGORITHM=RS256 + JWT_PRIVATE_KEY_PATH + JWT_PUBLIC_KEY_PATH）"
        )

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

    from sqlalchemy import text

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(f"DB pool 预热完成 | pool_size={engine.pool.size()}")
    except Exception as e:
        logger.error(f"DB pool 预热失败: {e}")

    await init_s3_clients()
    await ensure_bucket()

    await ws_manager.start_pubsub()

    cleanup_task = asyncio.create_task(_cleanup_orphan_multipart_uploads())

    logger.info(
        f"应用启动完成 | env={settings.ENVIRONMENT} | "
        f"algorithm={settings.ALGORITHM} | "
        f"prometheus={settings.PROMETHEUS_ENABLED} | "
        f"ws_pubsub={settings.WS_PUBSUB_ENABLED} | "
        f"minio_secure={settings.MINIO_SECURE}"
    )

    yield

    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task

    await ws_manager.stop_pubsub()
    await close_s3_clients()
    await close_redis()
    await close_redis_pubsub()
    await dispose_engine()
    logger.info("应用关闭完成，所有资源已释放")


async def _cleanup_orphan_multipart_uploads() -> None:
    from app.core.storage import get_s3_client

    async def _run_once() -> None:
        async with get_s3_client() as client:
            upload_entries: list[tuple[str, str]] = []
            paginator = client.get_paginator("list_multipart_uploads")
            async for page in paginator.paginate(Bucket=settings.MINIO_BUCKET):
                for upload in page.get("Uploads", []):
                    key = upload.get("Key", "")
                    upload_id = upload.get("UploadId", "")
                    if key.count("/") < 1:
                        continue
                    owner_id = key.split("/")[0]
                    upload_entries.append((key, upload_id))

            if not upload_entries:
                return

            pipeline = redis_client.pipeline(transaction=False)
            for key, upload_id in upload_entries:
                owner_id = key.split("/")[0]
                pipeline.exists(f"multipart:{owner_id}:{upload_id}")
            results = await pipeline.execute()

            orphans = [
                (key, upload_id) for (key, upload_id), alive in zip(upload_entries, results, strict=False) if not alive
            ]
            if not orphans:
                return

            async def _abort_one(key: str, upload_id: str) -> None:
                try:
                    await client.abort_multipart_upload(
                        Bucket=settings.MINIO_BUCKET,
                        Key=key,
                        UploadId=upload_id,
                    )
                    logger.bind(log_type="backup").info(f"清理孤儿分片上传: key={key} upload_id={upload_id}")
                except Exception as e:
                    logger.bind(log_type="backup").warning(f"清理孤儿分片上传失败: key={key} error={e}")

            async with asyncio.TaskGroup() as tg:
                for key, upload_id in orphans:
                    tg.create_task(_abort_one(key, upload_id))

    interval = 3600
    while True:
        try:
            await asyncio.sleep(interval)
            await _run_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"孤儿分片清理任务异常: {e}")


_docs_enabled = settings.ENVIRONMENT != "production"
app = FastAPI(
    title="Cloud Drive API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

register_exception_handlers(app)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request, exc):
    import traceback

    from fastapi.responses import JSONResponse

    logger.error(f"未处理异常: {exc}\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


if settings.PROMETHEUS_ENABLED:
    import ipaddress
    import secrets

    from prometheus_fastapi_instrumentator import Instrumentator
    from starlette.responses import PlainTextResponse

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    _METRICS_TOKEN = settings.METRICS_TOKEN.strip()

    def _is_internal_client(host: str | None) -> bool:
        if not host:
            return False
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            return False
        return addr.is_loopback or addr.is_private

    async def _metrics_auth_middleware(request, call_next):
        if request.url.path == "/metrics":
            if _METRICS_TOKEN:
                auth = request.headers.get("Authorization", "")
                if not secrets.compare_digest(auth, f"Bearer {_METRICS_TOKEN}"):
                    return PlainTextResponse("Unauthorized", status_code=401)
            elif not _is_internal_client(request.client.host if request.client else None):
                return PlainTextResponse("Forbidden", status_code=403)
        return await call_next(request)

    app.middleware("http")(_metrics_auth_middleware)
    logger.info(f"Prometheus 指标已启用，/metrics 鉴权方式：{'Bearer Token' if _METRICS_TOKEN else '仅内网可访问'}")

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
_cors_origins = []
for _origin in settings.CORS_ORIGINS.split(","):
    _origin = _origin.strip()
    if not _origin:
        continue
    if _origin == "*":
        _cors_origins.append(_origin)
        continue
    if not _origin.startswith(("http://", "https://")):
        logger.warning(f"CORS origin 缺少协议前缀，已跳过: {_origin}")
        continue
    _cors_origins.append(_origin)

if not _cors_origins:
    logger.warning("CORS_ORIGINS 为空，API 将无法被前端跨域访问")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "Range", "Origin", "X-CSRF-Token"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Range", "Accept-Ranges"],
)

# 请求日志与 X-Request-ID（最外层，覆盖全部中间件与路由）
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix="/api/v1")
app.include_router(health.router, tags=["health"])
