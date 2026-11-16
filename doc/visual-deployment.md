# 可视化部署控制台 开发文档

## 1. 文档定位

本文是「方案 C：项目内置部署控制台」的开发设计文档，供实现、评审与后续维护使用。

- 面向对象：参与本功能开发的后端 / 前端开发者。
- 前置阅读：根目录 `AGENTS.md`（导航与硬规则）、`backend/AGENTS.md`（分层约定）、`doc/deployment.md`（现有部署流程）。
- 与现有文档的关系：本文只描述新增的部署控制台，不重复部署、备份、配置等内容，相关细节引用既有文档。

## 2. 背景与目标

当前生产发布依赖手工执行：

```bash
git pull origin main
docker compose -f docker-compose.yml up -d --build
```

现有资产已把这条链路的大部分环节脚本化：`scripts/install.sh`、`scripts/upgrade.sh`、`scripts/doctor.sh`、`scripts/backup.sh`、`scripts/restore.sh`，`Makefile` 也提供了 `preflight-prod` 编排校验。问题不在「缺少命令」，而在：

| 问题 | 现状 | 目标 |
| --- | --- | --- |
| 状态不可见 | 需要 SSH 后执行 `docker compose ps` / 查日志 | 管理员在 `/admin` 直接看到每个服务状态与健康 |
| 顺序靠记忆 | 先备份、再构建、再验活，全靠人记 | 由控制台强制固定顺序，缺一步不往下走 |
| 失败无回滚 | 部署失败需人工 `git checkout` + 重建（分钟级） | 自动回滚到本地 `:rollback` 镜像（秒级） |
| 无操作记录 | 谁在何时发了哪个版本无从追溯 | 每次动作落结构化日志 + 最近历史 |

**非目标**：不做编排能力（不生成 / 修改 compose 文件）、不做多主机与 Kubernetes 调度、不对外网开放。

## 3. 范围边界

| 做 | 不做 |
| --- | --- |
| 容器与服务状态可视化、版本确认 | 替代 Docker Compose 的编排能力 |
| 白名单动作：`check` / `deploy` / `restart` / `rollback` | 任意 shell 执行、任意 compose 子命令 |
| 复用 `preflight.sh`、`upgrade.sh`、`restore.sh` 的语义 | 重写新的部署流水线 |
| 单实例（本机 Docker Compose）场景 | 多主机集群、Kubernetes |
| 管理员内网使用 | 公网暴露、多租户 |

## 4. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│ 展示层  /admin/deploy  (Next.js)                            │
│   状态卡 · 容器表 · 动作栏 · 步骤时间线 · 日志窗             │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP（管理员 JWT + CSRF）
┌───────────────────────▼─────────────────────────────────────┐
│ 控制层  backend (FastAPI)                                    │
│   endpoints/deploy.py → services/deploy_service.py           │
│                       → services/deploy_protocol.py          │
│   动作校验 · 并发锁 · 确认令牌 · 进度聚合 · 历史              │
└───────────────────────┬─────────────────────────────────────┘
                        │ 只读写共享卷 /deploy（文件协议）
┌───────────────────────▼─────────────────────────────────────┐
│ 执行层  deploy-runner（独立容器，独立 compose 文件）          │
│   认领任务 · 白名单动作 · 快照循环 · 心跳 · 调 docker compose │
└───────────────────────┬─────────────────────────────────────┘
                        │ /var/run/docker.sock（仅此容器持有）
                      Docker Engine / Compose
