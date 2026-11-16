#!/bin/bash
set -uo pipefail

QUEUE_DIR="${DEPLOY_QUEUE_DIR:-/deploy}"
COMPOSE_FILE="${COMPOSE_FILE:-${DEPLOY_REPO_PATH}/docker-compose.yml}"
REPO_DIR="${DEPLOY_REPO_PATH:-$(dirname "${COMPOSE_FILE}")}"
POLL_INTERVAL="${DEPLOY_POLL_INTERVAL:-2}"
SNAPSHOT_INTERVAL="${DEPLOY_SNAPSHOT_INTERVAL:-15}"
RETENTION_DAYS="${DEPLOY_RETENTION_DAYS:-7}"

SNAPSHOT_DIR="${QUEUE_DIR}/snapshot"
ROLLBACK_SERVICES="backend frontend celery-worker"
BUILD_SERVICES="backend celery-worker frontend"
PROJECT_NAME=""
IMAGE_MAP="{}"
ROLLBACK_MAP="{}"
TMP_PS=""
TMP_INSPECT=""

log() { printf '[deploy-runner] %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

heartbeat() { touch "${QUEUE_DIR}/heartbeat" 2>/dev/null || true; }

cleanup_tmp() { rm -f "${TMP_PS}" "${TMP_INSPECT}"; }
trap cleanup_tmp EXIT

ensure_dirs() {
  mkdir -p "${QUEUE_DIR}/queue" "${QUEUE_DIR}/running" "${QUEUE_DIR}/results" "${QUEUE_DIR}/logs" "${SNAPSHOT_DIR}"
  heartbeat
}

prune_old() {
  local dir
  for dir in queue running results logs; do
    find "${QUEUE_DIR}/${dir}" -type f -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
  done
}

write_meta() {
  local tmp="${SNAPSHOT_DIR}/meta.json.tmp"
  local app_version compose_hash git_commit image_tags

  app_version="${APP_VERSION:-}"
  compose_hash=""
  if [ -f "${COMPOSE_FILE}" ]; then
    compose_hash=$(sha256sum "${COMPOSE_FILE}" 2>/dev/null | cut -d' ' -f1)
    compose_hash="${compose_hash:0:12}"
  fi
  git_commit=""
  if [ -d "${REPO_DIR}/.git" ]; then
    git_commit=$(git -C "${REPO_DIR}" rev-parse --short HEAD 2>/dev/null || true)
  fi

  image_tags='{}'
  if [ -f "${SNAPSHOT_DIR}/containers.json" ]; then
    image_tags=$(jq -c '[.services[]? | select(.service != "" and .image != "") | {(.service): .image}] | add // {}' \
      "${SNAPSHOT_DIR}/containers.json" 2>/dev/null || echo '{}')
  fi

  jq -n \
    --arg collected_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg app_version "${app_version}" \
    --arg compose_hash "${compose_hash}" \
    --arg git_commit "${git_commit}" \
    --argjson image_tags "${image_tags}" \
    '{
      collected_at: $collected_at,
      app_version: (if $app_version == "" then null else $app_version end),
      compose_hash: (if $compose_hash == "" then null else $compose_hash end),
      git_commit: (if $git_commit == "" then null else $git_commit end),
      image_tags: $image_tags
    }' >"${tmp}" && mv "${tmp}" "${SNAPSHOT_DIR}/meta.json"
}

