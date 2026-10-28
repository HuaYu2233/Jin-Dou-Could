FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

RUN rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list \
    && echo 'deb http://deb.debian.org/debian bookworm main' > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6.9 /uv /uvx /bin/

ENV UV_SYSTEM_PYTHON=1

COPY pyproject.toml .
COPY uv.lock* ./
RUN uv pip install --system --no-cache .

FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

RUN rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list \
    && echo 'deb http://deb.debian.org/debian bookworm main' > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]