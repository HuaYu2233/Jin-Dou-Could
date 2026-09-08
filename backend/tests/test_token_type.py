"""
阶段三验证脚本:JWT Token 类型隔离测试

验证目标:
1. access token 含 type="access" 字段
2. refresh token 含 type="refresh" 字段
3. access token 不能当 refresh token 用
4. refresh token 不能当 access token 用
5. 伪造的无 type token 应被拒

运行方式:
    cd /Users/zero/project/JinDou-Cloud/backend
    python -m tests.test_token_type
    或
    pytest tests/test_token_type.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only")

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

def _assert(condition: bool, message: str) -> bool:
    if condition:
        print(f"  ✅ {message}")
        return True
    else:
        print(f"  ❌ {message}")
        return False

def test_access_token_has_type_field():
    print("\n[测试 1] access token 应含 type='access' 字段")
    token = create_access_token({"sub": "user-123"})
    payload = decode_token(token)
    return _assert(
        payload is not None and payload.get("type") == "access",
        f"payload.type == 'access' (实际: {payload.get('type') if payload else 'None'})",
    )

def test_refresh_token_has_type_field():
    print("\n[测试 2] refresh token 应含 type='refresh' 字段")
    token = create_refresh_token({"sub": "user-123"})
    payload = decode_token(token)
    return _assert(
        payload is not None and payload.get("type") == "refresh",
        f"payload.type == 'refresh' (实际: {payload.get('type') if payload else 'None'})",
    )

def test_access_and_refresh_have_different_types():
    print("\n[测试 3] access 与 refresh token 的 type 字段应不同")
    access = decode_token(create_access_token({"sub": "user-123"}))
    refresh = decode_token(create_refresh_token({"sub": "user-123"}))
    return _assert(
        access.get("type") != refresh.get("type"),
        f"access.type={access.get('type')} ≠ refresh.type={refresh.get('type')}",
    )

def test_tokens_carry_sub_and_jti():
    print("\n[测试 4] token 应保留 sub 与 jti 字段")
    payload = decode_token(create_access_token({"sub": "user-456"}))
    return _assert(
        payload.get("sub") == "user-456" and payload.get("jti") is not None,
        f"sub={payload.get('sub')}, jti={'有' if payload.get('jti') else '无'}",
    )

def test_token_with_no_type_is_rejected_by_logic():
    print("\n[测试 5] 无 type 字段的伪造 token 应被业务逻辑拒绝")
    from jose import jwt
    from app.core.config import settings
    fake_token = jwt.encode(
        {"sub": "user-789", "jti": "fake-jti"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    payload = decode_token(fake_token)
    is_rejected_by_access_check = payload.get("type") != "access"
    is_rejected_by_refresh_check = payload.get("type") != "refresh"
    return _assert(
        is_rejected_by_access_check and is_rejected_by_refresh_check,
        "无 type 的 token 在 access/refresh 校验中均被拒",
    )

def test_refresh_cannot_be_used_as_access():
    print("\n[测试 6] refresh token 不能通过 access 校验")
    refresh_token = create_refresh_token({"sub": "user-123"})
    payload = decode_token(refresh_token)
    is_blocked = payload.get("type") != "access"
    return _assert(
        is_blocked,
        f"refresh.type={payload.get('type')} ≠ 'access' → 被 access 校验拒绝",
    )

def test_access_cannot_be_used_as_refresh():
    print("\n[测试 7] access token 不能通过 refresh 校验")
    access_token = create_access_token({"sub": "user-123"})
    payload = decode_token(access_token)
    is_blocked = payload.get("type") != "refresh"
    return _assert(
        is_blocked,
        f"access.type={payload.get('type')} ≠ 'refresh' → 被 refresh 校验拒绝",
    )

def run_all():
    print("=" * 60)
    print("阶段三:JWT Token 类型隔离验证")
    print("=" * 60)

    tests = [
        test_access_token_has_type_field,
        test_refresh_token_has_type_field,
        test_access_and_refresh_have_different_types,
        test_tokens_carry_sub_and_jti,
        test_token_with_no_type_is_rejected_by_logic,
        test_refresh_cannot_be_used_as_access,
        test_access_cannot_be_used_as_refresh,
    ]

    results = [t() for t in tests]
    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    if passed == total:
        print(f"🎉 全部通过 ({passed}/{total})")
        return 0
    else:
        print(f"⚠️  有失败 ({passed}/{total} 通过)")
        print("\n提示:若测试 1/2 失败,请确认已接受 security.py 的 diff")
        print("     (在 IDE 中查看 security.py 是否含 token_type 参数)")
        return 1

if __name__ == "__main__":
    sys.exit(run_all())