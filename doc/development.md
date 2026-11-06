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
make dev              # 启动（db/redis/minio/pgbouncer/backend/frontend）
make dev-restart      # 重建 backend + frontend
make hot-reload       # 用 docker cp 同步后端代码，触发 uvicorn --reload
make down             # 停止
make logs             # 跟随 backend + frontend 日志
```

> 开发模式不启动 `celery-worker`（Celery 走 Eager 同步执行），也不启动 `backup` / `nginx` / 监控组件。需要真实 Worker 时用 `make prod`。

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
- Python 3.12+ 语法（`requires-python = ">=3.12"`，ruff `target-version = "py312"`）
- 行宽 120 字符（ruff `line-length = 120`）
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

# 安全专项（也可直接通过 pytest 运行）
uv run python -m tests.test_token_type
uv run python -m tests.test_user_cache_desensitize
uv run python -m tests.test_upload_security
uv run python -m tests.test_share_rate_limit
uv run python -m tests.test_search_escape
```

### 3.6 代码检查

提交前必须全部通过（与 CI 一致）：

```bash
cd backend

# Lint
uv run ruff check .

# 格式检查（只检查不修改）
uv run ruff format --check .

# 测试
uv run pytest -q
```

需要自动格式化时执行 `uv run ruff format .`，格式化后必须重跑 `pytest` 确认行为未变。

> 本项目未引入 pyright，类型检查依赖 ruff 与 pytest。

### 3.7 注册 Celery 任务

新增任务模块后，必须在 `app/core/celery_app.py` 的 `_TASK_MODULES` 列表中显式登记：

```python
_TASK_MODULES = [
    "app.tasks.alert_tasks",
    "app.tasks.backup_tasks",
    "app.tasks.email_tasks",
    "app.tasks.thumbnail_tasks",
]

celery_app = Celery("jindou_cloud", broker=_broker_url, backend=_backend_url, include=_TASK_MODULES)
```

Worker 通过 `include` 导入任务模块，未登记的模块不会出现在 `celery inspect registered` 列表中，任务调用会静默丢失。验证方式：

```bash
docker compose logs celery-worker | grep "tasks\]" -A 10
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

查询 key 统一在 `lib/query/keys.ts` 中定义，业务 Hook 位于对应页面目录（如 `app/dashboard/hooks/useFileList.ts`）：

```typescript
// lib/query/keys.ts
export const queryKeys = {
  files: {
    all: ["files"] as const,
    list: (params: { category: string; page: number; folderId: string | null; keyword: string }) =>
      [...queryKeys.files.all, "list", params] as const,
  },
};

// app/dashboard/hooks/useFileList.ts
const queryKey = queryKeys.files.list({ category, page, folderId: currentFolderId, keyword: debouncedKeyword });

const { data, isLoading, error, refetch } = useQuery<FileListResult>({
  queryKey,
  enabled,
  queryFn: async () => {
    const cursor = page > 1 ? cursorMap[page - 1] : undefined;
    if (debouncedKeyword) return searchFiles(debouncedKeyword, (page - 1) * PAGE_SIZE, PAGE_SIZE, cursor);
    if (category === "all") return listFolderContents(currentFolderId ?? undefined, (page - 1) * PAGE_SIZE, PAGE_SIZE);
    if (category === "trash") return Promise.all([listTrashFiles(...), listTrashFolders(...)]);
    return listFiles((page - 1) * PAGE_SIZE, PAGE_SIZE, category, cursor);
  },
});
```

要点：

- 同一个 Hook 内按 `category` 与是否有 `keyword` 分流到不同接口，返回结构由 Hook 归一化为 `FileListResult`
- `next_cursor` 存入 `cursorMap` 按页码缓存，仅用于 `page > 1` 的翻页请求，避免深分页退化
- 关键词做 300ms 防抖后再进入 `queryKey`，避免每次按键触发请求

> 缓存 key 只描述查询参数，不含用户身份。用户维度的数据必须在登出时随缓存一并清空，见 4.8。

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

### 4.8 会话边界约定

TanStack Query 的缓存 key 不含用户身份，因此缓存与登录会话必须绑定。登出清理集中在 `app/dashboard/layout.tsx` 的未认证分支：

```tsx
useEffect(() => {
  if (isLoading) return;
  if (!isAuthenticated) {
    queryClient.clear();
    useNotificationStore.getState().clearAll();
    router.replace("/login");
  }
}, [isAuthenticated, isLoading, router, queryClient]);
```

新增约束：

- 新增按用户维度存放的客户端状态（Zustand store、模块级变量、localStorage）时，必须同步加入上述清理分支
- 登出请求必须**先** `await logoutApi()` 等服务端删除 Cookie，再清本地状态并跳转；顺序颠倒会与 proxy 的 Cookie 校验产生跳转回弹
- 清理使用 `queryClient.clear()`，不要用 `invalidateQueries()`，后者会用旧 Cookie 再打一轮请求

### 4.9 新增文件分类

文件分类横跨前后端，新增一个分类需同步改动以下位置：

| 位置                                       | 改动                                         |
| ------------------------------------------ | -------------------------------------------- |
| `backend/app/services/file_validation.py`  | `_ARCHIVE_MIME_TYPES` 等集合与 `ALLOWED_MIME_TYPES` |
| `backend/tests/test_service_file.py`       | 分类映射用例                                 |
| `frontend/app/dashboard/types.ts`          | `CategoryId` 联合类型                        |
| `frontend/app/dashboard/components/Sidebar.tsx` | `NAV_ITEMS` 导航项                     |
| `frontend/lib/i18n/locales/{zh-CN,zh-TW,en}.ts` | `sidebar.<category>` 词条，三份必须同步 |

> `file_type` 在上传时推导并落库，调整分类规则不会重新归类历史文件。需要纠正存量数据时必须单独写迁移脚本。

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
3. 在 `app/core/celery_app.py` 的 `_TASK_MODULES` 中登记模块（否则 Worker 不会加载，见 3.7）
4. 在服务层调用 `task.delay()` 或 `task.apply_async()`
5. 重建 Worker 使新模块生效：`docker compose up -d --force-recreate celery-worker`

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