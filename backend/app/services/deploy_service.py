import json
import secrets
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from loguru import logger

from app.core.config import settings
from app.core.exceptions import (
    DeployBusy,
    DeployConfirmRequired,
    DeployDisabled,
    DeployInvalidAction,
    DeployTaskNotFound,
)
from app.core.redis import redis_client
from app.services import deploy_protocol

LOCK_KEY = "deploy:lock"
CONFIRM_KEY_PREFIX = "deploy:confirm:"
CONFIRM_TTL_SECONDS = 60
DANGEROUS_ACTIONS = ("deploy", "rollback")
RESTART_TARGETS = ("backend", "frontend", "celery-worker")
PARAM_KEYS = ("backup_first", "pull", "build_only")
ACTION_STEPS = {
    "check": ("preflight", "doctor"),
    "deploy": ("preflight", "backup", "tag_rollback", "pull", "build", "up", "health"),
    "restart": ("restart", "health"),
    "rollback": ("tag_rollback", "up", "health"),
}


def allowed_actions() -> list[str]:
    return [item.strip() for item in settings.DEPLOY_ALLOWED_ACTIONS.split(",") if item.strip()]


def ensure_enabled() -> None:
    if not settings.DEPLOY_ENABLED:
        raise DeployDisabled()


def _running_task_ids() -> list[str]:
    ids: list[str] = []
    for path in deploy_protocol.list_running():
        data = deploy_protocol.read_json(path)
        if data and data.get("task_id"):
            ids.append(str(data["task_id"]))
    return ids


def _latest_result() -> dict | None:
    data = deploy_protocol.latest_result()
    if not data:
        return None
    return {
        "task_id": data.get("task_id"),
        "action": data.get("action"),
        "status": data.get("status"),
        "finished_at": data.get("finished_at"),
    }


def get_status() -> dict:
    ensure_enabled()
    running_ids = _running_task_ids()
    return {
        "enabled": settings.DEPLOY_ENABLED,
        "runner_online": deploy_protocol.runner_online(),
        "running_task_id": running_ids[0] if running_ids else None,
        "allowed_actions": allowed_actions(),
        "last_result": _latest_result(),
    }


def get_containers() -> dict:
    ensure_enabled()
    snapshot = deploy_protocol.container_snapshot()
    age = deploy_protocol.heartbeat_age_seconds()
    heartbeat_age = int(age) if age is not None else None
    if not snapshot:
        return {
            "available": False,
            "collected_at": None,
            "compose_project": None,
            "heartbeat_age_seconds": heartbeat_age,
            "runner_online": deploy_protocol.runner_online(),
            "services": [],
        }
    services = [item for item in snapshot.get("services", []) if isinstance(item, dict)]
    return {
        "available": True,
        "collected_at": snapshot.get("collected_at"),
        "compose_project": snapshot.get("compose_project"),
        "heartbeat_age_seconds": heartbeat_age,
        "runner_online": deploy_protocol.runner_online(),
        "services": services,
    }


def get_versions() -> dict:
    ensure_enabled()
    meta = deploy_protocol.meta_snapshot() or {}
    image_tags = meta.get("image_tags") or {}
    if not isinstance(image_tags, dict):
        image_tags = {}
    return {
        "app_version": str(meta.get("app_version") or settings.APP_VERSION),
        "image_tags": {str(k): str(v) for k, v in image_tags.items()},
        "compose_hash": meta.get("compose_hash"),
        "git_commit": meta.get("git_commit"),
        "collected_at": meta.get("collected_at"),
    }


def get_history(limit: int = 20) -> list[dict]:
    ensure_enabled()
    items: list[dict] = []
    for data in deploy_protocol.recent_results(limit):
        items.append(
            {
                "task_id": data.get("task_id"),
                "action": data.get("action"),
                "target": data.get("target"),
                "status": data.get("status"),
                "step": data.get("step"),
                "started_at": data.get("started_at"),
                "finished_at": data.get("finished_at"),
                "rolled_back": bool(data.get("rolled_back", False)),
                "requested_by": data.get("requested_by"),
                "error": data.get("error"),
            }
        )
    return items


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_action(
    *,
    task_id: str,
    action: str,
    target: str | None,
    admin_id: str,
    result: str,
    duration_ms: int,
    params: dict | None = None,
) -> None:
    logger.bind(log_type="deploy").info(
        f"task_id={task_id} action={action} target={target} admin_id={admin_id} "
        f"result={result} duration_ms={duration_ms} params={json.dumps(params or {}, ensure_ascii=False)} "
        f"at={_now_iso()}"
    )


def _validate_action(action: str) -> str:
    normalized = (action or "").strip()
    if normalized not in allowed_actions():
        raise DeployInvalidAction()
    return normalized


