# 配置说明

所有配置通过 `.env` 文件管理，参考 `.env.example` 模板。

## 1. 数据库与存储

| 配置项                | 说明           | 默认值     | 必填 |
| --------------------- | -------------- | ---------- | ---- |
| `POSTGRES_USER`       | 数据库用户名   | clouduser  | 是   |
| `POSTGRES_PASSWORD`   | 数据库密码     | -          | 是   |
| `POSTGRES_DB`         | 数据库名       | clouddrive | 是   |
| `REDIS_PASSWORD`      | Redis 密码     | -          | 是   |
| `MINIO_ROOT_USER`     | MinIO 用户名   | minioadmin | 是   |
| `MINIO_ROOT_PASSWORD` | MinIO 密码     | -          | 是   |
| `MINIO_SECURE`        | MinIO TLS 连接 | false      | 否   |

### MinIO 与上传

| 配置项                    | 说明                             | 默认值       | 必填 |
| ------------------------- | -------------------------------- | ------------ | ---- |
| `MINIO_ENDPOINT`          | 后端访问 MinIO 的内部地址        | minio:9000   | 否   |
| `MINIO_PUBLIC_ENDPOINT`   | 浏览器访问 MinIO 的对外地址      | localhost:9000 | 否 |
| `MINIO_BUCKET`            | 存储桶名称                       | cloud-drive  | 否   |
| `MINIO_DOWNLOAD_EXPIRES`  | 预签名下载链接有效期（秒）       | 3600         | 否   |
| `MAX_UPLOAD_SIZE`         | 单文件大小上限（字节）           | 104857600    | 否   |
| `UPLOAD_CHUNK_SIZE`       | 分片读取步长（字节）             | 8388608      | 否   |
| `MULTIPART_THRESHOLD`     | 触发分片上传的阈值（字节）       | 16777216     | 否   |
| `UPLOAD_PART_SIZE`        | 分片大小（字节）                 | 5242880      | 否   |

## 2. JWT 与认证

| 配置项                        | 说明                     | 默认值 | 必填 |
| ----------------------------- | ------------------------ | ------ | ---- |
| `SECRET_KEY`                  | JWT 签名密钥（≥32 字符） | -      | 是   |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 过期时间    | 30     | 否   |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh Token 过期时间   | 7      | 否   |

> ⚠️ `SECRET_KEY` 必须为 32 字符以上的强随机值，弱密钥将导致启动失败。

## 3. 前端与网络

| 配置项                | 说明                     | 默认值                | 必填 |
| --------------------- | ------------------------ | --------------------- | ---- |
| `NEXT_PUBLIC_API_URL` | 浏览器访问后端地址       | http://localhost:8000 | 是   |
| `API_URL`             | Docker 内部后端地址      | http://backend:8000   | 否   |
| `CORS_ORIGINS`        | 允许的前端源（逗号分隔） | http://localhost:3000 | 是   |

## 4. 管理与配额

| 配置项                  | 说明                     | 默认值            | 必填 |
| ----------------------- | ------------------------ | ----------------- | ---- |
| `ADMIN_EMAIL`           | 自动成为管理员的邮箱     | -                 | 否   |
| `MAX_USERS`             | 最大注册用户数（0=不限） | 0                 | 否   |
| `DEFAULT_STORAGE_QUOTA` | 新用户默认配额（字节）   | 1073741824（1GB） | 否   |

## 5. 日志

| 配置项               | 说明         | 默认值 | 必填 |
| -------------------- | ------------ | ------ | ---- |
| `LOG_LEVEL`          | 日志级别     | INFO   | 否   |
| `LOG_DIR`            | 日志目录     | logs   | 否   |
| `LOG_RETENTION_DAYS` | 日志保留天数 | 30     | 否   |

日志级别：DEBUG / INFO / WARNING / ERROR

## 6. 备份

| 配置项                  | 说明                       | 默认值      | 必填 |
| ----------------------- | -------------------------- | ----------- | ---- |
| `BACKUP_RETENTION_DAYS` | 备份保留天数               | 7           | 否   |
| `BACKUP_CRON`           | 备份 Cron 表达式           | `0 3 * * *` | 否   |
| `BACKUP_RUN_ON_START`   | 启动时立即备份             | false       | 否   |
| `BACKUP_ENCRYPT_KEY`    | 备份加密密钥（留空不加密） | -           | 否   |

## 7. 告警

| 配置项                   | 说明                   | 默认值  | 必填 |
| ------------------------ | ---------------------- | ------- | ---- |
| `ALERT_ENABLED`          | 启用日志告警           | false   | 否   |
| `ALERT_MIN_LEVEL`        | 触发告警的最低级别     | ERROR   | 否   |
| `ALERT_COOLDOWN_SECONDS` | 同一错误冷却时间（秒） | 300     | 否   |
| `ALERT_WEBHOOK_URL`      | Webhook 地址           | -       | 否   |
| `ALERT_WEBHOOK_TYPE`     | Webhook 类型           | generic | 否   |
| `ALERT_EMAIL_ENABLED`    | 启用邮件告警           | false   | 否   |

Webhook 类型：`generic` / `dingtalk` / `feishu` / `wechat`

### 邮件告警

| 配置项                      | 说明        | 默认值 |
| --------------------------- | ----------- | ------ |
| `ALERT_EMAIL_SMTP_HOST`     | SMTP 服务器 | -      |
| `ALERT_EMAIL_SMTP_PORT`     | SMTP 端口   | 587    |
| `ALERT_EMAIL_SMTP_USER`     | SMTP 用户   | -      |
| `ALERT_EMAIL_SMTP_PASSWORD` | SMTP 密码   | -      |
| `ALERT_EMAIL_FROM`          | 发件人      | -      |
| `ALERT_EMAIL_TO`            | 收件人      | -      |
| `ALERT_EMAIL_USE_TLS`       | 使用 TLS    | true   |

