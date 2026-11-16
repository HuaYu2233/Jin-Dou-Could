# 踩坑记录

按时间顺序记录本项目已发生的、容易复发的坑。每条包含：症状、根因、规避方式、相关提交。

维护约定：新坑追加到末尾，不修改历史条目；若某条已被根治，在条目内标注「已根治」并说明方式。

---

## 1. 终端 heredoc / 多行命令导致 shell 进入续行态（已规避）

**记录时间**：2026-10-31

### 症状

- 提示符出现 `cmdand dquote>`、`cmdand heredoc>` 等前缀，命令不再执行。
- `echo hello`、`printf` 等简单命令返回**空输出**。
- 两个不相关的命令块被拼接在同一输入流中，例如：
  ```
  cmdand heredoc>     print("get_client_ipimport faulthandler, importlib.util, os, sys, traceback
  ```
- 终端看起来"卡住"，但进程实际没有卡死。

### 根因

shell 并没有损坏，它一直停在 **PS2 续行提示符**等待输入结束：

- `cmdand` = 仍处于上一条 `&&` 链中；
- `dquote` = 双引号未闭合；
- `heredoc` = heredoc 未遇到终止符。

触发条件是多行命令（跨行 `python3 -c "..."`、`<<'PYEOF'` heredoc）被注入交互式 zsh。当 PTY 处于忙状态（上一条命令未结束或输出仍在刷新）时，写入可能被截断或交错，**负责闭合引号/heredoc 的那一行丢失**。此后所有注入内容都被当作字符串或 heredoc 正文吞掉，因此任何命令都不会执行、也不会回显。

### 规避

1. 命令写成单行，多条用 `;` 或 `&&` 串联。
2. 不使用 heredoc。
3. 多行 Python 先写脚本文件，再单行执行 `python3 script.py`。
4. 输出过长时重定向到文件，用文件读取工具查看。
5. 终端静默时先发哨兵 `echo READY`，无回显则换终端并重新验证。

### 相关

- 无代码提交。排查期间通过 `faulthandler.dump_traceback_later(8)` 确认目标脚本秒级正常结束，证明并非进程卡死。

---

## 2. 终端回显吞掉逗号与中文（显示层假象）

**记录时间**：2026-10-31

### 症状

终端显示的命令/输出中，逗号丢失、中文错乱：

```text
实际: def connect(self, user_id: str, ws: WebSocket):
显示: def connect(self user_id: str ws: WebSocket)

实际: refactor(backend): 修复 P2 lint 项...
显示: refactor(backend):  P2 lin t
```

### 根因

终端回显渲染层的问题，命令实际执行正确、退出码正常。与第 1 条独立，但容易被误判为"命令写错了"。

### 规避

**不要用终端输出审查代码、核对 commit message 或判断 lint 结果**。使用文件读取工具查看重定向后的文件，或用 `git show` / `git log -1 --format=%B` 复核。

---

## 3. 新建终端未真正生效

**记录时间**：2026-10-31

### 症状

指定新建终端后，返回的仍是同一个已卡死的 `terminal_id`，后续命令继续静默。

### 规避

「新建终端」必须以**收到哨兵回显**（`echo READY` 有输出）为验证标准，仅凭返回的 terminal_id 无法判断是否真的新建。

---

## 4. pytest 测试用 `return` 返回断言结果，导致永远不失败（假绿）

**记录时间**：2026-10-31

### 症状

`backend/tests/test_share_rate_limit.py` 的 4 个测试在 `pytest -q` 下始终 `4 passed`，即使断言条件实际为假也照样通过。同时产生 `PytestReturnNotNoneWarning`。

### 根因

测试写成：

```python
def test_xxx():
    return _assert(...)  # 返回 bool
```

pytest 对测试函数的非 `None` 返回值**只发警告，不判失败**。因此断言结果为 `False` 时测试依然 pass，形成"假绿"——会污染整个测试基线的可信度（当时汇报的 `202 passed` 中有 4 个属于此类）。

### 修复

改为先打印再 `assert`：

```python
def _check(condition: bool, message: str) -> None:
    print(f"  {'✅' if condition else '❌'} {message}")
    assert condition, message
```

修复后 `PytestReturnNotNoneWarning` 消失（warnings 13 → 9），且断言失败会真实报错。

### 规避

- 测试函数一律用 `assert`，禁止 `return` 断言结果。
- 看到 `PytestReturnNotNoneWarning` 必须当作**真实缺陷**处理，不要忽略。

### 相关

提交 `ea71d73`。

---

