import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

import pytest

from app.core.config import settings
from app.core.exceptions import AppError
from app.services import env_config_service

ENV_SAMPLE = """# ==================== 基础 ====================
# 应用运行环境
ENVIRONMENT=production
SECRET_KEY=0123456789abcdef0123456789abcdef01234567

# ==================== MinIO ====================
# 对象存储访问密钥
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=secret
"""


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / ".env"
    path.write_text(ENV_SAMPLE, encoding="utf-8")
    monkeypatch.setattr(settings, "ENV_FILE_PATH", str(path))
    return path


class TestEnvConfigService:
    def test_is_enabled(self, env_file: Path):
        assert env_config_service.is_enabled() is True

    def test_get_config_parses_groups(self, env_file: Path):
        result = env_config_service.get_config()
        assert result["enabled"] is True
        assert result["path"] == str(env_file)
        names = [g["name"] for g in result["groups"]]
        assert "基础" in names
        assert "MinIO" in names
        fields = {f["key"]: f for g in result["groups"] for f in g["fields"]}
        assert fields["SECRET_KEY"]["sensitive"] is True
        assert fields["SECRET_KEY"]["required"] is True
        assert fields["MINIO_ROOT_USER"]["required"] is True
        assert fields["MINIO_ROOT_PASSWORD"]["required"] is True

    def test_save_config_roundtrip(self, env_file: Path):
        values = {
            "ENVIRONMENT": "staging",
            "SECRET_KEY": "a" * 40,
            "MINIO_ROOT_USER": "new-admin",
            "MINIO_ROOT_PASSWORD": "new-secret",
        }
        result = env_config_service.save_config(values)
        assert result["ok"] is True
        assert "- bak" not in result["backup"]
        assert ".env.bak." in result["backup"]
        content = env_file.read_text(encoding="utf-8")
        assert "ENVIRONMENT=staging" in content
        assert "MINIO_ROOT_USER=new-admin" in content

    def test_save_config_rejects_weak_secret(self, env_file: Path):
        values = {
            "SECRET_KEY": "change-me-in-production",
            "MINIO_ROOT_USER": "admin",
            "MINIO_ROOT_PASSWORD": "secret",
        }
        with pytest.raises(AppError) as exc:
            env_config_service.save_config(values)
        assert exc.value.details["errors"]

    def test_generate_sensitive_values_length(self):
        values = env_config_service.generate_sensitive_values()
        for key in ("SECRET_KEY", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"):
            assert len(values[key]) >= 32