## 8. 密码找回

| 配置项                               | 说明               | 默认值   |
| ------------------------------------ | ------------------ | -------- |
| `RESET_PASSWORD_SMTP_HOST`           | SMTP 服务器        | -        |
| `RESET_PASSWORD_SMTP_PORT`           | SMTP 端口          | 465      |
| `RESET_PASSWORD_SMTP_USER`           | SMTP 用户          | -        |
| `RESET_PASSWORD_SMTP_PASSWORD`       | SMTP 密码          | -        |
| `RESET_PASSWORD_FROM_EMAIL`          | 发件人邮箱         | -        |
| `RESET_PASSWORD_FROM_NAME`           | 发件人名称         | 筋斗云盘 |
| `RESET_PASSWORD_CODE_EXPIRE_SECONDS` | 验证码有效期（秒） | 600      |
| `RESET_PASSWORD_CODE_LENGTH`         | 验证码位数         | 6        |

> 留空则复用告警邮件 SMTP 配置

## 9. 环境与部署

| 配置项            | 说明                               | 默认值      |
| ----------------- | ---------------------------------- | ----------- |
| `ENVIRONMENT`     | 环境（production 时启用 Gunicorn） | development |
| `BACKEND_WORKERS` | Gunicorn Worker 数                 | 4           |

## 10. Celery 异步任务队列

| 配置项                      | 说明                                          | 默认值 |
| --------------------------- | --------------------------------------------- | ------ |
| `CELERY_BROKER_URL`         | Broker URL（留空自动从 REDIS_URL 派生 DB1）   | -      |
| `CELERY_RESULT_BACKEND_URL` | 结果后端 URL（留空自动从 REDIS_URL 派生 DB2） | -      |
| `CELERY_TASK_ALWAYS_EAGER`  | Eager 模式（同步执行，仅开发/测试用）         | false  |
| `CELERY_CONCURRENCY`        | Worker 并发数                                 | 4      |

## 11. 数据库连接池

| 配置项               | 说明         | 默认值 | 说明                                             |
| -------------------- | ------------ | ------ | ------------------------------------------------ |
| `DB_POOL_SIZE`       | 连接池大小   | 5      | 开发 5，生产建议 10                              |
| `DB_MAX_OVERFLOW`    | 溢出上限     | 5      | 允许超出 pool_size 的连接数                      |
| `DB_POOL_TIMEOUT`    | 获取超时(秒) | 30     | 等待可用连接的超时时间                           |
| `DB_POOL_RECYCLE`    | 连接回收(秒) | 3600   | 连接最大存活时间                                 |
| `DB_MAX_CONNECTIONS` | PG 最大连接  | 80     | 需 ≥ WORKERS × (POOL_SIZE + MAX_OVERFLOW) + 预留 |

## 12. 安全与限流

| 配置项                     | 说明                          | 默认值 |
| -------------------------- | ----------------------------- | ------ |
| `HTTPS_REDIRECT`           | 强制 HTTPS 重定向             | false  |
| `SECURITY_HEADERS_ENABLED` | 启用安全响应头                | true   |
| `RATE_LIMIT_ENABLED`       | 启用全局限流                  | true   |
| `RATE_LIMIT_PER_MINUTE`    | 每分钟每 IP 最大请求数        | 60     |
| `TRUSTED_PROXIES`          | 信任的反向代理 IP（逗号分隔） | -      |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`   | 登录失败最大次数      | 5      |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | 登录失败统计窗口（秒） | 300    |
| `LOGIN_RATE_LIMIT_LOCK_SECONDS`   | 触发后锁定时间（秒）   | 900    |
| `MAX_CONCURRENT_UPLOADS`          | 单用户最大并发上传数   | 3      |
| `MAX_CONCURRENT_DOWNLOADS`        | 单用户最大并发下载数   | 5      |
| `CSRF_ENABLED`             | CSRF 双提交 Cookie 防护       | true   |

## 13. WebSocket 与可观测性

| 配置项               | 说明                                       | 默认值 |
| -------------------- | ------------------------------------------ | ------ |
| `WS_PUBSUB_ENABLED`  | WebSocket Redis Pub/Sub 多 Worker 消息广播 | true   |
| `PROMETHEUS_ENABLED` | 启用 Prometheus 指标（`/metrics` 端点）    | false  |

## 14. 生产环境配置检查清单

- [ ] `SECRET_KEY` 设为 32+ 字符强随机值
- [ ] `POSTGRES_PASSWORD` 设为强密码
- [ ] `REDIS_PASSWORD` 设为强密码
- [ ] `MINIO_ROOT_PASSWORD` 设为强密码
- [ ] `ENVIRONMENT=production`
- [ ] `NEXT_PUBLIC_API_URL` 改为实际域名
- [ ] `CORS_ORIGINS` 改为实际域名
- [ ] `HTTPS_REDIRECT=true`（如启用 SSL）
- [ ] `CSRF_ENABLED=true`
- [ ] `SECURITY_HEADERS_ENABLED=true`
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] `CELERY_TASK_ALWAYS_EAGER=false`
- [ ] `BACKUP_ENCRYPT_KEY` 设为加密密钥
- [ ] 连接池配置合理：WORKERS × (POOL_SIZE + MAX_OVERFLOW) < DB_MAX_CONNECTIONS