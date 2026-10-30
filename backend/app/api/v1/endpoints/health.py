from fastapi import APIRouter
from app.services import health_service

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready():
    return await health_service.get_health()