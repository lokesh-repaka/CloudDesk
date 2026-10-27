import datetime
import os

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

# 1. Establish fully offline environment variables BEFORE importing application or settings
os.environ["DEMO_MODE"] = "true"
os.environ["ENVIRONMENT"] = "development"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["VECTOR_STORE"] = "memory"
os.environ["USE_FAKE_REDIS"] = "true"
os.environ["REDIS_URL"] = ""
os.environ["CHECKPOINT_DB_PATH"] = ":memory:"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = "clouddesk-offline-test-jwt-secret-min-32-chars"
os.environ["SUPABASE_JWT_SECRET"] = ""

from backend.app.core.config import Settings, get_settings
from backend.app.main import app


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Session-scoped offline settings fixture."""
    return get_settings()


def create_offline_token(email: str, role: str, sub: str, secret: str) -> str:
    """Generate a test JWT token valid for 8 hours signed with the test secret."""
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(hours=8)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(scope="session")
def admin_token(settings: Settings) -> str:
    """Token for demo admin user."""
    return create_offline_token(
        email="admin@clouddesk.demo",
        role="admin",
        sub="usr-admin-001",
        secret=settings.effective_jwt_secret,
    )


@pytest.fixture(scope="session")
def agent_token(settings: Settings) -> str:
    """Token for demo agent user."""
    return create_offline_token(
        email="sam.agent@clouddesk.demo",
        role="agent",
        sub="usr-agent-002",
        secret=settings.effective_jwt_secret,
    )


@pytest.fixture(scope="session")
def viewer_token(settings: Settings) -> str:
    """Token for demo viewer user."""
    return create_offline_token(
        email="vic.viewer@clouddesk.demo",
        role="viewer",
        sub="usr-viewer-003",
        secret=settings.effective_jwt_secret,
    )


@pytest.fixture(scope="session")
def admin_headers(admin_token: str) -> dict[str, str]:
    """Authorization headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def agent_headers(agent_token: str) -> dict[str, str]:
    """Authorization headers for agent user."""
    return {"Authorization": f"Bearer {agent_token}"}


@pytest.fixture(scope="session")
def viewer_headers(viewer_token: str) -> dict[str, str]:
    """Authorization headers for viewer user."""
    return {"Authorization": f"Bearer {viewer_token}"}


@pytest.fixture
def client():
    """Synchronous FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client():
    """Asynchronous HTTPX client fixture configured with ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
