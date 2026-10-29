DC = docker compose
DC_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: help dev dev-restart prod prod-build hot-reload logs down setup

help:
	@echo "Commands:"
	@echo "  make dev          - 开发模式启动（~2秒，依赖预装在镜像中）"
	@echo "  make dev-restart  - 重启 backend + frontend 容器"
	@echo "  make prod-build   - 生产构建镜像（BuildKit 缓存）"
	@echo "  make prod         - 生产模式启动"
	@echo "  make hot-reload   - 热更新后端代码（docker cp）"
	@echo "  make setup        - 初始化 git 性能优化（fsmonitor）"
	@echo "  make logs         - 查看日志"
	@echo "  make down         - 停止所有服务"

setup:
	@git config core.fsmonitor true && git config core.untrackedCache true && git config feature.manyFiles true && git fsmonitor--daemon start 2>/dev/null; echo "Git performance config applied (fsmonitor + untrackedCache)"

dev:
	@$(DC_DEV) up -d --no-build db redis minio backend frontend

dev-restart:
	@$(DC_DEV) up -d --force-recreate --no-build backend frontend

prod-build:
	@DOCKER_BUILDKIT=1 $(DC) build backend frontend

prod:
	@$(DC) up -d

hot-reload:
	@docker cp ./backend/app/. cloud-drive-backend:/app/app/ 2>/dev/null && echo "Synced! Uvicorn --reload will auto-detect." || echo "Backend not running"

logs:
	@$(DC_DEV) logs -f backend frontend

down:
	@$(DC) down