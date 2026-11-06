import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ValidationFailed
from app.services.file_validation import (
    _FILENAME_MAX_LEN,
    ALLOWED_MIME_TYPES,
    categorize_file_type,
    detect_real_mime_type,
    sanitize_filename,
    validate_mime_type,
)


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("photo.jpg") == "photo.jpg"

    def test_truncates_long_name(self):
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) == _FILENAME_MAX_LEN

    def test_strips_control_chars(self):
        assert sanitize_filename("file\x00\x01\x1f\x7f.txt") == "file.txt"

    def test_blocks_path_traversal(self):
        result = sanitize_filename("../../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result
        assert "../" not in result

    def test_strips_leading_trailing_dots_spaces(self):
        result = sanitize_filename("  .hidden.  ")
        assert not result.startswith(".")
        assert not result.endswith(".")
        assert not result.startswith(" ")

    def test_empty_name_fallback(self):
        assert sanitize_filename("") == "unknown"

    def test_path_sep_replaced(self):
        result = sanitize_filename("a/b\\c")
        assert "/" not in result
        assert "\\" not in result

    def test_only_dots_becomes_unknown(self):
        result = sanitize_filename("...")
        assert result == "unknown"

    def test_preserves_extension(self):
        assert sanitize_filename("document.pdf") == "document.pdf"


class TestValidateMimeType:
    def test_allowed_type_passes(self):
        validate_mime_type("image/jpeg", "image/jpeg")

    def test_disallowed_detected_type_raises(self):
        with pytest.raises(ValidationFailed, match="不允许的文件类型"):
            validate_mime_type("image/jpeg", "application/x-shellscript")

    def test_mismatch_raises(self):
        with pytest.raises(ValidationFailed, match="文件类型与声明不符"):
            validate_mime_type("image/jpeg", "image/png")

    def test_octet_stream_compatible(self):
        validate_mime_type("application/octet-stream", "image/png")

    def test_same_type_passes(self):
        validate_mime_type("video/mp4", "video/mp4")


class TestCategorizeFileType:
    def test_image(self):
        assert categorize_file_type("image/jpeg") == "image"
        assert categorize_file_type("image/png") == "image"

    def test_video(self):
        assert categorize_file_type("video/mp4") == "video"
        assert categorize_file_type("video/webm") == "video"

    def test_audio(self):
        assert categorize_file_type("audio/mpeg") == "audio"

    def test_document(self):
        assert categorize_file_type("application/pdf") == "document"
        assert categorize_file_type("text/plain") == "document"

    def test_archive(self):
        assert categorize_file_type("application/zip") == "archive"
        assert categorize_file_type("application/x-rar-compressed") == "archive"
        assert categorize_file_type("application/x-7z-compressed") == "archive"
        assert categorize_file_type("application/gzip") == "archive"
        assert categorize_file_type("application/x-tar") == "archive"

    def test_other(self):
        assert categorize_file_type("application/octet-stream") == "other"


class TestAllowedMimeTypes:
    def test_common_types_present(self):
        expected = {
            "image/jpeg",
            "image/png",
            "video/mp4",
            "audio/mpeg",
            "application/pdf",
            "text/plain",
            "application/zip",
        }
        assert expected.issubset(ALLOWED_MIME_TYPES)

    def test_dangerous_types_absent(self):
        dangerous = {
            "application/x-shellscript",
            "application/x-python",
            "text/x-php",
        }
        assert not dangerous.intersection(ALLOWED_MIME_TYPES)


class TestDetectRealMimeType:
    @pytest.mark.asyncio
    async def test_fallback_to_declared_for_unknown_content(self):
        buf = io.BytesIO(b"\x00\x00\x00\x00")
        result = await detect_real_mime_type(buf, "application/octet-stream")
        assert result == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_text_content_detected(self):
        buf = io.BytesIO(b"hello world")
        result = await detect_real_mime_type(buf, "application/octet-stream")
        assert result in ("text/plain", "application/octet-stream")


class _FakeSession:
    def __init__(self, value: int | None) -> None:
        self._value = value

    async def scalar(self, _stmt: object) -> int | None:
        return self._value


class TestCountFiles:
    @pytest.mark.asyncio
    async def test_uses_request_session(self):
        from app.services import file_service

        assert await file_service._count_files(_FakeSession(7), []) == 7

    @pytest.mark.asyncio
    async def test_none_result_becomes_zero(self):
        from app.services import file_service

        assert await file_service._count_files(_FakeSession(None), []) == 0


class _FakeRow:
    def __init__(self, created_at: datetime | None = None, deleted_at: datetime | None = None):
        self.created_at = created_at
        self.deleted_at = deleted_at


class _FakeScalars:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows

    def all(self) -> list[_FakeRow]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _PagingSession:
    def __init__(self, rows: list[_FakeRow], total: int | None) -> None:
        self._rows = rows
        self._total = total
        self.count_calls = 0
        self.execute_calls = 0

    async def scalar(self, _stmt: object) -> int | None:
        self.count_calls += 1
        return self._total

    async def execute(self, _stmt: object) -> _FakeResult:
        self.execute_calls += 1
        return _FakeResult(self._rows)


def _ts(day: int) -> datetime:
    return datetime(2024, 1, day, tzinfo=UTC)


class TestPaginate:
    @pytest.mark.asyncio
    async def test_cached_total_skips_count_query(self):
        from app.services import file_service

        db = _PagingSession([_FakeRow(_ts(1))], total=99)
        with patch.object(file_service, "redis_client") as mock_redis:
            mock_redis.hget = AsyncMock(return_value="5")
            mock_redis.hset = AsyncMock()
            mock_redis.expire = AsyncMock()

            files, total, _ = await file_service._paginate(
                db,
                filters=[],
                order_cols=[],
                cursor_col=None,
                cursor_attr="created_at",
                cursor=None,
                skip=0,
                limit=20,
                cache_field="k",
            )

        assert db.count_calls == 0
        assert db.execute_calls == 1
        assert total == 5
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_uncached_total_counts_and_stores(self):
        from app.services import file_service

        db = _PagingSession([], total=3)
        with patch.object(file_service, "redis_client") as mock_redis:
            mock_redis.hget = AsyncMock(return_value=None)
            mock_redis.hset = AsyncMock()
            mock_redis.expire = AsyncMock()

            _, total, _ = await file_service._paginate(
                db,
                filters=[],
                order_cols=[],
                cursor_col=None,
                cursor_attr="created_at",
                cursor=None,
                skip=0,
                limit=20,
                cache_field="k",
            )

        assert db.count_calls == 1
        assert total == 3
        mock_redis.hset.assert_awaited_once_with(file_service._CACHE_HASH_KEY, "k", "3")
        mock_redis.expire.assert_awaited_once_with(file_service._CACHE_HASH_KEY, file_service._CACHE_TTL)

    @pytest.mark.asyncio
    async def test_next_cursor_when_more_pages_remain(self):
        from app.services import file_service

        db = _PagingSession([_FakeRow(_ts(2)), _FakeRow(_ts(1))], total=5)
        with patch.object(file_service, "redis_client") as mock_redis:
            mock_redis.hget = AsyncMock(return_value=None)
            mock_redis.hset = AsyncMock()
            mock_redis.expire = AsyncMock()

            _, _, next_cursor = await file_service._paginate(
                db,
                filters=[],
                order_cols=[],
                cursor_col=None,
                cursor_attr="created_at",
                cursor=None,
                skip=0,
                limit=2,
                cache_field="k",
            )

        assert next_cursor == _ts(1).isoformat()

    @pytest.mark.asyncio
    async def test_no_next_cursor_on_last_page(self):
        from app.services import file_service

        db = _PagingSession([_FakeRow(_ts(2)), _FakeRow(_ts(1))], total=2)
        with patch.object(file_service, "redis_client") as mock_redis:
            mock_redis.hget = AsyncMock(return_value=None)
            mock_redis.hset = AsyncMock()
            mock_redis.expire = AsyncMock()

            _, _, next_cursor = await file_service._paginate(
                db,
                filters=[],
                order_cols=[],
                cursor_col=None,
                cursor_attr="created_at",
                cursor=None,
                skip=0,
                limit=2,
                cache_field="k",
            )

        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_null_timestamp_yields_no_cursor(self):
        from app.services import file_service

        db = _PagingSession([_FakeRow(deleted_at=None)], total=9)
        with patch.object(file_service, "redis_client") as mock_redis:
            mock_redis.hget = AsyncMock(return_value=None)
            mock_redis.hset = AsyncMock()
            mock_redis.expire = AsyncMock()

            _, _, next_cursor = await file_service._paginate(
                db,
                filters=[],
                order_cols=[],
                cursor_col=None,
                cursor_attr="deleted_at",
                cursor=None,
                skip=0,
                limit=1,
                cache_field="k",
            )

        assert next_cursor is None
