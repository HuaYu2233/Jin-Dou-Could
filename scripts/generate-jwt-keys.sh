#!/usr/bin/env bash
set -euo pipefail

KEY_BITS="${1:-4096}"
OUT_DIR="${2:-.}"

PRIVATE_KEY_FILE="${OUT_DIR}/jwt_private.pem"
PUBLIC_KEY_FILE="${OUT_DIR}/jwt_public.pem"

if ! command -v openssl &>/dev/null; then
  echo "错误: openssl 未安装" >&2
  exit 1
fi

if [ -f "$PRIVATE_KEY_FILE" ] || [ -f "$PUBLIC_KEY_FILE" ]; then
  echo "警告: 密钥文件已存在:"
  [ -f "$PRIVATE_KEY_FILE" ] && echo "  - $PRIVATE_KEY_FILE"
  [ -f "$PUBLIC_KEY_FILE" ] && echo "  - $PUBLIC_KEY_FILE"
  read -rp "是否覆盖? [y/N] " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
  fi
fi

echo "正在生成 ${KEY_BITS} 位 RSA 密钥对..."

openssl genrsa -out "$PRIVATE_KEY_FILE" "$KEY_BITS" 2>/dev/null
chmod 600 "$PRIVATE_KEY_FILE"

openssl rsa -in "$PRIVATE_KEY_FILE" -pubout -out "$PUBLIC_KEY_FILE" 2>/dev/null
chmod 644 "$PUBLIC_KEY_FILE"

echo ""
echo "密钥生成完成:"
echo "  私钥: $PRIVATE_KEY_FILE (权限 600)"
echo "  公钥: $PUBLIC_KEY_FILE  (权限 644)"
echo ""
echo "在 .env 中配置:"
echo "  ALGORITHM=RS256"
echo "  JWT_PRIVATE_KEY_PATH=$PRIVATE_KEY_FILE"
echo "  JWT_PUBLIC_KEY_PATH=$PUBLIC_KEY_FILE"
echo ""
echo "Docker Secrets 挂载方式:"
echo "  docker secret create jwt_private_key $PRIVATE_KEY_FILE"
echo "  docker secret create jwt_public_key  $PUBLIC_KEY_FILE"