```

### 4.1 关键决策：backend 不持有 docker.sock

backend 是对外提供 HTTP 的服务，一旦挂载 `/var/run/docker.sock`，任何后端漏洞都等价于宿主机 root。因此控制权外移到独立的 `deploy-runner` 容器：

- backend 只会**写 JSON 文件、读 JSON / JSONL 文件**，被攻破也拿不到容器控制权。
- socket 只挂在 runner 一个容器上；runner 不接业务网络、不映射端口、只执行固定动作。
- 该模式与项目既有做法一致：`backend/app/tasks/backup_tasks.py` 的「触发文件 + 监听者」（`scripts/backup-trigger-watcher.sh` 监听 `/backups/.trigger_*`），`.env.example` 中「已废弃 docker exec，改用共享卷触发文件，无需 Docker socket」的说明。控制台沿用同一范式，避免引入第二套跨容器通信机制。

### 4.2 为什么不用 Celery 承载部署任务

Celery worker 与 backend 共用同一镜像、同一网络、同一套配置，且其职责是「用户可触发的轻量异步任务」。部署会重启 backend 与 celery-worker 自身，任务执行者被自己杀掉属于设计缺陷。部署动作必须由**不参与被部署对象**的容器执行。

## 5. 共享卷协议

### 5.1 目录结构

```
/deploy/
├── queue/<task_id>.json        # backend 写入待执行任务（原子写）
├── running/<task_id>.json      # runner 认领（rename 即原子抢占）
├── results/<task_id>.json      # 终态结果
├── logs/<task_id>.jsonl        # 进度流，逐行追加
├── snapshot/
│   ├── containers.json         # 容器快照，15s 刷新
│   └── meta.json               # 版本、compose hash、采集时间
└── heartbeat                   # runner 存活心跳（mtime）
```

### 5.2 任务文件

```json
{
  "task_id": "8f2c1e4a-...",
  "action": "deploy",
  "target": null,
  "params": { "backup_first": true, "pull": true },
  "requested_by": "管理员 user_id",
  "requested_at": "2026-11-16T09:12:00Z"
}
```

约束：

- `task_id` 由 backend 生成，必须是 UUID4 字符串，写入前用正则 `^[0-9a-f-]{36}$` 校验。
- 写入方式为「写 `.tmp` → `os.replace`」，避免 runner 读到半写文件。
- `action` 必须是枚举值，`target` 只允许 `null` 或固定服务名，`params` 只允许白名单键。

### 5.3 进度流

`logs/<task_id>.jsonl` 一行一个事件：

```json
{"ts":"2026-11-16T09:12:05Z","step":"preflight","status":"running","pct":10,"msg":"生产编排校验通过"}
{"ts":"2026-11-16T09:12:31Z","step":"backup","status":"success","pct":25,"msg":"备份完成 20261116_091205"}
{"ts":"2026-11-16T09:13:40Z","step":"build","status":"running","pct":55,"msg":"镜像构建中"}
{"ts":"2026-11-16T09:14:02Z","step":"health","status":"success","pct":100,"msg":"/health/ready = ok"}
```

使用 JSONL 而非整份 JSON 的原因：

- backend 只需记录已读 offset 做增量解析，不必每次反序列化全部日志。
- runner 崩溃时已写入的进度不丢，可直接呈现「卡在哪一步」。
- 追加写本身是原子的（单行 < 4KB），无需额外锁。

### 5.4 结果文件

```json
{
  "task_id": "8f2c1e4a-...",
  "action": "deploy",
  "status": "success",
  "step": "health",
  "error": null,
  "started_at": "2026-11-16T09:12:03Z",
  "finished_at": "2026-11-16T09:14:02Z",
  "rolled_back": false
}
```

`status` 取值：`success` / `failed` / `rolled_back`。

### 5.5 快照文件

`snapshot/containers.json` 由 runner 每 15s 覆写，backend 只读：

```json
{
  "collected_at": "2026-11-16T09:14:15Z",
  "compose_project": "jindou-cloud",
  "services": [
    {
      "service": "backend",
      "container": "cloud-drive-backend",
      "state": "running",
      "health": "healthy",
      "image": "jindou-cloud-backend:latest",
      "created": "2026-11-16T09:13:55Z",
      "restart_count": 0,
      "ports": ["127.0.0.1:8000->8000/tcp"]
    }
  ]
}
```

`snapshot/meta.json` 记录 `app_version`、`compose_hash`、`git_commit`（可选，仓库目录可用时采集）。

### 5.6 心跳与僵尸任务

- runner 每个循环、每个步骤开始与结束时刷新 `/deploy/heartbeat` 的 mtime。
- backend 判定规则：`now - heartbeat_mtime > DEPLOY_HEARTBEAT_TIMEOUT`（默认 30s）视为执行器离线；此时页面对所有进行中任务显示「执行器无响应」。
- 任务硬超时 `DEPLOY_TASK_TIMEOUT`（默认 1800s）：runner 超时后写 `results` 为 `failed` 并清理 `running/`；backend 对超时未终态的任务标记 `stalled`，并允许管理员强制释放锁。
- 清理：`queue/`、`running/`、`logs/`、`results/` 中超过 7 天的任务文件由 runner 启动时清理一次。

## 6. 执行层：deploy-runner

### 6.1 动作白名单

仅四个动作，代码路径固定，不接受自由命令：

| action | 实现 | 风险 | 说明 |
| --- | --- | --- | --- |
| `check` | `scripts/preflight.sh` + `scripts/doctor.sh` | 只读 | 零风险，前端可直接触发 |
| `deploy` | 按 6.3 的步骤顺序执行 | 高 | 需确认令牌 |
| `restart` | `docker compose restart <service>` | 中 | `target` 硬匹配枚举 |
| `rollback` | 镜像标签回切 + `up -d`（可选 restore） | 高 | 需确认令牌 |

`target` 处理方式：

```bash
case "$target" in
  backend|frontend|celery-worker) ;;
  *) fail "不支持的目标服务: $target" ;;
esac
```

### 6.2 认领与执行流程

```
loop:
  1. 若 running/ 有未完成文件 → 继续（崩溃恢复）
  2. 否则扫描 queue/ 取最早任务
  3. mv queue/<id>.json running/<id>.json（rename 原子抢占，失败说明已被抢）
  4. 按 action 分派执行，每步追加 logs/<id>.jsonl 并刷新 heartbeat
  5. 写 results/<id>.json，删除 running/<id>.json
  6. sleep DEPLOY_POLL_INTERVAL（默认 2s）
```

串行执行是刻意设计：并发部署会互相覆盖镜像标签与容器状态，没有收益。

### 6.3 deploy 步骤序列

| # | step | 内容 | 失败处理 |
| --- | --- | --- | --- |
| 1 | `preflight` | 调用 `scripts/preflight.sh`（生产编排校验） | 直接失败，不动现状 |
| 2 | `backup` | 同步执行 `docker compose exec -T backup /bin/sh /scripts/backup.sh`（backup 容器未运行时改用 `run --rm --no-deps`），再校验最新备份目录 `manifest.json` 的 `status` 为 `success` | 失败则中止 |
| 3 | `tag_rollback` | 给 backend / frontend 当前镜像打 `:rollback` | 失败则中止 |
| 4 | `pull` | `git --no-pager pull --ff-only`（`params.pull=false` 或非 git 仓库时跳过） | 失败则中止 |
| 5 | `build` | `DOCKER_BUILDKIT=1 docker compose build backend celery-worker frontend` | 失败则中止（镜像未替换） |
| 6 | `up` | `docker compose up -d`（**不带 `--remove-orphans`**） | 失败则自动回滚 |
| 7 | `health` | `docker exec cloud-drive-backend curl -fsS http://localhost:8000/health/ready` 直到 `{"status":"ok"`，再用 `docker compose ps` 确认无 `unhealthy` 且无退出态服务 | 失败则自动回滚 |

