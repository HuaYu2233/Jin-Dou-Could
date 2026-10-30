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

# HTTPS
HTTPS_REDIRECT=true

# Worker 数量（建议 = CPU 核心数）
BACKEND_WORKERS=4

# 管理员邮箱
ADMIN_EMAIL=admin@example.com

# 最大用户数（0=不限）
MAX_USERS=0
```

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
make dev                    # 开发模式启动
make dev-restart            # 重启 backend + frontend
make prod                   # 生产模式启动
make down                   # 停止所有服务
make logs                   # 查看日志
make hot-reload             # 热更新后端代码
```

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

访问 `http://localhost:8000/metrics` 获取指标

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

## 8. CI/CD 自动部署

项目使用 GitHub Actions，配置文件位于 `.github/workflows/ci.yml`。

### 8.1 流水线阶段

```
Lint + TypeCheck + Test → Docker Build → Deploy (master/main)
```

### 8.2 配置 Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：

| Secret               | 说明                    |
| -------------------- | ----------------------- |
| `DOCKERHUB_USERNAME` | Docker Hub 用户名       |
| `DOCKERHUB_TOKEN`    | Docker Hub Access Token |
| `DEPLOY_HOST`        | 部署服务器 IP/域名      |
| `DEPLOY_USER`        | SSH 登录用户名          |
| `DEPLOY_SSH_KEY`     | SSH 私钥                |
| `DEPLOY_PATH`        | 服务器上项目路径        |
