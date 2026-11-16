# 功能清单与变更日志

## 1. 核心功能

### 1.1 文件管理

| 功能       | 说明                                  |
| ---------- | ------------------------------------- |
| 文件上传   | 流式直传 MinIO，内存占用 O(1)         |
| 文件下载   | MinIO 预签名 URL，支持 Range 请求     |
| 文件预览   | 图片/文档在线预览                     |
| 缩略图     | 图片上传后自动异步生成 256×256 缩略图 |
| 文件搜索   | pg_trgm 三元组相似度搜索 + GIN 索引   |
| 分类筛选   | 全部/图片/文档/视频/音频/压缩包/其他  |
| 文件移动   | 单个/批量移动文件到指定文件夹         |
| 拖拽移动   | 拖拽文件到文件夹图标完成移动          |
| 文件重命名 | 修改文件名                            |
| 回收站     | 软删除/恢复/彻底删除                  |
| 视图切换   | 网格视图/列表视图                     |
| 虚拟滚动   | react-virtuoso，万级文件无卡顿        |

### 1.2 文件夹管理

| 功能         | 说明                           |
| ------------ | ------------------------------ |
| 创建文件夹   | 支持嵌套文件夹                 |
| 文件夹列表   | 子文件夹 + 文件 + 面包屑导航   |
| 重命名文件夹 | 修改文件夹名称                 |
| 删除文件夹   | 级联软删除（文件夹及所有内容） |
| 恢复文件夹   | 从回收站恢复                   |
| 彻底删除     | 级联永久删除（数据库 + MinIO） |

### 1.3 文件分享

| 功能     | 说明                      |
| -------- | ------------------------- |
| 创建分享 | 生成分享链接 + 8 位提取码 |
| 分享访问 | 无需登录，输入提取码访问  |
| 分享下载 | 验证提取码后获取下载链接  |
| 取消分享 | 删除分享链接              |
| 分享列表 | 查看我的所有分享          |
| 防爆破   | 提取码验证限流            |

### 1.4 传输管理

| 功能     | 说明                                    |
| -------- | --------------------------------------- |
| 上传进度 | 实时追踪上传进度                        |
| 下载进度 | 实时追踪下载进度                        |
| 传输列表 | 侧边栏展示传输任务                      |
| 红点提示 | 有传输任务时侧边栏红点提示              |
| 自动清理 | 已完成/失败任务自动清理，最多保留 30 条 |

## 2. 用户功能

### 2.1 认证

| 功能       | 说明                         |
| ---------- | ---------------------------- |
| 注册       | 邮箱 + 用户名 + 密码         |
| 登录       | 邮箱 + 密码，JWT Cookie 认证 |
| Token 刷新 | Refresh Token 自动续期       |
| 退出登录   | Token 黑名单 + Cookie 清除   |
| 忘记密码   | 邮箱验证码重置               |
| 密保问题   | 通过密保问题重置密码         |

### 2.2 用户中心

| 功能       | 说明                |
| ---------- | ------------------- |
| 修改用户名 | 修改显示名称        |
| 修改密码   | 旧密码 + 新密码     |
| 头像上传   | 上传/裁剪头像       |
| 存储统计   | 已用容量/总配额显示 |

## 3. 管理功能

### 3.1 系统统计

| 功能     | 说明         |
| -------- | ------------ |
| 用户统计 | 总用户数     |
| 存储统计 | 总存储使用量 |
| 文件统计 | 总文件数     |

### 3.2 用户管理

| 功能      | 说明                       |
| --------- | -------------------------- |
| 用户列表  | 分页查看/搜索用户          |
| 配额调整  | 修改用户存储配额           |
| 启用/禁用 | 启用或禁用用户账号         |
| 删除用户  | 删除用户及其所有数据       |
| 重算存储  | 重新计算用户实际存储使用量 |

### 3.3 备份管理

| 功能     | 说明         |
| -------- | ------------ |
| 备份列表 | 查看所有备份 |
| 手动备份 | 触发即时备份 |
| 下载备份 | 下载备份文件 |

### 3.4 任务管理

| 功能     | 说明                 |
| -------- | -------------------- |
| 任务状态 | 查询异步任务状态     |
| 活跃任务 | 查看当前活跃任务列表 |

## 4. 系统功能

### 4.1 国际化

| 语言     | 代码  |
| -------- | ----- |
| 简体中文 | zh-CN |
| 繁体中文 | zh-TW |
| 英文     | en    |

