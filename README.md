# JinDou Cloud（筋斗云盘）

基于 Docker Compose 的全栈云存储应用，支持文件上传/下载、文件夹管理、文件分享、传输进度追踪、管理后台等功能。

## 技术栈

### 前端

| 技术           | 版本            | 用途           |
| -------------- | --------------- | -------------- |
| Next.js        | 16              | React 全栈框架 |
| React          | 19              | UI 库          |
| Zustand        | 5               | 状态管理       |
| TanStack Query | 5               | 请求缓存       |
| react-virtuoso | 4               | 虚拟滚动       |
| WebSocket      | 原生            | 实时通知       |
| Tailwind CSS   | 4 + CSS Modules | 样式方案       |
| TypeScript     | 5               | 类型安全       |
| Vitest         | 5               | 单元测试       |

### 后端

| 技术         | 版本        | 用途                  |
| ------------ | ----------- | --------------------- |
| FastAPI      | 0.128+      | Web 框架              |
| SQLAlchemy   | 2.0（异步） | ORM                   |
| Alembic      | 1.16+       | 数据库迁移            |
| python-jose  | 3.3+        | JWT 认证              |
| bcrypt       | 4.2         | 密码哈希              |
| MinIO        | 7.2+        | S3 兼容对象存储客户端 |
| Celery       | 5.4+        | 异步任务队列          |
| Loguru       | 0.7+        | 结构化日志            |
| python-magic | 0.4+        | MIME 类型检测         |
| Python       | 3.9+        | 运行时                |

### 基础设施

| 组件           | 版本   | 用途                                       |
| -------------- | ------ | ------------------------------------------ |
| PostgreSQL     | 15     | 关系数据库                                 |
| Redis          | 7      | 缓存 / 限流 / Token 黑名单 / Celery Broker |
| MinIO          | latest | 对象存储                                   |
| Nginx          | -      | 反向代理（可选）                           |
| Docker Compose | 2.0+   | 容器编排                                   |

## 项目结构

```
JinDou-Cloud/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 路由
│   │   │   ├── endpoints/      # auth, files, folders, shares, users, admin, health
│   │   │   └── api.py          # 路由聚合
│   │   ├── core/               # config, security, storage, logging, redis, alerting, celery_app
│   │   ├── db/                 # 数据库引擎与会话
│   │   ├── middleware/         # rate_limit, request_logging, security_headers
│   │   ├── models/             # SQLAlchemy 模型（user, file, folder, share）
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── services/           # 业务逻辑层
│   │   ├── tasks/              # Celery 异步任务（email, backup, thumbnail, alert）
│   │   └── main.py             # 应用入口
│   ├── alembic/                # 数据库迁移
│   ├── tests/                  # 测试套件（162 个测试）
│   ├── pyproject.toml          # 依赖声明（uv 管理）
│   ├── uv.lock                 # 依赖锁定文件
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/                   # Next.js 前端
│   ├── app/
│   │   ├── (auth)/             # 登录/注册/忘记密码
│   │   ├── admin/              # 管理后台（统计、用户管理、备份管理）
│   │   ├── dashboard/          # 主界面
│   │   │   ├── components/     # UI 组件
│   │   │   └── hooks/         # useFileList, useFileOperations
│   │   ├── profile/            # 用户中心
│   │   └── share/[token]/      # 分享访问页
│   ├── lib/
│   │   ├── api/                # API 封装（client, auth, files, admin）
│   │   ├── i18n/               # 国际化（zh-CN, zh-TW, en）
│   │   └── utils/              # 工具函数（format, image）
│   ├── stores/                 # Zustand stores（auth, transfers, i18n）
│   ├── tests/                  # 测试套件（28 个测试）
│   ├── vitest.config.ts        # Vitest 配置
│   ├── package.json
│   ├── Dockerfile
│   └── .dockerignore
├── nginx/                      # Nginx 配置（可选）
├── scripts/                    # 备份/恢复脚本 + Dockerfile.backup
├── backups/                    # 备份输出目录
├── .env.example                # 配置模板
├── .gitignore
└── docker-compose.yml
```

