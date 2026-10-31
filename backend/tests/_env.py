"""测试环境变量共享入口。

pytest 运行时由 conftest.py 注入,独立脚本(python -m tests.xxx)自行调用 setup_env(),
集中定义可避免各文件重复声明同一批变量、取值漂移。
"""

import os

TEST_ENV = {
    "SECRET_KEY": "test-secret-key-for-verification-only-at-least-32-chars!!",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
    "REDIS_URL": "redis://localhost:6379/15",
    "MINIO_ACCESS_KEY": "test-access-key",
    "MINIO_SECRET_KEY": "test-secret-key",
    "ENVIRONMENT": "test",
    "CSRF_ENABLED": "false",
    "TRUSTED_PROXIES": "127.0.0.1,testclient",
}


def setup_env() -> None:
    for key, value in TEST_ENV.items():
        os.environ.setdefault(key, value)
