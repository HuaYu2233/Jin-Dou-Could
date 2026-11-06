# 系统架构文档

## 1. 系统概述

JinDou Cloud（筋斗云盘）是一个基于 Docker Compose 的全栈云存储应用，提供文件上传/下载、文件夹管理、文件分享、传输进度追踪、管理后台等功能。

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      用户浏览器                          │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐  ┌──────────────────────┐
│   Nginx (可选)        │  │   Next.js 前端       │
│   反向代理 + HTTPS    │──│   :3000              │
└──────────────────────┘  └──────────┬───────────┘
                                     │ API 请求
                                     ▼
                          ┌──────────────────────┐
                          │   FastAPI 后端        │
                          │   :8000               │
                          │   Gunicorn × N Worker │
                          └──┬───┬───┬───┬───────┘
                             │   │   │   │
              ┌──────────────┘   │   │   └──────────────┐
              ▼                  ▼   ▼                  ▼
┌──────────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐
│  PostgreSQL 15   │ │  Redis 7   │ │  MinIO     │ │  Celery      │
│  关系数据库      │ │  缓存/限流 │ │  对象存储  │ │  Worker      │
└──────────────────┘ └────────────┘ └────────────┘ └──────────────┘
```

## 3. 技术栈

### 3.1 前端

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

### 3.2 后端

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
| Prometheus   | 6.1+        | 指标采集（prometheus-fastapi-instrumentator） |
| Python       | 3.12+       | 运行时                |

### 3.3 基础设施

| 组件           | 版本   | 用途                                                    |
| -------------- | ------ | ------------------------------------------------------- |
| PostgreSQL     | 15     | 关系数据库                                              |
| Redis          | 7      | 缓存 / 限流 / Token 黑名单 / Celery Broker / WS Pub/Sub |
| MinIO          | latest | 对象存储                                                |
| Nginx          | -      | 反向代理（可选）                                        |
| Prometheus     | 可选   | 指标采集                                                |
| Docker Compose | 2.0+   | 容器编排                                                |

## 4. 项目结构

```
JinDou-Cloud/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 路由
│   │   │   ├── endpoints/      # 各模块端点
│   │   │   └── api.py          # 路由聚合
│   │   ├── core/               # 核心模块（config, security, storage, client_ip, smtp 等）
│   │   ├── db/                 # 数据库引擎与会话
│   │   ├── middleware/         # 中间件（限流、日志、安全头、CSRF）
│   │   ├── models/             # SQLAlchemy 模型
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── services/           # 业务逻辑层
│   │   ├── tasks/              # Celery 异步任务
│   │   └── main.py             # 应用入口
│   ├── alembic/                # 数据库迁移
│   ├── tests/                  # 测试套件
│   └── pyproject.toml          # 依赖声明
├── frontend/                   # Next.js 前端
│   ├── app/                    # 页面路由
│   │   ├── (auth)/             # 登录/注册/忘记密码
│   │   ├── admin/              # 管理后台
│   │   ├── dashboard/          # 主界面
│   │   ├── profile/            # 用户中心
│   │   └── share/[token]/      # 分享访问页
│   ├── lib/                    # 工具库
│   │   ├── api/                # 接口封装：auth.ts / files.ts（文件+文件夹+分享）/ admin.ts，以及 client.ts / csrf.ts / refresh.ts / session.ts
│   │   ├── query/              # TanStack Query 的 keys.ts 与 QueryProvider
│   │   ├── i18n/               # 多语言资源（zh-CN / zh-TW / en）与切换
│   │   └── hooks/              # 通用 hooks（useIsHydrated、useWebSocket）
│   ├── stores/                 # Zustand 状态管理
│   └── tests/                  # 测试套件
├── scripts/                    # 备份/恢复脚本
├── nginx/                      # Nginx 配置（可选）
├── backups/                    # 备份输出目录
├── doc/                        # 项目文档
├── .env.example                # 配置模板
├── Makefile                    # 开发快捷命令
├── docker-compose.yml          # 生产编排
└── docker-compose.dev.yml      # 开发编排
```

## 5. 后端分层架构

后端采用经典的分层架构，职责清晰：

```
请求 → 中间件 → 路由(Endpoint) → 服务(Service) → 模型(Model) / 存储(Storage)
                                    ↓
                              Schema(验证/序列化)