## 快速开始

### 前置要求

- Docker 20+
- Docker Compose 2.0+

### 部署步骤

```bash
# 1. 克隆仓库
git clone <repository-url>
cd JinDou-Cloud

# 2. 复制配置模板并编辑
cp .env.example .env
# 编辑 .env，修改密码和密钥

# 3. 启动所有服务（开发模式，自动加载 docker-compose.override.yml）
docker compose up -d --build

# 4. 查看启动日志
docker compose logs -f backend
```

启动完成后访问：

| 服务                | 地址                       |
| ------------------- | -------------------------- |
| 前端                | http://localhost:3000      |
| 后端 API            | http://localhost:8000      |
| API 文档（Swagger） | http://localhost:8000/docs |
| MinIO 控制台        | http://localhost:9001      |
| PostgreSQL          | localhost:5433             |
| Redis               | localhost:6379             |

> **开发 vs 生产**：`docker compose up` 默认合并 `docker-compose.override.yml`（热重载 + volume 挂载）；生产部署使用 `docker compose -f docker-compose.yml up`（构建产物运行，无 volume）。

### 默认账号

首次启动后通过注册页面创建账号，或使用 `.env` 中配置的数据库凭据直接连接 PostgreSQL。

## 配置说明

所有配置通过 `.env` 文件管理，参考 `.env.example`：

### 数据库与存储

| 配置项                | 说明         | 默认值     |
| --------------------- | ------------ | ---------- |
| `POSTGRES_USER`       | 数据库用户名 | clouduser  |
| `POSTGRES_PASSWORD`   | 数据库密码   | -          |
| `POSTGRES_DB`         | 数据库名     | clouddrive |
| `REDIS_PASSWORD`      | Redis 密码   | -          |
| `MINIO_ROOT_USER`     | MinIO 用户名 | minioadmin |
| `MINIO_ROOT_PASSWORD` | MinIO 密码   | -          |

### JWT 与认证

| 配置项                        | 说明                     | 默认值 |
| ----------------------------- | ------------------------ | ------ |
| `SECRET_KEY`                  | JWT 签名密钥（≥32 字符） | -      |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 过期时间    | 30     |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh Token 过期时间   | 7      |

### 前端与网络

| 配置项                | 说明                     | 默认值                |
| --------------------- | ------------------------ | --------------------- |
| `NEXT_PUBLIC_API_URL` | 浏览器访问后端地址       | http://localhost:8000 |
| `API_URL`             | Docker 内部后端地址      | http://backend:8000   |
| `CORS_ORIGINS`        | 允许的前端源（逗号分隔） | http://localhost:3000 |

### 管理与配额

| 配置项                  | 说明                     | 默认值            |
| ----------------------- | ------------------------ | ----------------- |
| `ADMIN_EMAIL`           | 自动成为管理员的邮箱     | -                 |
| `MAX_USERS`             | 最大注册用户数（0=不限） | 0                 |
| `DEFAULT_STORAGE_QUOTA` | 新用户默认配额（字节）   | 1073741824（1GB） |

### 日志与告警

| 配置项                | 说明              | 默认值  |
| --------------------- | ----------------- | ------- |
| `LOG_LEVEL`           | 日志级别          | INFO    |
| `LOG_DIR`             | 日志目录          | logs    |
| `LOG_RETENTION_DAYS`  | 日志保留天数      | 30      |
| `ALERT_ENABLED`       | 启用日志告警      | false   |
| `ALERT_WEBHOOK_URL`   | 告警 Webhook 地址 | -       |
| `ALERT_WEBHOOK_TYPE`  | Webhook 类型      | generic |
| `ALERT_EMAIL_ENABLED` | 启用邮件告警      | false   |

### 备份

