"""
阶段五验证脚本:上传安全加固测试

验证目标:
1. sanitize_filename 截断超长文件名
2. sanitize_filename 去除控制字符
3. sanitize_filename 去除路径分隔符(防目录穿越)
4. sanitize_filename 去除首尾空格和点
5. detect_real_mime_type 探测真实类型
6. validate_mime_type 拒绝非白名单类型
7. validate_mime_type 拒绝声明与实际不符
8. ALLOWED_MIME_TYPES 包含常见类型

运行方式:
    cd /Users/zero/project/JinDou-Cloud/backend
    pytest tests/test_upload_security.py -v
    或
    python -m tests.test_upload_security
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

import asyncio
import inspect
import io
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import AppError
from app.services.file_validation import (
    ALLOWED_MIME_TYPES,
    detect_real_mime_type,
    sanitize_filename,
    validate_mime_type,
)


def test_sanitize_truncates_long_name():
    print("\n[测试 1] 超长文件名截断到 255")
    long_name = "a" * 300 + ".txt"
    result = sanitize_filename(long_name)
    assert len(result) == 255, f"截断后长度={len(result)} (期望 255)"


def test_sanitize_strips_control_chars():
    print("\n[测试 2] 去除控制字符")
    result = sanitize_filename("file\x00\x01\x1f\x7f.txt")
    assert result == "file.txt", f"结果='{result}' (期望 'file.txt')"


def test_sanitize_blocks_path_traversal():
    print("\n[测试 3] 去除路径分隔符(防目录穿越)")
    result = sanitize_filename("../../../etc/passwd")
    has_no_sep = "/" not in result and "\\" not in result
    has_no_traversal = "../" not in result and "..\\" not in result
    assert has_no_sep and has_no_traversal, f"结果='{result}' (无路径分隔符,无目录穿越)"


def test_sanitize_strips_leading_trailing_dots_spaces():
    print("\n[测试 4] 去除首尾空格和点(防 dotfile 滥用)")
    result = sanitize_filename("  .hidden.  ")
    assert not result.startswith(".") and not result.endswith(".") and not result.startswith(" "), (
        f"结果='{result}' (无首尾点/空格)"
    )


def test_sanitize_empty_name_fallback():
    print("\n[测试 5] 空文件名回退为 unknown")
    result = sanitize_filename("")
    assert result == "unknown", f"结果='{result}' (期望 'unknown')"


async def test_detect_real_mime_png():
    print("\n[测试 6] 探测 PNG 真实类型")
    png_header = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01"
        b"\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90w\x53\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    buf = io.BytesIO(png_header)
    detected = await detect_real_mime_type(buf, "image/jpeg")
    assert detected == "image/png", f"探测结果='{detected}' (期望 'image/png')"


async def test_detect_real_mime_pdf():
    print("\n[测试 7] 探测 PDF 真实类型")
    pdf_header = b"%PDF-1.4\n" + b"\x00" * 100
    buf = io.BytesIO(pdf_header)
    detected = await detect_real_mime_type(buf, "application/octet-stream")
    assert detected == "application/pdf", f"探测结果='{detected}' (期望 'application/pdf')"


def test_validate_rejects_disallowed_type():
    print("\n[测试 8] 拒绝非白名单类型")
    try:
        validate_mime_type("application/x-msdownload", "application/x-msdownload")
    except AppError as exc:
        print(f"  ✅ 正确拒绝: {exc}")
    else:
        raise AssertionError("未拒绝非白名单类型")


def test_validate_rejects_mismatch():
    print("\n[测试 9] 拒绝声明与实际不符")
    try:
        validate_mime_type("image/png", "application/pdf")
    except AppError as exc:
        print(f"  ✅ 正确拒绝: {exc}")
    else:
        raise AssertionError("未拒绝类型不符")


def test_validate_accepts_compatible():
    print("\n[测试 10] 兼容 octet-stream 声明")
    try:
        validate_mime_type("application/octet-stream", "image/png")
    except AppError as exc:
        raise AssertionError(f"误拒兼容类型: {exc}") from exc


def test_allowed_mime_covers_common_types():
    print("\n[测试 11] 白名单覆盖常见类型")
    required = {"image/png", "image/jpeg", "video/mp4", "audio/mpeg", "application/pdf"}
    missing = required - ALLOWED_MIME_TYPES
    assert not missing, f"缺失: {missing or '无'}"


async def test_detect_keeps_unlisted_type():
    print("\n[测试 12] 探测到非白名单类型时不回退声明值")
    with patch("magic.from_buffer", return_value="application/x-msdownload"):
        detected = await detect_real_mime_type(io.BytesIO(b"MZ" + b"\x00" * 64), "application/octet-stream")
    assert detected == "application/x-msdownload", f"探测结果='{detected}' (期望保留真实类型)"


def test_validate_rejects_unlisted_detected():
    print("\n[测试 13] 真实类型不在白名单时即使声明合法也拒绝")
    try:
        validate_mime_type("text/plain", "application/x-msdownload")
    except AppError as exc:
        print(f"  ✅ 正确拒绝: {exc}")
    else:
        raise AssertionError("未拒绝非白名单的真实类型")


def test_validate_accepts_mime_alias():
    print("\n[测试 14] 接受白名单别名类型")
    try:
        validate_mime_type("audio/mpeg", "audio/mp3")
    except AppError as exc:
        raise AssertionError(f"误拒白名单别名: {exc}") from exc


async def test_multipart_init_rejects_disallowed_mime():
    print("\n[测试 15] 分片上传初始化拒绝非白名单 MIME")
    from app.services import file_multipart

    owner = MagicMock()
    owner.id = "owner"
    try:
        await file_multipart.init_multipart_upload(owner, "evil.exe", "application/x-msdownload", 1024)
    except AppError as exc:
        print(f"  ✅ 正确拒绝: {exc}")
    else:
        raise AssertionError("分片上传未校验 MIME 白名单")


async def test_detect_fails_closed():
    print("\n[测试 16] 检测组件异常时拒绝而非放行")
    with patch("magic.from_buffer", side_effect=RuntimeError("boom")), pytest.raises(AppError):
        await detect_real_mime_type(io.BytesIO(b"%PDF-1.4"), "application/pdf")


def test_validate_accepts_text_subtype():
    print("\n[测试 17] 接受 libmagic 细分的文本子类型")
    for mime in ("text/x-python", "text/x-shellscript", "text/x-c", "text/xml"):
        try:
            validate_mime_type(mime, mime)
        except AppError as exc:
            raise AssertionError(f"误拒文本子类型 {mime}: {exc}") from exc
    try:
        validate_mime_type("text/plain", "text/x-script.python")
    except AppError as exc:
        raise AssertionError(f"误拒声明 text/plain 与实际文本子类型: {exc}") from exc


async def test_multipart_complete_requires_session():
    print("\n[测试 18] 分片上传会话缺失时拒绝合并")
    from app.services import file_multipart

    owner = MagicMock()
    owner.id = "owner"
    with patch.object(file_multipart, "redis_client") as mock_redis:
        mock_redis.hgetall = AsyncMock(return_value={})
        with pytest.raises(AppError):
            await file_multipart.complete_multipart_upload(
                db=AsyncMock(),
                owner=owner,
                upload_id="upload-1",
                storage_key="owner/key",
                filename="evil.exe",
                mime_type="application/x-msdownload",
                total_size=1024,
                parts=[{"PartNumber": 1, "ETag": "etag-1"}],
            )


async def test_multipart_complete_rejects_storage_key_mismatch():
    print("\n[测试 19] 分片上传完成时拒绝 storage_key 与会话不符")
    from app.services import file_multipart

    owner = MagicMock()
    owner.id = "owner"
    state = {
        "file_id": str(uuid4()),
        "storage_key": "owner/real",
        "filename": "a.txt",
        "real_mime_type": "text/plain",
        "total_size": "1024",
    }
    with patch.object(file_multipart, "redis_client") as mock_redis:
        mock_redis.hgetall = AsyncMock(return_value=state)
        with pytest.raises(AppError):
            await file_multipart.complete_multipart_upload(
                db=AsyncMock(),
                owner=owner,
                upload_id="upload-1",
                storage_key="owner/other",
                filename="a.txt",
                mime_type="text/plain",
                total_size=1024,
                parts=[{"PartNumber": 1, "ETag": "etag-1"}],
            )


async def test_multipart_part_rejects_part_number_out_of_range():
    print("\n[测试 20] 分片序号超出声明片数时拒绝")
    from app.services import file_multipart

    owner = MagicMock()
    owner.id = "owner"
    state = {"storage_key": "owner/key", "total_size": "1024", "total_parts": "1", "mime_type": "text/plain"}
    with patch.object(file_multipart, "redis_client") as mock_redis:
        mock_redis.hgetall = AsyncMock(return_value=state)
        with pytest.raises(AppError):
            await file_multipart.upload_multipart_part("owner/key", "upload-1", 2, b"x" * 16, owner.id)


async def test_multipart_part_rejects_exceeding_declared_size():
    print("\n[测试 21] 已上传数据超过声明大小时拒绝")
    from app.services import file_multipart

    owner = MagicMock()
    owner.id = "owner"
    state = {
        "storage_key": "owner/key",
        "total_size": "100",
        "total_parts": "1",
        "mime_type": "text/plain",
        "uploaded_bytes": "0",
    }
    with patch.object(file_multipart, "redis_client") as mock_redis:
        mock_redis.hgetall = AsyncMock(return_value=state)
        with pytest.raises(AppError):
            await file_multipart.upload_multipart_part("owner/key", "upload-1", 1, b"x" * 101, owner.id)


async def test_multipart_complete_rejects_part_count_mismatch():
    print("\n[测试 22] 分片数量与声明不符时拒绝合并")
    from app.services import file_multipart

    owner = MagicMock()
    owner.id = "owner"
    state = {
        "file_id": str(uuid4()),
        "storage_key": "owner/real",
        "filename": "a.txt",
        "real_mime_type": "text/plain",
        "total_size": "1024",
        "part_size": "512",
        "total_parts": "2",
        "part_1": "etag-1",
    }
    with patch.object(file_multipart, "redis_client") as mock_redis:
        mock_redis.hgetall = AsyncMock(return_value=state)
        with pytest.raises(AppError):
            await file_multipart.complete_multipart_upload(
                db=AsyncMock(),
                owner=owner,
                upload_id="upload-1",
                storage_key="owner/real",
                filename="a.txt",
                mime_type="text/plain",
                total_size=1024,
                parts=[{"PartNumber": 1, "ETag": "etag-1"}],
            )


async def test_multipart_complete_rejects_actual_size_mismatch():
    print("\n[测试 23] 合并后实际大小与声明不符时删除对象并拒绝")
    from app.services import file_multipart

    owner = MagicMock()
    owner.id = "owner"
    state = {
        "file_id": str(uuid4()),
        "storage_key": "owner/real",
        "filename": "a.txt",
        "real_mime_type": "text/plain",
        "total_size": "1024",
        "part_size": "512",
        "total_parts": "1",
        "part_1": "etag-1",
    }
    with (
        patch.object(file_multipart, "redis_client") as mock_redis,
        patch.object(file_multipart, "complete_multipart", new=AsyncMock()),
        patch.object(file_multipart, "head_object_size", new=AsyncMock(return_value=50 * 1024 * 1024)),
        patch.object(file_multipart, "delete_file", new=AsyncMock()) as mock_delete,
    ):
        mock_redis.hgetall = AsyncMock(return_value=state)
        with pytest.raises(AppError):
            await file_multipart.complete_multipart_upload(
                db=AsyncMock(),
                owner=owner,
                upload_id="upload-1",
                storage_key="owner/real",
                filename="a.txt",
                mime_type="text/plain",
                total_size=1024,
                parts=[{"PartNumber": 1, "ETag": "etag-1"}],
            )
    mock_delete.assert_awaited_once_with("owner/real")


def run_all() -> int:
    print("=" * 60)
    print("阶段五:上传安全加固验证")
    print("=" * 60)

    tests = [
        test_sanitize_truncates_long_name,
        test_sanitize_strips_control_chars,
        test_sanitize_blocks_path_traversal,
        test_sanitize_strips_leading_trailing_dots_spaces,
        test_sanitize_empty_name_fallback,
        test_detect_real_mime_png,
        test_detect_real_mime_pdf,
        test_validate_rejects_disallowed_type,
        test_validate_rejects_mismatch,
        test_validate_accepts_compatible,
        test_allowed_mime_covers_common_types,
        test_detect_keeps_unlisted_type,
        test_validate_rejects_unlisted_detected,
        test_validate_accepts_mime_alias,
        test_multipart_init_rejects_disallowed_mime,
        test_detect_fails_closed,
        test_validate_accepts_text_subtype,
        test_multipart_complete_requires_session,
        test_multipart_complete_rejects_storage_key_mismatch,
        test_multipart_part_rejects_part_number_out_of_range,
        test_multipart_part_rejects_exceeding_declared_size,
        test_multipart_complete_rejects_part_count_mismatch,
        test_multipart_complete_rejects_actual_size_mismatch,
    ]

    results = []
    for test in tests:
        try:
            if inspect.iscoroutinefunction(test):
                asyncio.run(test())
            else:
                test()
        except AssertionError as exc:
            print(f"  ❌ {test.__name__}: {exc}")
            results.append(False)
        else:
            results.append(True)

    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    if passed == total:
        print(f"🎉 全部通过 ({passed}/{total})")
        return 0
    print(f"⚠️  有失败 ({passed}/{total} 通过)")
    print("\n提示:若测试 6/7 失败,可能是 python-magic 未安装")
    print("     执行: pip install python-magic")
    print("     macOS 需额外: brew install libmagic")
    return 1


if __name__ == "__main__":
    sys.exit(run_all())
