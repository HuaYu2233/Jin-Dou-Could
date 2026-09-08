FROM python:3.11-slim-bookworm

WORKDIR /app

# Docker CLI（用于触发备份容器执行备份脚本）
COPY --from=docker:24-cli /usr/local/bin/docker /usr/local/bin/docker

# 安装系统依赖（重写 sources 只保留 bookworm 主仓库，避免 updates/security 的 InRelease 日期问题）
RUN rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list \
    && echo 'deb http://deb.debian.org/debian bookworm main' > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    gcc \
    libpq5 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（官方静态二进制，零 pip 残留）
COPY --from=ghcr.io/astral-sh/uv:0.6.9 /uv /uvx /bin/

# 关键：让 uv 直接装到系统 Python，不创建 .venv
ENV UV_SYSTEM_PYTHON=1

# 安装 Python 依赖（直接装到系统 Python，不创建 .venv）
COPY pyproject.toml .
COPY uv.lock** ./
RUN uv pip install --system --no-cache .

# 复制代码
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]