| 配置项                  | 说明                       | 默认值      |
| ----------------------- | -------------------------- | ----------- |
| `BACKUP_RETENTION_DAYS` | 备份保留天数               | 7           |
| `BACKUP_CRON`           | 备份 Cron 表达式           | `0 3 * * *` |
| `BACKUP_ENCRYPT_KEY`    | 备份加密密钥（留空不加密） | -           |

### Celery 异步任务队列

| 配置项                      | 说明                                            | 默认值 |
| --------------------------- | ----------------------------------------------- | ------ |
| `CELERY_BROKER_URL`         | Broker URL（留空自动从 `REDIS_URL` 派生 DB1）   | -      |
| `CELERY_RESULT_BACKEND_URL` | 结果后端 URL（留空自动从 `REDIS_URL` 派生 DB2） | -      |
| `CELERY_TASK_ALWAYS_EAGER`  | Eager 模式（同步执行，仅开发/测试用）           | false  |
| `CELERY_CONCURRENCY`        | Worker 并发数                                   | 4      |

### 性能与安全

| 配置项                     | 说明                         | 默认值 |
| -------------------------- | ---------------------------- | ------ |
| `BACKEND_WORKERS`          | Gunicorn worker 进程数       | 4      |
| `DB_POOL_SIZE`             | 数据库连接池大小             | 5      |
| `DB_MAX_OVERFLOW`          | 连接池溢出上限               | 5      |
| `DB_POOL_TIMEOUT`          | 获取连接超时（秒）           | 30     |
| `DB_MAX_CONNECTIONS`       | PostgreSQL 最大连接数        | 80     |
| `HTTPS_REDIRECT`           | 强制 HTTPS 重定向            | false  |
| `SECURITY_HEADERS_ENABLED` | 启用安全响应头               | true   |
| `RATE_LIMIT_ENABLED`       | 启用全局限流                 | true   |
| `RATE_LIMIT_PER_MINUTE`    | 每分钟每 IP 每路径最大请求数 | 60     |

### 密码找回

| 配置项                               | 说明               | 默认值 |
| ------------------------------------ | ------------------ | ------ |
| `RESET_PASSWORD_SMTP_HOST`           | SMTP 服务器        | -      |
| `RESET_PASSWORD_SMTP_PORT`           | SMTP 端口          | 465    |
| `RESET_PASSWORD_CODE_EXPIRE_SECONDS` | 验证码有效期（秒） | 600    |
| `RESET_PASSWORD_CODE_LENGTH`         | 验证码位数         | 6      |

### 迁移到生产环境

1. **不加载 override 文件**：`docker compose -f docker-compose.yml up` 跳过开发覆盖
2. **后端**：Gunicorn 多 worker 模式，构建产物内置代码
3. **前端**：`runner` 阶段多阶段构建镜像（~216MB，非 root 运行），standalone 模式
4. **HTTPS**：挂载 SSL 证书到 nginx，取消 `nginx.conf` 中 443 server 块注释，设 `HTTPS_REDIRECT=true`
5. **安全密钥**：修改所有密码和 `SECRET_KEY`（≥32 字符强随机值）
6. **域名配置**：`NEXT_PUBLIC_API_URL` 和 `CORS_ORIGINS` 改为实际域名

```bash
# 1. 修改 .env
#    ENVIRONMENT=production
#    NEXT_PUBLIC_API_URL=https://api.example.com
#    CORS_ORIGINS=https://cloud.example.com
#    HTTPS_REDIRECT=true
#    BACKEND_WORKERS=4

# 2. 挂载 SSL 证书（可选，启用 HTTPS）
#    将 fullchain.pem 和 privkey.pem 放入 nginx/ssl/

# 3. 构建并启动（仅使用 docker-compose.yml，不加载 override）
docker compose -f docker-compose.yml up -d --build

# 4. 验证生产模式
docker compose logs backend | grep -i gunicorn
curl -sI https://your-domain.com | grep -i strict-transport-security
```

