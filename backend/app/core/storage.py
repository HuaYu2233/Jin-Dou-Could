import asyncio
import aiobotocore.session
from botocore.config import Config
from app.core.config import settings
from contextlib import asynccontextmanager
from datetime import timedelta
from urllib.parse import quote
from loguru import logger
import io

_s3_config = Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
)

_session = aiobotocore.session.get_session()

_s3_client = None
_s3_client_ctx = None
_presigned_client = None
_presigned_client_ctx = None
_init_lock = asyncio.Lock()

_ENDPOINT_SCHEME = "https" if settings.MINIO_SECURE else "http"


async def init_s3_clients():
    global _s3_client, _s3_client_ctx, _presigned_client, _presigned_client_ctx
    async with _init_lock:
        if _s3_client is not None:
            return
        _s3_client_ctx = _session.create_client(
            "s3",
            endpoint_url=f"{_ENDPOINT_SCHEME}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1",
            config=_s3_config,
            use_ssl=settings.MINIO_SECURE,
        )
        _s3_client = await _s3_client_ctx.__aenter__()

        _presigned_client_ctx = _session.create_client(
            "s3",
            endpoint_url=f"{_ENDPOINT_SCHEME}://{settings.MINIO_PUBLIC_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1",
            config=_s3_config,
            use_ssl=settings.MINIO_SECURE,
        )
        _presigned_client = await _presigned_client_ctx.__aenter__()
        logger.info(f"S3 clients initialized (secure={settings.MINIO_SECURE})")


async def close_s3_clients():
    global _s3_client, _s3_client_ctx, _presigned_client, _presigned_client_ctx
    if _s3_client_ctx is not None:
        await _s3_client_ctx.__aexit__(None, None, None)
        _s3_client_ctx = None
        _s3_client = None
    if _presigned_client_ctx is not None:
        await _presigned_client_ctx.__aexit__(None, None, None)
        _presigned_client_ctx = None
        _presigned_client = None
    logger.info("S3 clients closed")


@asynccontextmanager
async def get_s3_client():
    if _s3_client is None:
        await init_s3_clients()
    yield _s3_client


@asynccontextmanager
async def get_presigned_s3_client():
    if _presigned_client is None:
        await init_s3_clients()
    yield _presigned_client


async def ensure_bucket() -> None:
    async with get_s3_client() as client:
        try:
            await client.head_bucket(Bucket=settings.MINIO_BUCKET)
        except client.exceptions.ClientError:
            await client.create_bucket(Bucket=settings.MINIO_BUCKET)

    try:
        async with get_s3_client() as client:
            await client.put_bucket_cors(
                Bucket=settings.MINIO_BUCKET,
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedMethods": ["GET", "HEAD"],
                            "AllowedOrigins": ["*"],
                            "AllowedHeaders": [
                                "Authorization",
                                "Content-Type",
                                "Accept",
                                "Range",
                                "Origin",
                            ],
                            "ExposeHeaders": [
                                "Content-Length",
                                "Content-Range",
                                "Content-Disposition",
                                "Content-Type",
                            ],
                            "MaxAgeSeconds": 3600,
                        }
                    ]
                },
            )
    except Exception:
        pass


async def upload_file(storage_key: str, data: bytes, mime_type: str, length: int) -> None:
    async with get_s3_client() as client:
        await client.put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=storage_key,
            Body=io.BytesIO(data),
            ContentType=mime_type,
        )


async def upload_fileobj(storage_key: str, fileobj, mime_type: str, length: int) -> None:
    async with get_s3_client() as client:
        await client.put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=storage_key,
            Body=fileobj,
            ContentType=mime_type,
        )


