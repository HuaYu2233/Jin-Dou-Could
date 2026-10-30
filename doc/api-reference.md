# API 接口文档

> 完整交互式文档：http://localhost:8000/docs（Swagger UI）

## 1. 概述

- **Base URL**: `/api/v1`
- **认证方式**: JWT Cookie（HttpOnly + Secure）
- **Content-Type**: `application/json`（文件上传使用 `multipart/form-data`）

## 2. 认证模块 `/api/v1/auth`

### 2.1 注册

```
POST /api/v1/auth/register
```

| 字段              | 类型   | 必填 | 说明     |
| ----------------- | ------ | ---- | -------- |
| email             | string | 是   | 邮箱地址 |
| username          | string | 是   | 用户名   |
| password          | string | 是   | 密码     |
| security_question | string | 否   | 密保问题 |
| security_answer   | string | 否   | 密保答案 |

**响应**: `UserResponse`

### 2.2 登录

```
POST /api/v1/auth/login
```

| 字段     | 类型   | 必填 | 说明 |
| -------- | ------ | ---- | ---- |
| email    | string | 是   | 邮箱 |
| password | string | 是   | 密码 |

**响应**: 设置 `access_token` / `refresh_token` Cookie，返回 `LoginResponse`

**限流**: 同一 IP + 邮箱 5 次失败后锁定 15 分钟

### 2.3 刷新 Token

```
POST /api/v1/auth/refresh
```

从 Cookie 读取 `refresh_token`，签发新的 `access_token`

### 2.4 退出登录

```
POST /api/v1/auth/logout
```

将 Token 加入 Redis 黑名单，清除 Cookie

### 2.5 忘记密码

```
POST /api/v1/auth/forgot-password
```

| 字段  | 类型   | 必填 | 说明 |
| ----- | ------ | ---- | ---- |
| email | string | 是   | 邮箱 |

发送验证码到邮箱

### 2.6 重置密码（验证码）

```
POST /api/v1/auth/reset-password
```

| 字段         | 类型   | 必填 | 说明   |
| ------------ | ------ | ---- | ------ |
| email        | string | 是   | 邮箱   |
| code         | string | 是   | 验证码 |
| new_password | string | 是   | 新密码 |

### 2.7 获取密保问题

```
POST /api/v1/auth/security-question
```

### 2.8 通过密保重置密码

```
POST /api/v1/auth/reset-password-by-security
```

## 3. 用户模块 `/api/v1/users`

### 3.1 获取当前用户信息

```
GET /api/v1/users/me
```

### 3.2 修改用户名

```
PATCH /api/v1/users/me
```

| 字段     | 类型   | 必填 | 说明   |
| -------- | ------ | ---- | ------ |
| username | string | 否   | 用户名 |

### 3.3 修改密码

```
POST /api/v1/users/me/password
```

| 字段         | 类型   | 必填 | 说明   |
| ------------ | ------ | ---- | ------ |
| old_password | string | 是   | 旧密码 |
| new_password | string | 是   | 新密码 |

### 3.4 上传头像

```
POST /api/v1/users/me/avatar
```

`multipart/form-data`，字段名 `file`

### 3.5 存储统计

```
GET /api/v1/users/me/storage
```

**响应**:

```json
{
  "used_storage": 536870912,
  "storage_quota": 1073741824
}
```

## 4. 文件模块 `/api/v1/files`

### 4.1 上传文件

```
POST /api/v1/files?folder_id={uuid}
```

`multipart/form-data`，字段名 `file`

**限制**:

- 单文件最大 100MB（`MAX_UPLOAD_SIZE`）
- MIME 类型白名单校验
- 文件名净化（去除特殊字符）
- 存储配额检查

**上传完成后**:

- 自动异步生成缩略图（图片文件）
- WebSocket 推送 `upload:complete` 和 `storage:changed`

### 4.2 文件列表

```
GET /api/v1/files?skip=0&limit=20&file_type=image&folder_id={uuid}&cursor={iso_time}
```

| 参数      | 类型   | 说明                                  |
| --------- | ------ | ------------------------------------- |
| skip      | int    | 偏移量（默认 0）                      |
| limit     | int    | 每页数量（1-100，默认 20）            |
| file_type | string | 文件类型过滤                          |
| folder_id | uuid   | 文件夹 ID                             |
| cursor    | string | 游标分页（上一页最后一条 created_at） |

### 4.3 搜索文件

```
GET /api/v1/files/search?keyword=xxx&skip=0&limit=20
```

使用 pg_trgm 三元组相似度搜索

### 4.4 移动文件

```
POST /api/v1/files/move
```

| 字段             | 类型      | 说明         |
| ---------------- | --------- | ------------ |
| file_ids         | uuid[]    | 文件 ID 列表 |
| target_folder_id | uuid/null | 目标文件夹   |

### 4.5 获取文件详情

```
GET /api/v1/files/{file_id}
```

### 4.6 预览文件

```
GET /api/v1/files/{file_id}/preview
```

返回 MinIO 预签名 URL

### 4.7 获取缩略图

```
GET /api/v1/files/{file_id}/thumbnail
```

优先返回缩略图，无缩略图时返回原图

### 4.8 下载文件

```
GET /api/v1/files/{file_id}/download
```

