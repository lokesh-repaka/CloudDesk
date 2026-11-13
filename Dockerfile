# ==============================================================================
# CloudDesk Support Platform — Root Backend Dockerfile (P14-2, CLAUDE.md §15)
# Multi-stage build targeting python:3.12-slim with non-root user and healthcheck.
# Mirrors backend/Dockerfile for standard repository-root container builds.
# ==============================================================================

ARG PYTHON_VERSION=3.12-slim

FROM python:${PYTHON_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:0.5.29 /uv /uvx /bin/

COPY pyproject.toml uv.lock* ./

RUN uv venv /opt/venv && \
    uv sync --frozen --no-dev --no-install-project

FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -g 10001 app && \
    useradd -u 10001 -g app -s /bin/bash -m -d /home/app app

WORKDIR /app

COPY --from=builder --chown=app:app /opt/venv /opt/venv

COPY --chown=app:app backend/ ./backend/
COPY --chown=app:app agents/ ./agents/
COPY --chown=app:app memory/ ./memory/
COPY --chown=app:app integrations/ ./integrations/
COPY --chown=app:app sample_data/ ./sample_data/
COPY --chown=app:app datasets/ ./datasets/
COPY --chown=app:app database/ ./database/
COPY --chown=app:app pyproject.toml ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
