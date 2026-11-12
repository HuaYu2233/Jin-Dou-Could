# 局域网快传（房间码模式）设计与实施文档

> 状态：方案已定稿，待实施
> 目标版本：下一迭代
> 影响范围：后端配置 / 数据模型 / API / 中间件 / 前端 dashboard + 新增公开页

## 1. 背景与目标

### 1.1 需求

在同一网络下的设备之间快速传输文件：登录用户创建「快传房间」，同网段的手机、另一台电脑用房间码或链接加入，无需注册即可上传、下载。

### 1.2 设计目标

| 目标 | 说明 |
| --- | --- |
| 零门槛加入 | 匿名用户仅凭房间码（可选密码）即可使用 |
| 不依赖 HTTPS | 部署环境可能为纯 HTTP，功能不得依赖安全上下文 |
| 不依赖固定 IP | 链接基于请求 origin 生成，支持局域网 IP 变动、虚拟机 NAT |
| 数据不落个人云盘 | 快传文件独立生命周期，不占用户配额、不进回收站与分享 |
| 容量可控 | 普通用户单文件 1GB、房间总量 1GB；管理员按服务器剩余空间 |
| 空间不足自动暂停 | 磁盘余量低于阈值时拒绝创建与上传，前端明确提示 |
| 部署简单 | 下载走后端流式代理，不需要把 MinIO 端口暴露到局域网 |

### 1.3 非目标（本期不做）

- WebRTC 点对点传输
- 匿名 WebSocket 实时推送（本期用轮询）
- 二维码生成（本期只展示房间码与可复制链接）
- MinIO 直链下载（保留开关，后续迭代启用）
- 定向发送给指定在线用户

## 2. 关键决策记录

| 决策项 | 结论 | 理由 |
| --- | --- | --- |
| 创建者身份 | 必须登录 | 需要归属与审计，且管理员容量策略依赖用户身份 |
| 加入者身份 | 允许匿名 | 手机端临时传文件不应强制注册 |
| 同网段校验 | 默认关闭，可选开启且仅提示 | 虚拟机 NAT、Docker 网桥、反向代理都会让后端看到代理 IP，强制校验会误杀 |
| 单文件上限（普通用户） | 1GB | 与需求一致 |
| 房间总量（普通用户） | 1GB | 与单文件上限一致，一个 1GB 文件即填满房间 |
| 单文件上限（管理员） | 取服务器剩余空间减安全余量 | 管理员代表站点运营方，可放开磁盘约束 |
| 下载方式 | 后端流式代理 + Range | 不依赖 MinIO 暴露、不依赖固定 IP 与 HTTPS |
| 上传方式 | 小文件单次 POST，大文件分片 | 规避 Nginx 300s 代理超时与单请求内存压力 |
| 实时刷新 | 3-5 秒轮询 | 匿名用户无登录态，现有 WS 按用户推送不适用 |
| 文件存储位置 | 同一 MinIO 桶，前缀 `lan-transfer/{room_id}/{file_id}` | 复用现有 S3 客户端与批量删除能力，清理时可按前缀扫描 |
| 数据库表 | 新建两张独立表 | 避免污染 `files` 表的查询、索引与配额语义 |

## 3. 现状核查结论（实施前置）

以下三点是实施中必须处理的既有约束，均已在代码中确认。

### 3.1 MinIO 未对局域网暴露

- [docker-compose.yml](../docker-compose.yml) 中 MinIO 端口绑定为 `127.0.0.1:9000`。
- `.env.example` 中 `MINIO_PUBLIC_ENDPOINT=localhost:9000`。
- 现有下载接口返回 MinIO 预签名直链，其他设备访问 `localhost` 必然失败。

结论：快传下载改为后端流式代理，路径为 `/api/v1/lan-transfer/public/...`，客户端只与后端交互。

### 3.2 匿名访客会被 CSRF 与全局限流拦截

- `app/middleware/csrf.py` 对所有 `/api/` 下的非安全方法校验 CSRF，匿名访客没有 cookie。
- `app/middleware/rate_limit.py` 按 IP 做全局 60 次/分钟限流，虚拟机 NAT 下所有访客共享同一 IP。

结论：`/api/v1/lan-transfer/public/` 前缀需要 CSRF 豁免，并改用房间维度限流桶。

### 3.3 现有「剩余空间」统计口径不是磁盘余量

- `app/services/admin_service.py` 的 `get_stats()` 统计的是用户配额与已用量之和，不是磁盘剩余空间。

结论：新增基于 `shutil.disk_usage()` 的磁盘余量探测，用于管理员容量与「空间不足暂停」判定。

### 3.4 现有 WebSocket 仅支持登录用户

- `app/core/ws_manager.py` 按 `user_id` 推送，匿名访客没有 `user_id`。

结论：本期不做房间维度 WS，前端轮询。

## 4. 总体设计

### 4.1 角色与权限矩阵

