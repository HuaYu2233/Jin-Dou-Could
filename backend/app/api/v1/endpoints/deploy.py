from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_admin
from app.models.user import User
from app.schemas.deploy import (
    DeployActionRequest,
    DeployActionResponse,
    DeployConfirmRequest,
    DeployConfirmResponse,
    DeployContainers,
    DeployHistoryItem,
    DeployStatus,
    DeployTaskDetail,
    DeployVersions,
)
from app.services import deploy_service

router = APIRouter()


@router.get("/status", response_model=DeployStatus)
async def get_status(_: User = Depends(get_current_admin)):
    return deploy_service.get_status()


@router.get("/containers", response_model=DeployContainers)
async def get_containers(_: User = Depends(get_current_admin)):
    return deploy_service.get_containers()


@router.get("/versions", response_model=DeployVersions)
async def get_versions(_: User = Depends(get_current_admin)):
    return deploy_service.get_versions()


@router.get("/history", response_model=list[DeployHistoryItem])
async def get_history(
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(get_current_admin),
):
    return deploy_service.get_history(limit)


@router.post("/confirm", response_model=DeployConfirmResponse)
async def post_confirm(
    payload: DeployConfirmRequest,
    admin: User = Depends(get_current_admin),
):
    return await deploy_service.issue_confirm_token(
        action=payload.action,
        target=payload.target,
        admin_id=str(admin.id),
    )


@router.post("/actions", response_model=DeployActionResponse)
async def post_action(
    payload: DeployActionRequest,
    admin: User = Depends(get_current_admin),
):
    return await deploy_service.submit_action(
        action=payload.action,
        target=payload.target,
        params=payload.params,
        confirm_token=payload.confirm_token,
        admin_id=str(admin.id),
    )


@router.get("/tasks/{task_id}", response_model=DeployTaskDetail)
async def get_task(
    task_id: str,
    _: User = Depends(get_current_admin),
):
    return deploy_service.get_task(task_id)
