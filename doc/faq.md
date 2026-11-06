# 常见问题（FAQ）

## 1. 部署相关

### Q: 启动报错 `SECRET_KEY 必须在 .env 中设置`

A: 在 `.env` 文件中设置 `SECRET_KEY`，要求 32 字符以上的强随机值：

```bash
# 生成随机密钥
openssl rand -hex 32
```

### Q: 首次启动很慢

A: 首次需要构建 Docker 镜像，约 5 分钟。后续启动使用缓存，开发模式约 2 秒。

```bash
# 首次构建
make prod-build

# 后续启动
make dev
```

### Q: 端口被占用怎么办？

A: 修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "127.0.0.1:8001:8000" # 将 8000 改为 8001
```

同时修改 `.env` 中的 `NEXT_PUBLIC_API_URL` 和 `CORS_ORIGINS`。

### Q: 如何查看容器日志？

A:

```bash
make logs                              # 所有服务日志
docker compose logs -f backend         # 后端日志
docker compose logs -f frontend        # 前端日志
tail -f backend/logs/app.log           # 结构化日志
```

## 2. 功能相关

### Q: 管理员账号如何创建？

A: 使用 `.env` 中 `ADMIN_EMAIL` 配置的邮箱注册，首个用户自动成为管理员。

验证：

```bash
docker compose exec backend env | grep ADMIN_EMAIL
```

### Q: 如何修改用户存储配额？

A: 管理员在「管理后台 → 用户管理」中调整，或通过 API：

```bash
curl -X PATCH http://localhost:8000/api/v1/admin/users/{user_id} \
  -H "Content-Type: application/json" \
  -d '{"storage_quota": 2147483648}'  # 2GB
```

### Q: 文件上传大小限制是多少？

A: 默认 100MB（`MAX_UPLOAD_SIZE=104857600`），可在 `.env` 中修改。

### Q: 如何启用 HTTPS？

A: 参考 [deployment.md](./deployment.md) 第 3.3 节。

### Q: 上传的压缩包不在「压缩包」分类里？

A: 分类由上传时探测出的真实 MIME 决定，白名单覆盖 `zip` / `rar` / `7z` / `gzip` / `x-gzip` / `tar` / `bzip2` / `xz`。

- 若文件被归为「其他」，说明其 MIME 不在上述集合内（例如 `application/x-rar` 之外的变体）
- 历史文件的 `file_type` 在上传时已落库，调整分类规则不会自动回填，需要重新上传或写迁移脚本
- 若上传直接被拒，则是 MIME 白名单未包含该类型，需要修改 `backend/app/services/file_validation.py` 后重启

### Q: 切换账号后还能看到上一个账号的文件？

A: 这是客户端缓存未清理的表现。正常登出会执行 `queryClient.clear()` 与通知 store 的 `clearAll()`；若仍复现，检查是否直接关闭标签页而未走登出流程（此时 localStorage 中的 `auth-storage` 与内存缓存会保留）。

排查：

```javascript
// 浏览器控制台
localStorage.removeItem("auth-storage");
location.reload();
```

### Q: 在 `.env` 里改了配置但没生效？

A: 变量必须被 `docker-compose.yml` 的 `environment` 段引用才会进入容器。核对方式：

```bash
docker compose config | grep -i 变量名
docker compose exec backend printenv | grep -i 变量名
```

若两处都没有，说明 compose 未透传，需要补 `environment` 后 `docker compose up -d` 重建。详见 [pitfalls.md](./pitfalls.md) 第 15 条。

## 3. 开发相关

### Q: 后端代码修改后不生效？

A: 开发模式下 uvicorn 自动热重载。如未生效：

```bash
make hot-reload    # 手动同步代码
make dev-restart   # 重启容器
```

### Q: 前端代码修改后不生效？

A: 开发模式下 Next.js 自动热重载。如未生效：

```bash
make dev-restart   # 重启容器
```

### Q: 如何运行数据库迁移？

A:

```bash
# 执行迁移
docker compose exec backend alembic upgrade head

# 生成新迁移
docker compose exec backend alembic revision --autogenerate -m "描述"
```

### Q: 如何连接数据库？

A:

```bash
# 通过 Docker
docker compose exec db psql -U clouduser -d clouddrive

# 通过本地客户端（端口 5433）
psql -h localhost -p 5433 -U clouduser -d clouddrive
```

### Q: 如何连接 Redis？

A:

```bash
docker compose exec redis redis-cli -a <password>
```

## 4. 备份相关

### Q: 如何手动备份？

A:

```bash
docker compose exec backup /scripts/backup.sh
```

### Q: 如何恢复备份？

A:

```bash
# 查看可用备份
ls -la backups/

# 恢复指定备份
docker compose exec -it backup /scripts/restore.sh 20261030_030000
```

> ⚠️ 恢复会覆盖当前数据！

### Q: 备份文件如何加密？

A: 设置 `BACKUP_ENCRYPT_KEY`：

```env
BACKUP_ENCRYPT_KEY=my-secret-key-123
```

## 5. 告警相关

### Q: 如何配置钉钉告警？

A:

```env
ALERT_ENABLED=true
ALERT_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
ALERT_WEBHOOK_TYPE=dingtalk
```

### Q: 如何配置飞书告警？

A:

```env
ALERT_ENABLED=true
ALERT_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
ALERT_WEBHOOK_TYPE=feishu
```

## 6. 性能相关

### Q: 文件很多时列表加载慢？

A: 项目已使用虚拟滚动（react-virtuoso）和游标分页优化。如仍慢，检查：

1. 数据库索引是否正常：`docker compose exec db psql -c "\di"`
2. 连接池是否够用：检查 `DB_POOL_SIZE` 和 `DB_MAX_OVERFLOW`
3. Redis 是否正常：`curl http://localhost:8000/health`

### Q: 上传大文件内存占用高？

A: 后端使用流式直传 MinIO，内存占用 O(1)。如仍有问题，检查：

1. Nginx 请求体大小限制（`client_max_body_size`）
2. Gunicorn timeout 配置

### Q: WebSocket 连接断开？

A: 前端使用指数退避重连（1→2→4→8→16s）。检查：

1. Redis 是否正常（WS Pub/Sub 依赖 Redis）
2. `WS_PUBSUB_ENABLED` 是否为 true
3. 网络代理是否支持 WebSocket

## 7. 故障排查

### Q: 所有服务启动失败

A:

```bash
# 查看日志
docker compose logs

# 检查端口占用
lsof -i :8000
lsof -i :3000
lsof -i :5433

# 重新构建
make prod-build
make dev
```

### Q: 后端健康检查失败

A:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

检查 DB/Redis/MinIO 连接。

### Q: 数据丢失

A: 检查是否误执行了 `docker compose down -v`（会删除数据卷）。如有备份，参考 [backup-restore.md](./backup-restore.md) 恢复。