返回 MinIO 预签名下载 URL

### 4.9 删除文件（软删除）

```
DELETE /api/v1/files/{file_id}
```

移入回收站，WebSocket 推送 `storage:changed`

### 4.10 恢复文件

```
POST /api/v1/files/{file_id}/restore
```

### 4.11 彻底删除

```
DELETE /api/v1/files/{file_id}/purge
```

从数据库和 MinIO 中永久删除

### 4.12 回收站列表

```
GET /api/v1/files/trash?skip=0&limit=20
```

## 5. 文件夹模块 `/api/v1/folders`

### 5.1 创建文件夹

```
POST /api/v1/folders
```

| 字段      | 类型      | 说明        |
| --------- | --------- | ----------- |
| name      | string    | 文件夹名称  |
| parent_id | uuid/null | 父文件夹 ID |

### 5.2 文件夹内容列表

```
GET /api/v1/folders?folder_id={uuid}&skip=0&limit=50
```

返回子文件夹、文件、面包屑导航、文件总数

### 5.3 重命名文件夹

```
PUT /api/v1/folders/{folder_id}
```

| 字段 | 类型   | 说明   |
| ---- | ------ | ------ |
| name | string | 新名称 |

### 5.4 删除文件夹（软删除）

```
DELETE /api/v1/folders/{folder_id}
```

级联软删除：文件夹及所有子文件/子文件夹移入回收站

### 5.5 恢复文件夹

```
POST /api/v1/folders/{folder_id}/restore
```

### 5.6 彻底删除文件夹

```
DELETE /api/v1/folders/{folder_id}/purge
```

级联删除：从数据库和 MinIO 中永久删除所有内容

### 5.7 回收站文件夹列表

```
GET /api/v1/folders/trash?skip=0&limit=20
```

## 6. 分享模块 `/api/v1/shares`

### 6.1 创建分享

```
POST /api/v1/shares/{file_id}
```

| 字段         | 类型 | 说明                      |
| ------------ | ---- | ------------------------- |
| expires_days | int  | 过期天数（null=永不过期） |

返回 `share_token` 和 `extract_code`

### 6.2 我的分享列表

```
GET /api/v1/shares?skip=0&limit=20
```

### 6.3 取消分享

```
DELETE /api/v1/shares/{share_id}
```

### 6.4 获取分享信息（公开）

```
GET /api/v1/shares/public/{token}
```

无需认证，返回文件基本信息

### 6.5 验证提取码（公开）

```
POST /api/v1/shares/public/{token}/verify
```

| 字段         | 类型   | 说明   |
| ------------ | ------ | ------ |
| extract_code | string | 提取码 |

**限流**: 同一 token 短时间内验证失败次数限制

### 6.6 下载分享文件（公开）

```
GET /api/v1/shares/public/{token}/download?extract_code=xxx
```

## 7. 管理模块 `/api/v1/admin`

> 需要管理员权限

### 7.1 系统统计

```
GET /api/v1/admin/stats
```

返回用户数、存储使用量、文件数等

### 7.2 用户列表

```
GET /api/v1/admin/users?skip=0&limit=20
```

### 7.3 修改用户

```
PATCH /api/v1/admin/users/{user_id}
```

| 字段          | 类型    | 说明       |
| ------------- | ------- | ---------- |
| username      | string  | 用户名     |
| storage_quota | int     | 存储配额   |
| is_active     | boolean | 是否启用   |
| is_admin      | boolean | 是否管理员 |

### 7.4 删除用户

```
DELETE /api/v1/admin/users/{user_id}
```

### 7.5 重算用户存储

```
POST /api/v1/admin/users/{user_id}/recalculate-storage
```

## 8. 备份模块 `/api/v1/admin/backups`

> 需要管理员权限

### 8.1 备份列表

```
GET /api/v1/admin/backups
```

### 8.2 触发备份

```
POST /api/v1/admin/backups
```

### 8.3 下载备份

```
GET /api/v1/admin/backups/{filename}
```

## 9. 任务模块 `/api/v1/admin/tasks`

> 需要管理员权限

### 9.1 任务状态

```
GET /api/v1/admin/tasks/{task_id}
```

### 9.2 活跃任务列表

```
GET /api/v1/admin/tasks/active
```

## 10. WebSocket `/api/v1/ws`

### 10.1 连接

```
WS /api/v1/ws
```

认证方式：首条消息发送 `{"type": "auth", "token": "xxx"}`，5 秒内未认证则断开

### 10.2 事件类型

| 事件              | 方向   | 说明             |
| ----------------- | ------ | ---------------- |
| `auth`            | 客户端 | 认证             |
| `upload:complete` | 服务端 | 上传完成通知     |
| `share:created`   | 服务端 | 分享创建通知     |
| `storage:changed` | 服务端 | 存储空间变更通知 |

**消息限制**: 单条消息最大 4KB

## 11. 健康检查

### 11.1 Liveness

```
GET /health
```

轻量心跳，检查 Redis 连通性

### 11.2 Readiness

```
GET /health/ready
```

全组件探测，返回各组件状态与延迟

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

### 11.3 Prometheus 指标

```
GET /metrics
```

需启用 `PROMETHEUS_ENABLED=true`