def _validate_params(action: str, params: dict | None) -> dict:
    if not params:
        return {}
    if action not in DANGEROUS_ACTIONS:
        raise DeployInvalidAction("该动作不支持参数")
    unknown = [key for key in params if key not in PARAM_KEYS]
    if unknown:
        raise DeployInvalidAction(f"不支持的参数: {','.join(unknown)}")
    non_bool = [key for key, value in params.items() if not isinstance(value, bool)]
    if non_bool:
        raise DeployInvalidAction(f"参数必须为布尔值: {','.join(non_bool)}")
    return dict(params)


def _validate_target(action: str, target: str | None) -> str | None:
    if action != "restart":
        return None
    normalized = (target or "").strip()
    if normalized not in RESTART_TARGETS:
        raise DeployInvalidAction("不支持的目标服务")
    return normalized


def _confirm_key(token: str) -> str:
    return f"{CONFIRM_KEY_PREFIX}{token}"


async def issue_confirm_token(*, action: str, target: str | None, admin_id: str) -> dict:
    ensure_enabled()
    normalized = _validate_action(action)
    if normalized not in DANGEROUS_ACTIONS:
        raise DeployInvalidAction("该动作无需确认令牌")
    token = secrets.token_urlsafe(24)
    await redis_client.setex(
        _confirm_key(token),
        CONFIRM_TTL_SECONDS,
        json.dumps({"action": normalized, "target": target, "user_id": admin_id}, ensure_ascii=False),
    )
    return {"confirm_token": token, "expires_in": CONFIRM_TTL_SECONDS}


async def _consume_confirm_token(*, token: str, action: str, target: str | None, admin_id: str) -> None:
    if not token:
        raise DeployConfirmRequired()
    key = _confirm_key(token)
    raw = await redis_client.get(key)
    if not raw:
        raise DeployConfirmRequired()
    try:
        record = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        await redis_client.delete(key)
        raise DeployConfirmRequired() from None
    if record.get("action") != action or record.get("target") != target or str(record.get("user_id")) != str(admin_id):
        raise DeployConfirmRequired()
    await redis_client.delete(key)


async def _current_lock_owner() -> str | None:
    owner = await redis_client.get(LOCK_KEY)
    return str(owner) if owner else None


async def _find_idempotent_task(action: str, target: str | None) -> str | None:
    for path in deploy_protocol.list_running():
        data = deploy_protocol.read_json(path)
        if not data:
            continue
        if data.get("action") == action and data.get("target") == target:
            return str(data.get("task_id") or path.stem)
    for path in deploy_protocol.list_queue():
        data = deploy_protocol.read_json(path)
        if not data:
            continue
        if data.get("action") == action and data.get("target") == target:
            return str(data.get("task_id") or path.stem)
    return None


async def submit_action(
    *,
    action: str,
    target: str | None,
    params: dict | None,
    confirm_token: str | None,
    admin_id: str,
) -> dict:
    ensure_enabled()
    normalized = _validate_action(action)
    resolved_target = _validate_target(normalized, target)
    resolved_params = _validate_params(normalized, params)
    if normalized == "deploy":
        resolved_params.setdefault("backup_first", settings.DEPLOY_REQUIRE_BACKUP)
        resolved_params.setdefault("pull", True)

    if normalized in DANGEROUS_ACTIONS:
        await _consume_confirm_token(
            token=confirm_token or "",
            action=normalized,
            target=resolved_target,
            admin_id=admin_id,
        )

    existing = await _find_idempotent_task(normalized, resolved_target)
    if existing:
        return {"task_id": existing, "status": "queued"}

    started = monotonic()
    task_id = str(uuid4())
    now = _now_iso()
    steps = ACTION_STEPS.get(normalized, ())
    task = {
        "task_id": task_id,
        "action": normalized,
        "target": resolved_target,
        "params": resolved_params,
        "status": "queued",
        "step": None,
        "step_index": 0,
        "total_steps": len(steps),
        "pct": 0,
        "started_at": now,
        "updated_at": now,
        "finished_at": None,
        "requested_by": str(admin_id),
        "created_at": now,
    }

    acquired = await redis_client.set(
        LOCK_KEY,
        task_id,
        nx=True,
        ex=settings.DEPLOY_TASK_TIMEOUT,
    )
    if not acquired:
        owner = await _current_lock_owner()
        raise DeployBusy(owner or "unknown")

    try:
        deploy_protocol.enqueue_task(task)
    except Exception:
        await redis_client.delete(LOCK_KEY)
        raise

    log_action(
        task_id=task_id,
        action=normalized,
        target=resolved_target,
        admin_id=str(admin_id),
        result="queued",
        duration_ms=int((monotonic() - started) * 1000),
        params=resolved_params,
    )
    return {"task_id": task_id, "status": "queued"}


def get_task(task_id: str) -> dict:
    ensure_enabled()
    detail = deploy_protocol.task_detail(task_id, settings.DEPLOY_MAX_LOG_LINES)
    if detail is None:
        raise DeployTaskNotFound()
    if deploy_protocol.is_stalled(task_id, settings.DEPLOY_TASK_TIMEOUT):
        detail["status"] = "stalled"
    return detail