两个细节：

- **健康检查必须在容器内执行**。runner 是独立容器，其中的 `127.0.0.1` 指向 runner 自身，而非宿主机。宿主机上的 `127.0.0.1:8000` 对 runner 不可达，除非额外加 `extra_hosts: host.docker.internal:host-gateway`；用 `docker exec` 进 backend 容器探活更简单也更贴近真实。
- **不能带 `--remove-orphans`**。`deploy-runner` 定义在 `docker-compose.ops.yml`，若用主文件单独执行 `up -d --remove-orphans`，compose 会把同项目下未在主文件声明的 `deploy-runner` 当作孤儿容器删除——部署过程中执行者把自己杀掉。`scripts/upgrade.sh` 里可以用这个参数（它跑在宿主机），控制台里不行。

`check` 与 `restart` 使用更短的步骤序列：

- `check`：`preflight` → `doctor`（`scripts/doctor.sh --strict`）。
- `restart`：`restart`（`docker compose restart <target>`）→ `health`。

**迁移不单列为步骤**：`docker-compose.yml` 中 backend 的启动命令已是 `alembic upgrade head && exec gunicorn ...`，容器启动即完成迁移。控制台不引入第二条迁移路径——两条路径意味着两套失败语义、两套锁与两套回滚策略。回滚数据用 `scripts/restore.sh`，与迁移回退解耦。

### 6.4 镜像保留与秒级回滚

现状只有 `latest`，回滚需重新 build。`deploy` 第 3 步打本地标签：

```bash
docker tag jindou-cloud-backend:latest  jindou-cloud-backend:rollback
docker tag jindou-cloud-frontend:latest jindou-cloud-frontend:rollback
```

镜像名以实际 `docker compose config` 输出为准（compose 默认按「项目名_服务名」生成，未显式设置 `image:` 时不要硬编码），runner 应在启动时解析一次并缓存。

回滚执行：

```bash
docker tag jindou-cloud-backend:rollback       jindou-cloud-backend:latest
docker tag jindou-cloud-frontend:rollback      jindou-cloud-frontend:latest
docker tag jindou-cloud-celery-worker:rollback jindou-cloud-celery-worker:latest
docker compose up -d backend frontend celery-worker
```

回滚范围必须与 `build` 范围一致（`backend` / `frontend` / `celery-worker`）：`celery-worker` 使用独立镜像 `backend/Dockerfile.celery`，若只回切 `backend` 与 `frontend`，回滚后会留下「旧 backend + 新 worker」的混合状态，异步任务仍按新代码执行。

不依赖 registry、不依赖 git，秒级完成。语义与 `scripts/upgrade.sh` 的 `on_error` 回滚分支保持一致。

数据回滚是**独立可选项**：`rollback` 动作只回切镜像；需要同时回退数据时，由管理员在终端执行 `docker compose exec backup /bin/sh /scripts/restore.sh <timestamp>`。原因：`restore.sh` 是交互式确认的破坏性操作，不适合由 HTTP 请求直接触发。

### 6.5 快照循环

```bash
docker compose -f "$COMPOSE_FILE" ps --format json > snapshot/containers.json.tmp
mv snapshot/containers.json.tmp snapshot/containers.json
```

`health` 字段优先取 `ps` 输出；缺失时对已知容器名补一次 `docker inspect --format '{{.State.Health.Status}}'`。这样 P1（只读阶段）无需暴露任何写接口即可渲染完整容器表。

### 6.6 镜像与编排文件

`scripts/Dockerfile.deploy`：

- 基础镜像 `docker:cli`（自带 compose v2 插件）。
- 追加 `bash`、`curl`、`jq`、`coreutils`。
- 不装 Python / Node，镜像保持轻量。

`docker-compose.ops.yml`（**独立文件，不并入 `docker-compose.yml`**）：

```yaml
services:
  deploy-runner:
    build:
      context: ./scripts
      dockerfile: Dockerfile.deploy
    container_name: cloud-drive-deploy-runner
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ${DEPLOY_REPO_PATH}:${DEPLOY_REPO_PATH}
      - deploy_queue:/deploy
    environment:
      - DEPLOY_REPO_PATH=${DEPLOY_REPO_PATH}
      - DEPLOY_QUEUE_DIR=/deploy
      - COMPOSE_FILE=${DEPLOY_REPO_PATH}/docker-compose.yml
      - DEPLOY_POLL_INTERVAL=${DEPLOY_POLL_INTERVAL:-2}
      - DEPLOY_SNAPSHOT_INTERVAL=${DEPLOY_SNAPSHOT_INTERVAL:-15}
    working_dir: ${DEPLOY_REPO_PATH}

volumes:
  deploy_queue:
```

两个必须写对的细节：

1. **仓库必须同路径挂载**（`${DEPLOY_REPO_PATH}:${DEPLOY_REPO_PATH}`）。若写成 `- .:/repo`，runner 内执行 `docker compose up -d` 时 compose 会把 `./backups` 等相对路径解析到宿主机 `/repo/backups`（不存在），容器直接起不来。
2. **必须独立 compose 文件**。`Makefile` 的 `preflight-prod` 对 `docker compose config` 输出做 grep 校验（检查 `ENVIRONMENT=production`、无 `npm run dev`、无 `--reload`、无源码 bind mount），多出的 ops 服务会污染校验语义；且并入主文件后 `docker compose up -d` 可能把 runner 一并纳入。

启动方式：

```bash
docker compose -f docker-compose.yml -f docker-compose.ops.yml up -d deploy-runner
```

