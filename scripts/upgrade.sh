#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${ROOT_DIR}"

COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
BACKUP_DIR_ROOT="backups"
HEALTH_URL="http://127.0.0.1:8000/health/ready"
HEALTH_TIMEOUT=180

DO_BACKUP=true
DO_PULL=true
DO_BUILD=true
ASSUME_YES=false
LATEST_BACKUP=""
PREVIOUS_TAG=""
PREVIOUS_COMMIT=""

usage() {
  cat <<'USAGE'
用法: scripts/upgrade.sh [选项]

流程: 升级前备份 → 拉取代码 → 重建镜像 → 滚动重启 → 健康校验

选项:
  --no-backup   跳过升级前备份（不推荐）
  --no-pull     跳过 git pull（例如部署目录不是 git 仓库）
  --no-build    跳过镜像重建（仅重启容器）
  -y, --yes     非交互模式，跳过确认
  -h, --help    显示帮助
USAGE
}

section() { printf '\n== %s ==\n' "$*"; }
ok() { printf '  ✓ %s\n' "$*"; }
note() { printf '  - %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die() { printf '✗ %s\n' "$*" >&2; exit 1; }

on_error() {
  printf '\n✗ 升级中断\n' >&2
  if [ -n "$LATEST_BACKUP" ]; then
    printf '回滚数据库与对象存储（需在终端交互确认）:\n  docker compose -f %s exec backup /bin/sh /scripts/restore.sh %s\n' \
      "$COMPOSE_FILE" "$(basename "$LATEST_BACKUP")" >&2
  fi
  printf '查看日志:\n  docker compose -f %s logs --tail 50 backend\n' "$COMPOSE_FILE" >&2
  if [ -n "$PREVIOUS_COMMIT" ]; then
    printf '回滚代码到升级前版本:\n  git checkout %s && docker compose -f %s up -d --build\n' \
      "$PREVIOUS_COMMIT" "$COMPOSE_FILE" >&2
  fi
}
trap on_error ERR

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
    --no-backup)
      DO_BACKUP=false
      shift
      ;;
    --no-pull)
      DO_PULL=false
      shift
      ;;
    --no-build)
      DO_BUILD=false
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

section "1/6 升级前检查"
command -v docker >/dev/null 2>&1 || die "未找到 docker"
docker info >/dev/null 2>&1 || die "Docker 守护进程未运行"
docker compose version >/dev/null 2>&1 || die "未找到 docker compose v2"
[ -f "$COMPOSE_FILE" ] || die "缺少 ${COMPOSE_FILE}，请在项目根目录运行"
[ -f "$ENV_FILE" ] || die "缺少 ${ENV_FILE}，请先运行 scripts/install.sh"
command -v curl >/dev/null 2>&1 || die "未找到 curl，健康检查需要它"
docker compose -f "$COMPOSE_FILE" config -q 2>/dev/null || die "编排校验失败，请检查 ${ENV_FILE}（SECRET_KEY 为必填项）"
ok "编排文件与 ${ENV_FILE} 校验通过"

running=$(docker compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | wc -l | tr -d ' ')
if [ "$running" = "0" ]; then
  die "未检测到运行中的服务，请先执行 scripts/install.sh 或 make prod"
fi
ok "检测到 ${running} 个运行中的容器"

if [ "$DO_PULL" = true ] && [ -d .git ]; then
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    warn "工作区存在未提交改动，git pull 可能失败"
  fi
  current=$(git --no-pager rev-parse --short HEAD 2>/dev/null || echo '?')
  PREVIOUS_COMMIT=$(git --no-pager rev-parse HEAD 2>/dev/null || echo '')
  PREVIOUS_TAG=$(git --no-pager describe --tags --exact-match 2>/dev/null || echo '')
  note "当前提交: ${current}"
  if [ -n "$PREVIOUS_TAG" ]; then
    note "升级前版本: ${PREVIOUS_TAG}"
  else
    note "当前提交未打标签，回滚将使用 commit ${current}"
  fi
