import re
import secrets
import shutil
import string
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.env_config import EnvConfigGroup

GROUP_RE = re.compile(r"^#\s*[-=]+\s*(.+?)\s*[-=]+\s*$")
KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$")
SENSITIVE_TOKENS = ("SECRET", "PASSWORD", "TOKEN", "ENCRYPT_KEY", "METRICS_TOKEN")
REQUIRED_KEYS = ("SECRET_KEY", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD")
WEAK_PATTERNS = {
    "change-me-in-production",
    "your-super-secret-key-change-this-in-production",
    "change-this-to-a-random-secret-key",
    "dev-secret-key-change-in-prod",
    "secret",
    "password",
    "test-secret-key",
}


def env_path() -> Path | None:
    raw = (settings.ENV_FILE_PATH or "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def is_enabled() -> bool:
    path = env_path()
    return bool(path) and path.is_file()


def _is_sensitive(key: str) -> bool:
    upper = key.upper()
    return any(tok in upper for tok in SENSITIVE_TOKENS)


def _parse(path: Path) -> list[EnvConfigGroup]:
    if not path.exists():
        return []
    groups: list[EnvConfigGroup] = []
    current_group = "基础"
    last_hint = ""
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line:
            last_hint = ""
            continue
        if GROUP_RE.match(line):
            current_group = GROUP_RE.match(line).group(1).strip()
            last_hint = ""
            continue
        stripped = line.lstrip()
        if stripped.startswith("#"):
            hint = stripped[1:].strip()
            if hint and not hint.startswith("=") and not hint.startswith("-"):
                last_hint = hint
            continue
        km = KEY_RE.match(line)
        if not km:
            continue
        key, value = km.group(1), km.group(2).strip()
        hint = last_hint
        last_hint = ""
        if current_group not in grouped:
            grouped[current_group] = []
            order.append(current_group)
        grouped[current_group].append(
            {
                "key": key,
                "value": value,
                "group": current_group,
                "hint": hint,
                "required": key in REQUIRED_KEYS,
                "sensitive": _is_sensitive(key),
            }
        )
    for name in order:
        groups.append(EnvConfigGroup(name=name, fields=grouped[name]))
    return groups


def get_config() -> dict:
    path = env_path()
    enabled = is_enabled()
    groups: list[EnvConfigGroup] = []
    if enabled and path:
        groups = _parse(path)
    return {
        "enabled": enabled,
        "path": str(path) if path else "",
        "backup": None,
        "groups": [g.model_dump() for g in groups],
    }


def _normalize_values(groups: list[EnvConfigGroup], submitted: dict[str, str]) -> dict[str, str]:
    values = {f.key: (f.value or "") for g in groups for f in g.fields}
    for key, val in submitted.items():
        values[key] = (val or "").strip()
    return values


def _validate(values: dict[str, str]) -> None:
    errors: list[str] = []
    sk = values.get("SECRET_KEY", "")
    if not sk:
        errors.append("SECRET_KEY 不能为空")
    elif len(sk) < 32 or sk.lower() in WEAK_PATTERNS or "chang" in sk.lower() or "example" in sk.lower():
        errors.append("SECRET_KEY 必须不少于 32 字符且不能为占位符/弱口令")
    for req in REQUIRED_KEYS:
        if not values.get(req):
            errors.append(f"{req} 不能为空")
    if errors:
        raise AppError("配置校验未通过", details={"errors": errors})


def save_config(values: dict[str, str]) -> dict:
    path = env_path()
    if not is_enabled() or not path:
        raise AppError("env 文件不可用，请先配置 ENV_FILE_PATH 挂载")
    groups = _parse(path)
    normalized = _normalize_values(groups, values)
    _validate(normalized)

    backup = path.parent / f".env.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(path, backup)

    out_lines: list[str] = []
    for group in groups:
        out_lines.append(f"# ==================== {group.name} ====================")
        for field in group.fields:
            if field.hint:
                for hint_line in field.hint.splitlines():
                    out_lines.append(f"# {hint_line}")
            out_lines.append(f"{field.key}={normalized.get(field.key, '')}")
        out_lines.append("")
    payload = "\n".join(out_lines).rstrip() + "\n"
    tmp = path.parent / f".env.tmp.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
    path.chmod(0o600)
    return {"ok": True, "path": str(path), "backup": str(backup), "errors": []}


def generate_sensitive_values() -> dict[str, str]:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-"
    out: dict[str, str] = {}
    for key in ("SECRET_KEY", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "METRICS_TOKEN"):
        out[key] = "".join(secrets.choice(alphabet) for _ in range(40))
    return out
