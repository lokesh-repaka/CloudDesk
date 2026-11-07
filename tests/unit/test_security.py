"""Unit and integration tests for JWT authentication and role-based access control (RBAC).

Covers:
- HS256 JWT access token generation and decoding
- Expiration, tampering, and none-algorithm rejection
- Role hierarchy enforcement: viewer (1) < agent (2) < admin (3)
- FastAPI dependency injection (get_current_user, require_role)
- Acceptance criteria: AC-061, AC-062
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.security import (
    ROLE_HIERARCHY,
    AuthenticatedUser,
    create_access_token,
    decode_access_token,
    get_current_user,
    require_role,
)
from backend.app.schemas.common import RoleEnum


class TestTokenGenerationAndDecoding:
    """Tests for token generation and signature validation."""

    def test_create_access_token_default_expiry(self, settings: Settings):
        """Token contains claims and defaults to 8 hours expiration."""
        payload = {"sub": "usr-test-001", "email": "test@clouddesk.demo", "role": "agent"}
        token = create_access_token(payload)

        decoded = jwt.decode(token, settings.effective_jwt_secret, algorithms=["HS256"])
        assert decoded["sub"] == "usr-test-001"
        assert decoded["email"] == "test@clouddesk.demo"
        assert decoded["role"] == "agent"
        assert "iat" in decoded
        assert "exp" in decoded

        # Default expiry should be 8 hours (28800 seconds) within a small tolerance
        delta = decoded["exp"] - decoded["iat"]
        assert 28790 <= delta <= 28810

    def test_create_access_token_custom_expiry(self, settings: Settings):
        """Token respects custom expires_delta."""
        payload = {"sub": "usr-test-002", "email": "custom@clouddesk.demo", "role": "viewer"}
        custom_delta = timedelta(minutes=15)
        token = create_access_token(payload, expires_delta=custom_delta)

        decoded = jwt.decode(token, settings.effective_jwt_secret, algorithms=["HS256"])
        delta = decoded["exp"] - decoded["iat"]
        assert 890 <= delta <= 910

    def test_decode_access_token_valid(self):
        """decode_access_token successfully validates and extracts payload."""
        payload = {"sub": "usr-123", "email": "user@clouddesk.demo", "role": "admin"}
        token = create_access_token(payload)

        decoded = decode_access_token(token)
        assert decoded["sub"] == "usr-123"
        assert decoded["email"] == "user@clouddesk.demo"
        assert decoded["role"] == "admin"

    def test_decode_access_token_expired_raises_401(self, settings: Settings):
        """Expired JWT raises HTTP 401 with 'Invalid or expired token'."""
        past_time = datetime.now(UTC) - timedelta(hours=1)
        expired_payload = {
            "sub": "usr-expired",
            "email": "expired@clouddesk.demo",
            "role": "agent",
            "iat": int((past_time - timedelta(minutes=5)).timestamp()),
            "exp": int(past_time.timestamp()),
        }
        token = jwt.encode(expired_payload, settings.effective_jwt_secret, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"

    def test_decode_access_token_tampered_signature_raises_401(self):
        """Token signed with wrong key raises HTTP 401."""
        tampered_token = jwt.encode(
            {"sub": "usr-hacker", "email": "hacker@evil.demo", "role": "admin"},
            "wrong-untrusted-secret-key-at-least-32-chars",
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(tampered_token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"

    def test_decode_access_token_none_algorithm_attack_rejected(self):
        """Penetration test: Token with 'none' algorithm must be rejected (CWE-345)."""
        # Manually construct an unsigned token (algorithm: none)
        header_b64 = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0"  # {"alg":"none","typ":"JWT"}
        payload_b64 = "eyJzdWIiOiJ1c3ItaGFjayIsImVtYWlsIjoiYUBiLmMiLCJyb2xlIjoiYWRtaW4ifQ"
        none_token = f"{header_b64}.{payload_b64}."

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(none_token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"

    def test_decode_access_token_malformed_string_raises_401(self):
        """Random unparseable string raises HTTP 401."""
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("definitely-not-a-valid-jwt-token")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"


class TestCurrentUserDependency:
    """Tests for get_current_user FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid(self):
        """Valid credentials resolve to AuthenticatedUser domain model."""
        token = create_access_token(
            {"sub": "usr-valid-01", "email": "agent@clouddesk.demo", "role": "agent"}
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        user = await get_current_user(credentials)
        assert isinstance(user, AuthenticatedUser)
        assert user.user_id == "usr-valid-01"
        assert user.email == "agent@clouddesk.demo"
        assert user.role == RoleEnum.AGENT

    @pytest.mark.asyncio
    async def test_get_current_user_missing_credentials_raises_401(self):
        """None credentials raise HTTP 401 with WWW-Authenticate header."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_get_current_user_missing_required_claims_raises_401(self):
        """Token missing required claim (e.g. email) raises HTTP 401."""
        token = create_access_token({"sub": "usr-incomplete", "role": "agent"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_role_claim_raises_401(self):
        """Token with unknown role raises HTTP 401."""
        token = create_access_token(
            {"sub": "usr-super", "email": "super@demo.com", "role": "super_root"}
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"


class TestRoleHierarchyAndAuthorization:
    """Tests for AC-061 numerical hierarchy and require_role authorization."""

    def test_role_hierarchy_values(self):
        """Verifies strict numerical hierarchy: viewer (1) < agent (2) < admin (3)."""
        assert ROLE_HIERARCHY[RoleEnum.VIEWER] == 1
        assert ROLE_HIERARCHY[RoleEnum.AGENT] == 2
        assert ROLE_HIERARCHY[RoleEnum.ADMIN] == 3
        assert (
            ROLE_HIERARCHY[RoleEnum.VIEWER]
            < ROLE_HIERARCHY[RoleEnum.AGENT]
            < ROLE_HIERARCHY[RoleEnum.ADMIN]
        )

    @pytest.mark.asyncio
    async def test_require_role_viewer_access(self):
        """require_role('viewer') permits viewer, agent, and admin."""
        check_viewer = require_role(RoleEnum.VIEWER)

        viewer_user = AuthenticatedUser(user_id="v1", email="v@demo.com", role=RoleEnum.VIEWER)
        agent_user = AuthenticatedUser(user_id="a1", email="a@demo.com", role=RoleEnum.AGENT)
        admin_user = AuthenticatedUser(user_id="adm1", email="adm@demo.com", role=RoleEnum.ADMIN)

        assert await check_viewer(viewer_user) == viewer_user
        assert await check_viewer(agent_user) == agent_user
        assert await check_viewer(admin_user) == admin_user

    @pytest.mark.asyncio
    async def test_require_role_agent_access(self):
        """require_role('agent') permits agent and admin; forbids viewer."""
        check_agent = require_role(RoleEnum.AGENT)

        viewer_user = AuthenticatedUser(user_id="v1", email="v@demo.com", role=RoleEnum.VIEWER)
        agent_user = AuthenticatedUser(user_id="a1", email="a@demo.com", role=RoleEnum.AGENT)
        admin_user = AuthenticatedUser(user_id="adm1", email="adm@demo.com", role=RoleEnum.ADMIN)

        # Viewer should be forbidden
        with pytest.raises(HTTPException) as exc_info:
            await check_agent(viewer_user)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

        # Agent and Admin pass
        assert await check_agent(agent_user) == agent_user
        assert await check_agent(admin_user) == admin_user

    @pytest.mark.asyncio
    async def test_require_role_admin_access(self):
        """require_role('admin') permits admin only; forbids agent and viewer."""
        check_admin = require_role(RoleEnum.ADMIN)

        viewer_user = AuthenticatedUser(user_id="v1", email="v@demo.com", role=RoleEnum.VIEWER)
        agent_user = AuthenticatedUser(user_id="a1", email="a@demo.com", role=RoleEnum.AGENT)
        admin_user = AuthenticatedUser(user_id="adm1", email="adm@demo.com", role=RoleEnum.ADMIN)

        with pytest.raises(HTTPException) as exc_info:
            await check_admin(viewer_user)
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as exc_info:
            await check_admin(agent_user)
        assert exc_info.value.status_code == 403

        assert await check_admin(admin_user) == admin_user

    def test_require_role_accepts_string_or_enum(self):
        """require_role normalizes string input to RoleEnum."""
        dep_str = require_role("agent")
        dep_enum = require_role(RoleEnum.AGENT)
        assert dep_str.min_role == RoleEnum.AGENT
        assert dep_enum.min_role == RoleEnum.AGENT

    def test_require_role_invalid_role_raises_value_error(self):
        """Initializing require_role with non-existent role raises ValueError."""
        with pytest.raises(ValueError):
            require_role("super_god_mode")


class TestRbacIntegrationWithFastApi:
    """Integration test simulating authenticated endpoints using TestClient."""

    @pytest.fixture
    def rbac_app(self):
        """Test application with endpoints gated by different role tiers."""
        test_app = FastAPI()

        viewer_guard = require_role(RoleEnum.VIEWER)
        agent_guard = require_role(RoleEnum.AGENT)
        admin_guard = require_role(RoleEnum.ADMIN)

        @test_app.get("/api/test/public")
        def public_endpoint():
            return {"status": "public"}

        @test_app.get("/api/test/viewer")
        def viewer_endpoint(user: Annotated[AuthenticatedUser, Depends(viewer_guard)]):
            return {"role": user.role.value, "access": "viewer"}

        @test_app.get("/api/test/agent")
        def agent_endpoint(user: Annotated[AuthenticatedUser, Depends(agent_guard)]):
            return {"role": user.role.value, "access": "agent"}

        @test_app.get("/api/test/admin")
        def admin_endpoint(user: Annotated[AuthenticatedUser, Depends(admin_guard)]):
            return {"role": user.role.value, "access": "admin"}

        return test_app

    def test_public_endpoint_accessible_without_auth(self, rbac_app):
        """Public endpoints are accessible without Authorization header."""
        client = TestClient(rbac_app)
        res = client.get("/api/test/public")
        assert res.status_code == 200
        assert res.json() == {"status": "public"}

    def test_protected_endpoints_reject_unauthenticated(self, rbac_app):
        """Protected endpoints return 401 when Authorization header is absent."""
        client = TestClient(rbac_app)
        for path in ["/api/test/viewer", "/api/test/agent", "/api/test/admin"]:
            res = client.get(path)
            assert res.status_code == 401
            assert res.json() == {"detail": "Invalid or expired token"}

    def test_viewer_access_boundaries(self, rbac_app, viewer_headers):
        """Viewer role accesses viewer endpoint; blocked from agent and admin endpoints."""
        client = TestClient(rbac_app)

        res_viewer = client.get("/api/test/viewer", headers=viewer_headers)
        assert res_viewer.status_code == 200

        res_agent = client.get("/api/test/agent", headers=viewer_headers)
        assert res_agent.status_code == 403

        res_admin = client.get("/api/test/admin", headers=viewer_headers)
        assert res_admin.status_code == 403

    def test_agent_access_boundaries(self, rbac_app, agent_headers):
        """Agent role accesses viewer and agent endpoints; blocked from admin endpoint."""
        client = TestClient(rbac_app)

        res_viewer = client.get("/api/test/viewer", headers=agent_headers)
        assert res_viewer.status_code == 200

        res_agent = client.get("/api/test/agent", headers=agent_headers)
        assert res_agent.status_code == 200

        res_admin = client.get("/api/test/admin", headers=agent_headers)
        assert res_admin.status_code == 403

    def test_admin_access_boundaries(self, rbac_app, admin_headers):
        """Admin role has unrestricted access across all role tiers."""
        client = TestClient(rbac_app)

        res_viewer = client.get("/api/test/viewer", headers=admin_headers)
        assert res_viewer.status_code == 200

        res_agent = client.get("/api/test/agent", headers=admin_headers)
        assert res_agent.status_code == 200

        res_admin = client.get("/api/test/admin", headers=admin_headers)
        assert res_admin.status_code == 200