## 5. `except Exception: pass` 吞掉模块导入失败

**记录时间**：2026-10-31

### 症状

`spec.loader.exec_module(mod)` 外层包了 `try/except Exception: pass`，导入失败时静默继续，后续 `hasattr` 断言拿到空模块，表现为"测试能跑但结果莫名全错"或"看起来正常"。

### 根因

`Settings` 是 pydantic 强校验，`SECRET_KEY` 要求 ≥32 字符，`MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` 为必填。独立运行时只设了 `SECRET_KEY` 且长度不足，`exec_module` 必然抛 `ValidationError`，异常被吞掉。

### 修复

1. 补齐环境变量：`SECRET_KEY`（≥32 字符）、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`。
2. 去掉 `try/except Exception: pass`，让导入失败直接暴露。

### 规避

不要用 `except Exception: pass` 包住模块导入。需要抑制异常时用 `contextlib.suppress` 并**明确异常类型**，不要用裸 `Exception`。

### 相关

提交 `ea71d73`。

---

## 6. 测试断言指向已重构迁移的模块

**记录时间**：2026-10-31

### 症状

`test_share_rate_limit.py` 从 `app/api/v1/endpoints/shares.py` 加载模块并断言 `SHARE_VERIFY_MAX_ATTEMPTS`、`SHARE_VERIFY_LOCK_SECONDS`、`get_client_ip` 存在，全部拿不到（独立运行 0/4 通过）。

### 根因

重构时这些符号已迁移到 service 层，但测试仍指向 endpoint 层：

| 符号                                                      | 原测试位置                       | 实际位置                        |
| --------------------------------------------------------- | -------------------------------- | ------------------------------- |
| `SHARE_VERIFY_MAX_ATTEMPTS` / `SHARE_VERIFY_LOCK_SECONDS` | `app/api/v1/endpoints/shares.py` | `app/services/share_service.py` |
| `get_client_ip`                                           | `app/api/v1/endpoints/auth.py`   | `app/services/auth_service.py`  |

叠加第 4、5 条后，问题被完全掩盖。

### 修复

测试改为加载 `app/services/share_service.py` 与 `app/services/auth_service.py`，并统一封装加载函数。

### 规避

重构搬迁符号时同步更新测试。断言前先确认符号真实位置（`grep -rn` 全仓检索，注意 `__pycache__` 里的二进制命中是干扰项）。

### 相关

提交 `ea71d73`。

---

## 7. `SECRET_KEY` 长度校验不通过

**记录时间**：2026-10-31

### 症状

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
SECRET_KEY
  Value error, SECRET_KEY 必须设置为不少于 32 字符的强随机值
```

### 根因

`Settings` 对 `SECRET_KEY` 有自定义校验，长度不足 32 字符直接抛错。调试脚本中用 `"k"` 之类的短值会触发。

### 规避

脚本/测试中的临时值统一用 `test-secret-key-for-verification-only-at-least-32-chars!!`；真实环境用 `openssl rand -hex 32`。

---

## 8. `uvx ruff@版本` 启动慢、本地未安装 ruff

**记录时间**：2026-10-31

### 症状

- `uv run ruff` 报 `error: Failed to spawn: ruff`，说明 ruff 不在项目 venv 中。
- 只能用 `uvx ruff@0.17.3`，每次都解析依赖、建临时环境，网络差时每次数秒。

### 根因

`pyproject.toml` 的 `[project.optional-dependencies].dev` 已声明 `ruff>=0.11.0`，但从未执行 `uv sync --extra dev`，依赖没同步进 `.venv`。

### 修复

```bash
cd backend && uv sync --extra dev
```

安装后 `uv run ruff check .` 耗时从"每次解析依赖"降到约 `0.07s`。

### 规避

统一使用 `uv run ruff`，不使用 `uvx`。`uv.lock` 随依赖声明变化需一并提交。

### 相关

提交 `d1c695e`（`uv.lock` 同步 dev 依赖）。

---

## 9. E712：SQLAlchemy 布尔列不能照 ruff 建议直接删比较

**记录时间**：2026-10-31

### 症状

ruff 的 E712 建议把 `User.is_active == True` 简化为 `User.is_active`。

### 根因

SQLAlchemy 中 `where(User.is_active)` 会把**裸列对象当作 truthy** 求值，生成的 SQL 语义错误，不是"筛选 is_active 为真的行"。

### 修复

改用 `.is_(True)` / `.is_(False)`。

### 规避

E712 出现在 SQLAlchemy 列上时，一律用 `.is_(True)`，不要接受 ruff 的自动简化建议。

