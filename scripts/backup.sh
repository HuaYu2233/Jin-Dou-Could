#!/bin/sh
set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/${TIMESTAMP}"
MANIFEST="${BACKUP_DIR}/manifest.json"

mkdir -p "${BACKUP_DIR}"

echo "===== 开始备份 ${TIMESTAMP} ====="

# 1. PostgreSQL 备份
echo "[1/3] 备份 PostgreSQL..."
PG_DUMP_START=$(date +%s)
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
  -h "${POSTGRES_HOST:-db}" \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --format=custom \
  | gzip > "${BACKUP_DIR}/postgres.dump.gz"
PG_DUMP_END=$(date +%s)
PG_DUMP_SIZE=$(stat -c%s "${BACKUP_DIR}/postgres.dump.gz" 2>/dev/null || stat -f%z "${BACKUP_DIR}/postgres.dump.gz")
echo "  PostgreSQL 备份完成: ${PG_DUMP_SIZE} 字节, 耗时 $((PG_DUMP_END - PG_DUMP_START))秒"

# 1.5 GPG 加密（如果配置了密钥）
PG_FILE="postgres.dump.gz"
PG_ENCRYPTED=false
if [ -n "${BACKUP_ENCRYPT_KEY}" ]; then
  echo "  [1.5/3] 加密 PostgreSQL 备份..."
  echo "${BACKUP_ENCRYPT_KEY}" | gpg --batch --yes --passphrase-fd 0 \
    --symmetric --cipher-algo AES256 \
    -o "${BACKUP_DIR}/postgres.dump.gz.gpg" \
    "${BACKUP_DIR}/postgres.dump.gz"
  rm -f "${BACKUP_DIR}/postgres.dump.gz"
  PG_FILE="postgres.dump.gz.gpg"
  PG_DUMP_SIZE=$(stat -c%s "${BACKUP_DIR}/${PG_FILE}" 2>/dev/null || stat -f%z "${BACKUP_DIR}/${PG_FILE}")
  PG_ENCRYPTED=true
  echo "  加密完成: ${PG_DUMP_SIZE} 字节"
fi

# 2. MinIO 备份
echo "[2/3] 备份 MinIO..."
MC_START=$(date +%s)
mc alias set local "http://${MINIO_HOST:-minio}:9000" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" --api S3v4 > /dev/null 2>&1
mc mirror --overwrite local/"${MINIO_BUCKET:-cloud-drive}" "${BACKUP_DIR}/minio/" > /dev/null 2>&1 || true
MC_END=$(date +%s)
echo "  MinIO 备份完成, 耗时 $((MC_END - MC_START))秒"

# 3. 生成清单
echo "[3/3] 生成备份清单..."
cat > "${MANIFEST}" << EOF
{
  "timestamp": "${TIMESTAMP}",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "postgres": {
    "file": "${PG_FILE}",
    "size": ${PG_DUMP_SIZE},
    "encrypted": ${PG_ENCRYPTED}
  },
  "minio": {
    "dir": "minio",
    "bucket": "${MINIO_BUCKET:-cloud-drive}"
  },
  "status": "success"
}
EOF

echo "===== 备份完成: ${BACKUP_DIR} ====="

# 4. 清理旧备份
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
echo "清理 ${RETENTION_DAYS} 天前的旧备份..."
find /backups -maxdepth 1 -type d -name "20*" -mtime +${RETENTION_DAYS} -exec rm -rf {} \; 2>/dev/null || true

echo "===== 备份流程结束 ====="