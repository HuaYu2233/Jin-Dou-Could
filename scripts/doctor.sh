#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${ROOT_DIR}"

COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
SECRETS_DIR="secrets"
BACKUP_DIR_ROOT="backups"
API_BASE="http://127.0.0.1:8000"

STRICT=false
PASS=0
WARN=0
FAIL=0

usage() {
  cat <<'USAGE'
用法: scripts/doctor.sh [选项]

只读体检，不修改任何文件或容器。

选项:
  --strict     警告也视为失败（退出码 1），适合 CI / 巡检
  -h, --help   显示帮助
USAGE
}

section() { printf '\n== %s ==\n' "$*"; }
pass() {
  PASS=$((PASS + 1))
  printf '  ✓ %s\n' "$*"
}
warn() {
  WARN=$((WARN + 1))
  printf '  ! %s\n' "$*"
}
fail() {
  FAIL=$((FAIL + 1))
  printf '  ✗ %s\n' "$*"
}

env_get() {
  local v
  v=$(grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d= -f2-)
  v="${v%\"}"
  v="${v#\"}"
  printf '%s' "$v"
}

file_mode() {
  stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1" 2>/dev/null || echo "?"
}

check_mode_secret() {
  local path="$1" label="$2" mode
  mode=$(file_mode "$path")
  case "$mode" in
    *4 | *5 | *6 | *7) warn "${label} ${path} 权限 ${mode}，同组/其他用户可读，建议 chmod 600" ;;
    *) pass "${label} ${path} 权限 ${mode}" ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --strict)
      STRICT=true
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

printf 'JinDou Cloud 部署体检 — %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"

section "1. 运行环境"
command -v docker >/dev/null 2>&1 && pass "docker 已安装" || fail "未找到 docker"
if docker info >/dev/null 2>&1; then
  pass "Docker 守护进程正常"
else
  fail "Docker 守护进程未运行"
fi
if docker compose version >/dev/null 2>&1; then
  pass "docker compose $(docker compose version --short 2>/dev/null || echo v2)"
else
  fail "未找到 docker compose v2"
fi
command -v curl >/dev/null 2>&1 && pass "curl 已安装" || warn "未找到 curl，健康检查将被跳过"

free_kb=$(df -Pk . 2>/dev/null | awk 'NR==2 {print $4}')
if [ -n "${free_kb:-}" ]; then
  if [ "$free_kb" -lt 1048576 ]; then
    warn "磁盘剩余 $(($free_kb / 1024)) MB，低于 1 GB"
  else
    pass "磁盘剩余 $(($free_kb / 1024)) MB"
  fi
fi

section "2. 配置文件"
if [ ! -f "$ENV_FILE" ]; then
  fail "缺少 ${ENV_FILE}，请先运行 scripts/install.sh"