### 相关

提交 `ea71d73`。

---

## 10. IDE 编辑卡顿（工作区索引过大）

**记录时间**：2026-10-31

### 症状

编辑一个 121 行的小文件，保存/编辑响应明显延迟，主观上像"卡死"。

### 根因

工作区约 3.5 万个文件，其中 `frontend/node_modules`（525M）、`backend/.venv`（137M）、`backups`（80M）占绝大多数。每次编辑 IDE 都要重新做导入图分析，而该测试文件又通过 `importlib` 指向 `app` 内部模块，会连带解析整条依赖链。

同时排除了其他因素：`.zshrc` 仅 16 行、无插件/主题、IDE 未开 `formatOnSave`、无 pre-commit、无 git hooks、无残留 ruff/pytest 进程。

### 修复

新建 `.vscode/settings.json`（该目录已在 `.gitignore`），配置 `files.watcherExclude`、`search.exclude`、`python.analysis.exclude`，排除 `node_modules` / `.venv` / `backups` / `.next` / `dist` / `coverage`。

### 规避

新增大的生成目录时，同步加入上述三处排除配置。

---

## 11. zsh 历史展开与多行 `python -c` 双重踩坑（`event not found` + `quote>`）

**记录时间**：2026-11-02

### 症状

两条独立故障在一次验证中同时出现：

1. 执行 `docker exec cloud-drive-backend python -c "..."` 时立即报：

   ```text
   zsh: event not found: /usr/bin/env
   ```

2. 随后改写为多行 `python -c '...'`，终端停在 `quote>` 续行态，继续输入的内容全部被当作字符串正文吞掉，提示符变成 `>....`。

### 根因

两处都是 **shell 层**问题，不是容器或代码问题：

1. **历史展开**：zsh 默认 `setopt bang_hist`，双引号内出现的 `!` 仍会触发历史引用。命令中 `b'#!/usr/bin/env python3\n...'` 的 `!` 被展开，`#` 后的 `/usr/bin/env` 被当作历史事件名，于是报 `event not found`。单引号内不会展开，脚本文件里也不会。
2. **未闭合单引号**：把多行 Python 直接塞进 `python -c '...'`，换行让 shell 认为引号还没闭合，进入 PS2（`quote>`）等待。此时再输入 `try:` / `except` 等内容，只会被当作字符串，永远等不到结束。

两者的共同点：**命令被写成了跨行/含特殊字符的形式**，违反「命令永远写成单行」。

### 修复

改为把验证逻辑写进脚本文件，用单行命令执行：

```bash
docker exec cloud-drive-backend python /tmp/verify_mime.py > /tmp/verify.txt 2>&1
```

脚本内部用单行 `print(...)` 与显式 `try/except AppError`，不依赖 shell 引号嵌套。

### 规避

- 双引号字符串内**禁止**出现 `!`（也不建议出现 `$`、反引号）。必须包含时外层改单引号，或写进脚本文件。
- `python -c` **只能单行**；多行代码写脚本文件再执行。
- 出现 `quote>` / `cmdand dquote>` 立即 `Ctrl-C` 中止，不要继续"补引号"。
- 判定卡住后换终端，并用 `echo READY` 哨兵确认，再继续。

### 相关

- 无代码提交。本次验证结论：容器内 `_canonical_mime('text/x-python')` → `text/plain`、`audio/mp3` → `audio/mpeg`、`application/x-msdownload` 保持原值；libmagic 对 Python 脚本实测返回 `text/x-script.python`，归一化后通过白名单。

---

## 12. libmagic 对截断的 PNG 头返回 `text/plain`

**记录时间**：2026-11-02

### 症状

测试里用 `b"\x89PNG\r\n\x1a\n" + b"\x00" * 64` 作为「PNG」样本，`detect_real_mime_type` 返回 `text/plain`，导致头像上传测试误判为拒绝。

### 根因

libmagic 判定 PNG 需要完整的 IHDR 块，仅有 8 字节签名 + 任意填充会被归类为文本。签名匹配不等于类型识别成功。

### 规避

构造测试样本时使用完整最小 PNG（含 IHDR/IDAT/IEND），不要只拼签名。`tests/test_upload_security.py` 的 `test_detect_real_mime_png` 里有可直接复用的字节串。

---

## 13. 上传链路遗留观察项（暂不修改）

**记录时间**：2026-11-02

以下三项经评估风险可控，未纳入本次修复，留作后续观察：