| 操作 | 创建者（登录） | 加入者（匿名） | 管理员（登录） |
| --- | --- | --- | --- |
| 创建房间 | 允许 | 禁止 | 允许（容量按磁盘余量） |
| 查看房间详情 | 允许 | 允许（凭 room token） | 允许 |
| 上传文件 | 允许 | 允许 | 允许 |
| 下载文件 | 允许 | 允许 | 允许 |
| 删除房间内任意文件 | 允许 | 允许（仅限本人上传的可选限制） | 允许 |
| 关闭房间 | 允许 | 禁止 | 允许 |
| 设置房间密码 | 允许 | 不允许修改 | 允许 |

### 4.2 数据流

```
创建房间
  浏览器(已登录) --POST /lan-transfer/rooms--> 后端
  后端: 校验登录态 -> 校验功能可用(磁盘余量/开关) -> 计算容量上限 -> 写入 transfer_rooms
  返回: room_id / code / join_url / 容量信息

加入房间
  浏览器(匿名) --POST /lan-transfer/public/rooms/{code}/join--> 后端
  后端: 校验 code -> 校验未过期未关闭 -> 校验密码(如设置) -> 签发 lan_room token
  返回: room_token / 房间信息 / 剩余容量

上传
  浏览器 --POST .../files 或 分片 init/part/complete--> 后端
  后端: 校验 room token -> 预占容量(Redis) -> 流式写入 MinIO -> 落库 -> 释放预占
  存储路径: lan-transfer/{room_id}/{file_id}

下载
  浏览器 --GET .../files/{file_id}/download (Range)--> 后端
  后端: 校验 room token -> get_object(Range) -> StreamingResponse(206/200)

过期清理
  后台协程每 10 分钟: 扫描过期/已关闭房间 -> 批量删除 MinIO 对象 -> 删除 DB 记录
```

### 4.3 容量与暂停判定

```
功能可用判定:
  LAN_TRANSFER_ENABLED == true
  且 disk_free >= LAN_TRANSFER_MIN_FREE_BYTES

单文件上限:
  普通用户: min(LAN_TRANSFER_USER_LIMIT, LAN_TRANSFER_USER_LIMIT) = 1GB
  管理员:   LAN_TRANSFER_ADMIN_LIMIT > 0 ? LAN_TRANSFER_ADMIN_LIMIT
                                       : disk_free - LAN_TRANSFER_MIN_FREE_BYTES

房间总量上限:
  普通用户: LAN_TRANSFER_USER_LIMIT = 1GB
  管理员:   同上

写入前校验:
  room_used(DB 求和) + room_reserved(Redis 在途) + 本次大小 <= room.max_total_size
  且 disk_free - disk_reserved >= 本次大小
```

## 5. 数据库设计

### 5.1 新增表 `transfer_rooms`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | 主键 |
| code | VARCHAR(12) | UNIQUE, INDEX | 房间码，8 位去混淆字符 |
| owner_id | UUID | FK→users.id, ON DELETE CASCADE, INDEX | 创建者 |
| title | VARCHAR(100) | NULLABLE | 房间标题 |
| password_hash | VARCHAR(255) | NULLABLE | 访问密码（bcrypt），为空表示无密码 |
| max_file_size | BIGINT | NOT NULL | 单文件上限（创建时固化） |
| max_total_size | BIGINT | NOT NULL | 房间总量上限（创建时固化） |
| expires_at | TIMESTAMP(tz) | NOT NULL, INDEX | 过期时间 |
| closed_at | TIMESTAMP(tz) | NULLABLE | 手动关闭时间 |
| created_at | TIMESTAMP(tz) | DEFAULT now() | 创建时间 |

索引：
- `ix_transfer_rooms_code`（唯一）
- `ix_transfer_rooms_owner_created`（`owner_id`, `created_at`）
- `ix_transfer_rooms_expires`（`expires_at`，清理扫描用）

### 5.2 新增表 `transfer_room_files`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | UUID | PK | 主键 |
| room_id | UUID | FK→transfer_rooms.id, ON DELETE CASCADE, INDEX | 所属房间 |
| uploader_id | UUID | FK→users.id, ON DELETE SET NULL, NULLABLE | 上传者，匿名为空 |
| filename | VARCHAR(255) | NOT NULL | 展示文件名（已清洗） |
| storage_key | VARCHAR(512) | UNIQUE, NOT NULL | MinIO 对象键 |
| size | BIGINT | NOT NULL | 字节数 |
| mime_type | VARCHAR(255) | NOT NULL | MIME 类型 |
| file_type | VARCHAR(50) | NOT NULL | 分类（image/document/video/audio/archive/other） |
| created_at | TIMESTAMP(tz) | DEFAULT now() | 创建时间 |

索引：
- `ix_transfer_room_files_room_created`（`room_id`, `created_at`）

### 5.3 与现有表的关系

- 不修改 `files`、`folders`、`shares` 表结构。
- 快传文件不写入 `files` 表，不参与 `used_storage` 计算。
- 迁移文件命名沿用现有风格，例如 `n9o0p1q2r3s4_add_transfer_rooms.py`。

