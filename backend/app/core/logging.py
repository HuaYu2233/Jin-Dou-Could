import sys
import json
import logging
import traceback
from pathlib import Path
from loguru import logger
from app.core.config import settings
from app.core.alerting import alert_sink

SENSITIVE_KEYS = {
    "password", "token", "authorization", "secret",
    "refresh_token", "access_token", "cookie",
}

def _sanitize(obj, depth=0):
    if depth > 5:
        return "<truncated>"
    if isinstance(obj, dict):
        return {
            k: "***" if k.lower() in SENSITIVE_KEYS else _sanitize(v, depth + 1)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v, depth + 1) for v in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)

def _json_patcher(record):
    try:
        extra = _sanitize(record["extra"])
        payload = {
            "time": record["time"].isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
            "extra": extra,
        }
        if record["exception"]:
            exc = record["exception"]
            payload["exception"] = "".join(
                traceback.format_exception(type(exc.value), exc.value, exc.traceback)
            )
        record["extra"]["_json_line"] = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        record["extra"]["_json_line"] = json.dumps({
            "time": str(record["time"]),
            "level": record["level"].name,
            "message": str(record["message"]),
            "error": "patcher_failed"
        }, ensure_ascii=False, default=str)

def setup_logging():
    logger.remove()

    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.configure(patcher=_json_patcher)

    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    logger.add(
        str(log_dir / "app.log"),
        level=settings.LOG_LEVEL,
        format="{extra[_json_line]}\n",
        rotation="00:00",
        retention=f"{settings.LOG_RETENTION_DAYS} days",
        compression="zip",
        encoding="utf-8",
    )

    logger.add(
        str(log_dir / "error.log"),
        level="ERROR",
        format="{extra[_json_line]}\n",
        rotation="00:00",
        retention=f"{settings.LOG_RETENTION_DAYS} days",
        compression="zip",
        encoding="utf-8",
    )

    logger.add(
        str(log_dir / "access.log"),
        level="INFO",
        format="{extra[_json_line]}\n",
        filter=lambda record: record["extra"].get("log_type") == "access",
        rotation="00:00",
        retention=f"{settings.LOG_RETENTION_DAYS} days",
        compression="zip",
        encoding="utf-8",
    )

    logger.add(
        alert_sink,
        level=settings.ALERT_MIN_LEVEL,
        filter=lambda record: record["extra"].get("log_type") != "access",
    )

    class InterceptHandler(logging.Handler):
        def emit(self, record):
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno
            frame, depth = sys._getframe(1), 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for name in ("sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.dialects"):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).setLevel(logging.WARNING)

    logger.info("日志系统已初始化", extra={"log_dir": str(log_dir)})

    test_path = log_dir / "app.log"
    try:
        test_path.write_text("", encoding="utf-8")
    except Exception as e:
        logger.error(f"日志目录不可写: {test_path} - {e}")