1. **分片会话过期后 abort 不校验归属**：`abort_multipart_upload` 在 Redis 会话为空时跳过 `storage_key` 比对，仅凭 `upload_id` 即可中止。`upload_id` 由 MinIO 生成、不可枚举，实际风险低；如需彻底收紧，可在会话缺失时校验 `storage_key` 是否以 `owner_id/` 开头。
2. **分片类型探测只覆盖前 2048 字节**：polyglot 文件（头部合法、尾部载荷恶意）可通过检测。这是基于文件头检测的固有局限，存储层已用 `nosniff` + `attachment` 预览语义降低影响面。
3. **SVG 会触发缩略图任务但必然失败**：`categorize_file_type` 将 `image/svg+xml` 归为 `image`，而 Pillow 不支持 SVG，任务重试耗尽后返回 `None`。可按 `mime_type in {"image/jpeg","image/png","image/webp","image/gif"}` 收紧入队条件，避免无谓重试。

---

## 14. 调试用 cookies.txt 被 git 跟踪

**记录时间**：2026-11-06

### 症状

`git ls-files` 中出现仓库根目录的 `cookies.txt`，内容为 `curl -c` 导出的 Cookie jar，含可用的 `access_token` / `refresh_token`。

### 根因

curl 调试命令直接写在仓库根目录导出，`.gitignore` 没有对应规则，`git add -A` 时被一并纳入。

### 规避

1. `.gitignore` 增加 `**/cookies.txt`；
2. 已跟踪的文件用 `git rm --cached cookies.txt` 停止跟踪，本地文件保留；
3. 凭据已过期时可不改写历史，但仍需轮换令牌；若为长期有效密钥，必须改写历史并作废密钥。

同类文件还有 `测试账号.txt`，同样依赖 `.gitignore` 拦截。

---

## 15. `.env` 变量未被 compose 透传，改动静默失效

**记录时间**：2026-11-06

### 症状

在 `.env` 中修改 `LOGIN_RATE_LIMIT_PER_MINUTE`、`MINIO_SECURE`、`TRUSTED_PROXIES` 等变量后，容器内行为不变，`settings` 仍是代码默认值，且无任何告警。

### 根因

Docker Compose 只会把 `environment` 段显式引用的变量注入容器，`.env` 仅用于为 compose 文件本身提供插值。`environment` 未列出的变量不会进入容器进程环境。

### 规避

1. 新增配置项必须三处同步：`.env.example` 声明 → `backend/app/core/config.py` 的 `Settings` 字段 → `docker-compose.yml` 的 `environment`；
2. Celery Worker 单独一份 `environment`，新增配置要两边都加，否则只有 API 生效、异步任务失败；
3. 核对渲染结果：`docker compose config` 查看最终注入的环境变量；
4. 核对容器内实际值：`docker compose exec backend printenv | grep -i 变量名`。

### 注意

`pydantic-settings` 配置了 `extra=forbid`，compose 里出现 `Settings` 未声明的变量会直接导致后端启动失败。因此只被进程使用、不参与 `Settings` 的变量（如 `BACKEND_WORKERS`，仅 gunicorn 读取）也必须保留字段声明，不能图省事删除。

---

## 16. 登出未清理客户端状态导致跨用户串数据

**记录时间**：2026-11-06

### 症状

同一浏览器内用户 A 登出、用户 B 登录后，文件列表首屏出现 A 的文件；通知未读角标继承上一用户的计数，刷新后消失。

### 根因

1. TanStack Query 的缓存 key 只包含查询参数（分类、页码、文件夹、关键词），**不含用户身份**，登出后缓存未失效；
2. 通知为纯内存 Zustand store，刷新页面才归零，登出时不重置。

### 修复

在 `frontend/app/dashboard/layout.tsx` 的未认证分支集中清理：

```tsx
queryClient.clear();
useNotificationStore.getState().clearAll();
```

### 规避

- 清理必须用 `queryClient.clear()`，不能用 `invalidateQueries()`：后者会让旧缓存数据在重新请求期间继续渲染，且会用已失效的 Cookie 再打一轮请求；
- 顺序必须是 `await logoutApi()` → 清本地状态 → `router.replace`。先清 store 会让 `closeSession` 置全局 `closed` 标记，后续请求被拦截，服务端 Cookie 反而没删干净；
- 新增任何用户维度的客户端状态（store、模块变量、localStorage）都要加入该清理分支。

---

## 17. 新增文件分类后压缩包格式缺失

**记录时间**：2026-11-06

### 症状

前端新增「压缩包」入口后，上传的 `.tar.gz`、`.tar`、`.bz2`、`.xz` 不出现在该分类下，甚至上传直接被拒。

