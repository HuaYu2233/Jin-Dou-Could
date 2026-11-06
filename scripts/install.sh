#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${ROOT_DIR}"

COMPOSE_FILE="docker-compose.yml"
DEV_COMPOSE_FILE="docker-compose.dev.yml"
ENV_FILE=".env"
ENV_EXAMPLE=".env.example"
SECRETS_DIR="secrets"
HEALTH_URL="http://127.0.0.1:8000/health/ready"
HEALTH_TIMEOUT=180

MODE="prod"
FORCE=false
ASSUME_YES=false
FRONTEND_URL=""
API_URL=""
MINIO_PUBLIC_ENDPOINT=""
ADMIN_EMAIL=""
RS256_CHOICE=""

usage() {
  cat <<'USAGE'
用法: scripts/install.sh [选项]

选项:
  --mode prod|dev             部署模式，默认 prod
  --frontend-url URL          前端访问地址，默认 http://localhost:3000
  --api-url URL               后端 API 访问地址，默认 http://localhost:8000
  --minio-endpoint HOST:PORT  浏览器访问 MinIO 的地址，默认 localhost:9000
  --admin-email EMAIL         管理员邮箱（首个用该邮箱注册的用户自动成为管理员）
  --rs256                     启用 JWT RS256（生成 RSA-4096 密钥对）
  --no-rs256                  使用 HS256 对称签名
  --force                     覆盖已存在的 .env（自动备份为 .env.bak.<时间戳>）
  -y, --yes                   非交互模式，全部采用默认值
  -h, --help                  显示帮助
USAGE
}

section() { printf '\n== %s ==\n' "$*"; }
ok() { printf '  ✓ %s\n' "$*"; }
note() { printf '  - %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die() { printf '✗ %s\n' "$*" >&2; exit 1; }

ask() {
  local prompt="$1" default="${2:-}" answer=""
  if [ "$ASSUME_YES" = true ]; then
    printf '%s' "$default"
    return 0
  fi
  if [ -n "$default" ]; then
    printf '%s [%s]: ' "$prompt" "$default" >&2
  else
    printf '%s (可留空): ' "$prompt" >&2
  fi
  read -r answer || answer=""
  printf '%s' "${answer:-$default}"
}

confirm() {
  local prompt="$1" default="${2:-n}" answer=""
  if [ "$ASSUME_YES" = true ]; then
    [ "$default" = "y" ]
    return $?
  fi
  printf '%s [%s]: ' "$prompt" "$default" >&2
  if ! read -r answer; then
    return 1
  fi
  answer="${answer:-$default}"
  case "$answer" in
    y | Y | yes | YES) return 0 ;;
    *) return 1 ;;
  esac
}

gen_hex() {
  local bytes="${1:-32}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  elif [ -r /dev/urandom ]; then
    LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c $((bytes * 2))
  else
    die "无法生成随机密钥：缺少 openssl 与 /dev/urandom"
  fi
}

set_env() {
  local key="$1" value="$2" tmp
  tmp=$(mktemp)
  awk -v k="$key" -v v="$value" '
    BEGIN { replaced = 0 }
    {
      if (index($0, k "=") == 1) {
        if (!replaced) { print k "=" v; replaced = 1 }
        next
      }
      print
    }
    END { if (!replaced) print k "=" v }
  ' "$ENV_FILE" >"$tmp"
  mv "$tmp" "$ENV_FILE"
}

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1
  fi
}