### 4.2 响应式设计

- 适配桌面、平板、手机屏幕
- 侧边栏可折叠

### 4.3 实时通知

- WebSocket 长连接
- 上传完成/分享创建/存储变更即时推送
- 指数退避重连（1→2→4→8→16s）
- 侧边栏未读角标，登录态内累计
- 登出时清空通知列表与未读计数，避免下一会话继承上一用户的角标

### 4.4 日志系统

| 日志文件     | 说明                           |
| ------------ | ------------------------------ |
| `app.log`    | 全量日志（JSON 格式）          |
| `error.log`  | 仅 ERROR 及以上                |
| `access.log` | HTTP 请求日志（含 request_id） |

- 每日轮转，超期自动清理
- 敏感数据脱敏（password/token/secret → `***`）

### 4.5 告警系统

- ERROR 及以上日志自动通知
- 支持 Webhook（钉钉/飞书/企业微信/通用）
- 支持邮件通知
- 去重冷却，防止刷屏
- Celery 异步发送，Worker 不可用时降级同步

### 4.6 健康检查

| 端点            | 用途           | 检查内容           |
| --------------- | -------------- | ------------------ |
| `/health`       | Liveness 心跳  | Redis 连通性       |
| `/health/ready` | Readiness 探测 | DB + MinIO + Redis |

### 4.7 可观测性

- Prometheus 指标（`/metrics`）
- 请求量/延迟/错误率/在途请求

## 5. 性能优化

| 优化项         | 措施                                                                                                                              |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 流式上传       | 直传 MinIO，内存 O(1)（非 O(N×文件大小)）                                                                                          |
| 分片上传       | ≥16MB 自动分片，MinIO Multipart API 三阶段（init→part→complete），Redis Hash 存会话状态（TTL 24h），支持断点续传/暂停/恢复/取消     |
| MinIO 异步     | `run_in_threadpool` 包装，不阻塞事件循环                                                                                           |
| S3 批量删除    | `delete_objects` 分批 1000 key，失败降级逐个重试                                                                                   |
| S3 初始化      | `asyncio.Lock` 保护客户端初始化与关闭，防止并发重复创建                                                                            |
| 虚拟滚动       | react-virtuoso（TableVirtuoso + VirtuosoGrid），仅渲染可视区域 DOM                                                                 |
| 请求缓存       | TanStack Query，staleTime 30s，自动去重/缓存/stale-while-revalidate，mutation 后精准失效                                           |
| 游标分页       | 移除 OFFSET 回退，skip>0 用子查询取分界点走 keyset 分页；前端 `cursorMap` 维护游标状态                                             |
| 三元组搜索     | pg_trgm `similarity()` + GIN 索引，替代低效 `ilike`                                                                                |
| 分页一致性     | `share_service.list_shares` 改两次查询（count + data），避免窗口函数跨分页 total 不一致                                            |
| 文件夹查询     | `list_folder_contents` 文件查询与 count 合并（3 次→2 次）；`delete_folder`/`restore_folder` 用 SQL SUM 替代 Python 遍历求和         |
| 缓存失效       | Redis Hash 分组存储替代独立 key，`HKEYS`+`HDEL` 按用户精确删除，避免 `SCAN` 全库遍历；TTL 30s/15s 提升至 120s/60s                   |
| GZip 压缩      | 中间件，≥500B 自动压缩                                                                                                            |
| 多 Worker      | Gunicorn 多 worker + Redis Pub/Sub WS 广播                                                                                         |
| WS 按需订阅    | Redis Pub/Sub 从 `psubscribe("ws:user:*")` 通配符改为按需 `subscribe`/`unsubscribe`，避免消息风暴                                  |
| 连接池         | 可配置 `pool_size`/`max_overflow`/`pool_timeout`/`pool_recycle`                                                                    |
| PgBouncer      | 数据库连接池代理，所有服务通过 pgbouncer:6432 连接，实际 DB 连接数从 60+ 降至 20                                                  |
| 缩略图         | 上传后异步生成 256×256 缩略图，前端渐进加载（shimmer → blur → sharp），列表优先请求缩略图                                          |
| MIME 异步      | `magic.from_buffer` 改为 `asyncio.to_thread` 避免阻塞事件循环                                                                      |
| 图片优化       | Next.js `remotePatterns` 配置 MinIO 图片优化，WebP 转码 + 按设备尺寸缩放 + 缓存 TTL 7200s                                          |
| 请求日志       | 纯 ASGI 中间件替代 BaseHTTPMiddleware，避免消耗 request body 和流式响应                                                            |
| 请求追踪       | `ContextVar` 注入 `request_id`+`user_id` 到所有日志；上游 `X-Request-ID` → 下游 `X-Correlation-ID` 跨服务追踪                      |
| Nginx 缓存     | MinIO 缩略图（120min）+ 文件下载（60min）代理缓存层；API 60r/m + 下载 30r/m 限流                                                   |
| 可观测性       | Prometheus 指标（`PROMETHEUS_ENABLED=true`），暴露 `/metrics`，采集请求量/延迟/错误率/在途请求                                     |
| 监控仪表盘     | Grafana + Prometheus + Redis/PostgreSQL/MinIO Exporter，预配置仪表盘 + 7 条告警规则                                                |
| Docker         | 多阶段构建：backend 315MB / frontend 216MB，生产无 `--reload`，非 root 运行，HEALTHCHECK                                           |
| Celery 镜像    | 独立 `Dockerfile.celery` 轻量镜像，不含 Gunicorn/Uvicorn/curl，减小体积和攻击面                                                     |
| 生命周期管理   | FastAPI lifespan 统一管理 S3 客户端、Redis 连接、数据库引擎、WS Pub/Sub 的初始化与优雅关闭                                          |
| 传输管理       | 已完成/失败任务自动清理，最多保留 30 条历史记录                                                                                    |

