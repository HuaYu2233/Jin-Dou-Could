# 安全设计文档

## 1. 安全架构概览

```
请求 → HTTPS 重定向 → 安全响应头 → 限流 → CSRF → CORS → 认证 → 业务逻辑
```

## 2. 认证与授权

### 2.1 JWT Token

| 属性           | Access Token     | Refresh Token     |
| -------------- | ---------------- | ----------------- |
| 用途           | API 请求认证     | 刷新 Access Token |
| 存储方式       | HttpOnly Cookie  | HttpOnly Cookie   |
| 过期时间       | 30 分钟          | 7 天              |
| Token 类型字段 | `type: "access"` | `type: "refresh"` |
| 黑名单         | Redis            | Redis             |

**防混用机制**：JWT payload 包含 `type` 字段，access token 不能用于 refresh 接口，反之亦然。

**账号状态校验**：登录、Token 刷新、常规 API 请求（含 Redis 缓存命中路径）与 WebSocket 认证均校验 `is_active`，禁用账号立即拒绝访问；管理员禁用用户时会清除该用户的 Redis 缓存。

### 2.2 密码安全

- **哈希算法**：bcrypt（cost factor 自动调整）
- **密码策略**：前端校验 + 后端校验
- **登录限流**：同一 IP + 邮箱 5 次失败后锁定 15 分钟

### 2.3 管理员权限

- `ADMIN_EMAIL` 配置的邮箱注册时自动设为管理员
- 管理接口使用 `get_current_admin` 依赖，校验 `is_admin=True`

## 3. 中间件安全

### 3.1 安全响应头（SecurityHeadersMiddleware）

| 头部                      | 值                                  | 说明           |
| ------------------------- | ----------------------------------- | -------------- |
| X-Content-Type-Options    | nosniff                             | 防止 MIME 嗅探 |
| X-Frame-Options           | DENY                                | 防止点击劫持   |
| X-XSS-Protection          | 1; mode=block                       | XSS 过滤       |
| Referrer-Policy           | strict-origin-when-cross-origin     | 引用策略       |
| Content-Security-Policy   | 严格 CSP 策略                       | CSP 策略       |
| Strict-Transport-Security | max-age=31536000; includeSubDomains | HSTS           |

> CSP 的 `connect-src` 动态读取 `MINIO_PUBLIC_ENDPOINT`，确保 MinIO 连接合法。

### 3.2 CSRF 防护（CSRFMiddleware）

- **实现方式**：纯 ASGI 中间件，避免 BaseHTTPMiddleware 性能开销
- **策略**：双提交 Cookie（Double Submit Cookie）
- **豁免**：GET/HEAD/OPTIONS 请求、WebSocket、`/health` 端点
- **scope 级解析**：直接解析 cookie 和 header，不构造 Request 对象

### 3.3 限流（RateLimitMiddleware）

- **算法**：Redis 滑动窗口限流
- **维度**：IP + 路径
- **默认规则**：每分钟每 IP 60 次请求
- **登录/注册**：更严格限流（5 次/5 分钟）
- **Redis 不可达时**：放行并记录告警日志（降级策略）
- **仅信任代理 IP** 读取 X-Forwarded-For（`TRUSTED_PROXIES`）

### 3.4 请求日志（RequestLoggingMiddleware）

- 纯 ASGI 中间件，避免消耗 request body
- 记录 request_id、方法、路径、状态码、耗时
- 敏感数据脱敏

## 4. 上传安全

### 4.1 MIME 类型检测

- 使用 `python-magic` 检测文件真实 MIME 类型（非依赖客户端声明）
- 白名单校验：仅允许指定类型上传
- 检测失败、检测组件不可用或真实类型不在白名单时拒绝上传（fail-closed）
- 分片上传在第 1 片落盘前探测真实类型，完成合并时以探测结果覆盖客户端声明值；未完成探测的分片会话拒绝合并
- 常见别名（`audio/mp3`、`application/mp4`）归一化后参与白名单判断
- 防止 MIME 嗅探：`X-Content-Type-Options: nosniff`

### 4.2 文件名净化

- 去除特殊字符、路径遍历字符（`../`、`..\\`）
- 限制文件名长度

### 4.3 上传大小限制

- 默认 100MB（`MAX_UPLOAD_SIZE`）
- 存储配额检查：上传前校验用户剩余空间

## 5. WebSocket 安全

| 措施           | 说明                                        |
| -------------- | ------------------------------------------- |
| 认证方式       | 首条消息发送 token（非 URL 参数，防止泄露） |
| 认证超时       | 5 秒内未认证则断开连接                      |
| 消息长度限制   | 单条消息最大 4KB                            |
| 账号状态       | 认证时查库校验 `is_active`，禁用账号断开    |
| 多 Worker 广播 | Redis Pub/Sub 消息总线                      |

## 6. 基础设施安全

### 6.1 Docker

| 措施          | 说明                            |
| ------------- | ------------------------------- |
| 非 root 运行  | 生产容器以非 root 用户运行      |
| 端口绑定      | 仅绑定 127.0.0.1（除前端 3000） |
| Docker socket | 备份容器不挂载 Docker socket    |
| 多阶段构建    | 生产镜像不包含开发工具          |
| HEALTHCHECK   | 各容器配置健康检查              |

### 6.2 Redis

| 措施          | 说明                           |
| ------------- | ------------------------------ |
| 密码认证      | `--requirepass`                |
| 禁用 FLUSHALL | `--rename-command FLUSHALL ""` |
| 端口绑定      | 仅绑定 127.0.0.1               |

### 6.3 PostgreSQL

| 措施       | 说明                     |
| ---------- | ------------------------ |
| 密码认证   | 独立用户 + 强密码        |
| 端口绑定   | 仅绑定 127.0.0.1:5433    |
| 最大连接数 | `max_connections` 可配置 |

### 6.4 MinIO

| 措施     | 说明                    |
| -------- | ----------------------- |
| 密码认证 | 独立用户 + 强密码       |
| 端口绑定 | API 9000 + Console 9001 |
| TLS 支持 | `MINIO_SECURE=true`     |

## 7. 缓存安全

### 7.1 用户缓存脱敏

Redis 中缓存的用户信息移除以下敏感字段：

- `hashed_password`
- `security_question`
- `security_answer`

### 7.2 缓存失效

- 用户信息变更时主动失效缓存
- 使用 `SCAN` 替代 `KEYS` 避免阻塞 Redis
- 分批删除（每批 500 key）

## 8. 告警/降级安全

| 场景            | 处理方式                                  |
| --------------- | ----------------------------------------- |
| Redis 不可达    | 限流放行 + 记录告警日志                   |
| Celery 不可达   | 告警降级为同步发送（`asyncio.to_thread`） |
| 告警发送失败    | `create_task` 异常回调捕获，不影响主流程  |
| S3 初始化竞态   | `asyncio.Lock` 保护，防止并发重复创建     |
| S3 批量删除失败 | 自动降级为逐个重试                        |

## 9. 安全配置检查

生产环境必须确保以下配置：

```env
SECRET_KEY=<32+ 字符强随机值>
POSTGRES_PASSWORD=<强密码>
REDIS_PASSWORD=<强密码>
MINIO_ROOT_PASSWORD=<强密码>
CSRF_ENABLED=true
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_ENABLED=true
HTTPS_REDIRECT=true
ENVIRONMENT=production
```
