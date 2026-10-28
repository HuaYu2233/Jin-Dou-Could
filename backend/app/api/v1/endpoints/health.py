from fastapi import APIRouter
from app.services import health_service

router = APIRouter()


@router.get("/health")
async def health():
    return await health_service.get_health()