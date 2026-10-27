from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import health
from backend.app.core.config import get_settings
from backend.app.core.logging import setup_logging
from backend.app.middleware.request_id import RequestIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management: initialize logging and future database tables."""
    setup_logging()
    yield


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

    # Middleware order (outermost last): CORS -> RequestId
    # Adding RequestId first, then CORS makes CORS outermost.
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Health routes (unprefixed as per CLAUDE.md)
    app.include_router(health.router)

    return app


app = create_application()