## 6. 配置项

### 6.1 新增环境变量

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `LAN_TRANSFER_ENABLED` | 快传总开关 | `true` |
| `LAN_TRANSFER_ROOM_TTL_HOURS` | 房间有效期（小时） | `24` |
| `LAN_TRANSFER_USER_LIMIT` | 普通用户单文件与房间总量上限（字节） | `1073741824` |
| `LAN_TRANSFER_ADMIN_LIMIT` | 管理员上限（字节），0 表示取磁盘余量 | `0` |
| `LAN_TRANSFER_MIN_FREE_BYTES` | 磁盘剩余低于该值暂停功能 | `2147483648` |
| `LAN_TRANSFER_MAX_FILES_PER_ROOM` | 单房间最大文件数 | `100` |
| `LAN_TRANSFER_JOIN_RATE_LIMIT` | 加入尝试次数上限 | `5` |
| `LAN_TRANSFER_JOIN_RATE_WINDOW_SECONDS` | 加入限流窗口（秒） | `300` |
| `LAN_TRANSFER_PART_SIZE` | 分片大小（字节） | `16777216` |
| `LAN_TRANSFER_CHUNK_THRESHOLD` | 触发分片的上传大小阈值（字节） | `33554432` |
| `LAN_TRANSFER_PUBLIC_BASE_URL` | 对外访问基地址，留空使用请求 origin | 空 |
| `LAN_TRANSFER_DIRECT_MINIO` | 是否返回 MinIO 直链（预留给后续迭代） | `false` |
| `LAN_TRANSFER_DISK_PATH` | 磁盘余量探测路径（容器内） | `/minio-data` |
| `LAN_TRANSFER_REQUIRE_SAME_SUBNET` | 是否提示非同网段（仅提示，不拒绝） | `false` |
| `LAN_TRANSFER_ALLOWED_CIDRS` | 视为同网段的 CIDR 列表 | 空（按私网地址判断） |

### 6.2 部署侧必须同步修改的既有配置

| 配置项 | 调整内容 |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | 改为局域网可达地址，例如 `http://192.168.1.10`，不能是 `localhost:8000` |
| `CORS_ORIGINS` | 加入该局域网地址 |
| `TRUSTED_PROXIES` | 若经 Nginx，需配置 Nginx 容器 IP 或固定网段，否则限流按同一 IP 计数 |
| `MINIO_PUBLIC_ENDPOINT` | 仅在使用预签名直链的场景需要改为局域网可达地址；快传流式代理不依赖此项 |

### 6.3 docker-compose 变更

backend 服务增加：

```yaml
volumes:
  - minio_data:/minio-data:ro
environment:
  - LAN_TRANSFER_ENABLED=${LAN_TRANSFER_ENABLED:-true}
  - LAN_TRANSFER_ROOM_TTL_HOURS=${LAN_TRANSFER_ROOM_TTL_HOURS:-24}
  - LAN_TRANSFER_USER_LIMIT=${LAN_TRANSFER_USER_LIMIT:-1073741824}
  - LAN_TRANSFER_ADMIN_LIMIT=${LAN_TRANSFER_ADMIN_LIMIT:-0}
  - LAN_TRANSFER_MIN_FREE_BYTES=${LAN_TRANSFER_MIN_FREE_BYTES:-2147483648}
  - LAN_TRANSFER_MAX_FILES_PER_ROOM=${LAN_TRANSFER_MAX_FILES_PER_ROOM:-100}
  - LAN_TRANSFER_JOIN_RATE_LIMIT=${LAN_TRANSFER_JOIN_RATE_LIMIT:-5}
  - LAN_TRANSFER_JOIN_RATE_WINDOW_SECONDS=${LAN_TRANSFER_JOIN_RATE_WINDOW_SECONDS:-300}
  - LAN_TRANSFER_PART_SIZE=${LAN_TRANSFER_PART_SIZE:-16777216}
  - LAN_TRANSFER_CHUNK_THRESHOLD=${LAN_TRANSFER_CHUNK_THRESHOLD:-33554432}
  - LAN_TRANSFER_PUBLIC_BASE_URL=${LAN_TRANSFER_PUBLIC_BASE_URL:-}
  - LAN_TRANSFER_DIRECT_MINIO=${LAN_TRANSFER_DIRECT_MINIO:-false}
  - LAN_TRANSFER_DISK_PATH=${LAN_TRANSFER_DISK_PATH:-/minio-data}
```

说明：`shutil.disk_usage()` 基于 `statvfs`，只读挂载同样可以读取文件系统容量，无需写权限。

## 7. 后端设计

### 7.1 新增文件

| 文件 | 职责 |
| --- | --- |
| `app/models/transfer_room.py` | `TransferRoom`、`TransferRoomFile` 模型 |
| `app/schemas/transfer_room.py` | 请求/响应模型 |
| `app/services/lan_transfer_service.py` | 业务逻辑 |
| `app/api/v1/endpoints/lan_transfer.py` | 路由 |
| `alembic/versions/<rev>_add_transfer_rooms.py` | 迁移 |
| `tests/test_service_lan_transfer.py` | 服务层测试 |
| `tests/test_api_lan_transfer.py` | 接口层测试 |

