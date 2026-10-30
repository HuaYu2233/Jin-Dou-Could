# 测试文档

## 1. 概述

| 模块 | 框架   | 测试数量 | 目录            |
| ---- | ------ | -------- | --------------- |
| 后端 | pytest | 162      | backend/tests/  |
| 前端 | vitest | 28       | frontend/tests/ |

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
```

### 2.2 测试分类

| 文件                           | 类型       | 说明                      |
| ------------------------------ | ---------- | ------------------------- |
| test_service_user.py           | Service    | 用户服务单元测试          |
| test_service_auth.py           | Service    | 认证服务单元测试          |
| test_service_file.py           | Service    | 文件服务单元测试          |
| test_service_share.py          | Service    | 分享服务单元测试          |
| test_schemas.py                | Schema     | Pydantic 模型验证测试     |
| test0test_deps.py              | Deps       | 依赖注入测试              |
| test_api_auth.py               | API        | 认证 API 集成测试         |
| test_api_files.py              | API        | 文件/文件夹/分享 API 测试 |
| test_middleware.py             | Middleware | 中间件测试                |
| test_token_type.py             | Security   | Token 类型校验            |
| test_user_cache_desensitize.py | Security   | 用户缓存脱敏测试          |
| test_upload_security.py        | Security   | 上传安全（MIME/文件名）   |
| test_share_rate_limit.py       | Security   | 分享提取码防爆破测试      |
| test_search_escape.py          | Security   | 搜索注入防护测试          |

### 2.3 测试配置

测试配置位于 `tests/conftest.py`，提供：

- 异步数据库会话 fixture
- 测试用户 fixture
- 测试文件 fixture
- Mock MinIO 客户端

### 2.4 CI 环境变量

```env
DATABASE_URL=postgresql+asyncpg://testuser:testpass@localhost:5432/testdb
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test-secret-key
ENVIRONMENT=test
CSRF_ENABLED=false
```

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

| 文件                           | 类型  | 说明                 |
| ------------------------------ | ----- | -------------------- |
| tests/utils/format.test.ts     | 工具  | 格式化函数测试       |
| tests/lib/i18n.test.ts         | i18n  | 翻译完整性测试       |
| tests/stores/auth.test.ts      | Store | Auth store 测试      |
| tests/stores/transfers.test.ts | Store | Transfers store 测试 |
| tests/stores/i18n.test.ts      | Store | i18n store 测试      |

### 3.3 测试配置

- `vitest.config.ts` - Vitest 配置
- 使用 `jsdom` 环境
- `@testing-library/react` + `@testing-library/jest-dom`

## 4. CI/CD 测试

### 4.1 GitHub Actions

配置文件：`.github/workflows/ci.yml`

| 阶段               | 触发条件 | 内容                 |
| ------------------ | -------- | -------------------- |
| Backend Test       | push/PR  | pytest 162 个测试    |
| Frontend Lint      | push/PR  | next lint (ESLint)   |
| Frontend TypeCheck | push/PR  | tsc --noEmit         |
| Frontend Test      | push/PR  | vitest run 28 个测试 |

### 4.2 测试服务

CI 使用 GitHub Actions Service Containers：

- PostgreSQL 16-alpine
- Redis 7-alpine

## 5. 编写测试指南

###> 5.1 后端测试

```python
import pytest
from app.services import user_service

@pytest.mark.asyncio
async def test_create_user(db_session):
    user = await user_service.create_user(db_session, UserCreate(
        email="test@example.com",
        username="test",
        password="Test123456",
    ))
    assert user.email == "test@example.com"
    assert user.is_active is True
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

## 6. 测试覆盖率

建议保持以下覆盖率目标：

| 模块        | 目标覆盖率 |
| ----------- | ---------- |
| services/   | ≥ 80%      |
| api/        | ≥ 70%      |
| middleware/ | ≥ 80%      |
| stores/     | ≥ 70%      |
