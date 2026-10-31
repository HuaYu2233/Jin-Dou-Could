"""
阶段四验证脚本:用户缓存脱敏测试

验证目标:
1. _serialize_user 序列化结果不含敏感字段
2. _deserialize_user 反序列化后敏感字段为 None
3. 缓存保留鉴权必需字段
4. invalidate_user_cache helper 存在且可调用

运行方式:
    cd /Users/zero/project/JinDou-Cloud/backend
    pytest tests/test_user_cache_desensitize.py -v
    或
    python -m tests.test_user_cache_desensitize
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

import uuid
from datetime import UTC, datetime

from app.api.deps import (
    USER_CACHE_TTL,
    _deserialize_user,
    _serialize_user,
    invalidate_user_cache,
)
from app.models.user import User

SENSITIVE_FIELDS = ("hashed_password", "security_question", "security_answer")
REQUIRED_FIELDS = (
    "id",
    "email",
    "username",
    "is_active",
    "is_admin",
    "avatar_key",
    "storage_quota",
    "used_storage",
    "created_at",
    "updated_at",
)


def _make_fake_user() -> User:
    user = User()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.username = "testuser"
    user.hashed_password = "$2b$12$FAKE_HASH_SHOULD_NOT_LEAK"
    user.is_active = True
    user.is_admin = False
    user.avatar_key = "avatars/test.png"
    user.security_question = "你的宠物叫什么"
    user.security_answer = "$2b$12$FAKE_ANSWER_HASH_SHOULD_NOT_LEAK"
    user.storage_quota = 3221225472
    user.used_storage = 1024
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    return user


def test_serialize_excludes_sensitive_fields():
    print("\n[测试 1] 序列化结果不含敏感字段")
    import json

    user = _make_fake_user()
    data = json.loads(_serialize_user(user))
    leaked = [f for f in SENSITIVE_FIELDS if f in data]
    assert not leaked, f"无敏感字段泄露 (泄露字段: {leaked or '无'})"


def test_serialize_keeps_required_fields():
    print("\n[测试 2] 序列化结果保留鉴权必需字段")
    import json

    user = _make_fake_user()
    data = json.loads(_serialize_user(user))
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    assert not missing, f"必需字段齐全 (缺失: {missing or '无'})"


def test_deserialize_sensitive_fields_are_none():
    print("\n[测试 3] 反序列化后敏感字段为 None(防御性)")
    user = _make_fake_user()
    restored = _deserialize_user(_serialize_user(user))
    assert restored.hashed_password is None, f"hashed_password is None (实际: {restored.hashed_password!r})"
    assert restored.security_question is None, f"security_question is None (实际: {restored.security_question!r})"
    assert restored.security_answer is None, f"security_answer is None (实际: {restored.security_answer!r})"


def test_deserialize_preserves_required_fields():
    print("\n[测试 4] 反序列化后必需字段正确还原")
    user = _make_fake_user()
    restored = _deserialize_user(_serialize_user(user))
    checks = [
        (restored.id == user.id, "id 一致"),
        (restored.email == user.email, "email 一致"),
        (restored.username == user.username, "username 一致"),
        (restored.is_active == user.is_active, "is_active 一致"),
        (restored.is_admin == user.is_admin, "is_admin 一致"),
        (restored.avatar_key == user.avatar_key, "avatar_key 一致"),
        (restored.storage_quota == user.storage_quota, "storage_quota 一致"),
        (restored.used_storage == user.used_storage, "used_storage 一致"),
    ]
    failed = [m for ok, m in checks if not ok]
    assert not failed, f"必需字段还原一致 (不一致: {failed or '无'})"


def test_invalidate_cache_helper_exists():
    print("\n[测试 5] invalidate_user_cache helper 存在且可调用")
    assert callable(invalidate_user_cache), (
        f"invalidate_user_cache 是可调用对象 (类型: {type(invalidate_user_cache).__name__})"
    )


def test_cache_ttl_is_reasonable():
    print("\n[测试 6] 缓存 TTL 合理(>0 且 ≤300)")
    assert 0 < USER_CACHE_TTL <= 300, f"USER_CACHE_TTL={USER_CACHE_TTL}s (合理范围 1-300)"


def run_all() -> int:
    print("=" * 60)
    print("阶段四:用户缓存脱敏验证")
    print("=" * 60)

    tests = [
        test_serialize_excludes_sensitive_fields,
        test_serialize_keeps_required_fields,
        test_deserialize_sensitive_fields_are_none,
        test_deserialize_preserves_required_fields,
        test_invalidate_cache_helper_exists,
        test_cache_ttl_is_reasonable,
    ]

    results = []
    for test in tests:
        try:
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
    print("\n提示:若测试 1/3 失败,请确认已接受 deps.py 的脱敏 diff")
    return 1


if __name__ == "__main__":
    sys.exit(run_all())
