from fastapi import APIRouter
from fastapi.responses import JSONResponse
from backend.app.core.config import get_settings

router = APIRouter(tags=["health"])


def probe_readiness() -> tuple[bool, dict[str, str]]:
    """Probe system configuration readiness without opening network connections (Phase 1)."""
    settings = get_settings()
    checks: dict[str, str] = {}
    is_ready = True

    # Database configuration probe
    if settings.DATABASE_URL and ("sqlite" in settings.DATABASE_URL or "postgresql" in settings.DATABASE_URL):
        checks["database"] = "ok"
    else:
        checks["database"] = "missing_database_url"
        is_ready = False

    # Redis / FakeRedis configuration probe
    if settings.USE_FAKE_REDIS or bool(settings.REDIS_URL):
        checks["redis"] = "ok"
    else:
        checks["redis"] = "missing_redis_url"
        is_ready = False

    # Vector store configuration probe
    if settings.VECTOR_STORE == "memory":
        checks["vector_store"] = "ok"
    elif settings.VECTOR_STORE == "qdrant" and settings.QDRANT_URL:
        checks["vector_store"] = "ok"
    else:
        checks["vector_store"] = "unconfigured_vector_store"
        is_ready = False

    # LLM configuration probe
    if settings.LLM_PROVIDER in ("fake", "openai", "anthropic", "azure", "google"):
        checks["llm"] = "ok"
    else:
        checks["llm"] = "unknown_llm_provider"
        is_ready = False

    return is_ready, checks


@router.get("/health")
async def health_root():
    """Unprefixed general health endpoint with environment and version."""
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }


@router.get("/health/live")
async def health_live():
    """Liveness probe: returns 200 with zero dependency I/O."""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready():
    """Readiness probe: validates configuration health and returns 503 when degraded."""
    is_ready, checks = probe_readiness()
    if is_ready:
        return {"status": "ready", "checks": checks}
    return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
