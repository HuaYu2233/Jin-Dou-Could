from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.api.v1.endpoints import health
from app.core.storage import ensure_bucket
from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.request_logging import RequestLoggingMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    ensure_bucket()
    yield

app = FastAPI(title="Cloud Drive API", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)

#加 CORS（最外层，确保错误响应也带 CORS 头）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["Content-Disposition", "Content-Length"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(health.router, tags=["health"])