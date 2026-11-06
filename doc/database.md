# 数据库设计文档

## 1. 概述

- **数据库**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0（异步模式）
- **迁移工具**: Alembic
- **字符集**: UTF-8

## 2. ER 关系图

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    users     │     │   folders    │     │    files     │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id (PK,UUID) │◄──┐ │ id (PK,UUID) │◄──┐ │ id (PK,UUID) │
│ email        │   │ │ owner_id (FK)│   │ │ owner_id (FK)│
│ username     │   │ │ parent_id(FK)│   │ │ folder_id(FK)│
│ hashed_pass  │   │ │ name         │   │ │ filename     │
│ is_active    │   │ │ deleted_at   │   │ │ storage_key  │
│ is_admin     │   │ │ created_at   │   │ │ size         │
│ avatar_key   │   │ │ updated_at   │   │ │ mime_type    │
│ security_*   │   └─│              │   └─│ file_type    │
│ storage_quota│     └──────────────┘     │ status       │
│ used_storage │                           │ thumbnail_key│
│ created_at   │     ┌──────────────┐     │ deleted_at   │
│ updated_at   │     │    shares    │     │ created_at   │
└──────────────┘     ├──────────────┤     │ updated_at   │
                     │ id (PK,UUID) │     └──────────────┘
                     │ file_id (FK) │
                     │ owner_id (FK)│
                     │ share_token  │
                     │ extract_code │
                     │ expires_at   │
                     │ views        │
                     │ created_at   │
                     └──────────────┘