else
  pass "存在 ${ENV_FILE}"
  check_mode_secret "$ENV_FILE" "配置文件"

  placeholders=""
  for key in POSTGRES_PASSWORD REDIS_PASSWORD MINIO_ROOT_PASSWORD SECRET_KEY; do
    value=$(env_get "$key")
    if [ -z "$value" ]; then
      fail "${key} 为空"
      continue
    fi
    case "$value" in
      change-your-password | change-your-redis-password | change-this-to-a-random-secret-key | \
        cloudpass123 | redispass123 | minioadmin123 | dev-secret-key-change-in-prod)
        placeholders="${placeholders} ${key}"
        ;;
    esac
  done
  if [ -n "$placeholders" ]; then
    fail "以下配置仍是模板默认值:${placeholders}"
  else
    pass "数据库 / Redis / MinIO / SECRET_KEY 均非默认占位值"
  fi

  secret_key=$(env_get SECRET_KEY)
  if [ "${#secret_key}" -ge 32 ]; then
    pass "SECRET_KEY 长度 ${#secret_key}（≥32）"
  else
    fail "SECRET_KEY 长度 ${#secret_key}，低于 32 字符"
  fi

  grafana_pwd=$(env_get GRAFANA_ADMIN_PASSWORD)
  if [ -z "$grafana_pwd" ] || [ "$grafana_pwd" = "admin" ]; then
    warn "GRAFANA_ADMIN_PASSWORD 为默认值，Grafana 面板存在弱口令风险"
  else
    pass "GRAFANA_ADMIN_PASSWORD 已自定义"
  fi

  environment=$(env_get ENVIRONMENT)
  environment="${environment:-production}"
  if [ "$environment" = "production" ]; then
    pass "ENVIRONMENT=production"
  else
    warn "ENVIRONMENT=${environment}，非生产模式（后端以单进程 uvicorn 运行）"
  fi

  if [ "$environment" = "production" ]; then
    [ "$(env_get HTTPS_REDIRECT)" = "true" ] && pass "HTTPS_REDIRECT 已启用" ||
      warn "HTTPS_REDIRECT 未启用，生产环境建议强制 HTTPS"

    frontend_url=$(env_get NEXT_PUBLIC_API_URL)
    case "$frontend_url" in
      *localhost* | 127.0.0.1*) warn "NEXT_PUBLIC_API_URL=${frontend_url} 仍指向 localhost，浏览器将无法访问" ;;
      *https://*) pass "NEXT_PUBLIC_API_URL 使用 HTTPS" ;;
      *) warn "NEXT_PUBLIC_API_URL 未使用 HTTPS" ;;
    esac

    cors=$(env_get CORS_ORIGINS)
    case "$cors" in
      *localhost* | 127.0.0.1*) warn "CORS_ORIGINS=${cors} 含 localhost，生产环境应改为实际域名" ;;
      *) pass "CORS_ORIGINS 已配置域名" ;;
    esac

    minio_public=$(env_get MINIO_PUBLIC_ENDPOINT)
    case "$minio_public" in
      "") warn "MINIO_PUBLIC_ENDPOINT 为空，预签名下载链接会使用内部地址，浏览器不可达" ;;
      localhost* | 127.0.0.1*)
        warn "MINIO_PUBLIC_ENDPOINT=${minio_public}，预签名下载链接在浏览器侧不可达"
        ;;
      *) pass "MINIO_PUBLIC_ENDPOINT=${minio_public}" ;;
    esac

    if [ "$(env_get ALGORITHM)" = "RS256" ]; then
      pass "JWT 使用 RS256 非对称签名"
    else
      warn "JWT 使用 HS256 对称签名，多服务场景建议切换 RS256"
    fi

    [ -n "$(env_get BACKUP_ENCRYPT_KEY)" ] && pass "备份加密已启用" ||
      warn "BACKUP_ENCRYPT_KEY 为空，备份未加密"

    [ -n "$(env_get TRUSTED_PROXIES)" ] && pass "TRUSTED_PROXIES 已配置" ||
      warn "TRUSTED_PROXIES 为空，经 Nginx/Cloudflare 后限流会把所有请求记成同一 IP"
  fi

  workers=$(env_get BACKEND_WORKERS)
  pool=$(env_get DB_POOL_SIZE)
  overflow=$(env_get DB_MAX_OVERFLOW)
  max_conn=$(env_get DB_MAX_CONNECTIONS)
  workers="${workers:-4}"
  pool="${pool:-5}"
  overflow="${overflow:-5}"
  max_conn="${max_conn:-100}"
  need=$((workers * (pool + overflow)))
  if [ "$need" -lt "$max_conn" ]; then
    pass "连接池上限 ${need} < DB_MAX_CONNECTIONS ${max_conn}（${workers}×(${pool}+${overflow})）"
  else
    fail "连接池上限 ${need} ≥ DB_MAX_CONNECTIONS ${max_conn}，可能耗尽数据库连接"
  fi
fi

section "3. 编排校验"
if docker compose -f "$COMPOSE_FILE" config -q >/dev/null 2>&1; then
  pass "${COMPOSE_FILE} 语法与变量校验通过"
  cfg=$(docker compose -f "$COMPOSE_FILE" config 2>/dev/null || true)

  if printf '%s' "$cfg" | grep -q 'npm run dev'; then
    fail "生产编排中出现 npm run dev（dev 前端混入生产栈）"
  else
    pass "生产编排未使用前端 dev 命令"
  fi

  if printf '%s' "$cfg" | grep -q -- '--reload'; then
    fail "生产编排中出现 uvicorn --reload（热重载混入生产栈）"
  else
    pass "生产编排未启用后端热重载"
  fi

  if printf '%s' "$cfg" | grep -q 'target: /app/app'; then
    fail "检测到后端源码 bind mount（dev 编排混入生产）"
  else
    pass "无后端源码 bind mount"
  fi

  if printf '%s' "$cfg" | grep -Eq 'target: /app$'; then
    fail "检测到前端源码 bind mount（dev 编排混入生产）"
  else
    pass "无前端源码 bind mount"
  fi

  if [ "$(printf '%s' "$cfg" | grep -c 'target: runner' || true)" -gt 0 ]; then
    pass "前端使用 runner（standalone）构建阶段"
  else
    warn "未检测到前端 runner 阶段，请确认前端为生产构建"
  fi
