from fastapi import APIRouter, Depends

from app.api.deps import get_current_admin
from app.models.user import User
from app.schemas.env_config import (
    EnvConfigResponse,
    EnvConfigSaveRequest,
    EnvConfigSaveResponse,
)
from app.services import env_config_service

router = APIRouter()


@router.get("", response_model=EnvConfigResponse)
async def get_config(_: User = Depends(get_current_admin)):
    return env_config_service.get_config()


@router.post("/save", response_model=EnvConfigSaveResponse)
async def save_config(
    payload: EnvConfigSaveRequest,
    _: User = Depends(get_current_admin),
):
    return env_config_service.save_config(payload.values)


@router.post("/generate", response_model=dict[str, str])
async def generate_values(_: User = Depends(get_current_admin)):
    return env_config_service.generate_sensitive_values()
