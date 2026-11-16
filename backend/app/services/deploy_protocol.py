import contextlib
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings

TASK_ID_RE = re.compile(r"^[0-9a-f-]{36}$")
TASK_KINDS = ("queue", "running", "results")
MAX_LOG_READ_BYTES = 512 * 1024


def root_dir() -> Path:
    return Path(settings.DEPLOY_QUEUE_DIR)


def ensure_dirs() -> None:
    root = root_dir()
    for name in (*TASK_KINDS, "logs", "snapshot"):
        (root / name).mkdir(parents=True, exist_ok=True)


def validate_task_id(task_id: str) -> str:
    if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id):
        raise ValueError(f"非法的 task_id: {task_id!r}")
    return task_id


def _safe_path(path: Path) -> Path:
    resolved_root = root_dir().resolve()
    resolved = path.resolve()
    if resolved_root != resolved and resolved_root not in resolved.parents:
        raise ValueError(f"路径越界: {path}")
    return resolved


def task_path(kind: str, task_id: str) -> Path:
    if kind not in TASK_KINDS:
        raise ValueError(f"非法任务目录: {kind}")
    validate_task_id(task_id)
    return _safe_path(root_dir() / kind / f"{task_id}.json")


def log_path(task_id: str) -> Path:
    validate_task_id(task_id)
    return _safe_path(root_dir() / "logs" / f"{task_id}.jsonl")


