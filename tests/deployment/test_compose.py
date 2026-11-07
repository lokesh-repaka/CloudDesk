"""Docker Compose Stack Deployment Tests (P14-3, CLAUDE.md §13, §15).

Verifies Docker Compose service architecture, dependency chaining (frontend -> backend -> redis, qdrant),
healthcheck probes, restart policies, named volumes, port mappings, and security hygiene in accordance with:
- CLAUDE.md §13 (compose services)
- CLAUDE.md §15 (frontend -> backend -> redis, qdrant, depends_on: service_healthy, named volumes, restart: unless-stopped)
- CWE-200 (Information Exposure / no plaintext production secrets)
- CWE-345 (Healthcheck and dependency integrity verification)
- CWE-668 (Resource isolation and pinned images)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


def _read_compose_text() -> str:
    assert COMPOSE_FILE.is_file(), f"Missing docker-compose.yml at {COMPOSE_FILE}"
    return COMPOSE_FILE.read_text(encoding="utf-8")


def _parse_compose() -> dict:
    """Minimal YAML parser for compose file validation without third-party parser dependency."""
    # Attempt import of PyYAML if available, else basic validation
    try:
        import yaml
        return yaml.safe_load(_read_compose_text())
    except ImportError:
        pass

    # Basic regex / structural fallback if yaml package is absent
    text = _read_compose_text()
    assert "services:" in text, "Compose file must contain 'services:' root key"
    return {"raw_text": text}


# ============================================================================
# 1. File Existence & Parsing Tests
# ============================================================================


def test_compose_file_exists():
    """Verify docker-compose.yml exists in the repository root."""
    assert COMPOSE_FILE.is_file(), (
        f"docker-compose.yml must exist at repository root ({COMPOSE_FILE})"
    )


def test_compose_declares_all_four_required_services():
    """Verify compose stack defines frontend, backend, redis, and qdrant (CLAUDE.md §15)."""
    text = _read_compose_text()

    for service in ("frontend", "backend", "redis", "qdrant"):
        pattern = rf"^\s{{2}}{service}:"
        assert re.search(pattern, text, re.MULTILINE), (
            f"Compose file must declare service '{service}'"
        )


# ============================================================================
# 2. Dependency Graph & Healthcheck Chaining Tests (CLAUDE.md §15)
# ============================================================================


def test_compose_dependency_chaining_and_health_conditions():
    """Verify frontend -> backend -> redis, qdrant with condition: service_healthy."""
    text = _read_compose_text()

    # Backend must depend on redis and qdrant with service_healthy
    assert re.search(r"backend:.*depends_on:.*redis:.*condition:\s*service_healthy", text, re.DOTALL), (
        "Backend service must depend on redis with condition: service_healthy"
    )
    assert re.search(r"backend:.*depends_on:.*qdrant:.*condition:\s*service_healthy", text, re.DOTALL), (
        "Backend service must depend on qdrant with condition: service_healthy"
    )

    # Frontend must depend on backend with service_healthy
    assert re.search(r"frontend:.*depends_on:.*backend:.*condition:\s*service_healthy", text, re.DOTALL), (
        "Frontend service must depend on backend with condition: service_healthy"
    )


def test_compose_all_services_define_healthchecks():
    """Verify redis, qdrant, backend, and frontend define active healthcheck probes (CWE-345)."""
    text = _read_compose_text()

    # Redis healthcheck: redis-cli ping
    assert "redis-cli" in text and "ping" in text, (
        "Redis service must define healthcheck using redis-cli ping"
    )

    # Qdrant healthcheck: healthz
    assert "healthz" in text, (
        "Qdrant service must define healthcheck probing healthz endpoint"
    )

    # Backend healthcheck: /health/live
    assert "/health/live" in text, (
        "Backend service must define healthcheck probing /health/live"
    )

    # Frontend healthcheck: /api/health
    assert "/api/health" in text, (
        "Frontend service must define healthcheck probing /api/health"
    )


# ============================================================================
# 3. Restart Policies & Named Volumes Tests (CLAUDE.md §15)
# ============================================================================


def test_compose_services_specify_restart_unless_stopped():
    """Verify all four services declare restart: unless-stopped (CLAUDE.md §15)."""
    text = _read_compose_text()
    matches = re.findall(r"restart:\s*[\"']?unless-stopped[\"']?", text)

    assert len(matches) >= 4, (
        f"All 4 services must specify 'restart: unless-stopped', found {len(matches)} occurrences."
    )


def test_compose_defines_named_volumes():
    """Verify top-level named volumes are defined for persistent data (CLAUDE.md §15)."""
    text = _read_compose_text()

    assert re.search(r"^volumes:\s*$", text, re.MULTILINE), (
        "docker-compose.yml must define a top-level 'volumes:' block"
    )
    assert "redis_data:" in text, "Must declare named volume 'redis_data'"
    assert "qdrant_data:" in text, "Must declare named volume 'qdrant_data'"


# ============================================================================
# 4. Port Mappings & Network Topology Tests
# ============================================================================


def test_compose_port_mappings():
    """Verify standard ports are exposed for local development access."""
    text = _read_compose_text()

    # Frontend 3000
    assert re.search(r"[\"']?3000:3000[\"']?", text), "Frontend must expose 3000:3000"
    # Backend 8000
    assert re.search(r"[\"']?8000:8000[\"']?", text), "Backend must expose 8000:8000"
    # Redis 6379
    assert re.search(r"[\"']?6379:6379[\"']?", text), "Redis must expose 6379:6379"
    # Qdrant 6333
    assert re.search(r"[\"']?6333:6333[\"']?", text), "Qdrant must expose 6333:6333"


def test_compose_defines_custom_network():
    """Verify services connect via a dedicated bridge network."""
    text = _read_compose_text()

    assert re.search(r"^networks:\s*$", text, re.MULTILINE), (
        "docker-compose.yml must define top-level 'networks:' block"
    )
    assert "clouddesk-net" in text or "clouddesk_network" in text or "default:" in text, (
        "docker-compose.yml must configure a dedicated network"
    )


# ============================================================================
# 5. Security & Secret Hygiene Audits (CWE-200, CWE-668)
# ============================================================================


def test_compose_no_hardcoded_secrets():
    """Security Audit (CWE-200): Ensure no real API keys or sensitive passwords in compose file."""
    text = _read_compose_text()

    assert "sk-proj-" not in text, "Real OpenAI key detected in docker-compose.yml"
    assert "sk-ant-" not in text, "Real Anthropic key detected in docker-compose.yml"
    assert "ghp_" not in text, "Real GitHub token detected in docker-compose.yml"
    assert "AKIA" not in text, "Real AWS key detected in docker-compose.yml"


def test_compose_service_images_pinned():
    """Security Audit (CWE-668): Ensure third-party images (redis, qdrant) use pinned version tags."""
    text = _read_compose_text()

    # Redis must be pinned, e.g. redis:7-alpine or redis:7.4-alpine
    assert re.search(r"image:\s*[\"']?redis:(?:7|7\.\d+)-alpine[\"']?", text), (
        "Redis image must use pinned version tag (e.g. redis:7-alpine)"
    )

    # Qdrant must be pinned
    assert re.search(r"image:\s*[\"']?qdrant/qdrant:v?1\.\d+[\"']?", text), (
        "Qdrant image must use pinned version tag (e.g. qdrant/qdrant:v1.12.1)"
    )