## API 概览

| 模块     | 路径前缀              | 主要功能                                         |
| -------- | --------------------- | ------------------------------------------------ |
| 认证     | `/api/v1/auth`        | 登录、注册、刷新 Token、忘记密码、密保问题       |
| 用户     | `/api/v1/users`       | 用户信息、修改资料、修改密码、存储统计           |
| 文件     | `/api/v1/files`       | 上传、下载、删除、预览、搜索、移动、回收站       |
| 文件夹   | `/api/v1/folders`     | 创建、重命名、删除、列表、回收站、恢复、彻底删除 |
| 分享     | `/api/v1/shares`      | 创建分享、提取码验证、公开访问                   |
| 管理     | `/api/v1/admin`       | 系统统计、用户管理、备份管理                     |
| 任务     | `/api/v1/admin/tasks` | 任务状态查询、活跃任务列表                       |
| 健康检查 | `/health`             | 各组件状态与延迟探测                             |

完整 API 文档：http://localhost:8000/docs

## 管理后台

使用 `.env` 中 `ADMIN_EMAIL` 配置的邮箱注册的首个用户自动成为管理员，登录后侧边栏出现「⚙️ 管理后台」入口。

- **系统统计**：用户数、存储使用量、文件数
- **用户管理**：查看/搜索用户、调整存储配额、启用/禁用账号
- **备份管理**：查看备份列表、手动触发备份、下载备份文件
- **任务管理**：查询异步任务状态、查看活跃任务列表

> 若注册时未生效，检查 `ADMIN_EMAIL` 环境变量是否已传入 backend 容器：
> `docker compose exec backend env | grep ADMIN_EMAIL`

## 测试

### 后端测试（162 个）

```bash
cd backend

# 运行全部测试
uv run pytest tests/ -v

# 按类型运行
uv run pytest tests/test_service_user.py -v    # Service 单元测试
uv run pytest tests/test_service_auth.py -v    # AuthService 测试
uv run pytest tests/test_service_file.py -v    # FileService 测试
uv run pytest tests/test_service_share.py -v    # ShareService 测试
uv run pytest tests/test_schemas.py -v         # Schema 验证测试
uv run pytest tests/test_deps.py -v            # 依赖注入测试
uv run pytest tests/test_api_auth.py -v        # Auth API 集成测试
uv run pytest tests/test_api_files.py -v       # Files/Folders/Shares API 测试
uv run pytest tests/test_middleware.py -v      # 中间件测试

# 安全专项测试
uv run python -m tests.test_token_type              # Token 类型校验
uv run python -m tests.test_user_cache_desensitize   # 用户缓存脱敏
uv run python -m tests.test_upload_security          # 上传安全（MIME/文件名）
uv run python -m tests.test_share_rate_limit         # 分享提取码防爆破
```

### 前端测试（28 个）

```bash
cd frontend

# 运行全部测试
npm run test

# 监听模式
npm run test:watch

# 按类型运行
npx vitest run tests/utils/format.test.ts      # 工具函数测试
npx vitest run tests/lib/i18n.test.ts          # i18n 翻译测试
npx vitest run tests/stores/auth.test.ts       # Auth store 测试
npx vitest run tests/stores/transfers.test.ts  # Transfers store 测试
npx vitest run tests/stores/i18n.test.ts       # i18n store 测试
```

## 日志系统

基于 Loguru 的结构化日志，输出 JSON 格式，支持轮转和脱敏。

| 日志文件     | 说明                           |
| ------------ | ------------------------------ |
| `app.log`    | 全量日志（按级别过滤）         |
| `error.log`  | 仅 ERROR 及以上                |
| `access.log` | HTTP 请求日志（含 request_id） |

- **轮转**：每日 0 点切割，超期自动清理
- **脱敏**：password/token/secret 等字段自动替换为 `***`
- **查看**：`tail -f backend/logs/app.log`