## 6. 版本记录

### 6.1 版本策略

遵循 [SemVer](https://semver.org/lang/zh-CN/)，格式 `MAJOR.MINOR.PATCH`，git 标签统一带 `v` 前缀（如 `v1.0.0`）。

| 变更类型 | 版本位 | 判定标准                                                                          |
| -------- | ------ | --------------------------------------------------------------------------------- |
| 不兼容   | MAJOR  | 需要不可逆的数据迁移、删除 API 路径/字段、`.env` 变量改名或语义变化、旧部署无法启动 |
| 新功能   | MINOR  | 新增接口/页面/可选配置项，旧部署不改配置也能运行                                   |
| 修复     | PATCH  | 修 bug、安全补丁、依赖升级、性能优化，用户无需改配置                               |

- 版本号单一来源为 `.env` 的 `APP_VERSION`，由 `scripts/release.sh` 同步到 `backend/pyproject.toml` 与 `frontend/package.json`。
- 运行时通过 `/health/ready` 的 `version` 字段暴露，备份清单 `manifest.json` 的 `app_version` 记录升级前版本。
- 数据库迁移遵守 expand/contract：先加表/加列（向后兼容），下个 MAJOR 再删旧结构，保证 PATCH/MINOR 可回滚。

### 6.2 v1.2.0（2026-11-16）

#### 新增

- 可视化部署控制台 `/admin/deploy`：容器与服务状态、版本确认、部署时间线、任务日志查看
- 部署接口 `/api/v1/deploy`：白名单动作 `check`/`deploy`/`restart`/`rollback`，并发锁 + 确认令牌 + 历史与日志读取
- 独立执行器 `deploy-runner`（`docker-compose.ops.yml` + `scripts/deploy-runner.sh`）：仅该容器持有 `docker.sock`，经 `/deploy` 共享卷文件协议串行执行，含心跳、容器快照、健康校验与失败自动回滚
- 新增 `scripts/preflight.sh`，`Makefile` 的 `preflight-prod` 改为复用该脚本
- 文档：新增 `doc/visual-deployment.md`、`doc/pitfalls.md`、`doc/codemap.md`

#### 变更

- 管理概览新增配额与磁盘口径提示
- 新增 12 个 `DEPLOY_*` 配置项，`DEPLOY_ENABLED=false` 默认关闭，旧部署不改配置即可运行
- README 精简，导航收敛到 `AGENTS.md` 与 `doc/`

#### 修复

- dashboard 的 `setError`/`setTotal` 空桩改为真实实现，操作错误条与分享分类总数恢复正常
- 传输队列新增 `enqueue` + runner 调度：上传/下载各限 3 并发，完成后 FIFO 自动推进，暂停/取消/移除时回收 runner
- 清理 `downloadFilesAsZip` 等 ZIP 残留与 `loadFiles` 死参数，传输视图区分传输中与排队

#### 升级注意

- 控制台默认关闭；启用需在 `.env` 设置 `DEPLOY_ENABLED=true` 与 `DEPLOY_REPO_PATH`（宿主机仓库绝对路径），再按 `doc/visual-deployment.md` 启动执行器
- 不启用控制台时无需部署 `deploy-runner`，主编排行为不变
- `deploy-runner` 与主编排同项目运行，控制台内不得使用 `--remove-orphans`，否则会删除执行器自身

#### 数据库迁移

- 无新增迁移

### 6.3 v1.1.0（2026-11-12）

#### 新增

- 局域网快传（房间码模式）：登录用户创建房间，同网段设备凭房间码或链接匿名加入，支持上传、下载、删除
- 后端接口：创建/详情/关闭房间、匿名加入、文件列表、分片上传（初始化/上传分片/完成）、流式下载（支持 Range）、删除文件
- 房间令牌（`X-Room-Token`）鉴权，公开路径豁免 CSRF 与全局 IP 限流，加入失败按 IP 单独限流
- 容量预占（Redis）与磁盘余量探测，余量低于 `LAN_TRANSFER_MIN_FREE_BYTES` 时创建与上传自动暂停
- 后台协程清理过期/已关闭房间及其对象，并回收孤儿分片上传
- 前端 dashboard 新增「局域网快传」入口，匿名加入页 `/transfer/[code]` 支持轮询刷新、分片上传与流式下载
- 管理后台新增磁盘余量与快传可用状态、活跃房间数统计

#### 变更

- 三语（zh-CN / zh-TW / en）补齐快传与磁盘状态文案
- CORS 允许 `X-Room-Token` 请求头
- 新增 15 个 `LAN_TRANSFER_*` 配置项，缺省值保证旧部署无需改配置即可运行
- 生产编排挂载 `minio_data` 为 `/minio-data:ro`，用于磁盘余量探测

#### 升级注意

- 需执行 `alembic upgrade head` 创建 `transfer_rooms` 与 `transfer_room_files`
- 若局域网其他设备需通过 IP 访问，建议设置 `LAN_TRANSFER_PUBLIC_BASE_URL`，否则链接按请求 origin 生成
- 下载默认走后端流式代理，无需把 MinIO 端口暴露到局域网

#### 数据库迁移

- 新增 1 个迁移（`n9o0p1q2r3s4`），仅加表与索引，向后兼容

### 6.4 v1.0.0（2026-11-12）

首个正式版本，功能清单见上文第 1~5 节。

#### 新增

- 文件/文件夹管理、分享、回收站、传输管理、用户中心、管理后台（用户/备份/任务）
- 三语国际化（zh-CN / zh-TW / en）、WebSocket 实时通知、Prometheus 指标、日志与告警系统
- 「压缩包」分类入口，归档 MIME 扩展至 zip/rar/7z/gzip/tar/bzip2/xz（`cade5c2`）
- 安装/升级/体检脚本 `scripts/install.sh`、`scripts/upgrade.sh`、`scripts/doctor.sh`（`a44408f`）

#### 变更

- 隔离 dev/prod 编排，生产编排拒绝 dev 挂载与热重载（`a44408f`）
- 抽取 IP 解析、SMTP 发信、文件列表分页为公共模块（`bda76f1`）
- 统一夸克风格视觉体系，缩略图请求去重（`c015b80`）
- 品牌名统一为「筋斗云盘」，补齐 compose 环境变量透传（`1dc8e5d`）
- 分享提取码扩展为 8 位（`9c271e3`）

#### 修复

- refresh token 重用检测失效、`/metrics` 鉴权收敛（`1e25b43`）
- 缩略图链路、WS 重连与容器依赖锁定（`92b2f66`）
- 退出登录无响应、分类请求被本地会话拦截（`b6cc0b0`）
- 登出时清理 TanStack Query 缓存与通知状态（`d52fa49`）
- 前端死代码与根目录失效配置清理（`2ff1308`）

#### 安全

- 停止跟踪 `cookies.txt`（`1dc8e5d`）
- 密码/Token/密钥日志脱敏、登录限流、分享提取码防爆破

#### 升级注意

- 本版本为首次部署基线，直接执行 `scripts/install.sh` 即可
- `.env` 新增 `APP_VERSION`（缺省 `1.0.0`，未设置也能启动）

#### 数据库迁移

- 基线迁移共 8 个（`alembic/versions/`），首次启动自动执行 `alembic upgrade head`

> 详细踩坑记录见 [pitfalls.md](./pitfalls.md)，配置项见 [configuration.md](./configuration.md)。