else
  fail "${COMPOSE_FILE} 校验失败（检查 ${ENV_FILE} 中 SECRET_KEY 等必填项）"
fi

if grep -Eq '^[[:space:]]*image: .*:latest$' "$COMPOSE_FILE" 2>/dev/null; then
  warn "编排中存在浮动 tag :latest，建议固定版本或 digest 以保证供应链可复现"
else
  pass "镜像版本已固定"
fi

section "4. 容器状态"
stack_q=$(docker compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | wc -l | tr -d ' ')
if [ "$stack_q" = "0" ]; then
  fail "未检测到运行中的容器（执行 make prod 或 scripts/install.sh）"
else
  pass "检测到 ${stack_q} 个容器"
  while IFS='|' read -r svc state health; do
    [ -z "$svc" ] && continue
    if [ "$state" != "running" ]; then
      fail "服务 ${svc} 状态 ${state}"
    elif [ "$health" = "unhealthy" ]; then
      fail "服务 ${svc} 健康检查失败"
    elif [ "$health" = "starting" ]; then
      warn "服务 ${svc} 健康检查进行中"
    else
      pass "服务 ${svc} 运行中${health:+（${health}）}"
    fi
  done < <(docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}|{{.State}}|{{.Health}}' 2>/dev/null)

  for c in $(docker ps -a --filter name=cloud-drive- --format '{{.Names}}' 2>/dev/null); do
    rc=$(docker inspect -f '{{.RestartCount}}' "$c" 2>/dev/null || echo 0)
    if [ "${rc:-0}" -gt 3 ]; then
      warn "${c} 重启 ${rc} 次，可能存在崩溃循环"
    fi
  done
fi

section "5. 端口暴露"
if [ "$stack_q" = "0" ]; then
  warn "栈未运行，跳过端口检查"
else
  while IFS='|' read -r name ports; do
    [ -z "$name" ] && continue
    case "$ports" in
      *0.0.0.0:* | *"[::]":*)
        case "$name" in
          cloud-drive-frontend | cloud-drive-nginx)
            pass "${name} 对外暴露（预期）"
            ;;
          *)
            warn "${name} 绑定到所有网卡: ${ports}（建议仅绑 127.0.0.1）"
            ;;
        esac
        ;;
    esac
  done < <(docker ps --format '{{.Names}}|{{.Ports}}' 2>/dev/null)
  pass "端口暴露检查完成（仅 frontend / nginx 应对外监听）"
fi

section "6. 健康探测"
if command -v curl >/dev/null 2>&1; then
  if curl -fsS --max-time 5 "${API_BASE}/health" >/dev/null 2>&1; then
    pass "GET /health 返回 2xx"
  else
    fail "GET /health 失败（后端未就绪或端口未监听）"
  fi

  ready=$(curl -fsS --max-time 8 "${API_BASE}/health/ready" 2>/dev/null || true)
  if [ -z "$ready" ]; then
    fail "GET /health/ready 无响应"
  else
    if printf '%s' "$ready" | head -c 30 | grep -q '{"status":"ok"'; then
      pass "整体状态 ok"
    else
      fail "整体状态 degraded"
    fi
    for comp in postgres redis minio; do
      if printf '%s' "$ready" | grep -q "\"${comp}\":{\"status\":\"ok\""; then
        pass "${comp} 连通"
      else
        fail "${comp} 探测失败"
      fi
    done
  fi
else
  warn "缺少 curl，跳过健康探测"
fi

section "7. 备份"
if [ ! -d "$BACKUP_DIR_ROOT" ]; then
  fail "备份目录 ${BACKUP_DIR_ROOT}/ 不存在"