wait_health() {
  local waited=0 body=""
  while [ "$waited" -lt "$HEALTH_TIMEOUT" ]; do
    if body=$(curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null); then
      if printf '%s' "$body" | head -c 30 | grep -q '{"status":"ok"'; then
        return 0
      fi
    fi
    sleep 3
    waited=$((waited + 3))
    printf '.'
  done
  return 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --frontend-url)
      FRONTEND_URL="${2:-}"
      shift 2
      ;;
    --api-url)
      API_URL="${2:-}"
      shift 2
      ;;
    --minio-endpoint)
      MINIO_PUBLIC_ENDPOINT="${2:-}"
      shift 2
      ;;
    --admin-email)
      ADMIN_EMAIL="${2:-}"
      shift 2
      ;;
    --rs256)
      RS256_CHOICE=true
      shift
      ;;
    --no-rs256)
      RS256_CHOICE=false
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    -y | --yes)
      ASSUME_YES=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      printf '未知参数: %s\n' "$1" >&2
      usage
      exit 2
      ;;
  esac
done

case "$MODE" in
  prod | dev) ;;
  *) die "非法 --mode: ${MODE}（只能是 prod 或 dev）" ;;
esac

section "1/6 环境预检"
command -v docker >/dev/null 2>&1 || die "未找到 docker，请先安装 Docker 20+"
docker info >/dev/null 2>&1 || die "Docker 守护进程未运行，请先启动 Docker"
docker compose version >/dev/null 2>&1 || die "未找到 docker compose v2（需要 Docker Compose 2.0+）"
command -v curl >/dev/null 2>&1 || die "未找到 curl，健康检查需要它"
ok "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '?') / compose $(docker compose version --short 2>/dev/null || echo '?')"

[ -f "$COMPOSE_FILE" ] || die "缺少 ${COMPOSE_FILE}，请在项目根目录运行"
[ -f "$ENV_EXAMPLE" ] || die "缺少 ${ENV_EXAMPLE}"
[ "$MODE" = "dev" ] && [ ! -f "$DEV_COMPOSE_FILE" ] && die "缺少 ${DEV_COMPOSE_FILE}"

running=$(docker compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | wc -l | tr -d ' ')
if [ "$running" != "0" ]; then
  die "检测到 ${running} 个容器已在运行。请先执行 make down，避免容器名与端口冲突"
fi
ok "当前无运行中的服务"

if [ "$MODE" = "prod" ]; then
  PORTS="80 3000 5433 6379 8000 9000 9001 9090 3001"
else
  PORTS="3000 5433 6379 8000 9000 9001"
fi
conflicts=""
for port in $PORTS; do
  if port_in_use "$port"; then
    conflicts="${conflicts} ${port}"
  fi
done
if [ -n "$conflicts" ]; then
  warn "以下端口已被占用:${conflicts}（若为本项目残留容器请先 make down）"
  confirm "端口冲突，仍要继续吗" n || die "已取消"
else
  ok "端口 ${PORTS} 均可用"
fi

free_kb=$(df -Pk . | awk 'NR==2 {print $4}')
if [ -n "$free_kb" ] && [ "$free_kb" -lt 2097152 ]; then
  warn "磁盘剩余 $(($free_kb / 1024)) MB，镜像构建建议至少 2 GB"
else
  ok "磁盘剩余 $((${free_kb:-0} / 1024)) MB"
fi

section "2/6 生成配置"
if [ -f "$ENV_FILE" ] && [ "$FORCE" != true ]; then
  confirm "${ENV_FILE} 已存在，是否重新生成（原文件会备份）" n || die "已取消。如需复用现有配置，直接执行 make prod / make dev"
fi
if [ -f "$ENV_FILE" ]; then
  backup_name="${ENV_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
  cp "$ENV_FILE" "$backup_name"
  ok "已备份原配置到 ${backup_name}"
fi
cp "$ENV_EXAMPLE" "$ENV_FILE"
chmod 600 "$ENV_FILE"
ok "已从 ${ENV_EXAMPLE} 生成 ${ENV_FILE}（权限 600）"

FRONTEND_URL=$(ask "前端访问地址" "${FRONTEND_URL:-http://localhost:3000}")
API_URL=$(ask "后端 API 访问地址" "${API_URL:-http://localhost:8000}")
MINIO_PUBLIC_ENDPOINT=$(ask "浏览器访问 MinIO 的地址（预签名下载链接用）" "${MINIO_PUBLIC_ENDPOINT:-localhost:9000}")
ADMIN_EMAIL=$(ask "管理员邮箱（留空则不设）" "${ADMIN_EMAIL:-}")

