import io
from loguru import logger
from app.core.celery_app import celery_app
from app.core.config import settings


@celery_app.task(
    name="tasks.generate_thumbnail",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    soft_time_limit=120,
    time_limit=150,
)
def generate_thumbnail(self, storage_key: str, file_id: str) -> str | None:
    try:
        from minio import Minio

        minio_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )

        response = minio_client.get_object(settings.MINIO_BUCKET, storage_key)
        data = response.read()
        response.close()
        response.release_conn()

        from PIL import Image

        img = Image.open(io.BytesIO(data))
        img.thumbnail((256, 256), Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)

        thumb_key = f"thumbnails/{file_id}.jpg"
        minio_client.put_object(
            settings.MINIO_BUCKET,
            thumb_key,
            buf,
            buf.getbuffer().nbytes,
            content_type="image/jpeg",
        )
        logger.bind(log_type="thumbnail").info(f"缩略图已生成: {thumb_key}")
        return thumb_key

    except ImportError:
        logger.bind(log_type="thumbnail").warning("Pillow 未安装，跳过缩略图生成")
        return None
    except Exception as exc:
        logger.bind(log_type="thumbnail").error(f"缩略图生成失败 [{storage_key}]: {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return None