### 7.2 修改文件

| 文件 | 改动 |
| --- | --- |
| `app/core/config.py` | 新增 `LAN_TRANSFER_*` 配置 |
| `app/core/security.py` | 新增 `create_room_token()`、`ROOM_TOKEN_TYPE = "lan_room"` |
| `app/core/storage.py` | 新增 `open_object_stream()`（支持 Range）、`head_object()` 封装 |
| `app/api/deps.py` | 新增 `get_room_context()` 依赖 |
| `app/api/v1/api.py` | 注册 `lan_transfer.router` |
| `app/middleware/csrf.py` | `/api/v1/lan-transfer/public/` 豁免 |
| `app/middleware/rate_limit.py` | public 路径跳过全局 IP 桶 |
| `app/main.py` | lifespan 增加房间清理协程；孤儿分片清理兼容 `lan-transfer/` 前缀 |
| `app/services/admin_service.py` | `get_stats()` 增加磁盘字段 |
| `.env.example` | 新增配置说明 |
| `docker-compose.yml` / `docker-compose.dev.yml` | 环境变量与只读挂载 |

### 7.3 房间令牌

```python
def create_room_token(room_id: uuid.UUID, role: str, subject: str, expires_delta: timedelta) -> str:
    return _create_token(
        {"sub": subject, "room_id": str(room_id), "role": role},
        expires_delta,
        token_type="lan_room",
    )
```

约束：

- `type` 必须为 `lan_room`，`get_current_user()` 会拒绝（其校验 `type == "access"`）。
- 有效期 = `min(房间剩余时间, LAN_TRANSFER_ROOM_TTL_HOURS)`。
- 仅通过 `X-Room-Token` 或 `Authorization: Bearer` 传递，不写 cookie。
- `get_room_context()` 校验 `payload["room_id"] == path room_id`，防止拿 A 房间令牌访问 B 房间。

### 7.4 服务层函数清单

| 函数 | 说明 |
| --- | --- |
| `get_disk_usage()` | 返回 `(total, used, free)`，路径不存在时回退 `/` 并告警 |
| `is_feature_available()` | 开关 + 磁盘余量判定 |
| `resolve_limits(user)` | 按身份计算 `(max_file_size, max_total_size)` |
| `create_room(db, owner, title, password, ttl_hours)` | 创建房间 |
| `get_room(db, room_id)` | 读取并校验状态 |
| `join_room(db, code, password, client_ip)` | 校验、限流、签发令牌 |
| `list_room_files(db, room_id)` | 文件列表 |
| `reserve_capacity(room_id, size)` | Redis 预占容量 |
| `release_capacity(room_id, size)` | 释放预占 |
| `add_room_file(db, room, uploader_id, filename, fileobj, mime_type, size)` | 校验 + 写入 + 落库 |
| `init_room_multipart(...)` / `upload_room_part(...)` / `complete_room_multipart(...)` | 分片上传 |
| `open_room_file_stream(room, file_id, range_header)` | 返回流与响应头 |
| `delete_room_file(db, room, file_id, requester_role)` | 删除单个文件 |
| `close_room(db, room)` | 关闭并触发清理 |
| `cleanup_expired_rooms()` | 周期清理 |

### 7.5 容量预占与并发控制

Redis 键：

| 键 | 用途 | TTL |
| --- | --- | --- |
| `lan_room:{room_id}:reserved` | 在途上传字节数（INCRBY/DECRBY） | 3600 |
| `lan_room:{room_id}:used` | 已落库字节数缓存 | 60 |
| `lan_room:{room_id}:files` | 文件数缓存 | 60 |
| `lan_join_fail:{code}:{ip}` | 加入失败计数 | 300 |
| `lan_join_lock:{code}:{ip}` | 加入锁定标记 | 300 |
| `lan_rl:{room_id}:{jti}` | 房间维度请求计数 | 60 |
| `lan_mpu:{upload_id}` | 分片上传存活标记（孤儿清理用） | 与房间有效期一致 |

写入流程：

1. `reserve_capacity` 先原子 `INCRBY`，若 `used + reserved > max_total_size` 则立即 `DECRBY` 并返回 507。
2. 流式写入 MinIO，`max_size` 传入 `max_file_size` 兜底。
3. 成功：落库、`DECRBY` 预占、刷新 `used` 缓存。
4. 失败：删除已写入的 MinIO 对象（若已创建）、`DECRBY` 预占。

### 7.6 流式下载

`storage.py` 新增：

```python
@asynccontextmanager
async def open_object_stream(storage_key: str, range_header: str | None = None):
    async with get_s3_client() as client:
        params = {"Bucket": settings.MINIO_BUCKET, "Key": storage_key}
        if range_header:
            params["Range"] = range_header
        resp = await client.get_object(**params)
        yield resp
```

