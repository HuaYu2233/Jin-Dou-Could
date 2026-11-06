DC = docker compose
DC_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev
PROD_CONFIG = /tmp/jindou-cloud-prod-config.yml

.PHONY: help dev dev-build dev-restart prod prod-build preflight-prod hot-reload logs down setup

help:
	@echo "Commands:"
	@echo "  make dev          - 开发模式启动（~2秒，依赖预装在镜像中）"
	@echo "  make dev-build    - 构建前端 dev 镜像（首次或依赖变更后）"
	@echo "  make dev-restart  - 重启 backend + frontend 容器"
	@echo "  make prod-build   - 生产构建镜像（BuildKit 缓存）"
	@echo "  make prod         - 生产模式启动（含编排校验）"
	@echo "  make hot-reload   - 热更新后端代码（docker cp）"
	@echo "  make setup        - 初始化 git 性能优化（fsmonitor）"
	@echo "  make logs         - 查看日志"
	@echo "  make down         - 停止所有服务"

setup:
	@git config core.fsmonitor true && git config core.untrackedCache true && git config feature.manyFiles true && git fsmonitor--daemon start 2>/dev/null; echo "Git performance config applied (fsmonitor + untrackedCache)"

dev-build:
	@DOCKER_BUILDKIT=1 $(DC_DEV) build frontend

dev:
	@docker image inspect jindou-cloud-frontend:dev >/dev/null 2>&1 || $(MAKE) dev-build
	@$(DC_DEV) up -d --no-build db redis minio pgbouncer backend frontend

dev-restart:
	@$(DC_DEV) up -d --force-recreate --no-build backend frontend

prod-build:
	@DOCKER_BUILDKIT=1 $(DC) build backend celery-worker frontend

preflight-prod:
	@$(DC) config > $(PROD_CONFIG) || { echo "✗ 生产编排校验失败：检查 .env（SECRET_KEY 必填）"; exit 1; }
	@grep -Eq 'ENVIRONMENT[:=] *production' $(PROD_CONFIG) || { echo "✗ 拒绝启动：ENVIRONMENT 必须为 production"; exit 1; }
	@! grep -q 'npm run dev' $(PROD_CONFIG) || { echo "✗ 拒绝启动：检测到前端 dev 命令（dev 编排混入生产）"; exit 1; }
	@! grep -q -- '--reload' $(PROD_CONFIG) || { echo "✗ 拒绝启动：检测到后端 --reload（dev 编排混入生产）"; exit 1; }
	@! grep -q 'target: /app/app' $(PROD_CONFIG) || { echo "✗ 拒绝启动：检测到后端源码 bind mount（dev 编排混入生产）"; exit 1; }
	@! grep -Eq 'target: /app$$' $(PROD_CONFIG) || { echo "✗ 拒绝启动：检测到前端源码 bind mount（dev 编排混入生产）"; exit 1; }
	@echo "✓ 生产编排校验通过（无 dev 挂载、无热重载）"

prod: preflight-prod
	@$(DC) up -d

hot-reload:
	@docker cp ./backend/app/. cloud-drive-backend:/app/app/ 2>/dev/null && echo "Synced! Uvicorn --reload will auto-detect." || echo "Backend not running"

logs:
	@$(DC_DEV) logs -f backend frontend

down:
	@$(DC_DEV) down