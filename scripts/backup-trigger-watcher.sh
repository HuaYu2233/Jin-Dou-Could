#!/bin/sh

# 监听共享卷 /backups 下的 .trigger_* 文件，检测到后执行备份

# 替代原 docker exec 触发方式，无需挂载 docker.sock
set -e

TRIGGER_DIR="/backups"
POLL_INTERVAL=2

mkdir -p "${TRIGGER_DIR}"

echo "[trigger-watcher] 监听备份触发文件: ${TRIGGER_DIR}/.trigger_*"

while true; do
    for f in "${TRIGGER_DIR}"/.trigger_*; do
        [ -f "$f" ] || continue
        echo "[trigger-watcher] $(date '+%Y-%m-%d %H:%M:%S') 检测到触发文件: $f"
        rm -f "$f"
        /scripts/backup.sh >> /var/log/backup.log 2>&1 || \
            echo "[trigger-watcher] 备份执行失败，请查看 /var/log/backup.log"
        break
    done
    sleep "${POLL_INTERVAL}"
done
