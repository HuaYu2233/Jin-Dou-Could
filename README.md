# JinDou Cloud（筋斗云盘）

一个基于 Docker Compose 的全栈云存储应用，支持文件上传/下载、文件夹管理、文件分享、传输进度追踪等功能。

## 技术栈

### 前端

- **框架**：Next.js 16 + React 19
- **状态管理**：Zustand
- **样式**：Tailwind CSS 4 + CSS Modules
- **语言**：TypeScript 5

### 后端

- **框架**：FastAPI 0.111
- **ORM**：SQLAlchemy 2.0（异步）
- **数据库迁移**：Alembic
- **认证**：python-jose（JWT）+ bcrypt
- **对象存储**：MinIO（S3 兑容）
- **日志**：Loguru（结构化 JSON + 轮转）
- **语言**：Python 3.11

### 基础设施

- **数据库**：PostgreSQL 15
- **缓存**：Redis 7
- **对象存储**：MinIO
- **反向代理**：Nginx（可选）
- **容器化**：Docker Compose

## 项目结构

```
JinDou-Cloud/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 路由
│   │   │   ├── endpoints/      # auth, files, folders, shares, users
│   │   │   └── api.py          # 路由聚合
│   │   ├── core/               # config, security, storage, logging, redis, alerting
│   │   ├── db/                 # 数据库引擎与会话
│   │   ├── middleware/         # request_logging, security_headers 中间件
│   │   ├── models/             # SQLAlchemy 模型
│   │   ├── schemas/            # Pydantic 模型
│   │   ├── services/           # 业务逻辑层
│   │   └── main.py             # 应用入口
│   ├── alembic/                # 数据库迁移
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # Next.js 前端
│   ├── app/
│   │   ├── (auth)/             # 登录/注册页
│   │   ├── admin/              # 管理后台（统计、用户管理）
│   │   ├── dashboard/          # 主界面
│   │   │   ├── components/      # UI 组件
│   │   │   ├── hooks/          # useFileList, useFileOperations
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx        # 容器组件
│   │   └── share/[token]/      # 分享访问页
│   ├── lib/
│   │   ├── api/                # API 封装（client, files）
│   │   ├── config.ts           # 前端配置中心
│   │   └── stores/             # Zustand stores（auth, transfers）
│   ├── package.json
│   └── Dockerfile
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

# 3. 启动所有服务
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

### 默认账号

首次启动后通过注册页面创建账号，或使用 `.env` 中配置的数据库凭据直接连接 PostgreSQL。

## 配置说明

所有配置通过 `.env` 文件管理，参考 `.env.example`：

| 配置项                        | 说明                       | 默认值                |
| ----------------------------- | -------------------------- | --------------------- |
| `POSTGRES_USER`               | 数据库用户名               | clouduser             |
| `POSTGRES_PASSWORD`           | 数据库密码                 | -                     |
| `POSTGRES_DB`                 | 数据库名                   | clouddrive            |
| `MINIO_ROOT_USER`             | MinIO 用户名               | minioadmin            |
| `MINIO_ROOT_PASSWORD`         | MinIO 密码                 | -                     |
| `SECRET_KEY`                  | JWT 签名密钥               | -                     |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 过期时间      | 30                    |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh Token 过期时间     | 7                     |
| `NEXT_PUBLIC_API_URL`         | 浏览器访问后端地址         | http://localhost:8000 |
| `API_URL`                     | Docker 内部后端地址        | http://backend:8000   |
| `CORS_ORIGINS`                | 允许的前端源（逗号分隔）   | http://localhost:3000 |
| `ADMIN_EMAIL`                 | 自动成为管理员的邮箱       | -                     |
| `MAX_USERS`                   | 最大注册用户数（0=不限）   | 0                     |
| `DEFAULT_STORAGE_QUOTA`       | 新用户默认配额（字节）     | 1073741824            |
| `LOG_LEVEL`                   | 日志级别                   | INFO                  |
| `LOG_DIR`                     | 日志目录                   | logs                  |
| `LOG_RETENTION_DAYS`          | 日志保留天数               | 30                    |
| `BACKUP_RETENTION_DAYS`       | 备份保留天数               | 7                     |
| `BACKUP_CRON`                 | 备份 Cron 表达式           | 0 3 \* \* \*          |
| `BACKUP_ENCRYPT_KEY`          | 备份加密密钥（留空不加密） | -                     |
| `ALERT_ENABLED`               | 启用日志告警               | false                 |
| `ALERT_WEBHOOK_URL`           | 告警 Webhook 地址          | -                     |
| `ALERT_EMAIL_ENABLED`         | 启用邮件告警               | false                 |
| `BACKEND_WORKERS`             | Gunicorn worker 进程数     | 4                     |
| `DB_POOL_SIZE`                | 数据库连接池大小           | 20                    |
| `DB_MAX_OVERFLOW`             | 连接池溢出上限             | 10                    |
| `DB_POOL_TIMEOUT`             | 获取连接超时（秒）         | 30                    |
| `HTTPS_REDIRECT`              | 强制 HTTPS 重定向（生产）  | false                 |
| `SECURITY_HEADERS_ENABLED`    | 启用安全响应头             | true                  |

### 迁移到生产环境

生产环境部署要点：

1. **环境变量**：`ENVIRONMENT=production`，后端自动切换为 Gunicorn 多 worker 模式
2. **HTTPS**：挂载 SSL 证书到 nginx，取消 `nginx.conf` 中 443 server 块注释，设 `HTTPS_REDIRECT=true`
3. **安全密钥**：修改所有密码和 `SECRET_KEY`（≥32 字符强随机值）
4. **域名配置**：`NEXT_PUBLIC_API_URL` 和 `CORS_ORIGINS` 改为实际域名

```bash
# 1. 修改 .env
#    ENVIRONMENT=production
#    NEXT_PUBLIC_API_URL=https://api.example.com
#    CORS_ORIGINS=https://cloud.example.com
#    HTTPS_REDIRECT=true
#    BACKEND_WORKERS=4

