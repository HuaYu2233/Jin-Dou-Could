from minio import Minio
from minio.error import S3Error
from app.core.config import settings
from datetime import timedelta
import io

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=False,
)

_presigned_client = Minio(
    settings.MINIO_PUBLIC_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=False,
    region='us-east-1',
)

def ensure_bucket() -> None:
    try:
        if not minio_client.bucket_exists(settings.MINIO_BUCKET):
            minio_client.make_bucket(settings.MINIO_BUCKET)
    except S3Error as e:
        raise RuntimeError(f"MinIO bucket init failed: {e}")

def upload_file(storage_key: str, data: bytes, mime_type: str, length: int) -> None:
    minio_client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key,
        data=io.BytesIO(data),
        length=length,
        content_type=mime_type,
    )

def upload_fileobj(storage_key: str, fileobj, mime_type: str, length: int) -> None:
    minio_client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key,
        data=fileobj,
        length=length,
        content_type=mime_type,
    )

def get_object_stream(storage_key: str):
    return minio_client.get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key,
    )

def stream_object(storage_key: str, chunk_size: int = 8192):
    response = minio_client.get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key,
    )
    try:
        for chunk in response.stream(chunk_size):
            yield chunk
    finally:
        response.close()
        response.release_conn()

def delete_file(storage_key: str) -> None:
    minio_client.remove_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key,
    )

def get_presigned_download_url(
    storage_key: str,
    expires: int = 3600,
    filename: str | None = None,
) -> str:
    from urllib.parse import quote
    response_headers: dict[str, str] = {}
    if filename:
        disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
        response_headers["response-content-disposition"] = disposition
    return _presigned_client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=storage_key,
        expires=timedelta(seconds=expires),
        response_headers=response_headers,
    )