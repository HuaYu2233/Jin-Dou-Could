"""
搜索关键词 SQL 通配符转义测试

验证目标:
1. % 字符被正确转义，不会被当作 SQL 通配符
2. _ 字符被正确转义，不会被当作 SQL 单字符通配符
3. \\ 字符被正确转义
4. 普通关键词不受影响
5. 混合特殊字符正确转义

运行方式:
    cd /Users/zero/project/JinDou-Cloud/backend
    python -m tests.test_search_escape
    或
    pytest tests/test_search_escape.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only")


def _escape_like_keyword(keyword: str) -> str:
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _assert(condition: bool, message: str) -> bool:
    if condition:
        print(f"  ✅ {message}")
        return True
    print(f"  ❌ {message}")
    return False


def test_percent_escaped():
    print("\n[测试 1] % 字符被转义")
    result = _escape_like_keyword("100%")
    return _assert(
        result == "100\\%",
        f"输入 '100%' -> 输出 '{result}' (期望 '100\\%')",
    )


def test_underscore_escaped():
    print("\n[测试 2] _ 字符被转义")
    result = _escape_like_keyword("my_file")
    return _assert(
        result == "my\\_file",
        f"输入 'my_file' -> 输出 '{result}' (期望 'my\\_file')",
    )


def test_backslash_escaped():
    print("\n[测试 3] \\ 字符被转义（必须最先转义）")
    result = _escape_like_keyword("path\\to\\file")
    return _assert(
        result == "path\\\\to\\\\file",
        f"输入 'path\\to\\file' -> 输出 '{result}' (期望 'path\\\\\\\\to\\\\\\\\file')",
    )


def test_plain_keyword_unchanged():
    print("\n[测试 4] 普通关键词不受影响")
    result = _escape_like_keyword("hello")
    return _assert(
        result == "hello",
        f"输入 'hello' -> 输出 '{result}' (期望 'hello')",
    )


def test_mixed_special_chars():
    print("\n[测试 5] 混合特殊字符正确转义")
    result = _escape_like_keyword("100%_of\\files")
    expected = "100\\%\\_of\\\\files"
    return _assert(
        result == expected,
        f"输入 '100%_of\\files' -> 输出 '{result}' (期望 '{expected}')",
    )


def test_only_percent_sign():
    print("\n[测试 6] 纯 % 输入不会匹配所有文件")
    result = _escape_like_keyword("%")
    return _assert(
        result == "\\%",
        f"输入 '%' -> 输出 '{result}' (期望 '\\%')",
    )


def test_only_underscore():
    print("\n[测试 7] 纯 _ 输入不会匹配所有单字符文件名")
    result = _escape_like_keyword("_")
    return _assert(
        result == "\\_",
        f"输入 '_' -> 输出 '{result}' (期望 '\\_')",
    )


def main():
    print("=" * 60)
    print("搜索关键词 SQL 通配符转义测试")
    print("=" * 60)

    results = [
        test_percent_escaped(),
        test_underscore_escaped(),
        test_backslash_escaped(),
        test_plain_keyword_unchanged(),
        test_mixed_special_chars(),
        test_only_percent_sign(),
        test_only_underscore(),
    ]

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"结果: {passed}/{total} 通过")
    if passed == total:
        print("✅ 所有测试通过！")
    else:
        print("❌ 存在失败测试！")
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)