backend 只需在 `docker-compose.yml` 中挂载同一 `deploy_queue` 卷到 `/deploy`，两者不需要网络互连。

## 7. 控制层：backend

### 7.1 新增配置项

在 `app/core/config.py` 的 `Settings` 中追加：

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DEPLOY_ENABLED` | bool | `False` | 总开关，关闭时所有接口返回 403 |
| `DEPLOY_QUEUE_DIR` | str | `/deploy` | 共享卷挂载点 |
| `DEPLOY_TASK_TIMEOUT` | int | `1800` | 单任务硬超时（秒） |
| `DEPLOY_HEARTBEAT_TIMEOUT` | int | `30` | 执行器离线判定阈值（秒） |
| `DEPLOY_MAX_LOG_LINES` | int | `500` | 接口返回的日志行数上限 |
| `DEPLOY_ALLOWED_ACTIONS` | str | `check,deploy,restart,rollback` | 允许的动作，逗号分隔 |
| `DEPLOY_REQUIRE_BACKUP` | bool | `True` | deploy 是否强制先备份 |

**四处同步**（本项目已记录过的坑，缺一处会静默回落默认值）：

1. `backend/app/core/config.py`
2. `.env.example`
3. `docker-compose.yml` 的 backend / celery-worker `environment` 段
4. 文档：`doc/configuration.md` 与本文第 11 节

### 7.2 模块拆分

| 文件 | 职责 | 依赖 |
| --- | --- | --- |
| `app/schemas/deploy.py` | 请求 / 响应模型 | 无 |
| `app/services/deploy_protocol.py` | 卷目录读写：原子写、认领状态、JSONL 增量解析、快照解析、路径校验 | 仅标准库 + `settings` |
| `app/services/deploy_service.py` | 业务编排：动作校验、Redis 锁、确认令牌、状态聚合、历史裁剪 | protocol + Redis + loguru |
| `app/api/v1/endpoints/deploy.py` | 路由层，只做参数解析与调用 service | service + deps |
| `app/api/v1/api.py` | 注册 `prefix="/admin/deploy"` | — |

`deploy_protocol.py` 单独拆出的理由：它是纯文件层，不依赖 Redis / Docker，可完全用临时目录做单元测试，坏 JSON、缺字段、路径穿越都在这一层被测死。分层方向遵循 `backend/AGENTS.md`：`endpoints → services → models/schemas/core`，endpoints 不写业务逻辑。

路由注册位置参照现有 `api.py`（`admin`、`backups`、`tasks` 均在 `/admin` 下），新增一行：

```python
api_router.include_router(deploy.router, prefix="/admin/deploy", tags=["deploy"])
```

### 7.3 状态机

```
idle ──POST action──▶ queued ──runner 认领──▶ running ──▶ success
                          │                     │
                          │                     ├──▶ failed ──(自动)──▶ rolled_back
                          └──(超时未认领)──▶ stalled
```

状态由「文件系统 + Redis」共同推导，不存进程内存：

- 任务态：`queue/`、`running/`、`results/` 文件是否存在。
- 锁：`deploy:lock`（Redis）。
- 历史：`deploy:history`（Redis list）。

backend 是多 worker（`BACKEND_WORKERS` 默认 4），进程内状态在 worker 之间不可见，且部署过程中 backend 会重启，因此任何状态都不能放内存。

### 7.4 API 契约

前缀 `/api/v1/admin/deploy`，全部依赖 `get_current_admin`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/status` | 开关状态、是否运行中、当前任务、上次结果、允许动作 |
| GET | `/containers` | 读快照，附带执行器心跳新鲜度 |
| GET | `/versions` | `APP_VERSION`、镜像 tag、compose hash、git commit |
| POST | `/actions` | 提交动作，返回 `{task_id}`；危险动作需 `confirm_token` |
| POST | `/confirm` | 为危险动作签发 60s 确认令牌（请求体含 `action` 与 `target`） |
| GET | `/tasks/{task_id}` | 任务详情 + 最近 N 行日志 |
| GET | `/history` | 最近 20 条记录 |

`GET /status` 响应：

```json
{
  "enabled": true,
  "runner_online": true,
  "running_task_id": "8f2c1e4a-...",
  "allowed_actions": ["check", "deploy", "restart"],
  "last_result": { "task_id": "...", "action": "deploy", "status": "success", "finished_at": "..." }
}
```

`POST /actions` 请求：

```json
{ "action": "restart", "target": "backend", "params": {}, "confirm_token": null }
```

`GET /tasks/{task_id}` 响应：

```json
{
  "task_id": "8f2c1e4a-...",
  "action": "deploy",
  "status": "running",
  "step": "build",
  "step_index": 5,
  "total_steps": 7,
  "pct": 55,
  "started_at": "2026-11-16T09:12:03Z",
  "updated_at": "2026-11-16T09:12:41Z",
  "finished_at": null,
  "logs": ["[preflight] 生产编排校验通过", "[backup] 备份完成 20261116_091205", "..."],
  "error": null
}
```

### 7.5 并发、幂等与确认令牌

**① 全局互斥锁**

```python
await redis_client.set("deploy:lock", task_id, nx=True, ex=settings.DEPLOY_TASK_TIMEOUT)
```

- 拿不到锁返回 `409`，响应体带当前 `running_task_id`，前端据此跳转到进度页。
- 锁放 Redis 而非进程内存：多 worker + 部署中途重启，内存态必然失效。

**② 确认令牌**

危险动作（`deploy` / `rollback`）两步走：

1. `POST /confirm`（请求体含 `action` 与 `target`）由服务端生成 `secrets.token_urlsafe(24)`，Redis 存 `deploy:confirm:{token} = {action,target,user_id}`，TTL 60s。
2. `POST /actions` 必须带该 token，服务端校验 `action` / `target` 与令牌记录一致后**立即删除**（一次性）。