if [ "$MODE" = "prod" ]; then
  ENVIRONMENT="production"
else
  ENVIRONMENT="development"
fi

set_env ENVIRONMENT "$ENVIRONMENT"
set_env NEXT_PUBLIC_API_URL "$FRONTEND_URL"
set_env CORS_ORIGINS "$FRONTEND_URL"
set_env MINIO_PUBLIC_ENDPOINT "$MINIO_PUBLIC_ENDPOINT"
set_env ADMIN_EMAIL "$ADMIN_EMAIL"
ok "环境: ${ENVIRONMENT} / 前端: ${FRONTEND_URL} / API: ${API_URL}"

if [ "${API_URL#https://}" != "$API_URL" ]; then
  set_env HTTPS_REDIRECT true
  ok "检测到 HTTPS API 地址，已启用 HTTPS_REDIRECT"
else
  set_env HTTPS_REDIRECT false
fi
if [ "${API_URL#http://localhost}" = "$API_URL" ] && [ "$MODE" = "prod" ]; then
  warn "API 地址不是 localhost 但未使用 https，生产环境建议启用 TLS"
fi

set_env POSTGRES_PASSWORD "$(gen_hex 24)"
set_env REDIS_PASSWORD "$(gen_hex 24)"
set_env MINIO_ROOT_PASSWORD "$(gen_hex 24)"
set_env SECRET_KEY "$(gen_hex 32)"
set_env GRAFANA_ADMIN_PASSWORD "$(gen_hex 16)"
ok "已生成 POSTGRES / REDIS / MINIO / SECRET_KEY / GRAFANA 随机凭据"

section "3/6 JWT 签名与备份密钥"
if [ -z "$RS256_CHOICE" ]; then
  if [ "$MODE" = "prod" ]; then
    rs_default="y"
  else
    rs_default="n"
  fi
  if confirm "启用 JWT RS256 非对称签名（生成 RSA-4096 密钥对）" "$rs_default"; then
    RS256_CHOICE=true
  else
    RS256_CHOICE=false
  fi
fi

JWT_VOLUME_READY=false
if [ "$RS256_CHOICE" = true ]; then
  mkdir -p "$SECRETS_DIR"
  if [ -f "${SECRETS_DIR}/jwt_private.pem" ] && [ -f "${SECRETS_DIR}/jwt_public.pem" ]; then
    ok "复用已有密钥 ${SECRETS_DIR}/jwt_private.pem"
  else
    bash "${SCRIPT_DIR}/generate-jwt-keys.sh" 4096 "$SECRETS_DIR" >/dev/null
    ok "已调用 generate-jwt-keys.sh 生成 RSA-4096 密钥对"
  fi
  chmod 600 "${SECRETS_DIR}/jwt_private.pem"
  chmod 644 "${SECRETS_DIR}/jwt_public.pem"
  set_env ALGORITHM RS256
  set_env JWT_PRIVATE_KEY_PATH /run/secrets/jwt_private.pem
  set_env JWT_PUBLIC_KEY_PATH /run/secrets/jwt_public.pem
  JWT_VOLUME_READY=true
else
  set_env ALGORITHM HS256
  ok "使用 HS256 对称签名（SECRET_KEY）"
fi

BACKUP_KEY_FILE="${SECRETS_DIR}/backup_encrypt_key"
if [ "$MODE" = "prod" ]; then
  if confirm "启用备份加密（GPG AES256，密钥丢失将无法恢复备份）" y; then
    mkdir -p "$SECRETS_DIR"
    backup_key=$(gen_hex 24)
    set_env BACKUP_ENCRYPT_KEY "$backup_key"
    printf '%s\n' "$backup_key" >"$BACKUP_KEY_FILE"
    chmod 600 "$BACKUP_KEY_FILE"
    ok "备份加密已启用，密钥保存到 ${BACKUP_KEY_FILE}（请离线备份）"
  else
    set_env BACKUP_ENCRYPT_KEY ""
    note "未启用备份加密"
  fi
