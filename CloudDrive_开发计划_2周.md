# Cloud Drive 开发计划文档

> **技术栈**: Next.js 16 (TS) + FastAPI + PostgreSQL + Redis + MinIO  
> **周期**: 2 周（14 天）  
> **目标**: 完成用户认证、文件上传下载、文件夹管理、基础文件列表

---

## 🎯 总体目标

- **第 1 周末**: `docker-compose up` 能跑通，能注册/登录，前后端 API 联通
- **第 2 周末**: 能上传/下载文件，能看到文件列表，能创建和管理文件夹

---

## 📅 Week 1：基础设施 + 用户认证

---

### Day 1｜周一：环境搭起来

**核心目标**: 所有容器能跑通，服务可访问

| 时间 | 任务 | 交付物/验收标准 |
|------|------|----------------|
| 上午 | 创建目录结构，放置 `docker-compose.yml`、`.env`、`backend/Dockerfile`、`frontend/Dockerfile` | 目录结构完整 |
| 下午 | `frontend` 目录执行 `npx create-next-app@latest .`（TS + App Router + Tailwind v4），覆盖默认配置 | `next.config.ts` 配置好 `allowedDevOrigins` |
| 傍晚 | `backend` 目录创建 `requirements.txt`，写最简 FastAPI 入口 `app/main.py`（仅一个 `/health` 路由返回 `{"status": "ok"}`） | 能 `uvicorn app.main:app` 本地跑起来 |
| 晚上 | 根目录执行 `docker-compose up --build`，解决报错直到全部绿灯 | `localhost:3000`、`localhost:8000/health`、`localhost:9001` 都能打开 |

**今日底线**: `docker-compose ps` 看到 5 个容器全部 Up。

---

### Day 2｜周二：数据库 + 用户表

**核心目标**: 后端能连上数据库，用户表创建成功

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 后端创建 `app/core/config.py`，用 `pydantic-settings` 管理环境变量（`DATABASE_URL`、`SECRET_KEY` 等） | 配置中心完成 |
| 下午 | 创建 `app/db/base.py`（SQLAlchemy 2.0 async 引擎 + AsyncSession） | 数据库连接池可用 |
| 傍晚 | 创建 `app/models/user.py`：User 表（id, email, hashed_password, username, is_active, created_at, storage_quota, used_storage） | 模型文件 |
| 晚上 | 安装 `alembic`，初始化迁移，生成第一张表 | `alembic upgrade head` 后 PostgreSQL 里有 `users` 表 |

**User 模型参考字段**:
```python
id: UUID (PK)
email: str (unique, index)
username: str
hashed_password: str
is_active: bool = True
is_superuser: bool = False
storage_quota: bigint = 1073741824  # 默认 1GB
used_storage: bigint = 0
created_at: datetime
updated_at: datetime
```

**今日底线**: FastAPI 容器里能执行 `alembic upgrade head` 且不报错。

---

### Day 3｜周三：后端注册 API

**核心目标**: 能写进数据库

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 创建 `app/schemas/user.py`：`UserCreate`（email, username, password）、`UserResponse`（不含密码） | Pydantic Schema |
| 下午 | 创建 `app/core/security.py`：bcrypt 哈希密码、`verify_password` | 密码工具 |
| 傍晚 | 创建 `app/services/user_service.py`：`create_user()` 逻辑（查重 → 哈希 → 入库） | 业务层 |
| 晚上 | 创建 `app/api/v1/endpoints/auth.py`：`POST /api/v1/auth/register` 路由 | 注册 API |

**今日底线**: 用 curl/Postman 调 `localhost:8000/api/v1/auth/register`，数据库里能看到新用户。

---

### Day 4｜周四：后端登录 + JWT

**核心目标**: 能发 Token

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | `security.py` 里加 `create_access_token()`、`create_refresh_token()`（`python-jose` + JWT） | JWT 工具 |
| 下午 | `auth.py` 里加 `POST /api/v1/auth/login`：校验密码 → 发双 Token（access + refresh） | 登录 API |
| 傍晚 | 创建 `app/api/deps.py`：`get_current_user()` 依赖，解析 JWT 返回当前用户 | 认证依赖 |
| 晚上 | 加一个受保护的路由（如 `GET /api/v1/users/me`）测试 Token | 带鉴权的接口 |

**Token 策略建议**:
- Access Token：15-30 分钟，放 Response Body
- Refresh Token：7 天，放 **HttpOnly Cookie**（前端后续用 `credentials: 'include'`）

**今日底线**: Postman 调登录拿到 Token，再带 Token 调 `/users/me` 能返回用户信息。

