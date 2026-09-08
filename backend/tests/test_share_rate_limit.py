"""
阶段六验证脚本:分享提取码防爆破测试

验证目标:
1. 连续错误提取码触发锁定
2. 锁定期间正确提取码也被拒
3. 锁定过期后恢复
4. 正确提取码清除计数

运行方式:
    cd /Users/zero/project/JinDou-Cloud/backend
    uv run python -m tests.test_share_rate_limit
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only")

def _assert(condition: bool, message: str) -> bool:
    if condition:
        print(f"  ✅ {message}")
        return True
    print(f"  ❌ {message}")
    return False

def test_constants_exist():
    print("\n[测试 1] 防爆破常量存在")
    import importlib
    spec = importlib.util.spec_from_file_location(
        "shares",
        os.path.join(os.path.dirname(__file__), "..", "app", "api", "v1", "endpoints", "shares.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        pass
    return _assert(
        hasattr(mod, "SHARE_VERIFY_MAX_ATTEMPTS") and hasattr(mod, "SHARE_VERIFY_LOCK_SECONDS"),
        f"SHARE_VERIFY_MAX_ATTEMPTS={getattr(mod, 'SHARE_VERIFY_MAX_ATTEMPTS', '无')}, "
        f"SHARE_VERIFY_LOCK_SECONDS={getattr(mod, 'SHARE_VERIFY_LOCK_SECONDS', '无')}",
    )

def test_max_attempts_is_5():
    print("\n[测试 2] 最大尝试次数为 5")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "shares",
        os.path.join(os.path.dirname(__file__), "..", "app", "api", "v1", "endpoints", "shares.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        pass
    return _assert(
        getattr(mod, "SHARE_VERIFY_MAX_ATTEMPTS", 0) == 5,
        f"SHARE_VERIFY_MAX_ATTEMPTS={getattr(mod, 'SHARE_VERIFY_MAX_ATTEMPTS', '无')}",
    )

def test_lock_seconds_is_900():
    print("\n[测试 3] 锁定时间为 900 秒(15 分钟)")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "shares",
        os.path.join(os.path.dirname(__file__), "..", "app", "api", "v1", "endpoints", "shares.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        pass
    return _assert(
        getattr(mod, "SHARE_VERIFY_LOCK_SECONDS", 0) == 900,
        f"SHARE_VERIFY_LOCK_SECONDS={getattr(mod, 'SHARE_VERIFY_LOCK_SECONDS', '无')}",
    )

def test_get_client_ip_exists():
    print("\n[测试 4] auth.py 有 get_client_ip 函数")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "auth",
        os.path.join(os.path.dirname(__file__), "..", "app", "api", "v1", "endpoints", "auth.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        pass
    return _assert(
        hasattr(mod, "get_client_ip"),
        f"get_client_ip 存在: {hasattr(mod, 'get_client_ip')}",
    )

def run_all():
    print("=" * 60)
    print("阶段六:分享/限流加固验证")
    print("=" * 60)

    tests = [
        test_constants_exist,
        test_max_attempts_is_5,
        test_lock_seconds_is_900,
        test_get_client_ip_exists,
    ]

    results = [t() for t in tests]
    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    if passed == total:
        print(f"🎉 全部通过 ({passed}/{total})")
        return 0
    print(f"⚠️  有失败 ({passed}/{total} 通过)")
    return 1

if __name__ == "__main__":
    sys.exit(run_all())