```

## 3. 表结构详情

### 3.1 users - 用户表

| 字段              | 类型          | 约束          | 说明               |
| ----------------- | ------------- | ------------- | ------------------ |
| id                | UUID          | PK            | 主键               |
| email             | VARCHAR(255)  | UNIQUE, INDEX | 邮箱地址           |
| username          | VARCHAR(100)  | NOT NULL      | 用户名             |
| hashed_password   | VARCHAR(255)  | NOT NULL      | 密码哈希（bcrypt） |
| is_active         | BOOLEAN       | DEFAULT true  | 是否启用           |
| is_admin          | BOOLEAN       | DEFAULT false | 是否管理员         |
| avatar_key        | VARCHAR(255)  | NULLABLE      | 头像 MinIO key     |
| security_question | VARCHAR(255)  | NULLABLE      | 密保问题           |
| security_answer   | VARCHAR(255)  | NULLABLE      | 密保答案（哈希）   |
| storage_quota     | BIGINT        | DEFAULT 1GB   | 存储配额（字节）   |
| used_storage      | BIGINT        | DEFAULT 0     | 已用存储（字节）   |
| created_at        | TIMESTAMP(tz) | DEFAULT now() | 创建时间           |
| updated_at        | TIMESTAMP(tz) | DEFAULT now() | 更新时间           |

### 3.2 folders - 文件夹表

| 字段       | 类型          | 约束                    | 说明                    |
| ---------- | ------------- | ----------------------- | ----------------------- |
| id         | UUID          | PK                      | 主键                    |
| owner_id   | UUID          | FK→users.id             | 所属用户                |
| parent_id  | UUID          | FK→folders.id, NULLABLE | 父文件夹（null=根目录） |
| name       | VARCHAR(255)  | NOT NULL                | 文件夹名称              |
| deleted_at | TIMESTAMP(tz) | NULLABLE                | 软删除时间              |
| created_at | TIMESTAMP(tz) | DEFAULT now()           | 创建时间                |
| updated_at | TIMESTAMP(tz) | DEFAULT now()           | 更新时间                |

**索引**:

- `ix_folders_owner_deleted_at` (owner_id, deleted_at)
- `ix_folders_owner_parent_name` (owner_id, parent_id, name)
- `ix_folders_parent_id` (parent_id)

### 3.3 files - 文件表

| 字段          | 类型          | 约束                    | 说明             |
| ------------- | ------------- | ----------------------- | ---------------- |
| id            | UUID          | PK                      | 主键             |
| owner_id      | UUID          | FK→users.id             | 所属用户         |
| folder_id     | UUID          | FK→folders.id, NULLABLE | 所在文件夹       |
| filename      | VARCHAR(255)  | NOT NULL                | 文件名           |
| storage_key   | VARCHAR(512)  | UNIQUE                  | MinIO 对象 key   |
| size          | BIGINT        | NOT NULL                | 文件大小（字节） |
| mime_type     | VARCHAR(255)  | NOT NULL                | MIME 类型        |
| file_type     | VARCHAR(50)   | NOT NULL                | 文件分类         |
| status        | VARCHAR(20)   | DEFAULT ready           | 状态             |
| thumbnail_key | VARCHAR(512)  | NULLABLE                | 缩略图 MinIO key |
| deleted_at    | TIMESTAMP(tz) | NULLABLE                | 软删除时间       |
| created_at    | TIMESTAMP(tz) | DEFAULT now()           | 创建时间         |
| updated_at    | TIMESTAMP(tz) | DEFAULT now()           | 更新时间         |

**索引**:

- `ix_files_owner_folder_created` (owner_id, folder_id, created_at)
- `ix_files_owner_deleted_at` (owner_id, deleted_at)
- `ix_files_owner_type_created` (owner_id, file_type, created_at)
- `ix_files_owner_deleted_filename` (owner_id, deleted_at, filename)
- `ix_files_filename_trgm` (filename) - GIN 三元组索引，支持模糊搜索

**`file_type` 取值**：`image` / `document` / `video` / `audio` / `archive` / `other`，由上传时 `python-magic` 探测出的真实 MIME 推导后落库，不随分类规则调整而回填。

### 3.4 shares - 分享表

| 字段         | 类型          | 约束          | 说明       |
| ------------ | ------------- | ------------- | ---------- |
| id           | UUID          | PK            | 主键       |
| file_id      | UUID          | FK→files.id   | 分享的文件 |
| owner_id     | UUID          | FK→users.id   | 分享创建者 |
| share_token  | VARCHAR(32)   | UNIQUE, INDEX | 分享令牌   |
| extract_code | VARCHAR(8)    | NOT NULL      | 提取码     |
| expires_at   | TIMESTAMP(tz) | NULLABLE      | 过期时间   |
| views        | INTEGER       | DEFAULT 0     | 访问次数   |
| created_at   | TIMESTAMP(tz) | DEFAULT now() | 创建时间   |

**索引**:

- `ix_shares_owner_created` (owner_id, created_at)

## 4. 软删除机制

文件和文件夹使用 `deleted_at` 字段实现软删除：

| 状态   | deleted_at 值 | 说明            |
| ------ | ------------- | --------------- |
| 正常   | NULL          | 文件/文件夹可见 |
| 回收站 | 非 NULL       | 已软删除        |

**级联软删除**：删除文件夹时，文件夹本身及所有子文件/子文件夹的 `deleted_at` 被设置为当前时间。

**彻底删除**：从数据库中 DELETE 记录，并从 MinIO 中删除对应的对象。

## 5. 迁移历史

| 迁移文件                                                 | 说明                         |
| -------------------------------------------------------- | ---------------------------- |
| 9e0bb531cd35_add_users_table                             | 创建用户表                   |
| 2ebb801da8c6_add_files_table                             | 创建文件表                   |
| c3d4e5f6a7b8_add_folders_table                           | 创建文件夹表                 |
| b2c3d4e5f6a7_add_shares_table                            | 创建分享表                   |
| a1b2c3d4e5f6_add_deleted_at_to_files                     | 文件表添加软删除字段         |
| d4e5f6a7b8c9_add_is_admin_to_users                       | 用户表添加管理员字段         |
| e5f6a7b8c9d0_add_avatar_key_to_users                     | 用户表添加头像字段           |
| f6a7b8c9d0e1_add_security_question_to_users              | 用户表添加密保问题字段       |
| g1h2i3j4k5l6_add_composite_indexes_for_cursor_pagination | 添加游标分页复合索引         |
| h2i3j4k5l6m7_add_deleted_at_to_folders                   | 文件夹表添加软删除字段       |
| i3j4k5l6m7n8_add_composite_indexes_for_type_filter...    | 添加类型过滤复合索引         |
| j4k5l6m7n8o9_add_search_and_folder_composite_indexes     | 添加搜索和文件夹复合索引     |
| k5l6m7n8o9p0_add_pgtrgm_extension_and_gin_index          | 添加 pg_trgm 扩展和 GIN 索引 |
| l7m8n9o0p1q2_add_thumbnail_key_to_files                  | 文件表添加缩略图字段         |
| m8n9o0p1q2r3_widen_share_extract_code                    | 分享提取码列扩宽到 8 位       |

## 6. Redis 数据结构

Redis 在项目中承担多种职责，使用不同的 DB 编号：

| DB  | 用途                                | Key 模式                                                        | 说明       |
| --- | ----------------------------------- | --------------------------------------------------------------- | ---------- |
| 0   | 缓存/限流/Token/WebSocket Pub/Sub   | `user:{id}`, `rl:{ip}:global`, `ws:user:{id}`                   | 默认数据库 |
| 1   | Celery Broker                       | Celery 内部管理                                                 | 任务队列   |
| 2   | Celery Result                       | Celery 内部管理                                                 | 任务结果   |

> `REDIS_URL` 默认带 `/0`，后端所有业务 key 与 Pub/Sub 频道都在 DB 0；Celery 的 broker/backend 由 `_build_celery_url` 从 `REDIS_URL` 派生到 DB 1 / DB 2。

### 6.1 主要 Key 设计

| Key 模式                            | 类型   | TTL                          | 说明                               |
| ----------------------------------- | ------ | ---------------------------- | ---------------------------------- |
| `user:{user_id}`                    | String | 60s                          | 用户信息缓存（JSON 序列化）        |
| `rl:{ip}:global`                    | ZSet   | 60s                          | 全局限流滑动窗口                   |
| `rl:{ip}:login`                     | ZSet   | 60s                          | 登录/注册路径限流滑动窗口          |
| `login_rl:{ip}:{email}`             | String | 300s                         | 登录失败计数                       |
| `login_lock:{ip}:{email}`           | String | 900s                         | 登录失败锁定标记                   |
| `token_blacklist:{jti}`             | String | 剩余 Token 有效期            | Token 黑名单                       |
| `share_verify:{token}:{ip}`         | String | 900s                         | 分享提取码验证失败计数             |
| `share_lock:{token}:{ip}`           | String | 900s                         | 分享提取码锁定标记                 |
| `reset_password_send_limit:{email}` | String | 60s                          | 重置验证码发送频率限制             |
| `reset_password_code:{email}`       | String | `RESET_PASSWORD_CODE_EXPIRE_SECONDS`（默认 600s） | 密码重置验证码 |
| `ws:user:{user_id}`                 | Pub/Sub 频道 | 无                       | WebSocket 多 Worker 消息广播       |

> 告警冷却（`ALERT_COOLDOWN_SECONDS`）是进程内内存字典，不写 Redis；多 Worker 部署时各 Worker 独立计时。

## 7. MinIO 对象存储

### 7.1 Bucket

| Bucket      | 说明     |
| ----------- | -------- |
| cloud-drive | 主存储桶 |

### 7.2 Key 设计

| 类型   | Key 格式                          | 说明              |
| ------ | --------------------------------- | ----------------- |
| 文件   | `{owner_id}/{file_id}/{filename}` | 原始文件          |
| 头像   | `avatars/{user_id}/{filename}`    | 用户头像          |
| 缩略图 | `thumbnails/{file_id}.webp`       | 256×256 缩略图    |
| 备份   | 由备份脚本管理                    | 数据库/MinIO 备份 |