相比「布尔 confirm 字段」：不可重放、与用户绑定、60 秒自动失效。前端弹窗可再要求输入动作名做二次确认。

令牌在动作提交前签发，此时尚无 `task_id`，所以 `confirm` 接口不接受路径参数，只接受动作描述。

**③ 幂等**

同一 `action` 在锁持有期内重复提交，直接返回既有 `task_id`（HTTP 200），不报错、不重复排队。避免管理员连点触发多次构建。

### 7.6 审计

P1~P3 阶段不建表，先落日志 + 结果文件：

- 每次动作写 `logger.bind(log_type="deploy")`，字段含 `task_id / action / target / admin_id / result / duration_ms / params`。
- `deploy` 提交时 `params` 自动补默认值：`backup_first`（取 `DEPLOY_REQUIRE_BACKUP`）、`pull=true`；键白名单仅 `backup_first` / `pull` / `build_only`，值必须为布尔，其余键或非布尔值返回 400。
- 历史列表不另设 Redis `deploy:history`：`/deploy/results` 目录下每个任务的结果文件已是持久化记录，`recent_results(limit)` 按 mtime 倒序读取并回填 `rolled_back`，与任务结果同源，避免两处状态不一致。
- 自动回滚的任务结果记为 `status=rolled_back`、`rolled_back=true`，`error` 保留触发回滚的原因；前端历史列表在该行追加「已回滚」标记。

需要长期审计与查询时（P4）再加 `deploy_records` 表：新增模型文件 + 新增 Alembic 迁移，**不修改历史迁移**。动作频率为月级，提前建表只增加迁移负担。

### 7.7 错误码映射

| 场景 | HTTP | 响应 |
| --- | --- | --- |
| `DEPLOY_ENABLED=false` | 403 | `{"detail": "部署控制台未启用", "code": "deploy_disabled"}` |
| 非管理员 | 403 | 沿用 `get_current_admin` 现有语义 |
| 非法 action / target | 400 | `{"code": "deploy_invalid_action"}` |
| 已有任务运行中 | 409 | `{"code": "deploy_busy", "running_task_id": "..."}` |
| 确认令牌缺失 / 过期 / 不匹配 | 403 | `{"code": "deploy_confirm_required"}` |
| 任务不存在 | 404 | `{"code": "deploy_task_not_found"}` |
| 执行器离线 | 200 | 正常返回，`runner_online=false`，不报错 |

## 8. 展示层：frontend

### 8.1 文件清单

| 文件 | 说明 |
| --- | --- |
| `frontend/lib/api/deploy.ts` | 类型与请求封装，统一走 `client()`（自动带 JWT 与 CSRF） |
| `frontend/lib/query/keys.ts` | 在 `queryKeys.admin` 下新增 `deploy` 分组 |
| `frontend/app/admin/deploy/page.tsx` | 页面骨架 |
| `frontend/app/admin/deploy/page.module.css` | 样式，沿用现有 CSS Modules 约定 |
| `frontend/app/admin/hooks/useAdminDeploy.ts` | 查询 + 动作提交 + 任务轮询 |
| `frontend/app/admin/components/DeployStatusCard.tsx` | 开关状态、版本、执行器在线状态 |
| `frontend/app/admin/components/ContainerTable.tsx` | 服务、状态、健康、镜像、重启次数、端口 |
| `frontend/app/admin/components/DeployTimeline.tsx` | 步骤时间线与 pct |
| `frontend/app/admin/components/LogViewer.tsx` | 等宽日志窗，自动滚底，最多 500 行 |
| `frontend/app/admin/layout.tsx` | `navItems` 增加一项 |
| `frontend/lib/i18n/locales/{zh-CN,zh-TW,en}.ts` | 三套文案同批补齐 |

每个新组件按现有约定配套同名 `.module.css`（`BackupTable.tsx` / `BackupTable.module.css` 即此模式）。

复用现有组件，不新造 UI 原语：`PageHeader`（`title` / `subtitle` / `extra`）、`StatCard`、`ErrorBar`、`Modal`（危险动作确认弹窗直接用 `Modal`，其已支持 `saving`、`confirmText` 与 `Esc` 关闭）。hook 层沿用 `useAdminBackups` 的写法：`useState` 存 `error`、`useMutation` 的 `onError` 统一转成中文提示。

### 8.2 页面信息架构

```
PageHeader（标题 + 副标题）
├── DeployStatusCard     开关 / 执行器在线 / 当前版本 / 上次结果
├── 动作栏                [预检] [重启服务 ▾] [部署] [回滚]
├── DeployTimeline       仅在 running 时出现
├── LogViewer            仅在 running 或查看最近任务时出现
├── ContainerTable       容器状态表
└── 版本区               APP_VERSION / 镜像 tag / compose hash / git commit
```

### 8.3 轮询策略

nginx 对 `/api/` 的限流为 `rate=60r/m burst=20`（`limit_req_zone ... zone=api_limit`），后端 `RATE_LIMIT_PER_MINUTE` 默认同为 60。**1 秒轮询会打满阈值**，页面开两分钟即被限流。策略：

| 查询 | 间隔 | 条件 |
| --- | --- | --- |
| `status` | 5s | 页面可见时 |
| `containers` | 15s | 与快照刷新周期对齐 |
| `task(id)` | 2s | 仅当 `status === "running"` |
| 任务终态 | 停止 | 命中 `success` / `failed` / `rolled_back` 立即停 |

实现方式：

```ts
refetchInterval: (query) => (query.state.data?.status === "running" ? 2000 : false)
```

