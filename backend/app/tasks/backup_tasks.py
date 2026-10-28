import time
from pathlib import Path
from loguru import logger
from app.core.celery_app import celery_app
from app.core.config import settings


@celery_app.task(
    name="tasks.trigger_backup",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
    soft_time_limit=600,
    time_limit=660,
)
def trigger_backup(self) -> str:
    if settings.BACKUP_TRIGGER_CMD:
        import subprocess
        try:
            result = subprocess.run(
                settings.BACKUP_TRIGGER_CMD,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"备份命令执行失败 (exit={result.returncode}): {result.stderr}"
                )
            logger.bind(log_type="backup").info("备份命令执行成功")
            return "backup triggered via command"
        except Exception as exc:
            logger.bind(log_type="backup").error(f"备份命令执行失败: {exc}")
            raise self.retry(exc=exc)

    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    trigger_file = backup_dir / f".trigger_{int(time.time())}"
    trigger_file.write_text("trigger")
    logger.bind(log_type="backup").info(f"备份触发文件已创建: {trigger_file.name}")
    return "backup triggered via file"