from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import auth, customers, health, knowledge, tickets
from backend.app.core.config import get_settings
from backend.app.core.logging import setup_logging
from backend.app.middleware.request_id import RequestIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management: initialize logging, database tables, and demo bootstrap."""
    setup_logging()
    settings = get_settings()
    if settings.DEMO_MODE:
        from backend.app.core.database import create_tables
        from backend.app.rag.ingest import ingest_knowledge_base
        from backend.app.services.seed_service import bootstrap_demo_data

        await create_tables()
        await bootstrap_demo_data()
        await ingest_knowledge_base()
    yield
    from backend.app.core.database import dispose_engine
    from backend.app.core.redis import close_redis_client

    await dispose_engine()
    await close_redis_client()


def create_application() -> FastAPI:
    """FastAPI application factory configuring middleware and routing."""
    settings = get_settings()

    app = FastAPI(
        title="CloudDesk Support API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware order (outermost last): CORS -> RequestId -> RateLimit -> Audit
    # In Starlette, later-added middleware wraps earlier-added middleware.
    from backend.app.middleware.audit import AuditMiddleware
    from backend.app.middleware.rate_limit import RateLimitMiddleware

    app.add_middleware(AuditMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
    )

    # Health routes (unprefixed as per CLAUDE.md)
    app.include_router(health.router)

    # API v1 routes
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["tickets"])
    app.include_router(customers.router, prefix="/api/v1/customers", tags=["customers"])
    app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])

    return app


app = create_application()
