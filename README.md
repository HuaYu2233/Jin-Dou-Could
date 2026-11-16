# JinDou Cloud（筋斗云盘）

基于 Docker Compose 的全栈云存储应用，支持文件上传/下载、文件夹管理、文件分享、传输进度追踪、管理后台等功能。

## 技术栈

- **前端**：Next.js 16 / React 19 / TypeScript / Zustand / TanStack Query / Tailwind CSS 4
- **后端**：FastAPI / SQLAlchemy 2.0（异步）/ Alembic / Celery / MinIO SDK / Loguru
- **基础设施**：PostgreSQL 15 / PgBouncer / Redis 7 / MinIO / Nginx / Prometheus + Grafana（可选）

各组件版本与用途详见 [architecture.md](./doc/architecture.md)。

## 快速开始

### 前置要求

- Docker 20+
- Docker Compose 2.0+

### 部署步骤

```bash
# 1. 克隆仓库
git clone <repository-url>
cd JinDou-Cloud

# 2. 复制配置模板并编辑（至少修改密码与 SECRET_KEY）
cp .env.example .env

# 3. 首次构建镜像（约 5 分钟，后续无需重复）
make prod-build

# 4. 开发模式启动（~2 秒，热重载）
make dev

# 5. 查看日志
make logs
```

启动后访问：

| 服务                | 地址                       |
| ------------------- | -------------------------- |
| 前端                | http://localhost:3000      |
| 后端 API            | http://localhost:8000      |
| API 文档（Swagger） | http://localhost:8000/docs |
| MinIO 控制台        | http://localhost:9001      |

首次启动后通过注册页面创建账号；`.env` 中 `ADMIN_EMAIL` 配置的邮箱注册后自动成为管理员。

开发/生产编排差异、生产部署步骤与运维命令见 [deployment.md](./doc/deployment.md)。

## 文档索引

| 文档                                             | 内容                                                 |
| ------------------------------------------------ | ---------------------------------------------------- |
| [architecture.md](./doc/architecture.md)         | 系统架构、技术栈、项目结构、分层设计、关键设计决策   |
| [configuration.md](./doc/configuration.md)       | 全部环境变量、默认值与注意事项                       |
| [deployment.md](./doc/deployment.md)             | 部署流程、运维命令、CI 门禁、监控与告警              |
| [development.md](./doc/development.md)           | 本地开发环境、代码规范、调试方式                     |
| [api-reference.md](./doc/api-reference.md)       | REST API 接口清单与调用示例                          |
| [database.md](./doc/database.md)                 | 数据模型、表结构与索引设计                           |
| [security.md](./doc/security.md)                 | 认证、中间件、上传、WebSocket 安全与加固清单         |
| [testing.md](./doc/testing.md)                   | 测试框架、运行方式与 CI 集成                         |
| [backup-restore.md](./doc/backup-restore.md)     | 备份策略、恢复流程与故障演练                         |
| [changelog.md](./doc/changelog.md)               | 功能清单、性能优化清单与版本记录                     |
| [faq.md](./doc/faq.md)                           | 常见问题排查                                         |
| [pitfalls.md](./doc/pitfalls.md)                 | 踩坑记录（症状 / 根因 / 规避）                       |
| [lan-transfer.md](./doc/lan-transfer.md)         | 局域网快传（房间码模式）设计与实施                   |
| [visual-deployment.md](./doc/visual-deployment.md) | 可视化部署控制台开发文档                           |
| [codemap.md](./doc/codemap.md)                   | 后端符号索引（`make map` 自动生成，勿手工编辑，不参与检索）  |

## 协作约定

门禁命令、终端使用约定与代码规范见 [.trae/rules/project_rules.md](./.trae/rules/project_rules.md)。