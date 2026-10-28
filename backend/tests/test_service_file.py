import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
import io
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.services.file_service import (
    sanitize_filename,
    detect_real_mime_type,
    validate_mime_type,
    categorize_file_type,
    ALLOWED_MIME_TYPES,
    _FILENAME_MAX_LEN,
)
from app.models.user import User
from app.models.file import File
from app.core.security import hash_password


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
        with pytest.raises(ValueError, match="不允许的文件类型"):
            validate_mime_type("image/jpeg", "application/x-shellscript")

    def test_mismatch_raises(self):
        with pytest.raises(ValueError, match="文件类型与声明不符"):
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

    def test_other(self):
        assert categorize_file_type("application/octet-stream") == "other"


class TestAllowedMimeTypes:
    def test_common_types_present(self):
        expected = {
            "image/jpeg", "image/png", "video/mp4", "audio/mpeg",
            "application/pdf", "text/plain", "application/zip",
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