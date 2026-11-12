#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${ROOT_DIR}"

PYPROJECT="backend/pyproject.toml"
CONFIG_PY="backend/app/core/config.py"
FRONTEND_DIR="frontend"
ENV_EXAMPLE=".env.example"
ENV_FILE=".env"
CHANGELOG="doc/changelog.md"
COMPOSE_FILE="docker-compose.yml"

VERSION=""
REMOTE=""
ASSUME_YES=false
SKIP_TESTS=false
NO_PUSH=false

usage() {
  cat <<'USAGE'
用法: scripts/release.sh <版本号> [选项]

版本号格式: MAJOR.MINOR.PATCH（可带预发布标识，如 1.1.0-rc.1），不带 v 前缀。

流程: 前置检查 → 门禁校验 → 同步版本号 → 提交 → 打标签 → 推送

选项:
  --remote <name> 推送目标远端，默认取当前分支的上游（无上游则 origin）
  --skip-tests    跳过测试与 lint 门禁（不推荐）
  --no-push       只提交与打标签，不推送到远端
  -y, --yes       非交互模式，跳过确认
  -h, --help      显示帮助
USAGE
}

section() { printf '\n== %s ==\n' "$*"; }
ok() { printf '  ✓ %s\n' "$*"; }
note() { printf '  - %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die() { printf '✗ %s\n' "$*" >&2; exit 1; }

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

rewrite() {
  local expr="$1" file="$2" tmp
  [ -f "$file" ] || die "缺少文件: ${file}"
  tmp=$(mktemp)
  sed -E "$expr" "$file" >"$tmp"
  mv "$tmp" "$file"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-tests)
      SKIP_TESTS=true
      shift
      ;;
    --no-push)
      NO_PUSH=true
      shift
      ;;
    --remote)
      [ $# -ge 2 ] || die "--remote 需要一个远端名称"
      REMOTE="$2"
      shift 2
      ;;
    -y | --yes)
      ASSUME_YES=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      printf '未知参数: %s\n' "$1" >&2
      usage
      exit 2
      ;;
    *)
      [ -z "$VERSION" ] || die "只允许一个版本号参数"
      VERSION="$1"
      shift
      ;;
  esac
done

[ -n "$VERSION" ] || { usage; exit 2; }
printf '%s' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$' \
  || die "版本号格式非法: ${VERSION}（应为 MAJOR.MINOR.PATCH）"

section "1/6 前置检查"
command -v git >/dev/null 2>&1 || die "未找到 git"
[ -d .git ] || die "当前目录不是 git 仓库"
[ -f "$PYPROJECT" ] || die "缺少 ${PYPROJECT}"
[ -f "$CHANGELOG" ] || die "缺少 ${CHANGELOG}"

if [ -n "$(git --no-pager status --porcelain 2>/dev/null)" ]; then
  git --no-pager status --short >&2
  die "工作区存在未提交改动，请先提交或 stash 后再发版"
fi
ok "工作区干净"

if git --no-pager rev-parse -q --verify "refs/tags/v${VERSION}" >/dev/null 2>&1; then
  die "标签 v${VERSION} 已存在，如需重发请先删除本地与远端标签"
fi
ok "标签 v${VERSION} 未被占用"

grep -qF " v${VERSION}" "$CHANGELOG" \
  || die "${CHANGELOG} 缺少 v${VERSION} 小节，请先补写版本记录（新增/变更/修复/安全/升级注意/数据库迁移）"
ok "${CHANGELOG} 已包含 v${VERSION} 小节"

branch=$(git --no-pager rev-parse --abbrev-ref HEAD)
case "$branch" in
  master | main | dev) ok "当前分支: ${branch}" ;;
  *) warn "当前分支为 ${branch}，通常应在 master/main 上发版" ;;
esac

section "2/6 门禁校验"
if [ "$SKIP_TESTS" = true ]; then
  warn "已跳过 lint 与测试（--skip-tests），请自行确认 CI 结果"
else
  (cd backend && uv run ruff check .)
  (cd backend && uv run ruff format --check .)
  (cd backend && uv run pytest -q)
  (cd frontend && npm run lint)
  (cd frontend && npx tsc --noEmit)
  (cd frontend && npm run test)
  ok "后端 ruff/pytest 与前端 lint/tsc/vitest 全部通过"