### 根因

分类集合 `_ARCHIVE_MIME_TYPES` 只覆盖 `zip` / `rar` / `7z`，而白名单 `ALLOWED_MIME_TYPES` 与分类集合是两份独立数据：类型不在白名单会被拒绝上传，不在分类集合会被归为 `other`。

### 规避

1. 归档类需同时覆盖 `zip` / `rar` / `7z` / `gzip` / `x-gzip` / `tar` / `bzip2` / `xz`；
2. `file_type` 在上传时由探测结果推导并落库，调整分类规则**不会**重新归类历史数据，纠正存量需单独写迁移；
3. 新增分类要同步前端 `CategoryId`、`Sidebar` 导航项与三份 i18n 词条。

---

## 18. Celery 任务模块未登记导致任务静默不执行

**记录时间**：2026-11-06

### 症状

任务函数已实现且被 API 调用 `.delay()`，Worker 日志无任何记录，文件缩略图始终不生成。

### 根因

Worker 通过 `Celery(include=...)` 导入任务模块，只按 `_TASK_MODULES` 列表加载。未登记的模块不会注册到 Worker，`send_task` 出去的只是未知任务名，被静默丢弃。

### 规避

新增 `app/tasks/xxx_tasks.py` 后，必须在 `backend/app/core/celery_app.py` 的 `_TASK_MODULES` 中登记，然后重建 Worker：

```bash
docker compose up -d --force-recreate celery-worker
docker compose logs celery-worker | grep "tasks\]"
```

---

## 19. 配置在 .env 里写了但容器收不到

**记录时间**：2026-11-06

### 症状

`.env` 里修改 `RESET_PASSWORD_CODE_LENGTH`、`API_URL` 等值后重启，行为完全没变化，容器内仍是默认值。

### 根因

`.env` 的值只有被 `docker-compose.yml` 的 `environment` 以 `${VAR}` 引用才会注入容器。变量若只写在 `Settings` 与 `.env.example` 中、而 compose 未引用，容器内读到的就是 `config.py` 里的默认值，属于**静默回落**，不会报错。

本次排查发现的真实缺口：

- `RESET_PASSWORD_CODE_EXPIRE_SECONDS` / `RESET_PASSWORD_CODE_LENGTH`：backend 与 celery-worker 都未透传。后者用于邮件正文的「有效期 N 分钟」文案，与 backend 生成验证码时的 TTL 必须一致；
- `API_URL`：frontend 容器里被硬编码为 `http://backend:8000`，`.env` 的值不生效，已改为 `${API_URL:-http://backend:8000}`。

### 规避

新增配置必须三处同步：`.env.example` → `backend/app/core/config.py` → `docker-compose.yml` 的 `environment`（需要时 backend 与 celery-worker 两处都加）。

用下面三条单行命令做双向校验（`comm` 输出为空即一致）：

```bash
grep -oE '\${[A-Z_]+' docker-compose.yml | sed 's/${//' | sort -u > /tmp/compose_vars.txt
grep -oE '^#? ?[A-Z_]+=' .env.example | tr -d '#= ' | sort -u > /tmp/env_vars.txt
comm -23 /tmp/compose_vars.txt /tmp/env_vars.txt
```

```bash
grep -oE '^    [A-Z][A-Z0-9_]*:' backend/app/core/config.py | tr -d ' :' | sort -u > /tmp/settings_vars.txt
comm -23 /tmp/settings_vars.txt /tmp/compose_vars.txt
```

```bash
comm -13 /tmp/compose_vars.txt /tmp/env_vars.txt
```

已知的合理例外，不算缺口：

- `DATABASE_URL` / `REDIS_URL` / `BACKUP_DIR`：由 compose 直接拼装或硬编码，不从 `.env` 读；
- `DATABASE_URL_DIRECT`：compose 显式注入，供启动命令里的 `alembic upgrade head` 使用（`$${DATABASE_URL_DIRECT}` 是容器内 shell 展开，不是 compose 插值）；
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`：compose 用 `${MINIO_ROOT_USER}` / `${MINIO_ROOT_PASSWORD}` 换名注入；
- `CELERY_CONCURRENCY`、`GRAFANA_ADMIN_USER` 等：只被容器启动命令/grafana 读取，不属于 `Settings`。

> 正则必须写成 `^#? ?[A-Z_]+=`。`.env.example` 的注释行是 `# VAR=...`（井号后有空格），用 `^#?[A-Z_]+=` 会漏掉全部注释变量，误报一堆「缺失」。