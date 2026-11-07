"""Deployment and Container Hygiene Tests (P14-2, CLAUDE.md §13, §15).

Verifies Dockerfile architecture, multi-stage build layers, non-root user execution,
healthcheck probes, .dockerignore secret filtering, and Next.js standalone packaging
in accordance with:
- CLAUDE.md §13 (Dockerfile hygiene: non-root, HEALTHCHECK)
- CLAUDE.md §15 (Containers, infrastructure, delivery)
- CWE-200 (Information Exposure / .dockerignore exclusion)
- CWE-250 (Execution with Unnecessary Privileges / non-root enforcement)
- CWE-345 (Insufficient Verification of Data Authenticity / HEALTHCHECK)
- CWE-668 (Exposure of Resource to Wrong Sphere / minimal attack surface)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
FRONTEND_DOCKERFILE = REPO_ROOT / "frontend" / "Dockerfile"
ROOT_DOCKERIGNORE = REPO_ROOT / ".dockerignore"
FRONTEND_DOCKERIGNORE = REPO_ROOT / "frontend" / ".dockerignore"
NEXT_CONFIG = REPO_ROOT / "frontend" / "next.config.ts"


# ============================================================================
# 1. File Existence Tests
# ============================================================================


def test_dockerfiles_and_dockerignore_files_exist():
    """Verify backend and frontend Dockerfiles and their .dockerignore files exist."""
    assert BACKEND_DOCKERFILE.is_file(), (
        f"Missing backend Dockerfile at {BACKEND_DOCKERFILE}"
    )
    assert FRONTEND_DOCKERFILE.is_file(), (
        f"Missing frontend Dockerfile at {FRONTEND_DOCKERFILE}"
    )
    assert ROOT_DOCKERIGNORE.is_file(), (
        f"Missing root .dockerignore at {ROOT_DOCKERIGNORE}"
    )
    assert FRONTEND_DOCKERIGNORE.is_file(), (
        f"Missing frontend .dockerignore at {FRONTEND_DOCKERIGNORE}"
    )


# ============================================================================
# 2. Backend Dockerfile Architecture & Hygiene Tests (CLAUDE.md §15)
# ============================================================================


def test_backend_dockerfile_multi_stage_architecture():
    """Verify backend/Dockerfile implements multi-stage build pattern."""
    content = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
    from_matches = re.findall(r"^FROM\s+([^\s]+)(?:\s+[Aa][Ss]\s+([^\s]+))?", content, re.MULTILINE)

    assert len(from_matches) >= 2, (
        "Backend Dockerfile must define at least two build stages (multi-stage build)."
    )

    stage_names = [m[1].lower() for m in from_matches if m[1]]
    assert any("builder" in name for name in stage_names), (
        "Backend Dockerfile must define a builder stage."
    )


def test_backend_dockerfile_base_image_specification():
    """Verify backend/Dockerfile uses python:3.12-slim or python:3.13-slim base image."""
    content = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"python:(?:3\.12|3\.13)-slim", content, re.IGNORECASE), (
        "Backend Dockerfile must use python:3.12-slim (or 3.13-slim) base image per CLAUDE.md §15."
    )
    # Ensure :latest is never used
    assert not re.search(r"python:latest", content, re.IGNORECASE), (
        "Backend Dockerfile must not use unpinned :latest tag (CWE-668)."
    )


def test_backend_dockerfile_non_root_user():
    """Verify backend/Dockerfile creates and switches to a dedicated non-root user (CWE-250)."""
    content = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    # Must contain user creation (useradd or adduser)
    assert re.search(r"(?:useradd|adduser)\b", content), (
        "Backend Dockerfile must create a dedicated non-root user (CWE-250)."
    )

    # Must contain USER instruction switching to non-root
    user_match = re.search(r"^USER\s+([^\s]+)", content, re.MULTILINE)
    assert user_match is not None, "Backend Dockerfile must define a USER directive."
    assert user_match.group(1).lower() in ("app", "appuser", "nonroot", "1000", "1001", "10001"), (
        f"Backend Dockerfile must switch to non-root user, found: {user_match.group(1)}"
    )


def test_backend_dockerfile_healthcheck_directive():
    """Verify backend/Dockerfile configures HEALTHCHECK on /health/live (CLAUDE.md §15, CWE-345)."""
    content = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in content, (
        "Backend Dockerfile must define a HEALTHCHECK instruction per CLAUDE.md §15."
    )
    assert "/health/live" in content, (
        "Backend Dockerfile HEALTHCHECK must probe /health/live endpoint per CLAUDE.md §15."
    )
    assert "8000" in content, (
        "Backend Dockerfile HEALTHCHECK must target port 8000."
    )


def test_backend_dockerfile_port_and_entrypoint():
    """Verify backend/Dockerfile exposes port 8000 and runs uvicorn entrypoint."""
    content = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    assert re.search(r"^EXPOSE\s+8000", content, re.MULTILINE), (
        "Backend Dockerfile must expose port 8000."
    )
    assert "uvicorn" in content, (
        "Backend Dockerfile entrypoint/CMD must invoke uvicorn server."
    )
    assert "backend.app.main:app" in content, (
        "Backend Dockerfile entrypoint must target backend.app.main:app."
    )


# ============================================================================
# 3. Frontend Dockerfile Architecture & Hygiene Tests (CLAUDE.md §15)
# ============================================================================


def test_frontend_dockerfile_multi_stage_architecture():
    """Verify frontend/Dockerfile implements multi-stage build pattern with node:22-alpine."""
    content = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
    from_matches = re.findall(r"^FROM\s+([^\s]+)(?:\s+[Aa][Ss]\s+([^\s]+))?", content, re.MULTILINE)

    assert len(from_matches) >= 2, (
        "Frontend Dockerfile must define multi-stage build (deps, builder, runner)."
    )

    # Base image node:22-alpine
    assert re.search(r"node:22-alpine", content, re.IGNORECASE), (
        "Frontend Dockerfile must use node:22-alpine base image per CLAUDE.md §15."
    )
    assert not re.search(r"node:latest", content, re.IGNORECASE), (
        "Frontend Dockerfile must not use unpinned :latest tag (CWE-668)."
    )


def test_frontend_dockerfile_non_root_user():
    """Verify frontend/Dockerfile runs as non-root user (e.g. nextjs:nodejs, CWE-250)."""
    content = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

    user_match = re.search(r"^USER\s+([^\s]+)", content, re.MULTILINE)
    assert user_match is not None, "Frontend Dockerfile must define a USER directive."
    assert user_match.group(1).lower() in ("nextjs", "node", "nonroot", "1001", "10001"), (
        f"Frontend Dockerfile must switch to non-root user, found: {user_match.group(1)}"
    )


def test_frontend_dockerfile_healthcheck_directive():
    """Verify frontend/Dockerfile configures HEALTHCHECK on /api/health (CLAUDE.md §15)."""
    content = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in content, (
        "Frontend Dockerfile must define a HEALTHCHECK instruction per CLAUDE.md §15."
    )
    assert "/api/health" in content, (
        "Frontend Dockerfile HEALTHCHECK must probe /api/health endpoint per CLAUDE.md §15."
    )
    assert "3000" in content, (
        "Frontend Dockerfile HEALTHCHECK must target port 3000."
    )


def test_frontend_dockerfile_standalone_support_and_entrypoint():
    """Verify frontend/Dockerfile copies standalone build outputs and exposes port 3000."""
    content = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

    assert re.search(r"^EXPOSE\s+3000", content, re.MULTILINE), (
        "Frontend Dockerfile must expose port 3000."
    )
    assert "standalone" in content, (
        "Frontend Dockerfile must reference standalone output packaging per CLAUDE.md §15."
    )
    assert "server.js" in content, (
        "Frontend Dockerfile CMD/entrypoint must invoke server.js."
    )


def test_next_config_declares_standalone_output():
    """Verify frontend/next.config.ts configures output: 'standalone' (CLAUDE.md §15)."""
    content = NEXT_CONFIG.read_text(encoding="utf-8")
    assert re.search(r'output:\s*["\']standalone["\']', content), (
        'next.config.ts must declare output: "standalone" per CLAUDE.md §15.'
    )


# ============================================================================
# 4. .dockerignore Secret Leak & Hygiene Tests (CWE-200)
# ============================================================================


def test_root_dockerignore_excludes_sensitive_files():
    """Verify root .dockerignore filters secrets, virtual environments, and caches (CWE-200)."""
    content = ROOT_DOCKERIGNORE.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}

    must_exclude = [
        ".git",
        ".env",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
    ]
    for pattern in must_exclude:
        assert any(pattern in line for line in lines), (
            f"Root .dockerignore must filter '{pattern}' to prevent secret / cache leakage."
        )


def test_frontend_dockerignore_excludes_sensitive_files():
    """Verify frontend/.dockerignore filters node_modules, build caches, and env files (CWE-200)."""
    content = FRONTEND_DOCKERIGNORE.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}

    must_exclude = [
        "node_modules",
        ".next",
        ".env",
    ]
    for pattern in must_exclude:
        assert any(pattern in line for line in lines), (
            f"Frontend .dockerignore must filter '{pattern}'."
        )


# ============================================================================
# 5. Security Audit Tests (CWE-200, CWE-250, CWE-668)
# ============================================================================


def test_security_cwe_200_no_secrets_in_dockerfiles():
    """Security Audit (CWE-200): Ensure no API keys or plaintext passwords exist in Dockerfiles."""
    for path in (BACKEND_DOCKERFILE, FRONTEND_DOCKERFILE):
        content = path.read_text(encoding="utf-8")
        assert "sk-proj-" not in content, f"Hardcoded OpenAI key found in {path}"
        assert "sk-ant-" not in content, f"Hardcoded Anthropic key found in {path}"
        assert "ghp_" not in content, f"Hardcoded GitHub token found in {path}"
        assert "AWS_SECRET" not in content, f"Hardcoded AWS secret found in {path}"


def test_security_cwe_250_no_sudo_in_dockerfiles():
    """Security Audit (CWE-250): Ensure sudo is never installed or executed in Dockerfiles."""
    for path in (BACKEND_DOCKERFILE, FRONTEND_DOCKERFILE):
        content = path.read_text(encoding="utf-8")
        assert "sudo" not in content.lower(), f"Unnecessary privilege escalation tool 'sudo' found in {path}"