def read_json(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def enqueue_task(task: dict) -> Path:
    task_id = validate_task_id(str(task.get("task_id", "")))
    path = task_path("queue", task_id)
    write_json_atomic(path, task)
    return path


def next_queue_task() -> tuple[str, dict] | None:
    for path in list_queue():
        data = read_json(path)
        if not data:
            continue
        task_id = str(data.get("task_id") or path.stem)
        try:
            validate_task_id(task_id)
        except ValueError:
            continue
        return task_id, data
    return None


def claim_task(task_id: str) -> dict | None:
    validate_task_id(task_id)
    source = task_path("queue", task_id)
    target = task_path("running", task_id)
    data = read_json(source)
    if not data:
        return None
    try:
        os.rename(source, target)
    except OSError:
        return None
    return read_json(target) or data


def update_running(task_id: str, patch: dict) -> dict | None:
    validate_task_id(task_id)
    path = task_path("running", task_id)
    data = read_json(path)
    if not data:
        return None
    data.update(patch)
    write_json_atomic(path, data)
    return data


def finish_task(task_id: str, result: dict) -> Path:
    validate_task_id(task_id)
    path = task_path("results", task_id)
    write_json_atomic(path, result)
    running = task_path("running", task_id)
    with contextlib.suppress(OSError):
        running.unlink()
    queued = task_path("queue", task_id)
    with contextlib.suppress(OSError):
        queued.unlink()
    return path


def task_state(task_id: str) -> str | None:
    kinds = locate_task(task_id)
    if "running" in kinds:
        return "running"
    if "queue" in kinds:
        return "queued"
    if "results" in kinds:
        return "finished"
    return None


def locate_task(task_id: str) -> list[str]:
    validate_task_id(task_id)
    found: list[str] = []
    for kind in TASK_KINDS:
        if task_path(kind, task_id).is_file():
            found.append(kind)
    return found


def _list_kind(kind: str) -> list[Path]:
    directory = root_dir() / kind
    if not directory.is_dir():
        return []
    files = [p for p in directory.glob("*.json") if p.is_file() and not p.name.endswith(".tmp")]
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def list_queue() -> list[Path]:
    return _list_kind("queue")


def list_running() -> list[Path]:
    return _list_kind("running")


def _parse_lines(raw_lines: list[bytes]) -> list[dict]:
    events: list[dict] = []
    for raw in raw_lines:
        if not raw.strip():
            continue
        try:
            item = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def read_log_events(task_id: str, offset: int = 0) -> tuple[list[dict], int]:
    path = log_path(task_id)
    if not path.is_file():
        return [], offset
    size = path.stat().st_size
    start = offset if 0 <= offset <= size else 0
    if size - start > MAX_LOG_READ_BYTES:
        start = max(size - MAX_LOG_READ_BYTES, 0)
    with open(path, "rb") as f:
        f.seek(start)
        chunk = f.read()
    complete = chunk
    if chunk and not chunk.endswith(b"\n"):
        cut = chunk.rfind(b"\n")
        complete = chunk[: cut + 1] if cut >= 0 else b""
    events = _parse_lines(complete.split(b"\n"))
    return events, min(start + len(complete), size)


def read_log_tail(task_id: str, limit: int) -> list[dict]:
    if limit <= 0:
        return []
    path = log_path(task_id)
    if not path.is_file():
        return []
    size = path.stat().st_size
    start = max(size - MAX_LOG_READ_BYTES, 0)
    with open(path, "rb") as f:
        f.seek(start)
        chunk = f.read()
    lines = [raw for raw in chunk.split(b"\n") if raw.strip()]
    return _parse_lines(lines[-limit:])


def container_snapshot() -> dict | None:
    return read_json(root_dir() / "snapshot" / "containers.json")


def meta_snapshot() -> dict | None:
    return read_json(root_dir() / "snapshot" / "meta.json")


def heartbeat_age_seconds() -> float | None:
    path = root_dir() / "heartbeat"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return max(time.time() - mtime, 0.0)


def runner_online() -> bool:
    age = heartbeat_age_seconds()
    if age is None:
        return False
    return age <= settings.DEPLOY_HEARTBEAT_TIMEOUT


def latest_result() -> dict | None:
    results = recent_results(1)
    return results[0] if results else None


def recent_results(limit: int) -> list[dict]:
    files = _list_kind("results")
    items: list[dict] = []
    for path in reversed(files):
        data = read_json(path)
        if not data:
            continue
        items.append(data)
        if len(items) >= limit:
            break
    items.sort(key=lambda d: str(d.get("finished_at") or ""), reverse=True)
    return items


def task_result(task_id: str) -> dict | None:
    try:
        path = task_path("results", task_id)
    except ValueError:
        return None
    return read_json(path)


def task_payload(task_id: str, kind: str) -> dict | None:
    try:
        path = task_path(kind, task_id)
    except ValueError:
        return None
    return read_json(path)


def task_detail(task_id: str, max_log_lines: int) -> dict | None:
    validate_task_id(task_id)
    state = task_state(task_id)
    if state is None:
        return None

    payload: dict = {}
    if state == "queued":
        payload = task_payload(task_id, "queue") or {}
    elif state == "running":
        payload = task_payload(task_id, "running") or {}
    else:
        payload = task_result(task_id) or {}

    status = str(payload.get("status") or state)
    if state == "queued" and payload.get("status") is None:
        status = "queued"

    logs = [str(item.get("msg") or item.get("line") or "") for item in read_log_tail(task_id, max_log_lines)]
    total_steps = int(payload.get("total_steps") or 0)
    step_index = int(payload.get("step_index") or 0)
    pct = int(payload.get("pct") or 0)
    if total_steps > 0 and pct == 0:
        pct = min(int(step_index * 100 / total_steps), 100)

    return {
        "task_id": task_id,
        "action": str(payload.get("action") or ""),
        "status": status,
        "step": payload.get("step"),
        "step_index": step_index,
        "total_steps": total_steps,
        "pct": pct,
        "started_at": payload.get("started_at"),
        "updated_at": payload.get("updated_at"),
        "finished_at": payload.get("finished_at"),
        "logs": [line for line in logs if line],
        "error": payload.get("error"),
    }


def is_stalled(task_id: str, timeout_seconds: int) -> bool:
    if task_state(task_id) != "running":
        return False
    payload = task_payload(task_id, "running") or {}
    stamp = payload.get("updated_at") or payload.get("started_at")
    if not stamp:
        return False
    try:
        updated = datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return False
    return (datetime.now(UTC) - updated).total_seconds() > timeout_seconds
