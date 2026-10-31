import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import io
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

from app.core import storage


class FakeS3Client:
    def __init__(self):
        self.created = []
        self.uploaded = []
        self.completed = []
        self.aborted = []
        self.put_objects = []

    async def create_multipart_upload(self, **kwargs):
        self.created.append(kwargs)
        return {"UploadId": f"upload-{len(self.created)}"}

    async def upload_part(self, **kwargs):
        self.uploaded.append(kwargs)
        return {"ETag": f"etag-{kwargs['PartNumber']}"}

    async def complete_multipart_upload(self, **kwargs):
        self.completed.append(kwargs)

    async def abort_multipart_upload(self, **kwargs):
        self.aborted.append(kwargs)

    async def put_object(self, **kwargs):
        self.put_objects.append(kwargs)


def _patch_client(fake: FakeS3Client):
    @asynccontextmanager
    async def _get_client():
        yield fake

    return patch.object(storage, "get_s3_client", _get_client)


class AsyncStream:
    def __init__(self, data: bytes, chunk_size: int = 1024):
        self._buf = io.BytesIO(data)
        self._chunk_size = chunk_size

    async def read(self, size: int = -1):
        return self._buf.read(size)


class TestUnknownSizeUpload:
    @pytest.mark.asyncio
    async def test_returns_actual_bytes_and_completes(self):
        fake = FakeS3Client()
        data = b"a" * 100
        with _patch_client(fake):
            total = await storage.upload_stream_multipart(
                "user/obj", io.BytesIO(data), "text/plain", chunk_size=40
            )
        assert total == 100
        assert len(fake.uploaded) == 3
        assert len(fake.completed) == 1
        assert fake.aborted == []

    @pytest.mark.asyncio
    async def test_parts_carry_incrementing_numbers(self):
        fake = FakeS3Client()
        with _patch_client(fake):
            await storage.upload_stream_multipart(
                "user/obj", io.BytesIO(b"b" * 30), "text/plain", chunk_size=10
            )
        numbers = [call["PartNumber"] for call in fake.uploaded]
        assert numbers == [1, 2, 3]
        assert fake.completed[0]["MultipartUpload"]["Parts"][0]["ETag"] == "etag-1"

    @pytest.mark.asyncio
    async def test_async_stream_supported(self):
        fake = FakeS3Client()
        data = b"c" * 50
        with _patch_client(fake):
            total = await storage.upload_stream_multipart(
                "user/obj", AsyncStream(data), "text/plain", chunk_size=25
            )
        assert total == 50
        assert len(fake.uploaded) == 2

    @pytest.mark.asyncio
    async def test_empty_stream_stores_empty_object(self):
        fake = FakeS3Client()
        with _patch_client(fake):
            total = await storage.upload_stream_multipart(
                "user/obj", io.BytesIO(b""), "text/plain"
            )
        assert total == 0
        assert len(fake.put_objects) == 1
        assert fake.put_objects[0]["Body"] == b""
        assert len(fake.aborted) == 1

    @pytest.mark.asyncio
    async def test_max_size_exceeded_aborts(self):
        fake = FakeS3Client()
        with _patch_client(fake), pytest.raises(ValueError):
            await storage.upload_stream_multipart(
                "user/obj", io.BytesIO(b"d" * 100), "text/plain",
                chunk_size=10, max_size=50,
            )
        assert len(fake.aborted) == 1
        assert fake.completed == []


class TestKnownSizeUpload:
    @pytest.mark.asyncio
    async def test_reads_exactly_total_size(self):
        fake = FakeS3Client()
        with _patch_client(fake):
            total = await storage.upload_stream_multipart(
                "user/obj", io.BytesIO(b"e" * 200), "text/plain",
                total_size=100, chunk_size=40,
            )
        assert total == 100
        assert len(fake.uploaded) == 3
        assert sum(len(call["Body"]) for call in fake.uploaded) == 100

    @pytest.mark.asyncio
    async def test_short_stream_stops_at_eof(self):
        fake = FakeS3Client()
        with _patch_client(fake):
            total = await storage.upload_stream_multipart(
                "user/obj", io.BytesIO(b"f" * 30), "text/plain",
                total_size=100, chunk_size=40,
            )
        assert total == 30
        assert len(fake.uploaded) == 1


class TestRemovedDuplicates:
    def test_dead_helpers_removed(self):
        assert not hasattr(storage, "upload_multipart")
        assert not hasattr(storage, "stream_object")