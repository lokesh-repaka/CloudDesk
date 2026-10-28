"""Integration and unit tests for demo authentication routes and token generation.

Covers:
- POST /api/v1/auth/login (exchanging demo/user credentials for HS256 JWT)
- GET /api/v1/auth/demo-tokens (fast token discovery for demo and local development)
- GET /api/v1/auth/me (authenticated user profile retrieval)
- POST /api/v1/auth/refresh (token renewal)
- Demo roles: admin@clouddesk.demo, sam.agent@clouddesk.demo, vic.viewer@clouddesk.demo
- Rejection of invalid credentials, malformed requests, and unauthenticated calls
"""

from backend.app.core.config import get_settings
from backend.app.core.security import decode_access_token
from backend.app.schemas.common import RoleEnum


class TestDemoLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_login_admin_success(self, client):
        """Admin demo credentials issue valid token with admin role."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@clouddesk.demo", "password": "any-password"},
        )
        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 28800
        assert data["user"]["email"] == "admin@clouddesk.demo"
        assert data["user"]["role"] == "admin"
        assert data["user"]["full_name"] == "Alice Admin"
        assert data["user"]["id"] == "usr-admin-001"

        # Verify decoded token contents
        payload = decode_access_token(data["access_token"])
        assert payload["sub"] == "usr-admin-001"
        assert payload["email"] == "admin@clouddesk.demo"
        assert payload["role"] == "admin"

    def test_login_agent_success(self, client):
        """Agent demo credentials issue valid token with agent role."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "sam.agent@clouddesk.demo"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["user"]["email"] == "sam.agent@clouddesk.demo"
        assert data["user"]["role"] == "agent"
        assert data["user"]["full_name"] == "Sam Agent"
        assert data["user"]["id"] == "usr-agent-002"

        payload = decode_access_token(data["access_token"])
        assert payload["role"] == "agent"

    def test_login_viewer_success(self, client):
        """Viewer demo credentials issue valid token with viewer role."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "vic.viewer@clouddesk.demo"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["user"]["email"] == "vic.viewer@clouddesk.demo"
        assert data["user"]["role"] == "viewer"
        assert data["user"]["full_name"] == "Vic Viewer"
        assert data["user"]["id"] == "usr-viewer-003"

        payload = decode_access_token(data["access_token"])
        assert payload["role"] == "viewer"

    def test_login_case_insensitive_email(self, client):
        """Email lookups normalize to lowercase."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "ADMIN@CLOUDDESK.DEMO"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "admin@clouddesk.demo"

    def test_login_unknown_email_returns_401(self, client):
        """Unrecognized email returns HTTP 401 with standard error envelope."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@unknown.com", "password": "password"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid credentials"

    def test_login_malformed_body_returns_422(self, client):
        """Empty or invalid payload returns HTTP 422 Unprocessable Entity."""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422


class TestDemoTokensEndpoint:
    """Tests for GET /api/v1/auth/demo-tokens."""

    def test_get_demo_tokens_success_in_demo_mode(self, client):
        """GET /api/v1/auth/demo-tokens returns all three demo roles with valid tokens."""
        response = client.get("/api/v1/auth/demo-tokens")
        assert response.status_code == 200
        data = response.json()

        assert "admin" in data
        assert "agent" in data
        assert "viewer" in data

        for role_name, expected_role in [
            ("admin", RoleEnum.ADMIN),
            ("agent", RoleEnum.AGENT),
            ("viewer", RoleEnum.VIEWER),
        ]:
            entry = data[role_name]
            assert entry["role"] == expected_role.value
            assert "token" in entry
            assert entry["expires_in"] == 28800

            # Verify that the generated demo token decodes successfully
            decoded = decode_access_token(entry["token"])
            assert decoded["role"] == expected_role.value
            assert decoded["email"] == entry["email"]

    def test_get_demo_tokens_disabled_in_production(self, client, monkeypatch):
        """Penetration test: Demo token endpoint must return 403 when DEMO_MODE is False (CWE-284)."""
        settings = get_settings()
        monkeypatch.setattr(settings, "DEMO_MODE", False)

        response = client.get("/api/v1/auth/demo-tokens")
        assert response.status_code == 403
        data = response.json()
        assert data["detail"] == "Demo tokens are disabled in this environment"


class TestCurrentUserProfileEndpoint:
    """Tests for GET /api/v1/auth/me."""

    def test_get_me_success_with_admin_token(self, client, admin_headers):
        """GET /api/v1/auth/me returns current authenticated user profile."""
        response = client.get("/api/v1/auth/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == "usr-admin-001"
        assert data["email"] == "admin@clouddesk.demo"
        assert data["role"] == "admin"
        assert "full_name" in data

    def test_get_me_success_with_agent_token(self, client, agent_headers):
        """GET /api/v1/auth/me returns agent profile."""
        response = client.get("/api/v1/auth/me", headers=agent_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == "usr-agent-002"
        assert data["email"] == "sam.agent@clouddesk.demo"
        assert data["role"] == "agent"

    def test_get_me_unauthenticated_returns_401(self, client):
        """GET /api/v1/auth/me without token returns HTTP 401."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid or expired token"

    def test_get_me_invalid_token_returns_401(self, client):
        """GET /api/v1/auth/me with invalid Bearer token returns HTTP 401."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer bad-token-here"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid or expired token"


class TestTokenRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh."""

    def test_refresh_token_success(self, client, agent_headers):
        """POST /api/v1/auth/refresh returns a fresh access token for authenticated caller."""
        response = client.post("/api/v1/auth/refresh", headers=agent_headers)
        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "sam.agent@clouddesk.demo"
        assert data["user"]["role"] == "agent"

        # Verify decoded refreshed token
        decoded = decode_access_token(data["access_token"])
        assert decoded["email"] == "sam.agent@clouddesk.demo"
        assert decoded["role"] == "agent"

    def test_refresh_token_unauthenticated_returns_401(self, client):
        """POST /api/v1/auth/refresh without token returns HTTP 401."""
        response = client.post("/api/v1/auth/refresh")
        assert response.status_code == 401


class TestEndToEndTokenFlow:
    """End-to-end integration test: login -> fetch me -> refresh -> re-fetch me."""

    def test_login_and_access_workflow(self, client):
        """Full lifecycle of logging in, consuming me endpoint, and refreshing token."""
        # 1. Login
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "sam.agent@clouddesk.demo"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        auth_header = {"Authorization": f"Bearer {token}"}

        # 2. Access /me
        me_res = client.get("/api/v1/auth/me", headers=auth_header)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "sam.agent@clouddesk.demo"

        # 3. Refresh token
        refresh_res = client.post("/api/v1/auth/refresh", headers=auth_header)
        assert refresh_res.status_code == 200
        new_token = refresh_res.json()["access_token"]
        new_auth_header = {"Authorization": f"Bearer {new_token}"}

        # 4. Access /me with refreshed token
        me_refreshed_res = client.get("/api/v1/auth/me", headers=new_auth_header)
        assert me_refreshed_res.status_code == 200
        assert me_refreshed_res.json()["email"] == "sam.agent@clouddesk.demo"