接口返回：

- 无 Range：`200`，`Content-Length` = 对象大小。
- 有 Range：`206`，透传 `Content-Range`、`Content-Length`。
- 响应头包含 `Content-Disposition: attachment; filename*=UTF-8''<encoded>`、`Content-Type`、`Accept-Ranges: bytes`。
- 使用 `StreamingResponse` 迭代 `resp["Body"].iter_chunks()`，避免整文件读入内存。

### 7.7 API 设计

#### 7.7.1 创建房间（需登录）

```
POST /api/v1/lan-transfer/rooms
Authorization: Bearer <access_token>

{
  "title": "临时传文件",
  "password": "1234",
  "ttl_hours": 24
}
```

响应 `201`：

```json
{
  "room_id": "uuid",
  "code": "A7K2M9QX",
  "join_url": "http://192.168.1.10/transfer/A7K2M9QX",
  "has_password": true,
  "max_file_size": 1073741824,
  "max_total_size": 1073741824,
  "used_size": 0,
  "file_count": 0,
  "expires_at": "2026-11-13T10:00:00+00:00"
}
```

错误：

| 状态码 | 场景 |
| --- | --- |
| `403` | `LAN_TRANSFER_ENABLED=false` |
| `507` | 磁盘剩余低于 `LAN_TRANSFER_MIN_FREE_BYTES` |

#### 7.7.2 房间详情（需登录，仅创建者）

```
GET /api/v1/lan-transfer/rooms/{room_id}
```

#### 7.7.3 关闭房间（需登录，仅创建者）

```
POST /api/v1/lan-transfer/rooms/{room_id}/close
```

响应 `200`：`{"message": "房间已关闭"}`。关闭后立即异步清理对象与记录。

#### 7.7.4 加入房间（匿名）

```
POST /api/v1/lan-transfer/public/rooms/{code}/join

{ "password": "1234" }
```

响应 `200`：

```json
{
  "room_token": "<jwt>",
  "room_id": "uuid",
  "title": "临时传文件",
  "max_file_size": 1073741824,
  "max_total_size": 1073741824,
  "used_size": 0,
  "file_count": 0,
  "expires_at": "2026-11-13T10:00:00+00:00",
  "same_subnet_hint": false
}
```

错误：

| 状态码 | 场景 |
| --- | --- |
| `404` | 房间码不存在 |
| `410` | 房间已过期或已关闭 |
| `403` | 密码错误 |
| `429` | 加入尝试超限 |
| `507` | 功能暂停 |

#### 7.7.5 房间文件列表（room token）

```
GET /api/v1/lan-transfer/public/rooms/{room_id}/files
X-Room-Token: <jwt>
```

响应：

```json
{
  "items": [
    {
      "id": "uuid",
      "filename": "photo.jpg",
      "size": 1048576,
      "mime_type": "image/jpeg",
      "file_type": "image",
      "uploader": "匿名",
      "created_at": "2026-11-12T10:00:00+00:00"
    }
  ],
  "used_size": 1048576,
  "max_total_size": 1073741824,
  "file_count": 1
}
```

#### 7.7.6 上传文件（room token）

小文件（小于 `LAN_TRANSFER_CHUNK_THRESHOLD`）：

```
POST /api/v1/lan-transfer/public/rooms/{room_id}/files
X-Room-Token: <jwt>
Content-Type: multipart/form-data

file=<binary>
```

大文件分片：

```
POST /api/v1/lan-transfer/public/rooms/{room_id}/multipart/init
POST /api/v1/lan-transfer/public/rooms/{room_id}/multipart/part?upload_id=&part_number=
POST /api/v1/lan-transfer/public/rooms/{room_id}/multipart/complete
POST /api/v1/lan-transfer/public/rooms/{room_id}/multipart/abort?upload_id=
```

错误：

| 状态码 | 场景 |
| --- | --- |
| `413` | 超过 `max_file_size` |
| `507` | 房间容量不足或磁盘不足 |
| `400` | 文件数超过 `LAN_TRANSFER_MAX_FILES_PER_ROOM` |
| `415` | MIME 类型不在允许列表 |

#### 7.7.7 下载文件（room token，支持 Range）

```
GET /api/v1/lan-transfer/public/rooms/{room_id}/files/{file_id}/download
X-Room-Token: <jwt>
Range: bytes=0-1048575
```

响应：`200` 或 `206`，流式输出。

#### 7.7.8 删除文件（room token）

```
DELETE /api/v1/lan-transfer/public/rooms/{room_id}/files/{file_id}
X-Room-Token: <jwt>
```

删除后释放容量并更新缓存。

#### 7.7.9 管理员统计扩展

`GET /api/v1/admin/stats` 增加：

```json
{
  "disk_total": 107374182400,
  "disk_free": 85899345920,
  "lan_transfer_available": true,
  "lan_transfer_active_rooms": 3
}
```

### 7.8 中间件调整