## 备份系统

独立 `backup` 容器，定时备份 PostgreSQL 和 MinIO 数据。

```bash
# 手动备份
docker compose exec backup /scripts/backup.sh

# 恢复（会覆盖当前数据，需交互确认）
docker compose exec -it backup /scripts/restore.sh 20260907_030000
```

- **Cron 定时**：`BACKUP_CRON` 配置，默认每天 3:00
- **保留策略**：`BACKUP_RETENTION_DAYS` 天后自动清理
- **GPG 加密**：设置 `BACKUP_ENCRYPT_KEY` 后用 AES256 加密数据库备份
- **备份目录**：`./backups/<时间戳>/`

## 告警

ERROR 及以上日志自动发送通知（需启用）。

```env
ALERT_ENABLED=true
ALERT_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
ALERT_WEBHOOK_TYPE=dingtalk  # dingtalk/feishu/wechat/generic
```

- **去重冷却**：同一错误在 `ALERT_COOLDOWN_SECONDS` 内不重复告警
- **邮件通知**：配置 `ALERT_EMAIL_*` 系列 SMTP 参数
- **异步发送**：通过 Celery Worker 异步执行，不阻塞请求和日志主流程；Worker 不可用时自动降级为同步发送

## 健康检查

```bash
curl http://localhost:8000/health
```

返回各组件状态与延迟：

```json
{
  "status": "ok",
  "checks": {
    "postgres": { "status": "ok", "latency_ms": 2.35 },
    "minio": { "status": "ok", "latency_ms": 5.12 },
    "redis": { "status": "ok", "latency_ms": 1.08 }
  }
}
```

任一组件异常时 `status` 为 `degraded`，可用于负载均衡器健康探测。

## 核心功能

- **文件管理**：上传、下载、删除、重命名、文件夹嵌套
- **文件预览**：图片缩略图、网格/列表视图切换
- **批量操作**：多选文件批量移动、删除
- **拖拽移动**：拖拽文件到文件夹图标完成移动
- **文件分享**：生成分享链接和提取码，支持一键复制
- **传输管理**：上传/下载进度追踪，侧边栏红点提示
- **存储统计**：侧边栏显示已用容量
- **回收站**：文件和文件夹恢复、彻底删除（级联软删除一致性）
- **响应式设计**：适配平板和手机屏幕
- **管理后台**：系统统计、用户管理、配额调整、备份管理
- **用户中心**：头像上传/裁剪、修改用户名/密码
- **国际化**：简体中文、繁体中文、英文
- **结构化日志**：JSON 格式、轮转、敏感数据脱敏
- **自动备份**：PostgreSQL + MinIO 定时备份、GPG 加密
- **异步任务队列**：Celery + Redis，邮件发送、备份触发、缩略图生成、告警通知异步执行
- **日志告警**：ERROR 日志通过 Webhook/邮件通知
- **健康检查**：检测 DB/MinIO/Redis 连通性与延迟

## 安全与性能优化

### 安全加固

| 模块     | 措施                                                               |
| -------- | ------------------------------------------------------------------ |
| 基础设施 | Docker socket 移除、端口绑定 127.0.0.1、Redis 密码 + 禁用 FLUSHALL |
| 认证     | JWT 增加 `type` 字段，防止 access/refresh token 混用               |
| 缓存     | Redis 用户缓存脱敏（移除密码、密保问题/答案）                      |
| 上传     | python-magic 真实 MIME 检测 + 白名单 + 文件名净化                  |
| 限流     | 提取码 5 次失败锁定 15 分钟；登录按真实 IP（X-Forwarded-For）限流  |
| 响应头   | CSP / HSTS / X-Frame-Options / nosniff / Referrer-Policy           |

### 性能优化

