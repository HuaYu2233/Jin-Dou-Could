#!/bin/sh
set -e

BACKUP_NAME="$1"

if [ -z "${BACKUP_NAME}" ]; then
  echo "用法: ./restore.sh <备份目录名，如 20260907_030000>"
  echo "可用备份:"
  ls -1 /backups/ 2>/dev/null | grep "20*" || echo "  (无)"
  exit 1
fi

BACKUP_DIR="/backups/${BACKUP_NAME}"

if [ ! -d "${BACKUP_DIR}" ]; then
  echo "错误: 备份目录 ${BACKUP_DIR} 不存在"
  exit 1
fi

echo "===== 恢复预览 ====="
echo "备份目录: ${BACKUP_DIR}"
if [ -f "${BACKUP_DIR}/manifest.json" ]; then
  cat "${BACKUP_DIR}/manifest.json"
  echo ""
fi

echo ""
echo "警告: 恢复将覆盖当前数据库和 MinIO 数据！"
printf "确认恢复？输入 YES 继续: "
read CONFIRM

if [ "${CONFIRM}" != "YES" ]; then
  echo "已取消"
  exit 0
fi

echo "===== 开始恢复 ====="

# 1. 恢复 PostgreSQL
if [ -f "${BACKUP_DIR}/postgres.dump.gz.gpg" ]; then
  echo "[1/2] 恢复 PostgreSQL（加密备份）..."
  if [ -z "${BACKUP_ENCRYPT_KEY}" ]; then
    echo "错误: 备份已加密但未配置 BACKUP_ENCRYPT_KEY"
    exit 1
  fi
  echo "${BACKUP_ENCRYPT_KEY}" | gpg --batch --yes --passphrase-fd 0 \
    --decrypt "${BACKUP_DIR}/postgres.dump.gz.gpg" 2>/dev/null | \
    gunzip -c | \
    PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
      -h "${POSTGRES_HOST:-db}" \
      -U "${POSTGRES_USER}" \
      -d "${POSTGRES_DB}" \
      --clean --if-exists --no-owner --no-privileges 2>&1 || true
  echo "  PostgreSQL 恢复完成"
elif [ -f "${BACKUP_DIR}/postgres.dump.gz" ]; then
  echo "[1/2] 恢复 PostgreSQL..."
  gunzip -c "${BACKUP_DIR}/postgres.dump.gz" | \
    PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
      -h "${POSTGRES_HOST:-db}" \
      -U "${POSTGRES_USER}" \
      -d "${POSTGRES_DB}" \
      --clean --if-exists --no-owner --no-privileges 2>&1 || true
  echo "  PostgreSQL 恢复完成"
else
  echo "[1/2] 未找到 PostgreSQL 备份，跳过"
fi

# 2. 恢复 MinIO
if [ -d "${BACKUP_DIR}/minio" ]; then
  echo "[2/2] 恢复 MinIO..."
  mc alias set local "http://${MINIO_HOST:-minio}:9000" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" --api S3v4 > /dev/null 2>&1
  mc mirror --overwrite "${BACKUP_DIR}/minio/" "local/${MINIO_BUCKET:-cloud-drive}" 2>&1 || true
  echo "  MinIO 恢复完成"
else
  echo "[2/2] 未找到 MinIO 备份，跳过"
fi

echo "===== 恢复完成 ====="