---

### Day 5｜周五：前端基础 + API 封装

**核心目标**: 项目结构清晰，API 层就绪

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 前端建目录：`app/(auth)/login`、`app/(auth)/register`、`app/(dashboard)/layout.tsx` | 路由结构 |
| 下午 | 创建 `lib/api/client.ts`：封装 `fetch`，自动带 Token、处理 401 | API 客户端 |
| 傍晚 | 创建 `lib/api/auth.ts`：`login()`、`register()`、`getMe()` 三个函数 | 认证 API 层 |
| 晚上 | 全局布局 `app/layout.tsx` 配好 Tailwind v4，写一个最简的 `app/page.tsx`（登录入口按钮） | 首页 |

**今日底线**: 前端页面能打开，点击按钮能发起请求（哪怕后端还没联调）。

---

### Day 6｜周六：前端登录/注册页面

**核心目标**: 能交互

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 安装 `react-hook-form` + `zod` + `@hookform/resolvers`，写登录表单 | 登录页 UI |
| 下午 | 写注册表单，表单校验（邮箱格式、密码 8 位以上） | 注册页 UI |
| 傍晚 | 联调后端：注册 → 跳转登录 → 登录 → 存 Token → 跳 `/dashboard` | 完整流程 |
| 晚上 | 登录态持久化：`localStorage` 存 access token，页面刷新后还在 | 状态保持 |

**今日底线**: 在浏览器里完成「注册 → 登录 → 进入 Dashboard」全流程。

---

### Day 7｜周日：缓冲 + 联调 + 文档

**核心目标**: 没 Bug，状态干净

| 任务 | 说明 |
|------|------|
| 修 Bug | 跨域问题、Cookie 带不上、Token 过期处理 |
| 写 README | 记录环境变量、启动命令、API 列表 |
| 代码整理 | 把 `console.log` 清掉，加必要的错误提示（如"邮箱已存在"） |
| 规划 Week 2 | 确认下周任务优先级 |

**本周验收**: 新用户能在浏览器注册登录，登录后看到 Dashboard 空页面。

---

## 📅 Week 2：文件上传 + 文件管理基础

---

### Day 8｜周一：前端路由守卫 + 状态管理

**核心目标**: 安全，未登录进不去

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 创建 `app/middleware.ts`：未登录用户访问 `/dashboard/*` 重定向到 `/login` | 路由守卫 |
| 下午 | 安装 `zustand`，创建 `stores/auth.ts`：全局存 `user` 信息、登录状态 | 状态管理 |
| 傍晚 | Dashboard 布局：侧边栏（文件/图片/视频分类）+ 顶部栏（用户头像/退出） | Dashboard 骨架 |
| 晚上 | 退出登录：清 Token、清状态、跳首页 | 退出功能 |

**今日底线**: 未登录直接输 `localhost:3000/dashboard` 会被踢回登录页。

---

### Day 9｜周二：文件上传后端 - 单文件

**核心目标**: 能存文件

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 后端 `app/core/minio_client.py`：封装 MinIO 客户端，启动时自动建 `cloud-drive` bucket | MinIO 工具类 |
| 下午 | 创建 `app/models/file.py`：`File` 表（id, user_id, filename, original_name, size, mime_type, storage_path, folder_id, created_at, updated_at, is_deleted） | 文件模型 |
| 傍晚 | `alembic` 生成新迁移，创建 `files` 表 | 数据库迁移 |
| 晚上 | `app/api/v1/endpoints/files.py`：`POST /api/v1/files/upload` 单文件上传，存 MinIO + 写元数据到 PG | 上传 API |

**今日底线**: Postman 调上传，MinIO 控制台里能看到文件对象，PG 里有记录。

---

### Day 10｜周三：文件上传后端 - 分片协议

**核心目标**: 支持大文件

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 设计分片上传协议：3 个接口  
① `POST /files/upload/init`（返回 upload_id）  
② `POST /files/upload/chunk`（传 chunk_index + 二进制）  
③ `POST /files/upload/complete`（合并） | 接口设计文档 |
| 下午 | 实现 `init` 和 `chunk`：每片临时存 MinIO `tmp/{upload_id}/{chunk_index}` | 分片存储 |
| 傍晚 | 实现 `complete`：按顺序合并分片 → 移入正式路径 → 写库 → 清 tmp | 合并逻辑 |
| 晚上 | 加容量检查：上传前 `used_storage + file_size > quota` 则拒绝 | 配额校验 |

**今日底线**: 能上传一个 100MB 的文件，MinIO 里没有残留 tmp 文件。

---