**进度以轮询为唯一真相源**，不依赖 WebSocket：现有 `useWebSocket` 只在 `dashboard/layout.tsx` 挂载，admin 页无 WS 实例；且其重连上限为 5 次，可能正好撞上重启窗口。WS 推送仅作为 P4 的增强项（复用 `ws_manager.send_to_user`）。

### 8.4 动作按钮禁用矩阵

| 条件 | 效果 |
| --- | --- |
| `enabled=false` | 全部置灰，提示「控制台未启用」 |
| 已有任务 running | 全部置灰，提供「查看当前进度」 |
| `check` | 恒可用（除开关关闭） |
| `deploy` / `rollback` | 弹 `Modal` 确认 + 输入动作名 |
| `restart` | 选择目标服务（下拉，非输入框） |
| `runner_online=false` | 全部置灰，提示「执行器离线」 |

### 8.5 重启期间的降级

部署会重启 backend，页面请求会短时返回 502：

- 捕获后显示「服务重启中，正在等待恢复」，不显示红色报错。
- 后台继续按 5s 轮询，恢复后自动回到正常态。
- 轮询在页面不可见时（`document.hidden`）暂停，回到可见时立即刷新一次。

### 8.6 i18n 键清单

`lib/i18n/index.ts` 中 `TranslationKey = keyof typeof zhCN`，新增键必须三份 locale 同批补齐，否则类型报错或回退为键名。现有 `admin.nav.*` 键位于 `zh-CN.ts` 第 66-69 行附近，新增键紧随其后。

| 键 | zh-CN |
| --- | --- |
| `admin.nav.deploy` | 部署管理 |
| `admin.deploy.title` | 部署管理 |
| `admin.deploy.subtitle` | 查看服务状态并执行部署动作 |
| `admin.deploy.disabled` | 部署控制台未启用 |
| `admin.deploy.runner.online` | 执行器在线 |
| `admin.deploy.runner.offline` | 执行器离线 |
| `admin.deploy.action.check` | 预检 |
| `admin.deploy.action.deploy` | 部署 |
| `admin.deploy.action.restart` | 重启服务 |
| `admin.deploy.action.rollback` | 回滚 |
| `admin.deploy.confirm.deploy` | 确认执行部署？将重建镜像并重启服务 |
| `admin.deploy.confirm.rollback` | 确认回滚到上一版本？ |
| `admin.deploy.confirm.inputHint` | 输入 {action} 以确认 |
| `admin.deploy.busy` | 已有任务执行中 |
| `admin.deploy.stalled` | 执行器无响应，任务可能已中断 |
| `admin.deploy.restarting` | 服务重启中，正在等待恢复 |
| `admin.deploy.step.preflight` | 编排校验 |
| `admin.deploy.step.backup` | 备份 |
| `admin.deploy.step.tag_rollback` | 保留回滚镜像 |
| `admin.deploy.step.pull` | 拉取代码 |
| `admin.deploy.step.build` | 构建镜像 |
| `admin.deploy.step.up` | 启动容器 |
| `admin.deploy.step.health` | 健康校验 |
| `admin.deploy.col.service` | 服务 |
| `admin.deploy.col.state` | 状态 |
| `admin.deploy.col.health` | 健康 |
| `admin.deploy.col.image` | 镜像 |
| `admin.deploy.col.restarts` | 重启次数 |
| `admin.deploy.col.ports` | 端口 |
| `admin.deploy.history.title` | 最近操作 |
| `admin.deploy.history.empty` | 暂无操作记录 |

## 9. 安全设计

| 层 | 措施 |
| --- | --- |
| 网络 | runner 不接业务网络、不映射端口；`DEPLOY_ENABLED` 默认 `false`；页面仅在 `/admin` 下 |
| 鉴权 | 全部路由依赖 `get_current_admin`；POST 走现有 CSRF 中间件 |
| 动作 | 枚举白名单 + `target` 硬匹配 + 危险动作一次性确认令牌 + 全局互斥锁 |
| 文件 | `task_id` 正则校验；路径由 `Path(root) / task_id` 构造后 `resolve()` 校验仍在根内（防穿越）；写入用 `.tmp` + `os.replace` |
| 日志 | 不打印 `.env` 内容、镜像凭据、令牌；错误信息脱敏后返回 |

**残余风险**：`docker.sock` 在 runner 内等价宿主机 root。缓解方式是「单用途容器 + 无网络 + 无端口 + 固定代码路径」，相较把 socket 交给 backend 低两个数量级。若需进一步收紧，可改用 `tecnativa/docker-socket-proxy` 只放行 `CONTAINERS` / `IMAGES`，但会失去执行 compose 与脚本的能力，需权衡。

## 10. 测试计划

### 10.1 后端

| 文件 | 覆盖点 |
| --- | --- |
| `tests/test_service_deploy_protocol.py` | 原子写、JSONL 坏行容错、缺字段降级、`task_id` 路径穿越拒绝、快照解析 |
| `tests/test_service_deploy.py` | 动作白名单、锁竞争、确认令牌过期与重放、超时判定 `stalled`、历史裁剪 |
| `tests/test_api_deploy.py` | `DEPLOY_ENABLED=false` → 403；非管理员 → 403；运行中重复提交 → 200 同 `task_id`；非法 action → 400；缺确认令牌 → 403 |

测试约定（见 `.trae/rules/project_rules.md`）：