fi

confirm "确认发布 v${VERSION}" y || die "已取消"

section "3/6 同步版本号"
(cd "$FRONTEND_DIR" && npm version "$VERSION" --no-git-tag-version --allow-same-version >/dev/null)
rewrite 's/^version = "[^"]*"/version = "'"${VERSION}"'"/' "$PYPROJECT"
rewrite 's/^    APP_VERSION: str = "[^"]*"/    APP_VERSION: str = "'"${VERSION}"'"/' "$CONFIG_PY"
rewrite 's/^APP_VERSION=.*/APP_VERSION='"${VERSION}"'/' "$ENV_EXAMPLE"
rewrite 's/APP_VERSION:-[0-9A-Za-z.-]+}/APP_VERSION:-'"${VERSION}"'}/' "$COMPOSE_FILE"
if [ -f "$ENV_FILE" ]; then
  if grep -q '^APP_VERSION=' "$ENV_FILE"; then
    rewrite 's/^APP_VERSION=.*/APP_VERSION='"${VERSION}"'/' "$ENV_FILE"
  else
    printf '\nAPP_VERSION=%s\n' "$VERSION" >>"$ENV_FILE"
  fi
  ok "已同步 ${ENV_FILE}"
fi
if (cd backend && uv lock >/dev/null 2>&1); then
  ok "已刷新 backend/uv.lock"
else
  warn "backend/uv.lock 刷新失败，请在 backend 目录执行 uv lock 后补提交"
fi
ok "已同步 ${PYPROJECT} / ${CONFIG_PY} / ${ENV_EXAMPLE} / ${COMPOSE_FILE} / frontend"

grep -q "version = \"${VERSION}\"" "$PYPROJECT" || die "pyproject 版本号同步失败"
grep -q "\"version\": \"${VERSION}\"" "${FRONTEND_DIR}/package.json" || die "package.json 版本号同步失败"
ok "版本号一致性校验通过"

section "4/6 提交"
git add "$PYPROJECT" "backend/uv.lock" "$CONFIG_PY" "$ENV_EXAMPLE" "$COMPOSE_FILE" "$CHANGELOG" \
  "${FRONTEND_DIR}/package.json" "${FRONTEND_DIR}/package-lock.json"
if git diff --cached --quiet; then
  note "版本号与记录已是最新，跳过提交，直接在当前 HEAD 打标签"
else
  git commit -m "chore(release): v${VERSION}" -m "同步版本号并归档 ${CHANGELOG} 版本记录"
  ok "已提交 $(git --no-pager rev-parse --short HEAD)"
fi

section "5/6 打标签"
git tag -a "v${VERSION}" -m "筋斗云盘 v${VERSION}"
ok "已创建附注标签 v${VERSION}"

section "6/6 推送"
if [ "$NO_PUSH" = true ]; then
  note "已跳过推送（--no-push），手动推送: git push <remote> ${branch} && git push <remote> v${VERSION}"
else
  if [ -z "$REMOTE" ]; then
    REMOTE=$(git --no-pager rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null | cut -d/ -f1 || true)
    [ -n "$REMOTE" ] || REMOTE=origin
  fi
  git remote get-url "$REMOTE" >/dev/null 2>&1 \
    || die "远端 ${REMOTE} 不存在，现有远端: $(git --no-pager remote | tr '\n' ' ')"
  note "推送目标: ${REMOTE}"
  git push "$REMOTE" "$branch"
  git push "$REMOTE" "v${VERSION}"
  ok "分支与标签已推送到 ${REMOTE}"
  if [ "$REMOTE" != origin ]; then
    warn "标签仅推送到 ${REMOTE}；GitHub CI 需推送到 origin 才会触发（git push origin ${branch} && git push origin v${VERSION}）"
  fi
fi

cat <<EOF

== 发布完成 ==
  版本: v${VERSION}
  提交: $(git --no-pager rev-parse --short HEAD)
  标签: v${VERSION}
  远端: ${REMOTE:-未推送}
  线上升级:
    scripts/upgrade.sh
  升级后确认版本:
    curl -fsS http://127.0.0.1:8000/health/ready
EOF