# 2. 挂载 SSL 证书（可选，启用 HTTPS）
#    将 fullchain.pem 和 privkey.pem 放入 nginx/ssl/

# 3. 重新构建并启动
docker compose up -d --build

# 4. 验证生产模式
docker compose logs backend | grep -i gunicorn
curl -sI https://your-domain.com | grep -i strict-transport-security
```

## API 概览

| 模块   | 路径前缀          | 主要功能                       |
| ------ | ----------------- | ------------------------------ |
| 认证   | `/api/v1/auth`    | 登录、注册、刷新 Token         |
| 用户   | `/api/v1/users`   | 用户信息、存储统计             |
| 文件   | `/api/v1/files`   | 上传、下载、删除、预览         |
| 文件夹 | `/api/v1/folders` | 创建、重命名、删除、列表       |
| 分享   | `/api/v1/shares`  | 创建分享、提取码验证、公开访问 |

完整 API 文档：http://localhost:8000/docs

## 管理后台

使用 `.env` 中 `ADMIN_EMAIL` 配置的邮箱注册的首个用户自动成为管理员，登录后侧边栏出现「⚙️ 管理后台」入口。

- **系统统计**：用户数、存储使用量、文件数
- **用户管理**：查看/搜索用户、调整存储配额、启用/禁用账号

> 若注册时未生效，检查 `ADMIN_EMAIL` 环境变量是否已传入 backend 容器：
> `docker compose exec backend env | grep ADMIN_EMAIL`

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
- **异步发送**：不阻塞请求和日志主流程

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
- **回收站**：文件恢复、彻底删除
- **响应式设计**：适配平板和手机屏幕
- **管理后台**：系统统计、用户管理、配额调整
- **用户中心**：头像上传/裁剪、修改用户名/密码
- **结构化日志**：JSON 格式、轮转、敏感数据脱敏
- **自动备份**：PostgreSQL + MinIO 定时备份、GPG 加密
- **日志告警**：ERROR 日志通过 Webhook/邮件通知
- **健康检查**：检测 DB/MinIO/Redis 连通性与延迟

## 安全与性能优化

本项目已完成多阶段安全加固与性能优化：

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

| 模块   | 措施                                                                     |
| ------ | ------------------------------------------------------------------------ |
| 上传   | 流式直传 MinIO，内存占用 O(1)（非 O(N×文件大小)）                        |
| MinIO  | 异步包装（`run_in_threadpool`），不阻塞事件循环                          |
| 部署   | Gunicorn 多 worker，充分利用多核，支持优雅关闭                           |
| 压缩   | GZip 中间件（≥500B 自动压缩）                                            |
| 数据库 | 连接池可配置（`pool_size`/`max_overflow`/`pool_timeout`/`pool_recycle`） |

### 验证测试

```bash
cd backend
uv run python -m tests.test_token_type              # Token 类型校验
uv run python -m tests.test_user_cache_desensitize   # 用户缓存脱敏
uv run python -m tests.test_upload_security          # 上传安全（MIME/文件名）
uv run python -m tests.test_share_rate_limit         # 分享提取码防爆破
```

## 常用命令

```bash
# 启动所有服务
docker compose up -d

# 重新构建（代码变更后）
docker compose up -d --build

# 查看日志
docker compose logs -f frontend
docker compose logs -f backend

# 重启单个服务
docker compose restart frontend
docker compose restart backend

# 停止所有服务
docker compose down

# 停止并删除数据卷（⚠️ 清空所有数据）
docker compose down -v

# 执行数据库迁移
docker compose exec backend alembic upgrade head

# 手动执行备份
docker compose exec backup /scripts/backup.sh

# 恢复备份（交互式确认）
docker compose exec -it backup /scripts/restore.sh <备份目录名>

# 查看备份列表
ls -la backups/

# 进入容器
docker compose exec backend bash
docker compose exec frontend sh
```

## 开发说明

### 前端开发

前端代码通过 volume 挂载到容器，修改后自动热重载：

```bash
docker compose exec frontend npm run lint   # 代码检查
docker compose exec frontend npm run build # 生产构建
```

### 后端开发

后端代码同样通过 volume 挂载，uvicorn 以 `--reload` 模式运行：

```bash
docker compose exec backend alembic revision --autogenerate -m "描述"  # 生成迁移
docker compose exec backend alembic upgrade head                       # 执行迁移
```

## License

MIT
