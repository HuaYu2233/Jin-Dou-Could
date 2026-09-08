#!/bin/sh
set -e

BACKUP_CRON="${BACKUP_CRON:-0 3 * * *}"

cat > /etc/crontabs/root << EOF
${BACKUP_CRON} /scripts/backup.sh >> /var/log/backup.log 2>&1
EOF

echo "备份服务已启动"
echo "Cron 表达式: ${BACKUP_CRON} (分 时 日 月 周)"
echo "备份保留: ${BACKUP_RETENTION_DAYS:-7} 天"
echo "下次备份时间: $(date -d "tomorrow ${BACKUP_CRON#* }" 2>/dev/null || echo "见 cron 表达式")"

# 启动时立即执行一次备份（可选，注释掉则不执行）
if [ "${RUN_ON_START:-false}" = "true" ]; then
  echo "启动时立即执行一次备份..."
  /scripts/backup.sh || true
fi

# 启动备份触发文件监听器（后台，替代 docker exec）
sh /scripts/backup-trigger-watcher.sh &
echo "备份触发监听器已启动（共享卷触发文件模式）"

# 启动 crond 前台运行
exec crond -f -l 2