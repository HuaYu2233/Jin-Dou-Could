from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from app.api.v1.api import api_router
from app.api.v1.endpoints import health
from app.core.storage import ensure_bucket, close_s3_clients
from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await ensure_bucket()
    yield
    await close_s3_clients()

app = FastAPI(title="Cloud Drive API", lifespan=lifespan)

# HTTPS 重定向（仅生产启用，最外层）
if settings.HTTPS_REDIRECT and settings.ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# 安全响应头（CSP/HSTS/X-Frame-Options 等）
app.add_middleware(SecurityHeadersMiddleware)

# 全局限流（滑动窗口，基于 IP + 路径）
app.add_middleware(RateLimitMiddleware)

# GZip 压缩（最小 500 字节以上才压缩）
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS（确保错误响应也带 CORS 头）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "Range", "Origin"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Range", "Accept-Ranges"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(health.router, tags=["health"])