#### CSRF 豁免

在 `CSRFMiddleware.__call__` 中，路径判断增加：

```python
_LAN_PUBLIC_PREFIX = "/api/v1/lan-transfer/public/"

if path.startswith(_LAN_PUBLIC_PREFIX):
    await self.app(scope, receive, send)
    return
```

位置需在 CSRF 校验之前、且仍保留 cookie 初始化逻辑（匿名页首次访问也应能拿到 csrf cookie，便于后续登录操作）。

#### 限流调整

`RateLimitMiddleware` 中对 `_LAN_PUBLIC_PREFIX` 跳过全局 IP 桶，改由服务层按 `room_id + token jti` 计数：

```python
_LAN_PUBLIC_PREFIX = "/api/v1/lan-transfer/public/"
```

房间维度限流上限建议：列表 `30 次/分钟`，上传分片 `300 次/分钟`，下载 `60 次/分钟`。

### 7.9 清理任务

在 `app/main.py` 的 `lifespan` 中新增协程 `_cleanup_expired_rooms()`，间隔 600 秒：

1. 查询 `expires_at < now` 或 `closed_at is not null` 且尚未清理的房间。
2. 收集其所有 `storage_key`，调用 `batch_delete_files`（已支持 1000 条分批）。
3. 删除 `transfer_room_files` 与 `transfer_rooms` 记录。
4. 清理 Redis 键 `lan_room:{room_id}:*`。

同时修改现有 `_cleanup_orphan_multipart_uploads()`：

- 现有逻辑用 `key.split("/")[0]` 当作 owner_id，对 `lan-transfer/...` 前缀会误判。
- 调整：`key` 以 `lan-transfer/` 开头时，改用 `lan_mpu:{upload_id}` 判断存活。

## 8. 前端设计

### 8.1 新增文件

| 文件 | 职责 |
| --- | --- |
| `lib/api/lanTransfer.ts` | 快传 API 封装（登录态与匿名两套请求） |
| `stores/lanTransfer.ts` | 房间状态、令牌、容量、可用性 |
| `app/dashboard/components/LanTransferView.tsx` | 登录用户的快传管理视图 |
| `app/dashboard/components/LanTransferView.module.css` | 样式 |
| `app/transfer/[code]/page.tsx` | 匿名加入页 |
| `tests/lanTransfer.test.ts` | 关键逻辑测试 |

### 8.2 修改文件

| 文件 | 改动 |
| --- | --- |
| `app/dashboard/types.ts` | `CategoryId` 增加 `"lan"` |
| `app/dashboard/components/Sidebar.tsx` | 新增「快传」导航项 |
| `app/dashboard/page.tsx` | 渲染 `LanTransferView`，传递创建/关闭回调 |
| `stores/transfers.ts` | `TransferType` 增加 `"lan-upload" \| "lan-download"` |
| `lib/query/keys.ts` | 增加 `lanTransfer` 查询键 |
| `lib/i18n/locales/zh-CN.ts` / `zh-TW.ts` / `en.ts` | 新增文案（三份同步） |
| `app/admin/page.tsx` | 展示磁盘余量与快传可用状态 |

### 8.3 请求策略：登录态与匿名态分离

- 创建/查看/关闭房间使用现有 `client()`，享受 401 自动刷新与跳登录。
- 匿名加入与房间内操作**不能使用 `client()`**：`client()` 在 401 时会触发 refresh 并跳转 `/login`，匿名场景会导致误跳转。
- 匿名请求使用独立封装：

```ts
async function lanPublicFetch<T>(path: string, init: RequestInit = {}, roomToken?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (roomToken) headers.set("X-Room-Token", roomToken);
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `请求失败 (${res.status})`);
  }
  return res.json();
}
```

### 8.4 加入链接生成

- 后端 `join_url` 生成规则：
  - `LAN_TRANSFER_PUBLIC_BASE_URL` 非空 → 使用该值拼接 `/transfer/{code}`。
  - 否则取请求 `Origin` 头；若无 `Origin`，回退 `Referer` 的 origin；仍无则返回相对路径 `/transfer/{code}`。
- 前端在房间页检测 `origin` 是否为 `localhost` 或 `127.0.0.1`，若是则显示提示：

> 当前通过本机地址访问，其他设备无法加入。请改用局域网 IP 或域名重新打开本页面。

### 8.5 上传与下载

上传：

- 小于 `LAN_TRANSFER_CHUNK_THRESHOLD`：`XMLHttpRequest` + `upload.onprogress`，复用现有进度上报模式。
- 大于等于阈值：按 `LAN_TRANSFER_PART_SIZE` 顺序分片，复用 `AbortController` 支持取消。
- 进度写入 `useTransferStore`，`type` 为 `lan-upload`。

下载：

- 使用 `fetch` 读取 `Content-Length`，以 `response.body.getReader()` 累计进度后触发浏览器保存。
- 因同源限制，`<a download>` 无法直接携带 `X-Room-Token`，必须走 fetch + Blob/Stream。
- 大文件注意内存：优先 `showSaveFilePicker`（可用时），不可用时回退 Blob 并提示"大文件建议分片下载"。