async def upload_multipart(
    storage_key: str,
    fileobj,
    mime_type: str,
    total_size: int,
    chunk_size: int | None = None,
) -> None:
    cs = chunk_size or settings.UPLOAD_CHUNK_SIZE
    async with get_s3_client() as client:
        resp = await client.create_multipart_upload(
            Bucket=settings.MINIO_BUCKET,
            Key=storage_key,
            ContentType=mime_type,
        )
        upload_id = resp["UploadId"]

        parts = []
        part_number = 1
        offset = 0
        try:
            while offset < total_size:
                read_len = min(cs, total_size - offset)
                chunk = fileobj.read(read_len) if hasattr(fileobj, "read") else await fileobj.read(read_len)
                if not chunk:
                    break
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                part_resp = await client.upload_part(
                    Bucket=settings.MINIO_BUCKET,
                    Key=storage_key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk,
                )
                parts.append({
                    "PartNumber": part_number,
                    "ETag": part_resp["ETag"],
                })
                part_number += 1
                offset += len(chunk)

            await client.complete_multipart_upload(
                Bucket=settings.MINIO_BUCKET,
                Key=storage_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except Exception:
            try:
                await client.abort_multipart_upload(
                    Bucket=settings.MINIO_BUCKET,
                    Key=storage_key,
                    UploadId=upload_id,
                )
            except Exception:
                pass
            raise


async def upload_stream_multipart(
    storage_key: str,
    stream,
    mime_type: str,
    total_size: int,
    chunk_size: int | None = None,
) -> None:
    cs = chunk_size or settings.UPLOAD_CHUNK_SIZE
    async with get_s3_client() as client:
        resp = await client.create_multipart_upload(
            Bucket=settings.MINIO_BUCKET,
            Key=storage_key,
            ContentType=mime_type,
        )
        upload_id = resp["UploadId"]

        parts = []
        part_number = 1
        uploaded = 0
        try:
            while uploaded < total_size:
                remaining = total_size - uploaded
                read_len = min(cs, remaining)
                chunk = await stream.read(read_len)
                if not chunk:
                    break
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                part_resp = await client.upload_part(
                    Bucket=settings.MINIO_BUCKET,
                    Key=storage_key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk,
                )
                parts.append({
                    "PartNumber": part_number,
                    "ETag": part_resp["ETag"],
                })
                part_number += 1
                uploaded += len(chunk)

            await client.complete_multipart_upload(
                Bucket=settings.MINIO_BUCKET,
                Key=storage_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except Exception:
            try:
                await client.abort_multipart_upload(
                    Bucket=settings.MINIO_BUCKET,
                    Key=storage_key,
                    UploadId=upload_id,
                )
            except Exception:
                pass
            raise


async def get_object_stream(storage_key: str):
    async with get_s3_client() as client:
        resp = await client.get_object(
            Bucket=settings.MINIO_BUCKET,
            Key=storage_key,
        )
        async with resp["Body"] as stream:
            return stream


async def stream_object(storage_key: str, chunk_size: int = 8192):
    async with get_s3_client() as client:
        resp = await client.get_object(
            Bucket=settings.MINIO_BUCKET,
            Key=storage_key,
        )
        async with resp["Body"] as stream:
            async for chunk in stream.iter_chunks(chunk_size):
                yield chunk


async def delete_file(storage_key: str) -> None:
    async with get_s3_client() as client:
        await client.delete_object(
            Bucket=settings.MINIO_BUCKET,
            Key=storage_key,
        )


async def batch_delete_files(storage_keys: list[str]) -> None:
    if not storage_keys:
        return
    batch_size = 1000
    all_errors: list[str] = []
    async with get_s3_client() as client:
        for i in range(0, len(storage_keys), batch_size):
            batch = storage_keys[i : i + batch_size]
            objects = [{"Key": key} for key in batch]
            resp = await client.delete_objects(
                Bucket=settings.MINIO_BUCKET,
                Delete={"Objects": objects, "Quiet": True},
            )
            errors = resp.get("Errors", [])
            if errors:
                all_errors.extend(e["Key"] for e in errors)
    if all_errors:
        raise RuntimeError(f"批量删除部分失败: {all_errors[:10]}")


async def get_presigned_download_url(
    storage_key: str,
    expires: int = 3600,
    filename: str | None = None,
) -> str:
    async with get_presigned_s3_client() as client:
        params = {
            "Bucket": settings.MINIO_BUCKET,
            "Key": storage_key,
        }
        if filename:
            disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
            params["ResponseContentDisposition"] = disposition
        url = await client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires,
        )
        return url


async def get_presigned_preview_url(
    storage_key: str,
    mime_type: str,
    filename: str,
    expires: int = 3600,
) -> str:
    async with get_presigned_s3_client() as client:
        params = {
            "Bucket": settings.MINIO_BUCKET,
            "Key": storage_key,
            "ResponseContentDisposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "ResponseContentType": mime_type,
        }
        url = await client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires,
        )
        return url