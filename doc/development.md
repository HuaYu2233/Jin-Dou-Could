# 开发指南

## 1. 环境准备

### 1.1 系统要求

| 软件           | 版本 |
| -------------- | ---- |
| Docker         | 20+  |
| Docker Compose | 2.0+ |
| Git            | -    |

### 1.2 初始化项目

```bash
git clone <repository-url>
cd JinDou-Cloud

# 复制配置模板
cp .env.example .env
# 编辑 .env，修改密码和密钥

# 启用 Git 性能优化
make setup

# 首次构建镜像（约 5 分钟）
make prod-build

# 开发模式启动
make dev
```

## 2. 开发模式

开发模式使用 `docker-compose.dev.yml` 覆盖生产配置：

| 特性         | 说明                                 |
| ------------ | ------------------------------------ |
| 热重载       | 后端 uvicorn --reload，前端 next dev |
| Volume 挂载  | 代码修改实时生效，无需重新构建       |
| Celery Eager | 任务同步执行，无需独立 Worker        |
| 调试日志     | LOG_LEVEL=DEBUG                      |

### 2.1 启动/停止

```bash
make dev              # 启动
make dev-restart      # 重启 backend + frontend
make down             # 停止
make logs             # 查看日志
```

### 2.2 热更新

后端代码修改后 uvicorn 自动检测并重载。如需手动同步：

```bash
make hot-reload
```

## 3. 后端开发

### 3.1 项目结构

```
backend/app/
├── api/v1/endpoints/   # 路由端点
├── core/               # 核心模块
├── db/                 # 数据库连接
├── middleware/         # 中间件
├── models/             # SQLAlchemy 模型
├── schemas/            # Pydantic Schema
├── services/           # 业务逻辑
├── tasks/              # Celery 异步任务
└── main.py             # 应用入口
```

### 3.2 添加新 API 端点

1. **定义模型**（如需新表）：`models/` 下创建或修改模型文件

2. **生成迁移**：

```bash
docker compose exec backend alembic revision --autogenerate -m "add xxx table"
docker compose exec backend alembic upgrade head
```

3. **定义 Schema**：`schemas/` 下创建请求/响应模型

4. **实现服务逻辑**：`services/` 下创建服务函数

5. **定义路由**：`api/v1/endpoints/` 下创建端点文件

6. **注册路由**：在 `api/v1/api.py` 中 include_router

### 3.3 代码规范

- 使用 `uv` 管理依赖（`pyproject.toml`）
- 类型注解：Python 3.9+ 语法
- 异步优先：所有数据库操作使用 `async`/`await`
- 服务层分离：路由层不直接操作数据库

### 3.4 依赖管理

```bash
# 添加依赖
cd backend
uv add <package-name>

# 安装依赖
uv sync
```

### 3.5 运行测试

```bash
cd backend

# 全部测试
uv run pytest tests/ -v

# 按模块
uv run pytest tests/test_service_user.py -v
uv run pytest tests/test_api_auth.py -v
uv run pytest tests/test_middleware.py -v

# 安全专项
uv run python -m tests.test_token_type
uv run python -m tests.test_upload_security
```

### 3.6 代码检查

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run pyright
```

## 4. 前端开发

### 4.1 项目结构

```
frontend/
├── app/                # Next.js App Router 页面
│   ├── (auth)/         # 认证相关页面
│   ├── admin/          # 管理后台
│   ├── dashboard/      # 主界面
│   ├── profile/        # 用户中心
│   └── share/          # 分享页面
├── lib/                # 工具库
│   ├── api/            # API 封装
│   ├── hooks/          # 自定义 Hooks
│   ├── i18n/           # 国际化
│   ├── query/          # TanStack Query
│   └── utils/          # 工具函数
├── stores/             # Zustand 状态管理
└── tests/              # 测试
```

### 4.2 添加新页面

1. 在 `app/` 下创建目录和 `page.tsx`
2. 如需布局，创建 `layout.tsx`
3. 样式使用 Tailwind CSS + CSS Modules（`*.module.css`）

### 4.3 API 调用

使用 TanStack Query 进行数据请求和缓存：

```typescript
// lib/query/useFiles.ts
export const useFileList = (params) => {
  return useQuery({
    queryKey: [QUERY_KEYS.files, params],
    queryFn: () => fetchFiles(params),
    staleTime: 30_000,
  });
};
```

### 4.4 状态管理

使用 Zustand 创建 store：

```typescript
// stores/xxx.ts
import { create } from "zustand";

const useXxxStore = create((set) => ({
  data: null,
  setData: (data) => set({ data }),
}));
```

### 4.5 国际化

翻译文件位于 `lib/i18n/locales/`：

- `zh-CN.ts` - 简体中文
- `zh-TW.ts` - 繁体中文
- `en.ts` - 英文

添加新翻译时需同步更新三个文件。

### 4.6 运行测试

```bash
cd frontend

# 全部测试
npm run test

# 监听模式
npm run test:watch

# 按模块
npx vitest run tests/utils/format.test.ts
npx vitest run tests/stores/auth.test.ts
```

### 4.7 代码检查

```bash
# Lint
npm run lint

# Type check
npx tsc --noEmit

# Build
npm run build
```

## 5. 数据库迁移

### 5.1 生成迁移

```bash
docker compose exec backend alembic revision --autogenerate -m "描述"
```

### 5.2 执行迁移

```bash
docker compose exec backend alembic upgrade head
```

### 5.3 回滚迁移

```bash
docker compose exec backend alembic downgrade -1  # 回滚一个版本
```

### 5.4 查看迁移历史

```bash
docker compose exec backend alembic history
docker compose exec backend alembic current
```

## 6. 异步任务开发

### 6.1 添加新任务

1. 在 `tasks/` 下创建任务文件
2. 使用 `@celery_app.task` 装饰器
3. 在服务层调用 `task.delay()` 或 `task.apply_async()`

### 6.2 查看任务状态

```bash
# 活跃任务
docker compose exec celery-worker celery -A app.core.celery_app:celery_app inspect active

# 等待任务
docker compose exec celery-worker celery -A app.core.celery_app:celery_app inspect reserved
```

## 7. WebSocket 开发

### 7.1 发送消息

在服务层使用 `ws_manager`：

```python
from app.core.ws_manager import ws_manager

await ws_manager.send_to_user(str(user_id), "event:type", {
    "key": "value",
})
```

### 7.2 前端接收

使用 `useWebSocket` hook：

```typescript
const { lastEvent } = useWebSocket();
// 监听事件并处理
```

## 8. Git 工作流

### 8.1 分支策略

| 分支       | 用途     |
| ---------- | -------- |
| main       | 生产发布 |
| dev        | 开发集成 |
| feature/\* | 功能开发 |
| fix/\*     | 修复     |

### 8.2 提交规范

```
type(scope): description

type: feat | fix | docs | style | refactor | test | chore
scope: backend | frontend | infra | db
```

示例：

```
feat(backend): add file version history
fix(frontend): fix upload progress display
chore(infra): update docker compose config
```