else
  pass "备份目录 ${BACKUP_DIR_ROOT}/ 存在"
  latest=$(ls -1d "${BACKUP_DIR_ROOT}"/20* 2>/dev/null | sort | tail -n1 || true)
  count=$(ls -1d "${BACKUP_DIR_ROOT}"/20* 2>/dev/null | wc -l | tr -d ' ')
  if [ -z "$latest" ]; then
    warn "尚无备份记录"
  else
    pass "共 ${count} 份备份，最新 $(basename "$latest")"
    if grep -q '"status": "success"' "${latest}/manifest.json" 2>/dev/null; then
      pass "最新备份清单状态 success"
    else
      fail "最新备份清单缺失或状态异常"
    fi
    if [ -z "$(find "$latest" -maxdepth 0 -mmin -2880 2>/dev/null)" ]; then
      warn "最新备份超过 48 小时，请确认 BACKUP_CRON 与 backup 容器是否正常"
    else
      pass "最新备份在 48 小时内"
    fi
  fi

  if docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}|{{.State}}' 2>/dev/null | grep -q '^backup|running'; then
    pass "backup 容器运行中（定时备份生效）"
  else
    warn "backup 容器未运行，定时备份不会执行"
  fi
fi

if [ -n "$(env_get BACKUP_ENCRYPT_KEY)" ]; then
  if [ -f "${SECRETS_DIR}/backup_encrypt_key" ]; then
    check_mode_secret "${SECRETS_DIR}/backup_encrypt_key" "备份密钥"
  else
    warn "备份已加密但未找到 ${SECRETS_DIR}/backup_encrypt_key，请确认密钥已离线保存"
  fi
fi

section "8. 密钥文件"
if [ "$(env_get ALGORITHM)" = "RS256" ]; then
  private_path=$(env_get JWT_PRIVATE_KEY_PATH)
  public_path=$(env_get JWT_PUBLIC_KEY_PATH)
  if [ -f "${SECRETS_DIR}/jwt_private.pem" ]; then
    check_mode_secret "${SECRETS_DIR}/jwt_private.pem" "JWT 私钥"
  else
    fail "ALGORITHM=RS256 但缺少 ${SECRETS_DIR}/jwt_private.pem（执行 scripts/generate-jwt-keys.sh 4096 secrets）"
  fi
  if [ -f "${SECRETS_DIR}/jwt_public.pem" ]; then
    pass "存在 ${SECRETS_DIR}/jwt_public.pem"
  else
    fail "ALGORITHM=RS256 但缺少 ${SECRETS_DIR}/jwt_public.pem"
  fi

  case "${private_path} ${public_path}" in
    */run/secrets/*) pass "容器内密钥路径指向 /run/secrets（jwt_keys 卷）" ;;
    *) warn "JWT 密钥路径为 ${private_path} / ${public_path}，请确认容器内可读" ;;
  esac

  if [ "$stack_q" != "0" ]; then
    if docker compose -f "$COMPOSE_FILE" exec -T backend test -r /run/secrets/jwt_private.pem >/dev/null 2>&1; then
      pass "backend 容器可读 /run/secrets/jwt_private.pem"
    else
      fail "backend 容器无法读取 /run/secrets/jwt_private.pem（appuser 非 root，卷内需 644）"
    fi
  fi
else
  pass "JWT 使用 HS256，无需 RSA 密钥文件"
fi

section "9. 近期错误日志"
if [ "$stack_q" = "0" ]; then
  warn "栈未运行，跳过日志扫描"
else
  err_count=$(docker compose -f "$COMPOSE_FILE" logs --since 1h --no-color backend 2>/dev/null \
    | grep -c -E '"level": "ERROR"|Traceback' || true)
  if [ "${err_count:-0}" -eq 0 ]; then
    pass "后端近 1 小时无 ERROR"
  else
    warn "后端近 1 小时出现 ${err_count} 条 ERROR/Traceback，请查看 make logs"
  fi
fi

printf '\n== 汇总 ==\n  通过 %d / 警告 %d / 失败 %d\n' "$PASS" "$WARN" "$FAIL"

exit_code=0
if [ "$FAIL" -gt 0 ]; then
  exit_code=1
  printf '  存在失败项，请优先处理\n'
elif [ "$STRICT" = true ] && [ "$WARN" -gt 0 ]; then
  exit_code=1
  printf '  --strict 模式下警告视为失败\n'
else
  printf '  未发现阻塞性问题\n'
fi

exit "$exit_code"