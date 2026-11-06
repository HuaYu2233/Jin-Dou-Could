# 测试文档

## 1. 概述

| 模块 | 框架   | 测试数量 | 目录            |
| ---- | ------ | -------- | --------------- |
| 后端 | pytest | 246      | backend/tests/  |
| 前端 | vitest | 46       | frontend/tests/ |

## 2. 后端测试

### 2.1 运行方式

```bash
cd backend

# 全部测试
uv run pytest tests/ -v

# 按模块运行
uv run pytest tests/test_service_user.py -v
uv run pytest tests/test_service_auth.py -v
uv run pytest tests/test_service_file.py -v
uv run pytest tests/test_service_share.py -v
uv run pytest tests/test_schemas.py -v
uv run pytest tests/test_deps.py -v
uv run pytest tests/test_api_auth.py -v
uv run pytest tests/test_api_files.py -v
uv run pytest tests/test_middleware.py -v

# 安全专项测试
uv run python -m tests.test_token_type
uv run python -m tests.test_user_cache_desensitize
uv run python -m tests.test_upload_security
uv run python -m tests.test_share_rate_limit
uv run python -m tests.test_search_escape
```

> 门禁命令统一使用 `uv run pytest -q`（与 CI 一致）；上述安全专项脚本带 `__main__` 入口，便于单独快速验证。

### 2.2 测试分类

| 文件                           | 类型       | 说明                      |
| ------------------------------ | ---------- | ------------------------- |
| test_service_user.py           | Service    | 用户服务单元测试          |
| test_service_auth.py           | Service    | 认证服务单元测试          |
| test_service_file.py           | Service    | 文件服务单元测试          |
| test_service_share.py          | Service    | 分享服务单元测试          |
| test_core_client_ip.py         | Core       | 客户端 IP 解析测试        |
| test_core_smtp.py              | Core       | SMTP 发信测试             |
| test_celery_app.py             | Core       | Celery 配置与任务注册测试 |
| test_schemas.py                | Schema     | Pydantic 模型验证测试     |
| test_deps.py                   | Deps       | 依赖注入测试              |
| test_api_auth.py               | API        | 认证 API 集成测试         |
| test_api_files.py              | API        | 文件/文件夹/分享 API 测试 |
| test_middleware.py             | Middleware | 中间件测试                |
| test_request_logging.py        | Middleware | 请求日志中间件测试        |
| test_exceptions.py             | Exception  | 异常处理与统一响应测试    |
| test_storage_multipart.py      | Storage    | MinIO 分片上传测试        |
| test_ws_manager.py             | Core       | WebSocket 连接管理测试    |
| test_token_type.py             | Security   | Token 类型校验            |
| test_user_cache_desensitize.py | Security   | 用户缓存脱敏测试          |
| test_upload_security.py        | Security   | 上传安全（MIME/文件名）   |
| test_share_rate_limit.py       | Security   | 分享提取码防爆破测试      |
| test_search_escape.py          | Security   | 搜索注入防护测试          |

### 2.3 测试配置

测试配置位于 `tests/conftest.py`，提供：

- `event_loop`（session 级）：独立事件循环
- `fake_user` / `fake_admin`：测试用户对象（不落库）
- `auth_headers` / `admin_headers`：对应的 JWT 认证头
- `mock_db`：AsyncMock 数据库会话
- `mock_redis`：patch `app.core.redis.redis_client`
- `api_client`：基于 `ASGITransport` 的异步 HTTP 客户端

conftest 同时通过 `os.environ.setdefault` 兜底测试所需环境变量（`SECRET_KEY`、`DATABASE_URL`、`REDIS_URL`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`ENVIRONMENT`、`CSRF_ENABLED`、`TRUSTED_PROXIES`）。

### 2.4 测试环境变量

`tests/_env.py` 集中声明默认值（`setup_env()` 用 `os.environ.setdefault` 注入，pytest 由 `conftest.py` 自动调用）：

```env
SECRET_KEY=test-secret-key-for-verification-only-at-least-32-chars!!
DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test_db
REDIS_URL=redis://localhost:6379/15
MINIO_ACCESS_KEY=test-access-key
MINIO_SECRET_KEY=test-secret-key
ENVIRONMENT=test
CSRF_ENABLED=false
TRUSTED_PROXIES=127.0.0.1,testclient
```

CI 环境变量（`.github/workflows/ci.yml`）覆盖数据库与 Redis 地址：

```env
DATABASE_URL=postgresql+asyncpg://testuser:testpass@localhost:5432/testdb
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test-secret-key-that-is-long-enough-32chars
ENVIRONMENT=test
CSRF_ENABLED=false
```