```

| 层级      | 目录               | 职责                                        |
| --------- | ------------------ | ------------------------------------------- |
| 路由层    | `api/v1/endpoints` | HTTP 请求处理、参数校验、响应格式化         |
| 服务层    | `services/`        | 业务逻辑、数据编排、权限校验                |
| 模型层    | `models/`          | 数据库表定义（SQLAlchemy ORM）              |
| Schema 层 | `schemas/`         | 请求/响应数据验证与序列化（Pydantic）       |
| 核心层    | `core/`            | 配置、安全、存储、日志、Redis、Celery、客户端 IP 解析、SMTP 发信等 |
| 中间件层  | `middleware/`      | 限流、请求日志、安全头、CSRF                |
| 任务层    | `tasks/`           | Celery 异步任务（邮件、备份、缩略图、告警） |

## 6. 前端架构

### 6.1 页面路由

| 路由               | 功能           | 认证   |
| ------------------ | -------------- | ------ |
| `/login`           | 登录           | 否     |
| `/register`        | 注册           | 否     |
| `/forgot-password` | 忘记密码       | 否     |
| `/dashboard`       | 文件管理主界面 | 是     |
| `/profile`         | 用户中心       | 是     |
| `/admin`           | 管理后台       | 管理员 |
| `/share/[token]`   | 分享访问       | 否     |

### 6.2 状态管理

| Store           | 职责                     |
| --------------- | ------------------------ |
| `auth`          | 用户认证状态、Token 管理 |
| `transfers`     | 上传/下载传输进度追踪    |
| `i18n`          | 国际化语言切换           |
| `notifications` | WebSocket 通知管理       |

> `notifications` 为纯内存 store，不持久化。登出时必须调用 `clearAll()` 清零 `unreadCount`，否则下一个会话会继承上一用户的未读角标。

### 6.3 数据流

```
用户操作 → Zustand Store → API Client → FastAPI 后端
    ↑                                    │
    └── TanStack Query 缓存 ←──────── 响应
    └── WebSocket 实时推送 ←──────── 事件通知
```

### 6.4 会话边界与缓存隔离

TanStack Query 的缓存 key 只描述查询参数（`category` / `page` / `folderId` / `keyword`），**不含用户身份**。因此缓存的生命周期必须与登录会话绑定：

```
登出（本地或服务端触发）→ queryClient.clear() + notifications.clearAll() → 跳转 /login
```

- 使用 `clear()` 而非 `invalidateQueries()`：登出场景需要丢弃缓存，invalidate 会在跳转前用旧 Cookie 再打一轮请求
- 清理逻辑集中放在 `app/dashboard/layout.tsx` 的未认证分支，任何进入该分支的路径（主动登出、Cookie 失效、Token 刷新失败）都会执行
- 新增任何按用户维度存放的客户端状态时，必须同步加入该清理分支

## 7. 容器编排

### 7.1 服务列表

| 容器            | 镜像/构建          | 端口           | 依赖              |
| --------------- | ------------------ | -------------- | ----------------- |
| `db`            | postgres:15-alpine | 127.0.0.1:5433 | -                 |
| `redis`         | redis:7-alpine     | 127.0.0.1:6379 | -                 |
| `minio`         | minio/minio:latest | 9000/9001      | -                 |
| `backend`       | 构建               | 127.0.0.1:8000 | db, redis, minio  |
| `celery-worker` | 构建               | -              | db, redis, minio  |
| `frontend`      | 构建               | 3000           | backend           |
| `backup`        | 构建               | -              | db, minio         |
| `nginx`         | nginx:alpine       | 80             | frontend, backend |

监控栈（随主栈一并启动，端口均绑定 127.0.0.1）：

| 容器                | 镜像                                          | 端口           | 说明               |
| ------------------- | --------------------------------------------- | -------------- | ------------------ |
| `prometheus`        | prom/prometheus:v2.54.1                       | 127.0.0.1:9090 | 指标采集与告警规则 |
| `grafana`           | grafana/grafana:11.4.0                        | 127.0.0.1:3001 | 仪表盘             |
| `redis-exporter`    | oliver006/redis_exporter:v1.62.0              | 127.0.0.1:9121 | Redis 指标导出     |
| `postgres-exporter` | quay.io/prometheuscommunity/postgres-exporter:v0.16.0 | 127.0.0.1:9187 | PostgreSQL 指标导出 |

> `pgbouncer` 同样在主栈内，但 backend 的 `DATABASE_URL` 默认直连 `db`，未经代理；需要走连接池代理时手动改为指向 `pgbouncer:5432`。

### 7.2 开发 vs 生产

| 特性     | 开发模式                     | 生产模式                 |
| -------- | ---------------------------- | ------------------------ |
| 配置文件 | docker-compose.yml + dev.yml | 仅 docker-compose.yml    |
| 后端运行 | uvicorn --reload（热重载）   | Gunicorn × N Worker      |
| 前端运行 | npm run dev（热重载）        | next start（standalone） |
| 代码加载 | Volume 挂载                  | 构建产物内置             |
| Celery   | Eager 模式（同步执行）       | 独立 Worker 容器         |
| 启动时间 | ~2 秒                        | 需构建                   |

## 8. 关键设计决策

1. **流式上传**：文件直传 MinIO，后端不缓存完整文件，内存占用 O(1)
2. **异步 ORM**：SQLAlchemy 2.0 async，所有数据库操作异步执行
3. **游标分页**：大列表使用 `cursor` 分页替代 `offset`，避免深分页性能问题
4. **三元组搜索**：pg_trgm + GIN 索引实现模糊搜索，替代低效 ILIKE
5. **WS 多 Worker**：Redis Pub/Sub 消息总线，支持多 Gunicorn Worker 跨进程广播
6. **CSRF 纯 ASGI**：自定义 ASGI 中间件，避免 BaseHTTPMiddleware 性能开销
7. **多阶段构建**：Docker 镜像最小化，backend 315MB / frontend 216MB
8. **非 root 运行**：生产容器以非 root 用户运行，降低安全风险
9. **会话边界隔离**：客户端缓存与通知状态随登出整体清空，避免同一浏览器内跨用户串数据
10. **公共能力下沉**：客户端 IP 解析、SMTP 发信、游标分页统一收敛到单一实现，避免多处副本各自漂移