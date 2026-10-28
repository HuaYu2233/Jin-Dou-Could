from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_admin
from app.models.user import User
from app.core.celery_app import celery_app

router = APIRouter()


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    _: User = Depends(get_current_admin),
):
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


@router.get("/active")
async def get_active_tasks(
    _: User = Depends(get_current_admin),
):
    inspector = celery_app.control.inspect()
    active = inspector.active() or {}
    reserved = inspector.reserved() or {}
    return {
        "active": {k: [{"id": t["id"], "name": t["name"]} for t in v] for k, v in active.items()},
        "reserved": {k: [{"id": t["id"], "name": t["name"]} for t in v] for k, v in reserved.items()},
    }