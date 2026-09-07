from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, files, shares, folders, admin, backups

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(shares.router, prefix="/shares", tags=["shares"])
api_router.include_router(folders.router, prefix="/folders", tags=["folders"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(backups.router, prefix="/admin/backups", tags=["backups"])