- 断言必须用 `assert`，禁止 `return` 断言结果。
- 禁止 `except Exception: pass` 包裹模块导入。
- 需要真实 `Settings` 时补齐 `SECRET_KEY`（≥32 字符）、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`。
- `deploy_protocol` 测试用 `tmp_path` 构造临时队列目录，不依赖 Redis 与 Docker。

### 10.2 前端

现有测试目录结构为 `frontend/tests/{components,hooks,lib,stores,utils}`，新增文件按此归类：

| 文件 | 覆盖点 |
| --- | --- |
| `tests/hooks/useAdminDeploy.test.tsx` | 空闲不轮询、running 时 2s 轮询、终态停止、502 进入「重启中」态、开关关闭时禁用 |
| `tests/components/DeployTimeline.test.tsx` | 步骤高亮、pct 渲染、步骤文案映射 |
| `tests/lib/deployApi.test.ts` | 请求路径与 payload、错误码到提示文案的映射 |

### 10.3 手工验收

| 阶段 | 验收动作 |
| --- | --- |
| P0 | 页面数据与 `curl /health/ready` 一致；`DEPLOY_ENABLED=false` 时只读接口返回 403 |
| P1 | 停掉 runner 后页面显示「执行器离线」；容器重启次数与 `docker compose ps` 一致 |
| P2 | 连点三次 `restart` 只产生一个任务；非管理员访问 403；无 CSRF 头 403；连续刷新 2 分钟不触发限流 |
| P3 | 人为让健康检查失败，验证自动回滚到 `:rollback` 镜像并恢复服务；备份失败时部署中止且现状不变 |

## 11. 配置与环境变量总表

需同时写入 `.env.example` 与 `docker-compose.yml`：

| 变量 | 默认 | 写入位置 | 说明 |
| --- | --- | --- | --- |
| `DEPLOY_ENABLED` | `false` | backend environment | 总开关 |
| `DEPLOY_QUEUE_DIR` | `/deploy` | backend environment | 共享卷挂载点 |
| `DEPLOY_TASK_TIMEOUT` | `1800` | backend environment | 单任务硬超时 |
| `DEPLOY_HEARTBEAT_TIMEOUT` | `30` | backend environment | 执行器离线阈值 |
| `DEPLOY_MAX_LOG_LINES` | `500` | backend environment | 日志返回上限 |
| `DEPLOY_ALLOWED_ACTIONS` | `check,deploy,restart,rollback` | backend environment | 允许动作 |
| `DEPLOY_REQUIRE_BACKUP` | `true` | backend environment | 部署前强制备份 |
| `DEPLOY_REPO_PATH` | 宿主机仓库绝对路径 | ops compose + runner | 同路径挂载必需 |
| `DEPLOY_POLL_INTERVAL` | `2` | runner environment | 轮询队列间隔（秒） |
| `DEPLOY_SNAPSHOT_INTERVAL` | `15` | runner environment | 快照刷新间隔（秒） |
| `DEPLOY_RETENTION_DAYS` | `7` | runner environment | 任务文件保留天数 |
| `DEPLOY_HEALTH_TIMEOUT` | `180` | runner environment | 健康检查等待上限（秒） |

`docker-compose.yml` 的 backend 需新增卷挂载（现有已挂 `./backups:/backups`，在其后追加）：

```yaml
volumes:
  - ./backups:/backups
  - deploy_queue:/deploy
```

并在文件末尾 `volumes:` 段声明 `deploy_queue`（与 ops 文件同名卷，二者共享同一卷）。

## 12. 实施计划

每个阶段可独立上线、独立验收。

### P0 只读·纯 API（0.5 天）

- [ ] `config.py` 新增 `DEPLOY_*` 配置，四处同步
- [ ] `schemas/deploy.py`、`services/deploy_service.py`（仅状态聚合）
- [ ] `endpoints/deploy.py`：`/status`、`/versions`、`/history`
- [ ] `api.py` 注册路由
- [ ] 前端页面：状态卡 + 版本区 + 健康摘要 + 备份入口链接
- [ ] 三份 locale 补齐 `admin.nav.deploy` 与 `admin.deploy.*`

验收：不新增容器、不碰 socket；页面数据与 `/health/ready` 一致。

### P1 只读·快照（1 天）

- [ ] `scripts/Dockerfile.deploy`、`docker-compose.ops.yml`
- [ ] runner 快照循环 + 心跳
- [ ] `deploy_protocol.py` 快照解析 + 心跳新鲜度
- [ ] `/containers` 接口
- [ ] 前端 `ContainerTable` + 执行器在线状态

验收：停掉 runner 后页面明确显示「执行器离线」；容器状态与 `docker compose ps` 一致。

### P2 动作·安全子集（1.5 天）

- [ ] `deploy_protocol.py` 任务队列写入与认领状态
- [ ] runner 认领循环 + `check` / `restart` 执行
- [ ] `deploy_service.py` 锁、确认令牌、幂等
- [ ] `/actions`、`/tasks/{id}`、`/confirm`
- [ ] 前端 `useAdminDeploy`、`DeployTimeline`、`LogViewer`、确认 `Modal`
- [ ] `scripts/preflight.sh` 抽取，`Makefile` 改为调用它

验收：连点三次只产生一个任务；非管理员 403；CSRF 缺失 403；2 分钟轮询不触发限流。

### P3 动作·部署与回滚（2 天）

- [x] runner `deploy` 七步序列 + 失败自动回滚
- [x] runner `rollback`（镜像标签回切）
- [x] 镜像保留（`:rollback` 标签，镜像名从 compose 配置解析）
- [x] `deploy` / `rollback` 强制确认令牌
- [x] 前端历史列表
- [x] 审计日志字段补齐

验收：人为让健康检查失败，验证自动回滚并恢复服务；备份失败时部署中止且现状不变。

实现要点（与本文 6.3/6.4 对应）：

- 镜像名由 `docker compose config --format json` 解析后缓存，只取 `backend` / `frontend` / `celery-worker`，显式 `image:` 优先，否则用 `项目名-服务名`。
- `deploy` 的 `backup` 步先 `exec -T backup`，失败再 `run --rm --no-deps -T backup`，随后校验最新 `manifest.json` 的 `status == "success"`，任一环节失败即中止且不动现状。
- `up` 与 `health` 失败均触发自动回滚：回切 `:rollback` → `up -d` → 重新探活，成功则结果记为 `status=rolled_back`、`rolled_back=true`；回滚本身失败则记 `failed` 并提示人工介入。
- `rollback` 动作只回切镜像并重启 `backend` / `frontend` / `celery-worker`，数据回退仍需终端执行 `restore.sh`。
- 备份与构建等长耗时步骤通过 `run_long` 后台执行并每 3 秒刷新心跳，避免后端误判执行器离线。
- 审计日志在 `log_action` 中补充 `params` 字段，`deploy` 提交时自动补默认值 `backup_first`（取 `DEPLOY_REQUIRE_BACKUP`）与 `pull=true`，`params` 键白名单为 `backup_first` / `pull` / `build_only`。

### P4 可选增强（1 天）

- [ ] `deploy_records` 表 + Alembic 迁移（新增，不改历史）
- [ ] WS 进度推送（复用 `ws_manager.send_to_user`）
- [ ] 与 Grafana 看板互链

## 13. 门禁与发布检查

改动完成后必须全部通过，与 CI（`.github/workflows/ci.yml`）一致：

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest -q

cd ../frontend
npm run lint
npm run test
```

