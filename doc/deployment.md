# 部署指南

## 1. 前置要求

| 软件           | 版本 | 说明       |
| -------------- | ---- | ---------- |
| Docker         | 20+  | 容器运行时 |
| Docker Compose | 2.0+ | 容器编排   |
| Git            | -    | 代码拉取   |

## 2. 快速部署（开发模式）

```bash
# 1. 克隆仓库
git clone <repository-url>
cd JinDou-Cloud

# 2. 复制配置模板并编辑
cp .env.example .env
# 编辑 .env，至少修改以下配置：
#   POSTGRES_PASSWORD=强密码
#   REDIS_PASSWORD=强密码
#   MINIO_ROOT_PASSWORD=强密码
#   SECRET_KEY=32字符以上的随机字符串

# 3. 首次构建镜像
make prod-build

# 4. 开发模式启动
make dev

# 5. 查看日志
make logs
```

启动后访问：

| 服务                | 地址                       |
| ------------------- | -------------------------- |
| 前端                | http://localhost:3000      |
| 后端 API            | http://localhost:8000      |
| API 文档（Swagger） | http://localhost:8000/docs |
| MinIO 控制台        | http://localhost:9001      |

## 3. 生产部署

### 3.1 环境配置

编辑 `.env`，修改以下关键配置：

```env
# 环境标识
ENVIRONMENT=production

# 数据库（强密码）
POSTGRES_PASSWORD=<强密码>

# Redis（强密码）
REDIS_PASSWORD=<强密码>

# MinIO（强密码）
MINIO_ROOT_PASSWORD=<强密码>

# JWT 密钥（≥32 字符强随机值）
SECRET_KEY=<openssl rand -hex 32>

# 域名配置
NEXT_PUBLIC_API_URL=https://api.example.com
CORS_ORIGINS=https://cloud.example.com

# 浏览器可访问的 MinIO 地址（预签名下载链接指向此地址，必须是公网可达域名）
MINIO_PUBLIC_ENDPOINT=minio.example.com:9000

# 可信反向代理 IP（逗号分隔，精确匹配，不支持 CIDR）
# 部署在 Nginx / Cloudflare 之后必须填写，否则限流会把所有请求记成同一个 IP
TRUSTED_PROXIES=127.0.0.1

# HTTPS
HTTPS_REDIRECT=true

# Worker 数量（建议 = CPU 核心数）
BACKEND_WORKERS=4

# 管理员邮箱
ADMIN_EMAIL=admin@example.com

# 最大用户数（0=不限）
MAX_USERS=0
```

> `.env` 中的变量只有被 `docker-compose.yml` 的 `environment` 段引用后才会进入容器。新增配置项时必须同时修改 `.env.example`、`config.py` 与 compose 的 `environment`，否则会静默回落到代码默认值，表现为「改了 `.env` 但不生效」。

### 3.2 启动生产服务

```bash
# 构建并启动（仅使用 docker-compose.yml，不加载 override）
docker compose -f docker-compose.yml up -d --build

# 验证
docker compose logs backend | grep -i gunicorn
curl -sI https://your-domain.com | grep -i strict-transport-security
```

### 3.3 HTTPS 配置（可选）

1. 将 SSL 证书放入 `nginx/ssl/` 目录：
   - `fullchain.pem`
   - `privkey.pem`

2. 取消 `nginx/nginx.conf` 中 443 server 块的注释

3. 设置环境变量：

   ```env
   HTTPS_REDIRECT=true
   ```

4. 重启 nginx：
   ```bash
   docker compose restart nginx
   ```

### 3.4 数据库连接池调优

生产环境需确保连接池配置合理：

```
WORKERS × (POOL_SIZE + MAX_OVERFLOW) < DB_MAX_CONNECTIONS
```

默认配置：4 × (5 + 5) = 40 < 80，有余量

如需调大：

```env
BACKEND_WORKERS=4
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=5
DB_MAX_CONNECTIONS=80
# 4 × (10 + 5) = 60 < 80 ✓
```

## 4. 常用运维命令

### 4.1 服务管理

```bash
make setup                  # 初始化 git 性能优化（fsmonitor + untrackedCache）
make prod-build             # 生产构建镜像（BuildKit 缓存，frontend 为 runner 阶段）
make prod                   # 生产模式启动（先跑 preflight-prod 编排校验）
make dev-build              # 构建前端 dev 镜像（首次或依赖变更后）
make dev                    # 开发模式启动（不含 celery-worker / backup / nginx）
make dev-restart            # 重建 backend + frontend 容器
make hot-reload             # 用 docker cp 同步后端代码，触发 uvicorn --reload
make logs                   # 跟随 backend + frontend 日志
make down                   # 停止所有服务
```

