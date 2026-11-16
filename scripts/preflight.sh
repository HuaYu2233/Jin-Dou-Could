#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${ROOT_DIR}"

COMPOSE_FILE="docker-compose.yml"
OUT_FILE="${PREFLIGHT_OUT:-}"

PASS=0
FAIL=0

pass() {
  PASS=$((PASS + 1))
  printf '  ✓ %s\n' "$*"
}

fail() {
  FAIL=$((FAIL + 1))
  printf '  ✗ %s\n' "$*" >&2
}

usage() {
  cat <<'USAGE'
用法: scripts/preflight.sh [选项]

生产编排校验，只读，不修改文件或容器。

选项:
  -o, --output <path>   将 docker compose config 输出保存到指定文件
  -h, --help            显示帮助

退出码: 0 通过 / 1 校验失败
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    -o | --output)
      [ $# -ge 2 ] || {
        printf '缺少 --output 的路径参数\n' >&2
        exit 2
      }
      OUT_FILE="$2"
      shift 2
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

printf 'JinDou Cloud 生产编排校验 — %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"

command -v docker >/dev/null 2>&1 || {
  printf '✗ 未找到 docker\n' >&2
  exit 1
}

CONFIG_CONTENT=$(docker compose -f "${COMPOSE_FILE}" config 2>/dev/null) || {
  printf '✗ 生产编排校验失败：检查 .env（SECRET_KEY 必填）\n' >&2
  exit 1
}

if [ -n "${OUT_FILE}" ]; then
  printf '%s\n' "${CONFIG_CONTENT}" >"${OUT_FILE}"
fi

check_absent() {
  local pattern="$1" label="$2"
  if printf '%s' "${CONFIG_CONTENT}" | grep -Eq -- "${pattern}"; then
    fail "${label}"
  else
    pass "${label}：未检出"
  fi
}

if printf '%s' "${CONFIG_CONTENT}" | grep -Eq -- 'ENVIRONMENT[:=] *production'; then
  pass "ENVIRONMENT 为 production"
else
  fail "拒绝启动：ENVIRONMENT 必须为 production"
fi

check_absent 'npm run dev' "前端 dev 命令"
check_absent '--reload' "后端热重载参数"
check_absent 'target: /app/app' "后端源码 bind mount"
check_absent 'target: /app$' "前端源码 bind mount"

if [ "${FAIL}" -gt 0 ]; then
  printf '\n✗ 生产编排校验失败（%d 项不通过）\n' "${FAIL}" >&2
  exit 1
fi

printf '\n✓ 生产编排校验通过（无 dev 挂载、无热重载）\n'