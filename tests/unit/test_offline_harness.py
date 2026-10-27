import datetime
import jwt
import pytest
from backend.app.core.config import get_settings


def test_offline_env_vars_active(settings):
    """Verify that tests/conftest.py establishes fully offline environment defaults."""
    assert settings.DEMO_MODE is True
    assert settings.LLM_PROVIDER == "fake"
    assert settings.VECTOR_STORE == "memory"
    assert settings.USE_FAKE_REDIS is True
    assert settings.CHECKPOINT_DB_PATH == ":memory:"
    assert "sqlite" in settings.DATABASE_URL


def test_auth_fixtures_generate_valid_tokens(settings, admin_headers, agent_headers, viewer_headers):
    """Verify admin_headers, agent_headers, and viewer_headers fixtures produce valid HS256 JWTs."""
    secret = settings.effective_jwt_secret

    # Verify Admin fixture
    assert "Authorization" in admin_headers
    admin_token = admin_headers["Authorization"].split("Bearer ")[-1]
    admin_payload = jwt.decode(admin_token, secret, algorithms=["HS256"])
    assert admin_payload["role"] == "admin"
    assert admin_payload["email"] == "admin@clouddesk.demo"
    assert admin_payload["exp"] > datetime.datetime.now(datetime.timezone.utc).timestamp()

    # Verify Agent fixture
    assert "Authorization" in agent_headers
    agent_token = agent_headers["Authorization"].split("Bearer ")[-1]
    agent_payload = jwt.decode(agent_token, secret, algorithms=["HS256"])
    assert agent_payload["role"] == "agent"
    assert agent_payload["email"] == "sam.agent@clouddesk.demo"

    # Verify Viewer fixture
    assert "Authorization" in viewer_headers
    viewer_token = viewer_headers["Authorization"].split("Bearer ")[-1]
    viewer_payload = jwt.decode(viewer_token, secret, algorithms=["HS256"])
    assert viewer_payload["role"] == "viewer"
    assert viewer_payload["email"] == "vic.viewer@clouddesk.demo"


def test_client_fixture(client):
    """Verify shared client fixture connects seamlessly to FastAPI app."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


async def test_async_client_fixture(async_client):
    """Verify async_client fixture performs non-blocking async requests."""
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers
