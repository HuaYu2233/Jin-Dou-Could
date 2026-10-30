# 备份与恢复文档

## 1. 概述

备份系统使用独立 `backup` 容器，定时备份 PostgreSQL 数据库和 MinIO 对象存储数据。

### 架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  backup      │────▶│  PostgreSQL  │     │    MinIO     │
│  容器        │     │  pg_dump     │     │  mc mirror   │
└──────┬───────┘     └──────────────┘     └──────────────┘
       │
       ▼
┌──────────────┐
│  backups/    │
│  <timestamp>/│
│  ├── db/     │
│  └── minio/  │
└──────────────┘
```

## 2. 配置

| 配置项                  | 说明                   | 默认值      |
| ----------------------- | ---------------------- | ----------- |
| `BACKUP_RETENTION_DAYS` | 备份保留天数           | 7           |
| `BACKUP_CRON`           | Cron 表达式            | `0 3 * * *` |
| `BACKUP_RUN_ON_START`   | 启动时立即备份         | false       |
| `BACKUP_ENCRYPT_KEY`    | 加密密钥（留空不加密） | -           |

## 3. 备份内容

每次备份包含：

| 内容       | 方式        | 说明                       |
| ---------- | ----------- | -------------------------- |
| PostgreSQL | `pg_dump`   | 全量数据库导出（SQL 格式） |
| MinIO      | `mc mirror` | 对象存储全量镜像           |

## 4. 备份目录结构

```
backups/
└── 20261030_030000/          # 时间戳目录
    ├── db/
    │   ├── clouddrive.sql.gz # 数据库备份（gzip 压缩）
    │   └── clouddrive.sql.gz.gpg  # 加密备份（如启用）
    └── minio/
        └── cloud-drive/      # MinIO 对象镜像
            ├── user1/
            └── user2/
```

## 5. 手动操作

### 5.1 手动备份

```bash
docker compose exec backup /scripts/backup.sh
```

### 5.2 恢复

```bash
# 交互式恢复（需确认）
docker compose exec -it backup /scripts/restore.sh 20261030_030000

# 查看可用备份
ls -la backups/
```

> ⚠️ 恢复操作会**覆盖当前数据**，请谨慎操作。

### 5.3 管理后台触发

管理员可在管理后台的「备份管理」页面手动触发备份。

## 6. 加密

### 6.1 启用加密

设置 `BACKUP_ENCRYPT_KEY` 环境变量：

```env
BACKUP_ENCRYPT_KEY=my-secret-key-123
```

启用后，数据库备份文件使用 GPG AES256 对称加密，生成 `.gpg` 文件。

### 6.2 解密

```bash
gpg --batch --decrypt --passphrase "my-secret-key-123" \
    -o clouddrive.sql.gz clouddrive.sql.gz.gpg
```

## 7. 定时备份

### 7.1 Cron 配置

默认每天凌晨 3:00 执行备份：

```env
BACKUP_CRON=0 3 * * *
```

Cron 表达式格式：`分 时 日 月 周`

### 7.2 保留策略

超过 `BACKUP_RETENTION_DAYS` 天的备份自动清理。

## 8. 备份脚本说明

| 脚本                                | 说明             |
| ----------------------------------- | ---------------- |
| `scripts/backup.sh`                 | 执行备份         |
| `scripts/restore.sh`                | 执行恢复         |
| `scripts/backup-entrypoint.sh`      | 容器入口点       |
| `scripts/backup-trigger-watcher.sh` | 监听触发文件     |
| `scripts/Dockerfile.backup`         | 备份容器构建文件 |

## 9. 恢复流程

1. 停止后端服务（避免数据写入）
2. 恢复 PostgreSQL 数据库
3. 恢复 MinIO 对象存储
4. 重启后端服务
5. 验证数据完整性

```bash
# 完整恢复流程
docker compose stop backend celery-worker

docker compose exec -it backup /scripts/restore.sh 20261030_030000

docker compose start backend celery-worker

# 验证
curl http://localhost:8000/health/ready
```

## 10. 备份监控

- 管理后台可查看备份列表和状态
- 备份失败时可通过告警系统通知
- 建议定期验证备份可恢复性
