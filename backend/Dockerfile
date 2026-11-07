# ==============================================================================
# CloudDesk Support Platform — Backend Dockerfile (P14-2, CLAUDE.md §15)
# Multi-stage build targeting python:3.12-slim with non-root user and healthcheck.
# Build context: repository root (e.g. docker build -f backend/Dockerfile .)
# ==============================================================================

# Global argument for reproducible base image pinning
ARG PYTHON_VERSION=3.12-slim

# ------------------------------------------------------------------------------
# Stage 1: Dependency Builder
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

# Prevent python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# Install uv from official binary image for fast, deterministic dependency resolution
COPY --from=ghcr.io/astral-sh/uv:0.5.29 /uv /uvx /bin/

# Copy dependency specifications first to leverage Docker layer caching
COPY pyproject.toml uv.lock* ./

# Create virtual environment and install production dependencies only
RUN uv venv /opt/venv && \
    uv sync --frozen --no-dev --no-install-project

# ------------------------------------------------------------------------------
# Stage 2: Final Minimal Runtime Image
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Install curl for reliable container HEALTHCHECK (CWE-345) and clean apt cache
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group (CWE-250)
RUN groupadd -g 10001 app && \
    useradd -u 10001 -g app -s /bin/bash -m -d /home/app app

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=app:app /opt/venv /opt/venv

# Copy application source directories with non-root ownership
COPY --chown=app:app backend/ ./backend/
COPY --chown=app:app agents/ ./agents/
COPY --chown=app:app memory/ ./memory/
COPY --chown=app:app integrations/ ./integrations/
COPY --chown=app:app sample_data/ ./sample_data/
COPY --chown=app:app datasets/ ./datasets/
COPY --chown=app:app database/ ./database/
COPY --chown=app:app pyproject.toml ./

# Switch to non-root user (CLAUDE.md §13, §15, CWE-250)
USER app

# Expose backend API HTTP port
EXPOSE 8000

# Container liveness health check probing /health/live (CLAUDE.md §15)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Production entrypoint starting FastAPI via Uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