> `SECRET_KEY` 需 ≥32 字符且不能命中弱值名单，否则 `Settings` 校验直接失败。独立运行 `python -m tests.xxx` 时，脚本内的 `setup_env()` 会补齐所需变量。

## 3. 前端测试

### 3.1 运行方式

```bash
cd frontend

# 全部测试
npm run test

# 监听模式
npm run test:watch

# 按模块运行
npx vitest run tests/utils/format.test.ts
npx vitest run tests/lib/i18n.test.ts
npx vitest run tests/stores/auth.test.ts
npx vitest run tests/stores/transfers.test.ts
npx vitest run tests/stores/i18n.test.ts
```

### 3.2 测试分类

| 文件                            | 类型  | 说明                 |
| ------------------------------- | ----- | -------------------- |
| tests/utils/format.test.ts      | 工具  | 格式化函数测试       |
| tests/lib/i18n.test.ts          | i18n  | 翻译完整性测试       |
| tests/lib/refresh.test.ts       | Lib   | Token 刷新逻辑测试   |
| tests/lib/csrf.test.ts          | Lib   | CSRF Token 处理测试  |
| tests/lib/hydration.test.tsx    | Lib   | 客户端水合测试       |
| tests/lib/session.test.ts       | Lib   | 会话生命周期测试     |
| tests/components/Header.test.tsx | 组件 | Header 交互测试      |
| tests/stores/auth.test.ts       | Store | Auth store 测试      |
| tests/stores/transfers.test.ts  | Store | Transfers store 测试 |
| tests/stores/i18n.test.ts       | Store | i18n store 测试      |

### 3.3 测试配置

- `vitest.config.ts`：`environment: "jsdom"`、`globals: true`
- 仅收集 `tests/**/*.test.ts` 与 `tests/**/*.test.tsx`
- `@` 别名指向 `frontend/` 根目录，与 Next.js 的 `tsconfig` paths 保持一致
- 使用 `@testing-library/react` + `@testing-library/jest-dom`

## 4. CI/CD 测试

### 4.1 GitHub Actions

配置文件：`.github/workflows/ci.yml`

| 阶段               | 触发条件 | 内容                          |
| ------------------ | -------- | ----------------------------- |
| Backend Lint       | push/PR  | `ruff check .` + `ruff format --check .` |
| Backend Test       | push/PR  | `pytest` 246 个测试 + 覆盖率  |
| Frontend Lint      | push/PR  | next lint (ESLint)            |
| Frontend TypeCheck | push/PR  | tsc --noEmit                  |
| Frontend Test      | push/PR  | vitest run 46 个测试          |

触发条件：push 到 `main` / `dev`，或向 `main` 发起 PR。

### 4.2 测试服务

CI 使用 GitHub Actions Service Containers：

- PostgreSQL 16-alpine
- Redis 7-alpine

## 5. 编写测试指南

### 5.1 后端测试

单元测试通过 `mock_db` / `mock_redis` 隔离外部依赖，不落库：

```python
import pytest
from app.services import user_service

@pytest.mark.asyncio
async def test_create_user(mock_db):
    user = await user_service.create_user(mock_db, UserCreate(
        email="test@example.com",
        username="test",
        password="Test123456",
    ))
    assert user.email == "test@example.com"
    assert user.is_active is True
```

API 集成测试使用 `api_client` 与 `auth_headers`：

```python
@pytest.mark.asyncio
async def test_get_me(api_client, auth_headers):
    resp = await api_client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"
```

### 5.2 前端测试

```typescript
import { describe, it, expect } from "vitest";
import { formatFileSize } from "@/lib/utils/format";

describe("formatFileSize", () => {
  it("formats bytes correctly", () => {
    expect(formatFileSize(1024)).toBe("1 KB");
  });
});
```

### 5.3 编写规范

- **必须用 `assert` 表达断言**，禁止 `return` 断言结果。pytest 收到非 `None` 返回值只发 `PytestReturnNotNoneWarning`，不会判失败，会产生「假绿」
- **禁止 `except Exception: pass` 包住模块导入**：导入失败会被静默吞掉，测试表面通过、实际全部未生效
- 用 `importlib` 动态加载模块做断言前，先确认目标符号的真实位置（本项目经历过 service 层与 endpoint 层重构）
- 布尔列断言用 `is True` / `is False`，与 ORM 层的 `.is_(True)` 语义保持一致
- 涉及 libmagic 的用例需构造完整的文件头（例如带 IHDR/IDAT/IEND 的最小 PNG），仅有签名会被识别为 `text/plain`

## 6. 测试覆盖率

建议保持以下覆盖率目标：

| 模块        | 目标覆盖率 |
| ----------- | ---------- |
| services/   | ≥ 80%      |
| api/        | ≥ 70%      |
| middleware/ | ≥ 80%      |
| stores/     | ≥ 70%      |