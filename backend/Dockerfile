FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（官方静态二进制，零 pip 残留）
COPY --from=ghcr.io/astral-sh/uv:0.6.9 /uv /uvx /bin/

# 关键：让 uv 直接装到系统 Python，不创建 .venv
ENV UV_SYSTEM_PYTHON=1

# 安装 Python 依赖（uv 兼容 requirements.txt 格式）
COPY requirements.txt .
RUN uv pip install --no-cache -r requirements.txt

# 复制代码
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]