补充要求：

- 后端符号变更后执行 `make map` 刷新 `doc/codemap.md`。
- 新增环境变量必须同步 `.env.example`、`docker-compose.yml`、`doc/configuration.md` 与本文第 11 节。
- 若新增 `scripts/preflight.sh`，`Makefile` 的 `preflight-prod` 必须改为调用该脚本，保证「什么算合法生产编排」只有一份定义。

## 14. 已知坑与规避

| 坑 | 后果 | 规避 |
| --- | --- | --- |
| runner 挂载路径与宿主机不一致 | compose 解析相对路径到不存在的目录，容器起不来 | `${DEPLOY_REPO_PATH}:${DEPLOY_REPO_PATH}` 同路径挂载 |
| runner 并入 `docker-compose.yml` | `preflight-prod` 的 grep 校验被污染；`up -d` 可能误启 runner | 使用独立的 `docker-compose.ops.yml` |
| 硬编码镜像名 | compose 实际镜像名随项目名变化，`docker tag` 打空标签 | 启动时从 `docker compose config` 解析并缓存 |
| 1 秒轮询 | 撞 nginx `60r/m` 与后端限流，页面把自己限死 | 2s 起，且仅在 running 时轮询 |
| 状态存进程内存 | 4 个 gunicorn worker 互不可见，部署重启后全丢 | 状态落 Redis + 文件 |
| 部署中途 backend 重启 | 发起请求的进程消失，任务「凭空中断」 | 执行权在 runner，backend 只读写文件；前端靠轮询恢复 |
| 新增配置只改 `config.py` | `.env` 改了不生效，静默回落默认值 | 四处同步 + 文档 |
| 另建第二条迁移执行路径 | 两套失败语义、两套锁、两套回滚 | 迁移继续由容器启动命令承担 |
| 只有 `latest` 镜像 | 回滚需重新 build，分钟级且依赖网络 | `deploy` 首步打 `:rollback` 标签 |
| 用 HTTP 直接触发 `restore.sh` | 交互式确认的破坏性操作被静默跳过或卡死 | 数据回滚留给终端手工执行 |
| i18n 漏语言 | `TranslationKey` 类型报错或回退为键名 | 三个 locale 同批补齐 |
| 用 Celery 执行部署 | worker 被自己重启，任务丢失 | 部署动作只在 runner 执行 |
| runner 内用 `127.0.0.1` 探活 | 指向 runner 自身，永远连不上 backend | 用 `docker exec` 进 backend 容器内探活 |
| `up -d --remove-orphans` | 把 ops 文件里的 `deploy-runner` 当孤儿删除，部署自杀 | 控制台执行时去掉该参数 |

## 15. 附录：脚本接口约定

控制台复用而非重写以下脚本，改动脚本时需保持接口兼容：

| 脚本 | 控制台用途 | 输入 | 输出约定 |
| --- | --- | --- | --- |
| `scripts/preflight.sh`（新增） | `deploy` 第 1 步 | 无 | 退出码 0 = 通过；非 0 输出失败原因 |
| `scripts/doctor.sh` | `check` 动作 | `--strict`（警告视为失败） | 退出码 0 = 无失败项 |
| `scripts/upgrade.sh` | `deploy` 语义参考 | `--no-backup` / `--no-pull` / `--no-build` / `-y` | 失败时 `on_error` 打印回滚指引 |
| `scripts/backup.sh` | `deploy` 第 2 步 | 无 | 产出 `backups/<timestamp>/manifest.json` |
| `scripts/restore.sh` | 数据回滚（终端手工执行） | `<timestamp>` | 交互确认后覆盖数据 |

`preflight.sh` 抽取后，`Makefile` 的 `preflight-prod` 应改为：

```makefile
preflight-prod:
	@scripts/preflight.sh
```

以保证 CI、`make prod` 与控制台三处判定一致。脚本内容即现有五条校验：`docker compose config` 成功、`ENVIRONMENT=production`、无 `npm run dev`、无 `--reload`、无源码 bind mount（`target: /app/app` 与 `target: /app`）。