write_snapshot() {
  if [ ! -f "${COMPOSE_FILE}" ]; then
    log "编排文件不存在，跳过快照: ${COMPOSE_FILE}"
    return 0
  fi

  local raw
  raw=$(docker compose -f "${COMPOSE_FILE}" ps --format json 2>/dev/null) || raw=""
  if [ -z "${raw}" ]; then
    log "docker compose ps 无输出，跳过快照"
    return 0
  fi

  TMP_PS=$(mktemp)
  printf '%s' "${raw}" | jq -s 'if length == 1 and (.[0] | type) == "array" then .[0] else . end' >"${TMP_PS}" 2>/dev/null || {
    log "解析 docker compose ps 输出失败"
    return 0
  }

  TMP_INSPECT=$(mktemp)
  local names name
  names=$(jq -r '.[].Name // empty' "${TMP_PS}" 2>/dev/null)
  printf '[' >"${TMP_INSPECT}"
  local first=true
  while IFS= read -r name; do
    [ -n "${name}" ] || continue
    local health restarts
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "${name}" 2>/dev/null || true)
    restarts=$(docker inspect --format '{{.RestartCount}}' "${name}" 2>/dev/null || echo 0)
    case "${restarts}" in
      [0-9]*) ;;
      *) restarts=0 ;;
    esac
    [ "${first}" = true ] || printf ',' >>"${TMP_INSPECT}"
    first=false
    jq -cn --arg name "${name}" --arg health "${health}" --argjson restarts "${restarts}" \
      '{name: $name, health: $health, restart_count: $restarts}' >>"${TMP_INSPECT}"
  done <<<"${names}"
  printf ']' >>"${TMP_INSPECT}"

  local tmp="${SNAPSHOT_DIR}/containers.json.tmp"
  local project
  project=$(jq -r '(.[0].Project // "")' "${TMP_PS}" 2>/dev/null)

  jq -n \
    --arg collected_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg project "${project}" \
    --slurpfile ps "${TMP_PS}" \
    --slurpfile insp "${TMP_INSPECT}" \
    'def insp($n): (($insp[0] // []) | map(select(.name == $n)) | .[0] // {});
     {
       collected_at: $collected_at,
       compose_project: (if $project == "" then null else $project end),
       services: [ $ps[0][] | {
         service: (.Service // ""),
         container: (.Name // ""),
         state: ((.State // "unknown") | ascii_downcase),
         health: (
           if ((.Health // "") == "")
           then ((insp(.Name).health // "") | if . == "" then null else . end)
           else .Health
           end
         ),
         image: (.Image // ""),
         created: (.CreatedAt // null),
         restart_count: (insp(.Name).restart_count // 0),
         ports: [
           (.Publishers // [])[]
           | "\(if (.URL // "") == "" then "" else (.URL + ":") end)\(.PublishedPort)->\(.TargetPort)/\(.Protocol)"
         ]
       } ]
     }' >"${tmp}" 2>/dev/null && mv "${tmp}" "${SNAPSHOT_DIR}/containers.json" \
    || log "写入容器快照失败"

  rm -f "${TMP_PS}" "${TMP_INSPECT}"
  TMP_PS=""
  TMP_INSPECT=""
}

LOG_DIR="${QUEUE_DIR}/logs"

emit() {
  local task_id="$1" step="$2" status="$3" pct="$4" msg="$5"
  local line
  line=$(jq -cn \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg step "${step}" \
    --arg status "${status}" \
    --argjson pct "${pct}" \
    --arg msg "${msg}" \
    '{ts: $ts, step: $step, status: $status, pct: $pct, msg: $msg}' 2>/dev/null) || return 0
  printf '%s\n' "${line}" >>"${LOG_DIR}/${task_id}.jsonl" 2>/dev/null || true
  log "[${task_id}] ${step} ${status} ${pct}% ${msg}"
  heartbeat
}

update_task() {
  local task_id="$1"
  shift
  local file="${QUEUE_DIR}/running/${task_id}.json"
  local tmp="${file}.tmp"
  [ -f "${file}" ] || return 0
  jq "$@" "${file}" >"${tmp}" 2>/dev/null && mv "${tmp}" "${file}"
}

task_field() {
  local task_id="$1" field="$2"
  jq -r "${field} // empty" "${QUEUE_DIR}/running/${task_id}.json" 2>/dev/null || true
}

finish_task() {
  local task_id="$1" status="$2" error="$3" rolled_back="${4:-false}"
  local running="${QUEUE_DIR}/running/${task_id}.json"
  local result="${QUEUE_DIR}/results/${task_id}.json"
  local tmp="${result}.tmp"

  if [ -f "${running}" ]; then
    jq \
      --arg status "${status}" \
      --arg finished_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg error "${error}" \
      --argjson rolled_back "${rolled_back}" \
      '.status = $status | .finished_at = $finished_at | .updated_at = $finished_at
       | .rolled_back = $rolled_back
       | .error = (if $error == "" then null else $error end)' \
      "${running}" >"${tmp}" 2>/dev/null && mv "${tmp}" "${result}"
    rm -f "${running}"
  fi
  [ -f "${result}" ] || log "任务 ${task_id} 结果写入失败"
}

compose() {
  docker compose -f "${COMPOSE_FILE}" "$@"
}

container_of() {
  compose ps -q "$1" 2>/dev/null | head -n1
}

image_base() {
  local ref="$1" last
  case "${ref}" in
    *@*)
      printf '%s' "${ref%%@*}"
      return 0
      ;;
  esac
  last="${ref##*/}"
  if printf '%s' "${last}" | grep -q ':'; then
    printf '%s' "${ref%:*}"
  else
    printf '%s' "${ref}"
  fi
}

image_ref() {
  local ref="$1" last
  case "${ref}" in
    *@*)
      printf '%s' "${ref}"
      return 0
      ;;
  esac
  last="${ref##*/}"
  if printf '%s' "${last}" | grep -q ':'; then
    printf '%s' "${ref}"
  else
    printf '%s' "${ref}:latest"
  fi
}

resolve_images() {
  if [ "${IMAGE_MAP}" != "{}" ]; then
    return 0
  fi
  if [ ! -f "${COMPOSE_FILE}" ]; then
    log "编排文件不存在，无法解析镜像名: ${COMPOSE_FILE}"
    return 1
  fi
  local raw
  raw=$(docker compose -f "${COMPOSE_FILE}" config --format json 2>/dev/null) || raw=""
  if [ -z "${raw}" ]; then
    log "docker compose config 无输出，无法解析镜像名"
    return 1
  fi

  PROJECT_NAME=$(printf '%s' "${raw}" | jq -r '.name // ""' 2>/dev/null || true)
  IMAGE_MAP=$(printf '%s' "${raw}" | jq -c '
    (.name // "") as $p
    | [ (.services // {}) | to_entries[]
        | select(.key == "backend" or .key == "frontend" or .key == "celery-worker")
        | { key: .key,
            value: (if (.value.image // "") != "" then .value.image
                    elif $p != "" then "\($p)-\(.key)"
                    else .key end) } ]
    | from_entries' 2>/dev/null) || IMAGE_MAP="{}"

  if [ "${IMAGE_MAP}" = "{}" ]; then
    log "镜像名解析为空，无法执行镜像标签操作"
    return 1
  fi
  log "镜像名解析完成：project=${PROJECT_NAME} images=${IMAGE_MAP}"
  return 0
}

image_of() {
  printf '%s' "${IMAGE_MAP}" | jq -r --arg svc "$1" '.[$svc] // ""' 2>/dev/null || true
}

running_image_of() {
  printf '%s' "${ROLLBACK_MAP}" | jq -r --arg svc "$1" '.[$svc] // ""' 2>/dev/null || true
}

capture_running_images() {
  local service cid image
  ROLLBACK_MAP="{}"
  for service in ${ROLLBACK_SERVICES}; do
    cid=$(container_of "${service}")
    [ -n "${cid}" ] || continue
    image=$(docker inspect --format '{{.Config.Image}}' "${cid}" 2>/dev/null || true)
    [ -n "${image}" ] || continue
    ROLLBACK_MAP=$(printf '%s' "${ROLLBACK_MAP}" \
      | jq -c --arg s "${service}" --arg i "${image}" '.[$s] = $i' 2>/dev/null) || ROLLBACK_MAP="{}"
  done
  log "运行中镜像快照：${ROLLBACK_MAP}"
}

tag_rollback_images() {
  local task_id="$1" service image source
  resolve_images || return 1
  capture_running_images
  for service in ${ROLLBACK_SERVICES}; do
    image=$(image_of "${service}")
    if [ -z "${image}" ]; then
      log "未解析到 ${service} 的镜像名"
      return 1
    fi
    source=$(running_image_of "${service}")
    [ -n "${source}" ] || source=$(image_ref "${image}")
    if ! docker tag "${source}" "$(image_base "${image}"):rollback" \
      >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
      log "打 :rollback 标签失败: ${service} 源=${source}"
      return 1
    fi
    log "${service} 回滚源已保留：${source}"
  done
  return 0
}

restore_rollback_images() {
  local task_id="$1" service image target declared
  resolve_images || return 1
  for service in ${ROLLBACK_SERVICES}; do
    image=$(image_of "${service}")
    if [ -z "${image}" ]; then
      log "未解析到 ${service} 的镜像名"
      return 1
    fi
    target=$(running_image_of "${service}")
    [ -n "${target}" ] || target=$(image_ref "${image}")
    if ! docker tag "$(image_base "${image}"):rollback" "${target}" \
      >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
      log "回切 ${service} 镜像失败，:rollback 标签可能不存在"
      return 1
    fi
    declared=$(image_ref "${image}")
    if [ "${target}" != "${declared}" ]; then
      docker tag "$(image_base "${image}"):rollback" "${declared}" \
        >>"${LOG_DIR}/${task_id}.stdout" 2>&1 || true
    fi
    log "${service} 已回切：${target} -> ${declared}"
  done
  return 0
}

wait_backend_health() {
  local timeout="${DEPLOY_HEALTH_TIMEOUT:-180}" waited=0 cid body
  cid=$(container_of backend)
  if [ -z "${cid}" ]; then
    log "未找到 backend 容器，健康检查失败"
    return 1
  fi
  while [ "${waited}" -lt "${timeout}" ]; do
    body=$(docker exec "${cid}" curl -fsS --max-time 5 http://localhost:8000/health/ready 2>/dev/null) || body=""
    if printf '%s' "${body}" | head -c 30 | grep -q '{"status":"ok"'; then
      return 0
    fi
    sleep 3
    waited=$((waited + 3))
  done
  return 1
}

assert_all_healthy() {
  local ps_json bad
  ps_json=$(compose ps --format json 2>/dev/null) || ps_json=""
  [ -n "${ps_json}" ] || return 0
  bad=$(printf '%s' "${ps_json}" | jq -s -r '
    [ (if length == 1 and (.[0] | type) == "array" then .[0] else . end)[]
      | select(((.State // "") | ascii_downcase) != "running"
               or ((.Health // "") | ascii_downcase) == "unhealthy")
      | .Service // "" ] | join(",")' 2>/dev/null) || bad=""
  if [ -n "${bad}" ]; then
    log "存在不健康或未运行的服务: ${bad}"
    return 1
  fi
  return 0
}

run_long() {
  local task_id="$1"
  shift
  "$@" >>"${LOG_DIR}/${task_id}.stdout" 2>&1 &
  local pid=$! rc=0
  while kill -0 "${pid}" 2>/dev/null; do
    sleep 3
    heartbeat
  done
  wait "${pid}" || rc=$?
  return "${rc}"
}

run_check() {
  local task_id="$1"
  emit "${task_id}" preflight running 10 "生产编排校验开始"
  update_task "${task_id}" '.step = "preflight" | .step_index = 1 | .pct = 10 | .status = "running"'
  if ! bash "${REPO_DIR}/scripts/preflight.sh" >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
    emit "${task_id}" preflight failed 10 "生产编排校验未通过"
    finish_task "${task_id}" failed "生产编排校验未通过"
    return 1
  fi
  emit "${task_id}" preflight success 25 "生产编排校验通过"
  update_task "${task_id}" '.pct = 25 | .step_index = 2 | .updated_at = (now | strftime("%Y-%m-%dT%H:%M:%SZ"))'

  emit "${task_id}" doctor running 60 "只读体检开始"
  update_task "${task_id}" '.step = "doctor" | .pct = 60'
  if ! bash "${REPO_DIR}/scripts/doctor.sh" --strict >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
    emit "${task_id}" doctor failed 90 "只读体检存在失败项"
    finish_task "${task_id}" failed "只读体检存在失败项，详见 stdout"
    return 1
  fi
  emit "${task_id}" doctor success 100 "只读体检通过"
  update_task "${task_id}" '.step = "doctor" | .step_index = 2 | .pct = 100'
  finish_task "${task_id}" success ""
  return 0
}

run_restart() {
  local task_id="$1" target
  target=$(task_field "${task_id}" '.target')

  case "${target}" in
    backend | frontend | celery-worker) ;;
    *)
      emit "${task_id}" restart failed 0 "不支持的目标服务: ${target}"
      finish_task "${task_id}" failed "不支持的目标服务"
      return 1
      ;;
  esac

  emit "${task_id}" restart running 50 "重启 ${target}"
  update_task "${task_id}" '.step = "restart" | .step_index = 1 | .pct = 50 | .status = "running"'
  if ! compose restart "${target}" >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
    emit "${task_id}" restart failed 50 "重启 ${target} 失败"
    finish_task "${task_id}" failed "重启 ${target} 失败"
    return 1
  fi
  emit "${task_id}" restart success 70 "${target} 已重启"

  emit "${task_id}" health running 85 "健康检查中"
  update_task "${task_id}" '.step = "health" | .step_index = 2 | .pct = 85'
  if [ "${target}" = "backend" ]; then
    if ! wait_backend_health; then
      emit "${task_id}" health failed 95 "/health/ready 未就绪"
      finish_task "${task_id}" failed "/health/ready 未就绪"
      return 1
    fi
  fi
  if ! assert_all_healthy; then
    emit "${task_id}" health failed 95 "存在不健康服务"
    finish_task "${task_id}" failed "存在不健康服务"
    return 1
  fi

  emit "${task_id}" health success 100 "/health/ready = ok"
  update_task "${task_id}" '.step = "health" | .step_index = 2 | .pct = 100'
  finish_task "${task_id}" success ""
  return 0
}

latest_backup_manifest() {
  local backups_dir="${REPO_DIR}/backups" latest
  [ -d "${backups_dir}" ] || return 1
  latest=$(find "${backups_dir}" -mindepth 2 -maxdepth 2 -name manifest.json -type f 2>/dev/null | sort | tail -n1)
  [ -n "${latest}" ] || return 1
  printf '%s' "${latest}"
}

run_deploy() {
  local task_id="$1" pull build_only backup_first manifest backup_status
  pull=$(task_field "${task_id}" '.params.pull')
  build_only=$(task_field "${task_id}" '.params.build_only')
  backup_first=$(task_field "${task_id}" '.params.backup_first')

  emit "${task_id}" preflight running 5 "生产编排校验开始"
  update_task "${task_id}" '.step = "preflight" | .step_index = 1 | .pct = 5 | .status = "running"'
  if ! bash "${REPO_DIR}/scripts/preflight.sh" >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
    emit "${task_id}" preflight failed 5 "生产编排校验未通过，部署中止"
    finish_task "${task_id}" failed "生产编排校验未通过，部署中止"
    return 1
  fi
  emit "${task_id}" preflight success 12 "生产编排校验通过"
  update_task "${task_id}" '.step_index = 1 | .pct = 12'

  if [ "${backup_first}" = "false" ] || [ "${backup_first}" = "0" ]; then
    emit "${task_id}" backup success 20 "按参数跳过备份"
  else
    emit "${task_id}" backup running 15 "备份开始"
    update_task "${task_id}" '.step = "backup" | .step_index = 2 | .pct = 15'
    if [ -n "$(container_of backup)" ]; then
      if ! run_long "${task_id}" compose exec -T backup /bin/sh /scripts/backup.sh; then
        emit "${task_id}" backup failed 16 "备份命令执行失败，部署中止"
        finish_task "${task_id}" failed "备份失败，部署中止"
        return 1
      fi
    else
      emit "${task_id}" backup running 16 "backup 容器未运行，改用一次性容器"
      if ! run_long "${task_id}" compose run --rm --no-deps -T backup /bin/sh /scripts/backup.sh; then
        emit "${task_id}" backup failed 16 "备份失败，部署中止"
        finish_task "${task_id}" failed "备份失败，部署中止"
        return 1
      fi
    fi
    manifest=$(latest_backup_manifest) || manifest=""
    if [ -z "${manifest}" ]; then
      emit "${task_id}" backup failed 18 "未找到备份清单 manifest.json，部署中止"
      finish_task "${task_id}" failed "未找到备份清单 manifest.json，部署中止"
      return 1
    fi
    backup_status=$(jq -r '.status // ""' "${manifest}" 2>/dev/null || true)
    if [ "${backup_status}" != "success" ]; then
      emit "${task_id}" backup failed 18 "备份清单状态为 ${backup_status:-空}，部署中止"
      finish_task "${task_id}" failed "备份清单状态非 success，部署中止"
      return 1
    fi
    emit "${task_id}" backup success 25 "备份完成 $(basename "$(dirname "${manifest}")")"
    update_task "${task_id}" '.step_index = 2 | .pct = 25'
  fi

  emit "${task_id}" tag_rollback running 30 "保留回滚镜像"
  update_task "${task_id}" '.step = "tag_rollback" | .step_index = 3 | .pct = 30'
  if ! tag_rollback_images "${task_id}"; then
    emit "${task_id}" tag_rollback failed 30 "保留回滚镜像失败，部署中止"
    finish_task "${task_id}" failed "保留回滚镜像失败，部署中止"
    return 1
  fi
  emit "${task_id}" tag_rollback success 35 ":rollback 标签已就绪"
  update_task "${task_id}" '.step_index = 3 | .pct = 35'

  emit "${task_id}" pull running 40 "拉取代码"
  update_task "${task_id}" '.step = "pull" | .step_index = 4 | .pct = 40'
  if [ "${pull}" = "false" ] || [ "${pull}" = "0" ] || [ ! -d "${REPO_DIR}/.git" ]; then
    emit "${task_id}" pull success 45 "跳过代码拉取"
  else
    if ! git -C "${REPO_DIR}" --no-pager pull --ff-only >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
      emit "${task_id}" pull failed 45 "代码拉取失败，部署中止"
      finish_task "${task_id}" failed "代码拉取失败，部署中止"
      return 1
    fi
    emit "${task_id}" pull success 45 "代码已更新"
  fi
  update_task "${task_id}" '.step_index = 4 | .pct = 45'

  emit "${task_id}" build running 50 "镜像构建中"
  update_task "${task_id}" '.step = "build" | .step_index = 5 | .pct = 50'
  if ! DOCKER_BUILDKIT=1 run_long "${task_id}" compose build ${BUILD_SERVICES}; then
    emit "${task_id}" build failed 50 "镜像构建失败，未替换现有镜像"
    finish_task "${task_id}" failed "镜像构建失败，未替换现有镜像"
    return 1
  fi
  emit "${task_id}" build success 70 "镜像构建完成"
  update_task "${task_id}" '.step_index = 5 | .pct = 70'

  if [ "${build_only}" = "true" ] || [ "${build_only}" = "1" ]; then
    emit "${task_id}" up success 100 "仅构建，跳过容器启动"
    finish_task "${task_id}" success ""
    return 0
  fi

  emit "${task_id}" up running 75 "启动容器"
  update_task "${task_id}" '.step = "up" | .step_index = 6 | .pct = 75'
  if ! compose up -d >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
    emit "${task_id}" up failed 75 "容器启动失败，自动回滚"
    if restore_rollback_images "${task_id}" \
      && compose up -d >>"${LOG_DIR}/${task_id}.stdout" 2>&1 \
      && wait_backend_health; then
      emit "${task_id}" up failed 100 "已回滚到 :rollback 镜像并恢复服务"
      finish_task "${task_id}" rolled_back "容器启动失败，已回滚" true
      return 1
    fi
    emit "${task_id}" up failed 100 "回滚失败，需人工介入"
    finish_task "${task_id}" failed "容器启动失败且回滚失败" false
    return 1
  fi
  emit "${task_id}" up success 85 "容器已启动"
  update_task "${task_id}" '.step_index = 6 | .pct = 85'

  emit "${task_id}" health running 90 "健康检查中"
  update_task "${task_id}" '.step = "health" | .step_index = 7 | .pct = 90'
  if ! wait_backend_health; then
    emit "${task_id}" health failed 90 "/health/ready 未就绪，自动回滚"
    if restore_rollback_images "${task_id}" \
      && compose up -d >>"${LOG_DIR}/${task_id}.stdout" 2>&1 \
      && wait_backend_health; then
      emit "${task_id}" health failed 100 "已回滚到 :rollback 镜像并恢复服务"
      finish_task "${task_id}" rolled_back "/health/ready 未就绪，已回滚" true
      return 1
    fi
    emit "${task_id}" health failed 100 "回滚失败，需人工介入"
    finish_task "${task_id}" failed "/health/ready 未就绪且回滚失败" false
    return 1
  fi
  if ! assert_all_healthy; then
    emit "${task_id}" health failed 92 "存在不健康服务，自动回滚"
    if restore_rollback_images "${task_id}" \
      && compose up -d >>"${LOG_DIR}/${task_id}.stdout" 2>&1 \
      && wait_backend_health; then
      emit "${task_id}" health failed 100 "已回滚到 :rollback 镜像并恢复服务"
      finish_task "${task_id}" rolled_back "存在不健康服务，已回滚" true
      return 1
    fi
    emit "${task_id}" health failed 100 "回滚失败，需人工介入"
    finish_task "${task_id}" failed "存在不健康服务且回滚失败" false
    return 1
  fi

  emit "${task_id}" health success 100 "/health/ready = ok"
  update_task "${task_id}" '.step_index = 7 | .pct = 100'
  finish_task "${task_id}" success ""
  return 0
}

run_rollback() {
  local task_id="$1"

  emit "${task_id}" tag_rollback running 30 "回切 :rollback 镜像"
  update_task "${task_id}" '.step = "tag_rollback" | .step_index = 1 | .pct = 30 | .status = "running"'
  if ! restore_rollback_images "${task_id}"; then
    emit "${task_id}" tag_rollback failed 30 "镜像回切失败，:rollback 标签可能不存在"
    finish_task "${task_id}" failed "镜像回切失败"
    return 1
  fi
  emit "${task_id}" tag_rollback success 50 "镜像已回切到 :rollback"
  update_task "${task_id}" '.step_index = 1 | .pct = 50'

  emit "${task_id}" up running 70 "重启 ${ROLLBACK_SERVICES}"
  update_task "${task_id}" '.step = "up" | .step_index = 2 | .pct = 70'
  if ! compose up -d ${ROLLBACK_SERVICES} >>"${LOG_DIR}/${task_id}.stdout" 2>&1; then
    emit "${task_id}" up failed 70 "容器启动失败"
    finish_task "${task_id}" failed "容器启动失败"
    return 1
  fi
  emit "${task_id}" up success 85 "容器已启动"
  update_task "${task_id}" '.step_index = 2 | .pct = 85'

  emit "${task_id}" health running 90 "健康检查中"
  update_task "${task_id}" '.step = "health" | .step_index = 3 | .pct = 90'
  if ! wait_backend_health; then
    emit "${task_id}" health failed 95 "/health/ready 未就绪"
    finish_task "${task_id}" failed "/health/ready 未就绪"
    return 1
  fi
  if ! assert_all_healthy; then
    emit "${task_id}" health failed 95 "存在不健康服务"
    finish_task "${task_id}" failed "存在不健康服务"
    return 1
  fi

  emit "${task_id}" health success 100 "/health/ready = ok"
  update_task "${task_id}" '.step_index = 3 | .pct = 100'
  finish_task "${task_id}" success ""
  return 0
}

execute_task() {
  local task_id="$1" action
  action=$(task_field "${task_id}" '.action')
  log "开始执行任务 ${task_id} action=${action}"

  case "${action}" in
    check) run_check "${task_id}" ;;
    deploy) run_deploy "${task_id}" ;;
    restart) run_restart "${task_id}" ;;
    rollback) run_rollback "${task_id}" ;;
    *)
      emit "${task_id}" dispatch failed 0 "不支持的动作为 ${action}"
      finish_task "${task_id}" failed "不支持的动作"
      ;;
  esac
}

recover_running() {
  local f task_id
  for f in "${QUEUE_DIR}/running"/*.json; do
    [ -f "$f" ] || continue
    task_id=$(basename "$f" .json)
    log "发现未完成任务，继续执行: ${task_id}"
    execute_task "${task_id}"
  done
}

process_tasks() {
  local f task_id
  recover_running

  for f in "${QUEUE_DIR}/queue"/*.json; do
    [ -f "$f" ] || continue
    task_id=$(basename "$f" .json)
    if ! mv "$f" "${QUEUE_DIR}/running/${task_id}.json" 2>/dev/null; then
      continue
    fi
    execute_task "${task_id}"
  done
}

main() {
  ensure_dirs
  log "执行器启动：queue=${QUEUE_DIR} compose=${COMPOSE_FILE} snapshot=${SNAPSHOT_INTERVAL}s"
  prune_old

  local last_snapshot=0 now elapsed
  while true; do
    heartbeat

    now=$(date +%s)
    elapsed=$((now - last_snapshot))
    if [ "${elapsed}" -ge "${SNAPSHOT_INTERVAL}" ]; then
      write_snapshot
      write_meta
      heartbeat
      last_snapshot=${now}
    fi

    process_tasks

    sleep "${POLL_INTERVAL}"
  done
}

main