> `make dev` 启动的是 `db / redis / minio / pgbouncer / backend / frontend`，不包含 `celery-worker`、`backup`、`nginx` 与监控组件。需要验证异步任务时改用 `make prod`，或单独 `docker compose up -d celery-worker`。
>
> 编排隔离规则：`docker-compose.dev.yml` 中的 backend / frontend / pgbouncer 带 `profiles: ["dev"]`，必须显式 `--profile dev` 才会启动；不带 profile 合并 dev 文件会因 `nginx` 依赖缺失而直接报错，从而阻断"dev 编排混入生产"。`make prod` 另会校验 `ENVIRONMENT=production` 且无 `npm run dev` / `--reload` / 源码 bind mount。

### 4.2 日志查看

```bash
docker compose logs -f frontend       # 前端日志
docker compose logs -f backend        # 后端日志
docker compose logs -f celery-worker  # Celery Worker 日志
tail -f backend/logs/app.log          # 结构化日志
tail -f backend/logs/error.log        # 错误日志
tail -f backend/logs/access.log       # 访问日志
```

### 4.3 数据库迁移

```bash
# 执行迁移
docker compose exec backend alembic upgrade head

# 生成新迁移
docker compose exec backend alembic revision --autogenerate -m "描述"

# 查看当前版本
docker compose exec backend alembic current
```

### 4.4 容器调试

```bash
docker compose exec backend bash      # 进入后端容器
docker compose exec frontend sh       # 进入前端容器
docker compose exec db psql -U clouduser -d clouddrive  # 连接数据库
docker compose exec redis redis-cli -a <password>       # 连接 Redis
```

### 4.5 数据清理

```bash
# 停止并删除容器（保留数据卷）
docker compose down

# 停止并删除所有数据（⚠️ 不可恢复）
docker compose down -v
```

## 5. 备份与恢复

详见 [backup-restore.md](./backup-restore.md)

## 6. 监控与告警

### 6.1 健康检查

```bash
# Liveness（轻量）
curl http://localhost:8000/health

# Readiness（全组件探测）
curl http://localhost:8000/health/ready
```

### 6.2 Prometheus 指标

启用 Prometheus：

```env
PROMETHEUS_ENABLED=true
```

启用后 `/metrics` 端点生效，默认**仅内网可访问**（回环与私有网段，如 Docker 网络内的 `prometheus` 容器），公网来源返回 403。

如需显式鉴权，设置固定令牌：

```env
METRICS_TOKEN=<足够长的随机串>
```

设置后请求必须携带 `Authorization: Bearer <token>`，否则返回 401；同时在 `monitoring/prometheus/prometheus.yml` 的 `cloud-drive-backend` job 下补充：

```yaml
  - job_name: cloud-drive-backend
    metrics_path: /metrics
    authorization:
      type: Bearer
      credentials: <METRICS_TOKEN 的值>
```

```bash
curl -H "Authorization: Bearer $METRICS_TOKEN" http://localhost:8000/metrics
```

> 令牌由环境变量固定，不再每次重启变化，也不会写入日志。

监控栈组成（`docker compose up -d` 会一并启动，无 profile 隔离）：

| 服务              | 端口（仅绑定 127.0.0.1） | 作用                            |
| ----------------- | ----------------------- | ------------------------------- |
| `prometheus`      | 9090                    | 抓取 backend / redis / pg / minio |
| `grafana`         | 3001                    | 仪表盘，管理员账号见配置文档    |
| `redis-exporter`  | 9121                    | Redis 指标                      |
| `postgres-exporter` | 9187                  | PostgreSQL 指标                 |

MinIO 指标走 `/minio/v2/metrics/cluster`（`MINIO_PROMETHEUS_AUTH_TYPE=public`），无需额外鉴权。

### 6.3 告警配置

```env
ALERT_ENABLED=true
ALERT_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
ALERT_WEBHOOK_TYPE=dingtalk  # dingtalk/feishu/wechat/generic
ALERT_MIN_LEVEL=ERROR
ALERT_COOLDOWN_SECONDS=300
```

## 7. 更新部署

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 重新构建并启动
docker compose -f docker-compose.yml up -d --build

# 3. 执行数据库迁移
docker compose exec backend alembic upgrade head

# 4. 验证
docker compose logs -f backend
```

## 8. CI 门禁

项目使用 GitHub Actions，配置文件位于 `.github/workflows/ci.yml`。

### 8.1 流水线阶段

```
Backend Lint  ┐
Backend Test  ├─→ 三个 job 并行，全部通过才算绿灯
Frontend Check┘
```

| Job              | 内容                                                          |
| ---------------- | ------------------------------------------------------------- |
| `backend-lint`   | `ruff check .` + `ruff format --check .`                      |
| `backend-test`   | `pytest tests/ -v` + 覆盖率（Service Container: PG16 + Redis7）|
| `frontend-check` | `npm run lint` + `npx tsc --noEmit` + `npm run test`          |

触发条件：push 到 `main` / `dev`，或向 `main` 发起 PR。

> 当前流水线**只做门禁校验，不含 Docker 构建与自动部署**。生产发布仍按第 7 节手动执行 `git pull` + `docker compose up -d --build`。

### 8.2 本地等价命令

提交前在本地跑同样的检查，避免把红叉推上去：

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
cd ../frontend && npm run lint && npx tsc --noEmit && npm run test
```