| 模块     | 措施                                                                                                            |
| -------- | --------------------------------------------------------------------------------------------------------------- |
| 上传     | 流式直传 MinIO，内存占用 O(1)（非 O(N×文件大小)）                                                               |
| MinIO    | 异步包装（`run_in_threadpool`），不阻塞事件循环                                                                 |
| 部署     | Gunicorn 多 worker，充分利用多核，支持优雅关闭                                                                  |
| 压缩     | GZip 中间件（≥500B 自动压缩）                                                                                   |
| 数据库   | 连接池可配置（`pool_size`/`max_overflow`/`pool_timeout`/`pool_recycle`）                                        |
| 限流     | Redis 滑动窗口限流，按 IP + 路径粒度控制                                                                        |
| 任务     | Celery 异步队列，邮件/备份/缩略图/告警不阻塞请求                                                                |
| 缩略图   | 图片上传后自动异步生成 256×256 缩略图，前端渐进加载（shimmer → blur → sharp），列表优先请求缩略图而非原图       |
| 分页     | 窗口函数 `count() over()` 合并数据+总数为单次查询，消除 N+1 count 问题                                          |
| 搜索     | pg_trgm `similarity()` 三元组相似度搜索 + GIN 索引，替代低效 `ilike`                                            |
| 文件夹   | `list_folder_contents` 文件查询与 count 合并，3 次查询→2 次                                                     |
| Docker   | 多阶段构建：backend 315MB / frontend 216MB，生产无 `--reload`，非 root 运行，HEALTHCHECK                        |
| 虚拟滚动 | react-virtuoso（TableVirtuoso + VirtuosoGrid），文件列表仅渲染可视区域 DOM，万级文件无卡顿                      |
| 请求缓存 | TanStack Query（useQuery + useMutation），自动去重/缓存/stale-while-revalidate，mutation 后乐观更新或精准失效   |
| 实时通知 | WebSocket 长连接，上传完成/分享创建/存储变更即时推送，前端自动 invalidate 对应缓存，指数退避重连（1→2→4→8→16s） |

## 常用命令

```bash
# ---- 服务管理 ----
docker compose up -d                          # 启动（开发模式）
docker compose up -d --build                  # 重新构建
docker compose -f docker-compose.yml up -d --build  # 生产模式
docker compose down                           # 停止
docker compose down -v                        # 停止并删除数据卷（⚠️ 清空所有数据）
docker compose restart frontend               # 重启单个服务

# ---- 日志 ----
docker compose logs -f frontend               # 前端日志
docker compose logs -f backend                # 后端日志
tail -f backend/logs/app.log                  # 结构化日志

# ---- 数据库迁移 ----
docker compose exec backend alembic upgrade head                    # 执行迁移
docker compose exec backend alembic revision --autogenerate -m "描述"  # 生成迁移

# ---- 备份与恢复 ----
docker compose exec backup /scripts/backup.sh                       # 手动备份
docker compose exec -it backup /scripts/restore.sh <备份目录名>      # 恢复
ls -la backups/                                                    # 查看备份列表

# ---- Celery Worker ----
docker compose logs -f celery-worker                               # Worker 日志
docker compose exec celery-worker celery -A app.core.celery_app:celery_app inspect active  # 活跃任务
docker compose exec celery-worker celery -A app.core.celery_app:celery_app inspect reserved # 等待任务

# ---- 容器调试 ----
docker compose exec backend bash
docker compose exec frontend sh

# ---- 健康检查 ----
curl http://localhost:8000/health
```

## 开发说明

项目使用 Docker Compose 的 **override 机制**区分开发与生产：

| 场景 | 命令                                      | 配置文件                                             | 特点                                                      |
| ---- | ----------------------------------------- | ---------------------------------------------------- | --------------------------------------------------------- |
| 开发 | `docker compose up`                       | `docker-compose.yml` + `docker-compose.override.yml` | volume 挂载、热重载、dev 构建目标、Celery Eager 模式      |
| 生产 | `docker compose -f docker-compose.yml up` | 仅 `docker-compose.yml`                              | 构建产物运行、Gunicorn 多 worker、独立 Celery Worker 容器 |