### 8.6 轮询策略

- 房间页每 4 秒请求一次文件列表。
- 页面 `visibilitychange` 为隐藏时暂停轮询，恢复可见时立即刷新一次。
- 连续失败 3 次后降频至 15 秒，并在 UI 上提示网络异常。

### 8.7 国际化文案键

```
lan.title
lan.create
lan.createTitle
lan.createPassword
lan.createTtl
lan.code
lan.copyLink
lan.copyCode
lan.copied
lan.join
lan.joinPassword
lan.joinError
lan.files
lan.empty
lan.upload
lan.uploading
lan.download
lan.delete
lan.close
lan.closeConfirm
lan.paused
lan.pausedHint
lan.localhostHint
lan.sameSubnetHint
lan.expired
lan.capacity
lan.fileCount
lan.anonymous
```

### 8.8 空状态与异常状态

| 状态 | 展示 |
| --- | --- |
| 功能暂停 | 入口置灰 + 提示"服务器存储空间不足，快传已暂停" |
| 房间已过期 | 加入页显示"房间已过期或被关闭" |
| 密码错误 | 输入框下方红色提示，保留输入 |
| 容量已满 | 上传区禁用 + 显示"房间空间已满" |
| 网络异常 | 顶部横幅 + 重试按钮 |

## 9. 安全设计

| 风险 | 缓解措施 |
| --- | --- |
| 房间码被暴力枚举 | 8 位、去混淆字符集；加入失败按 `code + IP` 计数，5 次后锁定 300 秒 |
| 无密码房间被陌生人使用 | 默认 TTL 24 小时；创建者可在创建时设置密码；可随时关闭 |
| 跨房间越权 | `get_room_context()` 强校验 `token.room_id == path.room_id` |
| 令牌被用于云盘接口 | 令牌 `type=lan_room`，`get_current_user()` 校验 `type=access`，互不通用 |
| 明文 HTTP 下令牌被嗅探 | 令牌仅限单房间、随房间过期、不含用户凭据；`sub` 为匿名标识或用户 ID |
| 匿名上传滥用磁盘 | 房间总量 1GB、文件数上限、磁盘余量阈值、单房间 TTL |
| 路径穿越 | 文件名复用 `sanitize_filename()`；存储键由服务端生成 `lan-transfer/{room_id}/{file_id}` |
| 恶意文件类型 | 复用 `detect_real_mime_type()` 与 `validate_mime_type()` |
| CSRF | public 路径豁免，但仅接受 room token，不依赖 cookie 鉴权 |
| 内存耗尽 | 上传流式、下载流式，均不整文件读入内存 |
| 并发写爆盘 | Redis 预占容量 + MinIO 分片 `max_size` 兜底 |

## 10. 部署前置条件

即使代码完成，以下任一项未满足都会导致"其他设备无法访问"。

| 检查项 | 要求 |
| --- | --- |
| 后端可达 | 当前 `127.0.0.1:8000` 仅本机可用，需经 Nginx 80 端口或改绑定地址 |
| 前端可达 | 前端 `3000:3000` 已对局域网开放，或经 Nginx |
| `NEXT_PUBLIC_API_URL` | 必须为局域网可达地址，不能是 `localhost:8000` |
| `CORS_ORIGINS` | 包含实际访问来源 |
| `TRUSTED_PROXIES` | 经 Nginx 时配置，否则限流按同一 IP |
| 防火墙 | 放行 80 / 3000 端口 |
| 虚拟机网络 | 桥接模式最佳；NAT 模式下宿主机以外的设备无法直连，需端口转发 |

### 虚拟机与主机场景说明

| 场景 | 可用性 | 说明 |
| --- | --- | --- |
| 服务在虚拟机，网络为桥接 | 可用 | 主机与其他设备均可通过 VM 的 LAN IP 访问 |
| 服务在虚拟机，网络为 NAT + 端口转发 | 可用 | 主机可通过转发访问；其他设备需另行配置转发 |
| 服务在虚拟机，网络为 Host-Only | 仅主机可用 | 其他局域网设备无法访问 |
| 服务在主机 Docker，虚拟机作为客户端（桥接） | 可用 | 正常走局域网 |
| 服务在主机 Docker，虚拟机作为客户端（NAT） | 可用 | 源 IP 被 SNAT，限流会合并计数，但功能不受影响 |

关键结论：同网段校验默认关闭，因此 NAT 场景不会被误判拒绝；房间码 + 密码 + 限流 + TTL 构成实际安全边界。

## 11. 测试计划

### 11.1 后端单元测试