### Day 11｜周四：前端上传组件

**核心目标**: 能拖拽上传

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 创建 `components/upload/UploadDropzone.tsx`：拖拽区域、文件选择、显示待传列表 | 上传组件 |
| 下午 | 实现分片上传前端逻辑：切片（每片 5MB）、串行/并行上传、进度计算 | 上传逻辑 |
| 傍晚 | 上传进度条 UI：`components/upload/UploadProgress.tsx` | 进度组件 |
| 晚上 | 上传完成后刷新文件列表（现在列表是空的，先打印日志确认） | 上传完成回调 |

**今日底线**: 浏览器里拖拽一个文件，能看到进度条走到 100%，后端有记录。

---

### Day 12｜周五：文件列表 + 下载/删除

**核心目标**: 能看能下能删

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 后端 `GET /api/v1/files`：查询当前用户文件列表（分页、排序） | 列表 API |
| 下午 | 前端 `components/file/FileList.tsx`：表格/网格展示文件名、大小、时间 | 文件列表 UI |
| 傍晚 | 下载：后端 `GET /api/v1/files/{id}/download` 返回预签名 URL（MinIO `presigned_get_object`） | 下载 API |
| 晚上 | 删除：后端 `DELETE /api/v1/files/{id}`（软删除 `is_deleted=true`）+ 前端垃圾桶图标 | 删除功能 |

**今日底线**: Dashboard 能看到上传的文件，能点击下载，能删除。

---

### Day 13｜周六：文件夹管理

**核心目标**: 能分类

| 时间 | 任务 | 交付物 |
|------|------|--------|
| 上午 | 后端 `Folder` 模型（id, user_id, name, parent_id, created_at），自关联树 | 文件夹表 |
| 下午 | 后端 API：创建文件夹、获取文件夹树（平铺或树形 JSON） | 文件夹 API |
| 傍晚 | 前端：面包屑导航、左侧文件夹树、点击切换目录 | 文件夹 UI |
| 晚上 | 上传时指定 `folder_id`，文件列表按当前目录过滤 | 目录关联 |

**今日底线**: 能建文件夹，能把文件传进指定文件夹，切换目录看到不同内容。

---

### Day 14｜周日：缓冲 + 联调 + 清理

**核心目标**: 可用，能交付

| 任务 | 说明 |
|------|------|
| 端到端测试 | 注册 → 上传 3 个文件 → 建文件夹 → 移进去 → 下载 → 删除 → 退出 |
| 容量显示 | Dashboard 顶部加进度条：`已用 150MB / 1GB` |
| 错误处理 | 上传失败重试、网络断开提示、超配额提示 |
| 代码提交 | 打 `git tag v0.1.0`，写 Week 2 总结 |

**本周验收**: 用户能注册登录，能拖拽上传文件（支持大文件），能建文件夹管理，能下载和删除。

---

## ✅ 每日检查清单

每天下班前问自己：

1. **今天的代码在 Docker 里能跑吗？**（`docker-compose up` 不报错）
2. **数据库迁移是最新的吗？**（`alembic current` 确认）
3. **API 能用 curl 通吗？**（不要只依赖浏览器）
4. **今天写的有提交到 Git 吗？**（每天一 commit，防丢）

---

## ⚠️ 风险提醒 / 避坑指南

| 坑 | 提前规避 |
|----|----------|
| **MinIO 外网访问** | 开发期 MinIO 返回的 URL 是内网地址，前端直接访问会失败。后端用 `presigned_url` 时，确保 `MINIO_ENDPOINT` 配的是容器名（`minio:9000`），但给前端的 URL 要转成 `localhost:9000` |
| **SQLAlchemy async 坑** | 所有 ORM 操作必须 `await session.execute()`，同步操作会阻塞整个事件循环 |
| **Next.js 14+ 路由** | App Router 的 `page.tsx` 默认是 Server Component，调 API 用 `fetch`。表单交互必须加 `'use client'` |
| **Tailwind v4 没有 config 文件** | 别找 `tailwind.config.ts`，主题变量直接写在 `globals.css` 的 `@theme` 里 |
| **Refresh Token 放 Cookie** | 前端 `fetch` 必须加 `credentials: 'include'`，后端 CORS 必须配 `allow_credentials=True` |
| **大文件内存溢出** | 分片上传时，后端不要一次性读整个文件到内存，用 `StreamingResponse` 或分片流式处理 |

---

## 📁 配套目录结构

项目完整目录树见 `DIRECTORY_STRUCTURE.md`（或之前的对话记录）。

---

*文档生成时间: 2026-08-28*  
*版本: v1.0*