fi

confirm "确认开始升级" y || die "已取消"

section "2/6 升级前备份"
if [ "$DO_BACKUP" = true ]; then
  mkdir -p "$BACKUP_DIR_ROOT"
  if docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}|{{.State}}' 2>/dev/null | grep -q '^backup|running'; then
    note "通过 backup 容器执行 /scripts/backup.sh"
    docker compose -f "$COMPOSE_FILE" exec -T backup /bin/sh /scripts/backup.sh
  else
    note "backup 容器未运行，使用一次性容器执行 /scripts/backup.sh"
    docker compose -f "$COMPOSE_FILE" run --rm --no-deps --entrypoint /bin/sh backup -c "/scripts/backup.sh"
  fi

  LATEST_BACKUP=$(ls -1d "${BACKUP_DIR_ROOT}"/20* 2>/dev/null | sort | tail -n1 || true)
  [ -n "$LATEST_BACKUP" ] || die "备份失败：${BACKUP_DIR_ROOT}/ 下未生成备份目录"
  if grep -q '"status": "success"' "${LATEST_BACKUP}/manifest.json" 2>/dev/null; then
    ok "备份完成: ${LATEST_BACKUP}"
  else
    die "备份清单缺失或状态异常: ${LATEST_BACKUP}/manifest.json"
  fi
else
  warn "已跳过升级前备份（--no-backup），出问题将无法回滚数据"
fi

section "3/6 拉取代码"
if [ "$DO_PULL" = true ]; then
  if [ -d .git ]; then
    git --no-pager pull --ff-only
    ok "已拉取到 $(git --no-pager rev-parse --short HEAD 2>/dev/null || echo '?')"
  else
    note "当前目录不是 git 仓库，跳过"
  fi
else
  note "已跳过 git pull（--no-pull）"
fi

section "4/6 重建镜像"
if [ "$DO_BUILD" = true ]; then
  DOCKER_BUILDKIT=1 docker compose -f "$COMPOSE_FILE" build backend celery-worker frontend
  ok "镜像重建完成"
else
  note "已跳过镜像重建（--no-build）"
fi

section "5/6 滚动重启"
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
ok "已按 ${COMPOSE_FILE} 重新拉起服务"

section "6/6 升级后校验"
printf '  等待 /health/ready'
if wait_health; then
  printf '\n'
  ok "后端就绪"
else
  printf '\n'
  die "等待 ${HEALTH_TIMEOUT}s 仍未就绪，升级可能失败"
fi

running_version=$(curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null \
  | tr ',' '\n' | sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' | head -n1 || true)
if [ -n "$running_version" ]; then
  ok "当前运行版本: ${running_version}"
else
  warn "无法从 /health/ready 读取版本号，请检查 APP_VERSION 是否已透传"
fi

note "数据库迁移由 backend 启动命令自动执行（alembic upgrade head）"
current_rev=$(docker compose -f "$COMPOSE_FILE" exec -T backend alembic current 2>/dev/null | tail -n1 || true)
if [ -n "$current_rev" ]; then
  ok "当前迁移版本: ${current_rev}"
else
  warn "无法读取 alembic current，请手动检查"
fi

bad=$(docker compose -f "$COMPOSE_FILE" ps --format '{{.Service}}|{{.State}}|{{.Health}}' 2>/dev/null \
  | awk -F'|' '$2 != "running" || $3 == "unhealthy" {print $1}' | tr '\n' ' ')
if [ -n "$bad" ]; then
  die "以下服务状态异常: ${bad}"
fi
ok "全部服务运行正常"

cat <<EOF

== 升级完成 ==
  备份目录: ${LATEST_BACKUP:-(本次未备份)}
  运行版本: ${running_version:-未知}
  如需回滚数据:
    docker compose -f ${COMPOSE_FILE} exec backup /bin/sh /scripts/restore.sh <备份目录名>
  部署体检:
    scripts/doctor.sh
EOF