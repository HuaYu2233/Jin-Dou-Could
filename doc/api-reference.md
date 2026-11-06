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
PATCH /api/v1/users/me/profile
```

| 字段     | 类型   | 必填 | 说明   |
| -------- | ------ | ---- | ------ |
| username | string | 否   | 用户名 |

### 3.3 修改密码

```
PATCH /api/v1/users/me/password
```

| 字段         | 类型   | 必填 | 说明   |
| ------------ | ------ | ---- | ------ |
| old_password | string | 是   | 旧密码 |
| new_password | string | 是   | 新密码 |

改密成功后旧 Access Token 立即进入 Redis 黑名单，需重新登录。

### 3.4 修改密保问题

```
PATCH /api/v1/users/me/security-question
```

| 字段              | 类型   | 必填 | 说明     |
| ----------------- | ------ | ---- | ------------ |
| security_question | string | 是   | 密保问题 |
| security_answer   | string | 是   | 密保答案 |

### 3.5 上传头像

```
POST /api/v1/users/me/avatar
```

`multipart/form-data`，字段名 `file`

**限制**:

- 最大 2MB（`MAX_AVATAR_SIZE`）
- 仅接受 JPG/PNG/WEBP/GIF，以 `python-magic` 探测的真实类型为准；声明的 `Content-Type` 不参与放行判断
- 读取按 2MB 上限截断，超限返回 413

### 3.6 获取头像地址

```
GET /api/v1/users/me/avatar
```

**响应**: `{"url": "..."}`；未设置头像返回 404。

### 3.7 存储用量

容量数据包含在 `UserResponse` 中，无独立端点：

```json
{
  "used_storage": 536870912,
  "storage_quota": 1073741824
}
```

`GET /api/v1/users/me` 返回上述字段；上传完成与删除后通过 WebSocket `storage:changed` 事件推送最新值。

## 4. 文件模块 `/api/v1/files`

### 4.1 上传文件

```
POST /api/v1/files?folder_id={uuid}
```

`multipart/form-data`，字段名 `file`

**限制**:

- 单文件最大 100MB（`MAX_UPLOAD_SIZE`）
- MIME 类型白名单校验（以 `python-magic` 探测结果为准，检测失败直接拒绝）
- 分片上传在第 1 片探测真实类型，完成合并时以探测结果覆盖声明值；上传会话过期后需重新初始化
- 分片序号不得超过声明片数，累计已上传字节不得超过声明大小；合并时校验分片数量与序号连续性
- 合并后以 MinIO 实际对象大小为准写入记录与配额，超过单文件上限或与声明偏差超过一个分片时删除对象并拒绝
- 文本子类型（`text/x-python`、`text/x-shellscript` 等）按 `text/plain` 参与白名单判断
- 常见归档格式（`zip` / `rar` / `7z` / `gzip` / `tar` / `bzip2` / `xz`）在白名单内，归类为 `archive`
- 文件名净化（去除特殊字符）
- 存储配额检查

**上传完成后**:

- 自动异步生成缩略图（图片文件）
- WebSocket 推送 `upload:complete` 和 `storage:changed`

### 4.2 文件列表

```
GET /api/v1/files?skip=0&limit=20&file_type=image&folder_id={uuid}&cursor={iso_time}
```

| 参数      | 类型   | 说明                                                    |
| --------- | ------ | ------------------------------------------------------- |
| skip      | int    | 偏移量（默认 0）                                        |
| limit     | int    | 每页数量（1-100，默认 20）                              |
| file_type | string | 文件类型过滤：`image` / `document` / `video` / `audio` / `archive` / `other` |
| folder_id | uuid   | 文件夹 ID                                               |
| cursor    | string | 游标分页（上一页返回的 `next_cursor`，与 `skip` 二选一） |

`skip` 与 `cursor` 双模式兼容：传入 `cursor` 时优先按游标查询，响应中的 `next_cursor` 供下一页使用；未传时按 `skip` 偏移查询。

`file_type` 由上传时检测出的真实 MIME 推导并落库，归档类覆盖 `zip` / `rar` / `7z` / `gzip` / `x-gzip` / `tar` / `bzip2` / `xz`。历史记录不会因分类规则调整而重新归类。

### 4.3 搜索文件

```
GET /api/v1/files/search?keyword=xxx&skip=0&limit=20&cursor={iso_time}
```

使用 pg_trgm 三元组相似度搜索，参数语义与 4.2 一致（`cursor` 优先于 `skip`）。

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

`text/html`、`application/xhtml+xml`、`image/svg+xml` 的预签名 URL 使用 `attachment` 下载语义，其余类型使用 `inline`

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

### 4.13 分片上传：初始化

```
POST /api/v1/files/multipart/init
```

| 字段       | 类型      | 必填 | 说明                        |
| ---------- | --------- | ---- | --------------------------- |
| filename   | string    | 是   | 文件名                      |
| mime_type  | string    | 否   | 声明类型，默认 `application/octet-stream` |
| total_size | int       | 是   | 文件总字节数                |
| folder_id  | uuid/null | 否   | 目标文件夹                  |

**响应**: `upload_id`、`storage_key`、`part_size`（`UPLOAD_PART_SIZE`）、`total_parts`

初始化时即校验配额与并发上传槽位（`MAX_CONCURRENT_UPLOADS`），超限直接拒绝。

### 4.14 分片上传：上传单片

```
POST /api/v1/files/multipart/part?storage_key=xxx&upload_id=xxx&part_number=1
```

`multipart/form-data`，字段名 `part`

| 参数        | 位置  | 说明                       |
| ----------- | ----- | -------------------------- |
| storage_key | query | 初始化返回的对象 key       |
| upload_id   | query | 初始化返回的 upload id     |
| part_number | query | 分片序号，从 1 开始        |
| part        | form  | 分片二进制内容             |

**响应**: `{"part_number": n, "etag": "..."}`，`etag` 需在完成时回传

### 4.15 分片上传：完成合并

```
POST /api/v1/files/multipart/complete
```

| 字段        | 类型   | 必填 | 说明                                  |
| ----------- | ------ | ---- | ------------------------------------- |
| upload_id   | string | 是   | 初始化返回的 upload id                |
| storage_key | string | 是   | 初始化返回的对象 key                  |
| filename    | string | 是   | 文件名                                |
| mime_type   | string | 是   | 真实类型（合并时以服务端探测结果覆盖） |
| total_size  | int    | 是   | 文件总字节数                          |
| folder_id   | uuid   | 否   | 目标文件夹                            |
| parts       | array  | 是   | `[{part_number, etag}, ...]`          |

**响应**: `FileUploadResponse`，与单次上传一致；完成后推送 `upload:complete` 与 `storage:changed`

### 4.16 分片上传：中止

```
POST /api/v1/files/multipart/abort?storage_key=xxx&upload_id=xxx
```

清理 MinIO 未完成的分片会话，用于前端主动取消或失败重试

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

返回子文件夹、文件、面包屑导航、文件总数。

| 参数      | 类型 | 说明                       |
| --------- | ---- | -------------------------- |
| folder_id | uuid | 文件夹 ID，不传则为根目录 |
| skip      | int  | 偏移量（默认 0）           |
| limit     | int  | 每页数量（1-200，默认 50） |

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

返回 `share_token` 和 `extract_code`（8 位大写字母 + 数字）。同一文件重复创建分享会直接返回已存在的分享记录。

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
| extract_code | string | 提取码（8 位） |

**限流**: 同一 token + 客户端 IP 在 15 分钟内验证失败 5 次后锁定，锁定期间返回 429。

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

**响应**: `BackupInfo` 数组（时间戳、文件清单、大小等）

### 8.2 触发备份

```
POST /api/v1/admin/backups/trigger
```

**响应**: `{"detail": "备份已触发", "timestamp": null}`，实际执行在 Celery Worker 中进行

### 8.3 下载备份文件

```
GET /api/v1/admin/backups/{timestamp}/download?file=xxx
```

| 参数      | 位置  | 说明                 |
| --------- | ----- | -------------------- |
| timestamp | path  | 备份时间戳           |
| file      | query | 备份内的具体文件名   |

不存在时返回 404

### 8.4 删除备份

```
DELETE /api/v1/admin/backups/{timestamp}
```

删除该时间戳下的整份备份，不存在时返回 404

## 9. 任务模块 `/api/v1/admin/tasks`

> 需要管理员权限

### 9.1 任务状态

```
GET /api/v1/admin/tasks/status/{task_id}
```

**响应**: `{"task_id": "...", "status": "PENDING|STARTED|SUCCESS|FAILURE", "result": ...}`

### 9.2 活跃任务列表

```
GET /api/v1/admin/tasks/active
```

**响应**: `{"active": {...}, "reserved": {...}}`，按 Worker 分组列出正在执行与已派发未执行的任务

## 10. WebSocket `/api/v1/ws`

### 10.1 连接

```
WS /api/v1/ws
```

认证优先级：优先读取握手 Cookie 中的 `access_token`；不存在时要求首条消息发送 `{"type": "auth", "token": "xxx"}`，5 秒内未认证则以 `4001` 关闭。

认证失败原因码统一为 `4001`，reason 会区分「认证超时」「认证消息过长」「认证失败」「账号已被禁用」等。

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

需启用 `PROMETHEUS_ENABLED=true`。默认仅内网来源（回环/私有网段）可访问，其他来源返回 403；若配置了 `METRICS_TOKEN`，则必须携带 `Authorization: Bearer <token>`，未携带或错误返回 401。