else
  note "开发模式不启用备份加密"
fi

section "4/6 构建镜像"
if command -v make >/dev/null 2>&1 && grep -q '^prod-build:' Makefile; then
  make -s prod-build
else
  DOCKER_BUILDKIT=1 docker compose -f "$COMPOSE_FILE" build backend celery-worker frontend
fi
ok "镜像构建完成"

if [ "$JWT_VOLUME_READY" = true ]; then
  docker compose -f "$COMPOSE_FILE" create --no-deps backend >/dev/null 2>&1 || true
  jwt_vol=$(docker volume ls --format '{{.Name}}' | grep -E '_jwt_keys$' | head -n1 || true)
  if [ -n "$jwt_vol" ]; then
    if docker run --rm \
      -v "${jwt_vol}:/keys" \
      -v "${ROOT_DIR}/${SECRETS_DIR}:/src:ro" \
      alpine:3.18 sh -c 'cp /src/jwt_private.pem /src/jwt_public.pem /keys/ && chmod 644 /keys/jwt_private.pem /keys/jwt_public.pem' >/dev/null 2>&1; then
      ok "RSA 密钥已写入卷 ${jwt_vol}（容器内 /run/secrets，后端以非 root 运行故需 644）"
    else
      warn "密钥写入卷失败，已回退到 HS256（如需 RS256 请手动写入 ${jwt_vol}）"
      set_env ALGORITHM HS256
    fi
  else
    warn "未找到 jwt_keys 卷，已回退到 HS256"
    set_env ALGORITHM HS256
  fi
fi

section "5/6 启动服务"
if [ "$MODE" = "prod" ]; then
  docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
  ok "已启动生产栈（仅 ${COMPOSE_FILE}，不含 dev 覆盖）"
else
  DOCKER_BUILDKIT=1 docker compose -f "$COMPOSE_FILE" -f "$DEV_COMPOSE_FILE" --profile dev build frontend
  docker compose -f "$COMPOSE_FILE" -f "$DEV_COMPOSE_FILE" --profile dev up -d --no-build \
    db redis minio pgbouncer backend frontend
  ok "已启动开发栈（含 --profile dev）"
fi

section "6/6 健康检查"
printf '  等待 /health/ready'
if wait_health; then
  printf '\n'
  ok "后端就绪（PostgreSQL / Redis / MinIO 全部 ok）"
else
  printf '\n'
  warn "等待 ${HEALTH_TIMEOUT}s 仍未就绪，请查看日志: docker compose -f ${COMPOSE_FILE} logs backend"
fi

exited=$(docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}|{{.State}}' 2>/dev/null | awk -F'|' '$2 != "running" {print $1}' | tr '\n' ' ')
if [ -n "$exited" ]; then
  warn "以下服务未在运行: ${exited}"
fi

cat <<EOF

== 安装完成 ==
  前端:        ${FRONTEND_URL}
  后端 API:    ${API_URL}
  API 文档:    ${API_URL%/}/docs
  MinIO 控制台: http://${MINIO_PUBLIC_ENDPOINT/9000/9001}
  管理员邮箱:  ${ADMIN_EMAIL:-(未设置，任何人都可注册，不会自动提权)}

  配置文件:    ${ENV_FILE}（权限 600）
  密钥目录:    ${SECRETS_DIR}/
EOF
if [ -f "$BACKUP_KEY_FILE" ]; then
  printf '  备份密钥:    %s（丢失将无法恢复加密备份）\n' "$BACKUP_KEY_FILE"
fi
cat <<'EOF'

  下一步:
    scripts/doctor.sh           # 部署体检
    make logs                   # 查看日志
    make down                   # 停止服务
EOF