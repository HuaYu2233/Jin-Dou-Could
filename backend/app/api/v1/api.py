from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, files

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])  # 新增
api_router.include_router(files.router, prefix="/files", tags=["files"])