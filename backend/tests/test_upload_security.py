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
    python -m tests.test_upload_security
    或
    pytest tests/test_upload_security.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only")

import io
from app.services.file_service import (
    sanitize_filename,
    detect_real_mime_type,
    validate_mime_type,
    ALLOWED_MIME_TYPES,
)

def _assert(condition: bool, message: str) -> bool:
    if condition:
        print(f"  ✅ {message}")
        return True
    print(f"  ❌ {message}")
    return False

def test_sanitize_truncates_long_name():
    print("\n[测试 1] 超长文件名截断到 255")
    long_name = "a" * 300 + ".txt"
    result = sanitize_filename(long_name)
    return _assert(
        len(result) == 255,
        f"截断后长度={len(result)} (期望 255)",
    )

def test_sanitize_strips_control_chars():
    print("\n[测试 2] 去除控制字符")
    result = sanitize_filename("file\x00\x01\x1f\x7f.txt")
    return _assert(
        result == "file.txt",
        f"结果='{result}' (期望 'file.txt')",
    )

def test_sanitize_blocks_path_traversal():
    print("\n[测试 3] 去除路径分隔符(防目录穿越)")
    result = sanitize_filename("../../../etc/passwd")
    has_no_sep = "/" not in result and "\\" not in result
    has_no_traversal = "../" not in result and "..\\" not in result
    return _assert(
        has_no_sep and has_no_traversal,
        f"结果='{result}' (无路径分隔符,无目录穿越)",
    )

def test_sanitize_strips_leading_trailing_dots_spaces():
    print("\n[测试 4] 去除首尾空格和点(防 dotfile 滥用)")
    result = sanitize_filename("  .hidden.  ")
    return _assert(
        not result.startswith(".") and not result.endswith(".") and not result.startswith(" "),
        f"结果='{result}' (无首尾点/空格)",
    )

def test_sanitize_empty_name_fallback():
    print("\n[测试 5] 空文件名回退为 unknown")
    result = sanitize_filename("")
    return _assert(
        result == "unknown",
        f"结果='{result}' (期望 'unknown')",
    )

def test_detect_real_mime_png():
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
    detected = detect_real_mime_type(buf, "image/jpeg")
    return _assert(
        detected == "image/png",
        f"探测结果='{detected}' (期望 'image/png')",
    )

def test_detect_real_mime_pdf():
    print("\n[测试 7] 探测 PDF 真实类型")
    pdf_header = b"%PDF-1.4\n" + b"\x00" * 100
    buf = io.BytesIO(pdf_header)
    detected = detect_real_mime_type(buf, "application/octet-stream")
    return _assert(
        detected == "application/pdf",
        f"探测结果='{detected}' (期望 'application/pdf')",
    )

def test_validate_rejects_disallowed_type():
    print("\n[测试 8] 拒绝非白名单类型")
    try:
        validate_mime_type("application/x-msdownload", "application/x-msdownload")
        return _assert(False, "未拒绝非白名单类型")
    except ValueError as e:
        return _assert(True, f"正确拒绝: {e}")

def test_validate_rejects_mismatch():
    print("\n[测试 9] 拒绝声明与实际不符")
    try:
        validate_mime_type("image/png", "application/pdf")
        return _assert(False, "未拒绝类型不符")
    except ValueError as e:
        return _assert(True, f"正确拒绝: {e}")

def test_validate_accepts_compatible():
    print("\n[测试 10] 兼容 octet-stream 声明")
    try:
        validate_mime_type("application/octet-stream", "image/png")
        return _assert(True, "兼容 octet-stream 声明")
    except ValueError as e:
        return _assert(False, f"误拒兼容类型: {e}")

def test_allowed_mime_covers_common_types():
    print("\n[测试 11] 白名单覆盖常见类型")
    required = {"image/png", "image/jpeg", "video/mp4", "audio/mpeg", "application/pdf"}
    missing = required - ALLOWED_MIME_TYPES
    return _assert(
        not missing,
        f"缺失: {missing or '无'}",
    )

def run_all():
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
    ]

    results = [t() for t in tests]
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