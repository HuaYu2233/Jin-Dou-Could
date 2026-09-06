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
- **对象存储**：MinIO（S3 兼容）
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
│   │   ├── core/               # config, security, storage
│   │   ├── db/                 # 数据库引擎与会话
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

| 配置项                        | 说明                     | 默认值                |
| ----------------------------- | ------------------------ | --------------------- |
| `POSTGRES_USER`               | 数据库用户名             | clouduser             |
| `POSTGRES_PASSWORD`           | 数据库密码               | -                     |
| `POSTGRES_DB`                 | 数据库名                 | clouddrive            |
| `MINIO_ROOT_USER`             | MinIO 用户名             | minioadmin            |
| `MINIO_ROOT_PASSWORD`         | MinIO 密码               | -                     |
| `SECRET_KEY`                  | JWT 签名密钥             | -                     |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 过期时间    | 30                    |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh Token 过期时间   | 7                     |
| `NEXT_PUBLIC_API_URL`         | 浏览器访问后端地址       | http://localhost:8000 |
| `API_URL`                     | Docker 内部后端地址      | http://backend:8000   |
| `CORS_ORIGINS`                | 允许的前端源（逗号分隔） | http://localhost:3000 |

### 迁移到生产环境

```bash
# 1. 修改 .env 中的配置
#    - NEXT_PUBLIC_API_URL 改为实际域名（如 https://api.example.com）
#    - CORS_ORIGINS 改为前端域名（如 https://cloud.example.com）
#    - 修改所有密码和 SECRET_KEY

# 2. 重新构建并启动
docker compose up -d --build
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