| 用例 | 断言重点 |
| --- | --- |
| 创建房间-普通用户 | `max_file_size == 1GB`、`max_total_size == 1GB` |
| 创建房间-管理员 | 上限等于磁盘余量减安全余量 |
| 创建房间-磁盘不足 | 返回 507 |
| 创建房间-开关关闭 | 返回 403 |
| 加入房间-正确码 | 返回 `lan_room` 令牌 |
| 加入房间-密码错误 | 返回 403，失败计数 +1 |
| 加入房间-连续失败 | 第 6 次返回 429 |
| 加入房间-已过期 | 返回 410 |
| 跨房间令牌 | 用 A 房间令牌访问 B 房间返回 403 |
| room token 访问云盘接口 | 返回 401（类型不符） |
| 上传-超过单文件上限 | 返回 413，MinIO 无残留对象 |
| 上传-超过房间总量 | 返回 507，预占已释放 |
| 上传-文件数超限 | 返回 400 |
| 上传-非法 MIME | 返回 415 |
| 并发上传 | 预占生效，总和不超上限 |
| 下载-Range | 返回 206 且 `Content-Range` 正确 |
| 删除文件 | 对象删除、容量释放 |
| 关闭房间 | 对象与记录清理完成 |
| 清理任务 | 过期房间被清除，未过期不受影响 |

### 11.2 前端测试

| 用例 | 断言重点 |
| --- | --- |
| `lanTransfer` store | 创建、加入、重置状态 |
| 容量计算 | 剩余容量展示与禁用逻辑 |
| 可用性置灰 | 暂停时上传按钮禁用 |
| 轮询 | 可见性切换时启停 |

### 11.3 手工联调清单

1. 主机浏览器登录，创建带密码房间。
2. 手机连接同一 WiFi，访问 `join_url`，输入密码加入。
3. 手机上传 500MB 文件，观察进度与主机列表刷新。
4. 主机下载该文件，验证 Range 断点续传（可用 `curl -H "Range: bytes=0-1023"`）。
5. 删除文件后确认 MinIO 对象已清理。
6. 关闭房间后确认加入页返回 410。
7. 将磁盘剩余压到阈值以下，确认创建与上传均返回 507。
8. 虚拟机 NAT 场景重复步骤 2-4。

### 11.4 门禁命令

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

```bash
cd frontend
npm run lint
npm run test
```

## 12. 实施里程碑

| 里程碑 | 内容 | 交付物 | 预估 |
| --- | --- | --- | --- |
| M1 | 配置、模型、迁移、磁盘探测 | `config.py`、模型、迁移、`get_disk_usage()` | 1 人日 |
| M2 | 服务层、接口、令牌、限流、容量、暂停逻辑 | `lan_transfer_service.py`、路由、`deps.py`、中间件 | 1.5 人日 |
| M3 | 前端入口、快传视图、匿名加入页、进度、i18n | 组件、页面、store、API 封装 | 1.5 人日 |
| M4 | 清理任务、流式 Range、联调、门禁 | 清理协程、测试补齐、文档 | 1 人日 |
| 合计 | | | 约 5 人日 |

## 13. 风险与已知限制

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| `localhost` 访问导致链接不可用 | 其他设备无法加入 | 前端提示 + `LAN_TRANSFER_PUBLIC_BASE_URL` 覆盖 |
| 明文 HTTP 令牌可嗅探 | 同网段可窃取房间令牌 | 单房间、短 TTL、不含用户凭据；建议部署 HTTPS |
| 上传经后端中转 | 多一跳，占用后端带宽 | 局域网内仍可跑满；后续 `LAN_TRANSFER_DIRECT_MINIO` 切换直链 |
| Nginx 300s 超时 | 超大文件单请求中断 | 大文件强制分片 |
| 轮询带来额外请求 | 房间多人时压力上升 | 4 秒间隔 + 可见性暂停 + 失败降频 |
| MinIO 只读挂载路径不存在 | 磁盘探测失败 | 回退 `/` 并记录告警日志 |
| 匿名删除权限过大 | 互相误删 | 可选配置为"仅创建者可删除他人文件"，本期默认允许 |

## 14. 回滚方案

1. 功能级回滚：设置 `LAN_TRANSFER_ENABLED=false`，入口置灰，已有房间不再可加入。
2. 数据级回滚：迁移仅新增两张表，回滚迁移删除表即可，不影响 `files` 等既有表。
3. 代码级回滚：新增路由独立注册，移除 `api.py` 中 `lan_transfer.router` 一行即可下线接口。
4. 残留清理：`lan-transfer/` 前缀对象可用脚本按前缀批量删除。

## 15. 后续迭代（不在本期范围）

| 方向 | 说明 |
| --- | --- |
| MinIO 直链下载 | `LAN_TRANSFER_DIRECT_MINIO=true`，暴露 MinIO 端口或经 Nginx 代理 |
| 房间维度 WebSocket | 匿名访客凭 room token 订阅房间频道，替换轮询 |
| 二维码 | 房间页展示二维码，手机扫码直达 |
| 定向发送 | 向指定在线用户推送文件，需要在线用户列表 |
| 断点续传 | 上传分片校验与续传 |
| 限速与优先级 | 房间维度带宽限制，避免挤占云盘主业务 |