from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.core.storage import ensure_bucket

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    yield

app = FastAPI(title="Cloud Drive API", lifespan=lifespan)

#加 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⚠️ 【需修改】确认前缀正确
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}