### 前端开发

前端采用多阶段 Dockerfile，override 文件自动切换到 `dev` 阶段（热重载 + volume 挂载）：

- **开发模式**（`dev` 阶段）：代码通过 volume 挂载，修改后自动热重载
- **生产模式**（`runner` 阶段）：多阶段构建，仅包含 standalone 产物，镜像 ~150MB，非 root 用户运行

```bash
docker compose exec frontend npm run lint    # 代码检查
docker compose exec frontend npm run build   # 生产构建
docker compose exec frontend npm run test    # 运行测试
```

### 后端开发

后端代码在开发模式下通过 volume 挂载，uvicorn 以 `--reload` 模式运行；生产模式使用构建产物内置代码，Gunicorn 多 worker 运行：

```bash
docker compose exec backend alembic revision --autogenerate -m "描述"  # 生成迁移
docker compose exec backend alembic upgrade head                       # 执行迁移
docker compose exec backend pytest tests/ -v                           # 运行测试
```

## CI/CD

项目使用 GitHub Actions 实现自动化流水线，配置文件位于 `.github/workflows/ci.yml`。

### 流水线阶段

```
┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│ Backend Lint │  │ Backend TC  │  │ Backend Test │
│   (ruff)     │  │  (pyright)  │  │   (pytest)   │
└──────┬───────┘  └──────┬──────┘  └──────┬───────┘
       │                 │                 │
┌──────┴───────┐  ┌──────┴──────┐  ┌──────┴───────┐
│ Frontend Lint│  │ Frontend TC │  │ Frontend Test│
│  (eslint)    │  │  (tsc)      │  │  (vitest)    │
└──────┬───────┘  └──────┬──────┘  └──────┬───────┘
       │                 │                 │
       └────────┬───────┴────────┬───────┘
                │                │
         ┌──────┴──────┐  ┌─────┴──────┐
         │ Docker Build│  │   Deploy   │
         │ (3 images)  │→ │ (master)   │
         └─────────────┘  └────────────┘
```

| 阶段               | 触发条件         | 内容                                      |
| ------------------ | ---------------- | ----------------------------------------- |
| Backend Lint       | push/PR          | `ruff check` + `ruff format --check`      |
| Backend TypeCheck  | push/PR          | `pyright` 类型检查                        |
| Backend Test       | push/PR          | `pytest` 162 个测试                       |
| Frontend Lint      | push/PR          | `next lint` (ESLint)                      |
| Frontend TypeCheck | push/PR          | `tsc --noEmit`                            |
| Frontend Test      | push/PR          | `vitest run` 28 个测试                    |
| Docker Build       | Lint+Test 通过   | 构建 backend / frontend / backup 三个镜像 |
| Deploy             | master/main 分支 | 推送镜像到 Docker Hub + SSH 部署          |

### 配置 Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：

| Secret               | 说明                    |
| -------------------- | ----------------------- |
| `DOCKERHUB_USERNAME` | Docker Hub 用户名       |
| `DOCKERHUB_TOKEN`    | Docker Hub Access Token |
| `DEPLOY_HOST`        | 部署服务器 IP/域名      |
| `DEPLOY_USER`        | SSH 登录用户名          |
| `DEPLOY_SSH_KEY`     | SSH 私钥                |
| `DEPLOY_PATH`        | 服务器上项目路径        |

### 并发控制

同一分支的多次推送会自动取消前序运行中的流水线（`concurrency: cancel-in-progress`），避免重复构建浪费资源。

### 缓存策略

- **uv 缓存**：后端依赖通过 `setup-uv` 的 `enable-cache` 缓存
- **npm 缓存**：前端依赖通过 `setup-node` 的 `cache: npm` 缓存
- **Docker 缓存**：构建层通过 GitHub Actions Cache（`type=gha`）缓存，跨运行复用

## License
