from celery import Celery
from app.core.config import settings


def _build_celery_url(base_url: str, db: int) -> str:
    if base_url:
        return base_url
    url = settings.REDIS_URL
    if "/" in url and url.rsplit("/", 1)[1].isdigit():
        url = url.rsplit("/", 1)[0]
    return f"{url}/{db}"


celery_app = Celery(
    "jindou_cloud",
    broker=_build_celery_url(settings.CELERY_BROKER_URL, 1),
    backend=_build_celery_url(settings.CELERY_RESULT_BACKEND_URL, 2),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["app.tasks"])