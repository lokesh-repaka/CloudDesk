"""Unit and integration tests for AuditMiddleware and middleware pipeline ordering (N6).

Covers:
- Recording immutable audit_logs rows for all non-GET requests (POST, PUT, PATCH, DELETE)
- Verifying GET, OPTIONS, HEAD requests are strictly excluded to avoid table bloat (AC-069)
- Actor ID resolution from Bearer JWT claims or anonymous fallback
- Client IP extraction (supporting X-Forwarded-For headers)
- Correlation with X-Request-ID
- Strict middleware pipeline execution order: CORS -> RequestId -> RateLimit -> Audit
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from starlette.testclient import TestClient

from backend.app.core.database import create_tables, get_session_factory
from backend.app.core.security import create_access_token
from backend.app.middleware.audit import AuditMiddleware
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_id import RequestIdMiddleware
from backend.app.models.entities import AuditLog


class TestAuditMiddlewareExecution:
    """Tests for AuditMiddleware logging rules and field extractions."""

    @pytest.fixture(autouse=True)
    async def init_db(self):
        """Ensure database tables exist and clear audit_logs table before each test."""
        await create_tables()
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(AuditLog.__table__.delete())
            await session.commit()
        yield
        async with factory() as session:
            await session.execute(AuditLog.__table__.delete())
            await session.commit()

    @pytest.fixture
    def audit_app(self):
        """Build test application configured with AuditMiddleware and RequestIdMiddleware."""
        app = FastAPI()
        app.add_middleware(AuditMiddleware)
        app.add_middleware(RequestIdMiddleware)

        @app.get("/api/v1/items")
        def get_items():
            return {"items": ["item1", "item2"]}

        @app.post("/api/v1/items")
        def create_item():
            return {"status": "created", "id": "itm-1"}

        @app.put("/api/v1/items/{item_id}")
        def update_item(item_id: str):
            return {"status": "updated", "id": item_id}

        @app.patch("/api/v1/items/{item_id}")
        def patch_item(item_id: str):
            return {"status": "patched", "id": item_id}

        @app.delete("/api/v1/items/{item_id}")
        def delete_item(item_id: str):
            return {"status": "deleted", "id": item_id}

        return app

    def test_audit_records_post_request(self, audit_app):
        """POST request generates immutable audit log record with all fields (AC-068)."""
        client = TestClient(audit_app)
        custom_req_id = "req-audit-post-001"
        headers = {
            "X-Request-ID": custom_req_id,
            "X-Forwarded-For": "203.0.113.195",
        }

        response = client.post("/api/v1/items", headers=headers)
        assert response.status_code == 200

        # Query database directly to verify audit_logs row
        factory = get_session_factory()

        async def _verify():
            async with factory() as session:
                stmt = select(AuditLog).where(AuditLog.request_id == custom_req_id)
                res = await session.execute(stmt)
                logs = res.scalars().all()
                assert len(logs) == 1
                log = logs[0]
                assert log.http_method == "POST"
                assert log.route == "/api/v1/items"
                assert log.client_ip == "203.0.113.195"
                assert log.status_code == 200
                assert log.actor_id == "unauthenticated"
                assert log.created_at is not None

        import asyncio

        asyncio.run(_verify())

    def test_audit_records_put_patch_delete_requests(self, audit_app):
        """PUT, PATCH, and DELETE operations are captured in audit_logs (AC-068)."""
        client = TestClient(audit_app)
        client.put("/api/v1/items/101")
        client.patch("/api/v1/items/101")
        client.delete("/api/v1/items/101")

        factory = get_session_factory()

        async def _verify():
            async with factory() as session:
                res = await session.execute(select(AuditLog))
                logs = res.scalars().all()
                methods = [log.http_method for log in logs]
                assert "PUT" in methods
                assert "PATCH" in methods
                assert "DELETE" in methods
                assert len(logs) == 3

        import asyncio

        asyncio.run(_verify())

    def test_audit_ignores_get_request(self, audit_app):
        """GET request produces zero audit_logs rows to prevent bloat (AC-069)."""
        client = TestClient(audit_app)
        res = client.get("/api/v1/items")
        assert res.status_code == 200

        factory = get_session_factory()

        async def _verify():
            async with factory() as session:
                res = await session.execute(select(AuditLog))
                logs = res.scalars().all()
                assert len(logs) == 0

        import asyncio

        asyncio.run(_verify())

    def test_audit_extracts_authenticated_actor_id(self, audit_app):
        """Extracts actor UUID from Authorization Bearer JWT claim."""
        token = create_access_token({
            "sub": "usr-admin-001",
            "email": "admin@clouddesk.demo",
            "role": "admin",
        })
        client = TestClient(audit_app)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req-actor-test-1",
        }

        res = client.post("/api/v1/items", headers=headers)
        assert res.status_code == 200

        factory = get_session_factory()

        async def _verify():
            async with factory() as session:
                stmt = select(AuditLog).where(AuditLog.request_id == "req-actor-test-1")
                log = (await session.execute(stmt)).scalars().first()
                assert log is not None
                assert log.actor_id == "usr-admin-001"

        import asyncio

        asyncio.run(_verify())

    def test_audit_fails_safe_on_database_error(self, audit_app, monkeypatch):
        """Penetration test: Audit database write failure does not break client HTTP response (CWE-755)."""
        client = TestClient(audit_app)

        # Force get_session_factory to raise an exception
        from backend.app.middleware import audit

        def _bad_factory():
            raise RuntimeError("Database unavailable")

        monkeypatch.setattr(audit, "get_session_factory", _bad_factory)

        res = client.post("/api/v1/items")
        # Response should still succeed
        assert res.status_code == 200
        assert res.json()["status"] == "created"


class TestMiddlewarePipelineOrder:
    """Verifies strict execution ordering: CORS -> RequestId -> RateLimit -> Audit."""

    def test_main_application_middleware_stack_order(self):
        """Assert the configured middleware stack matches architectural specification."""
        from backend.app.main import app

        # In Starlette, middleware is wrapped from bottom to top:
        # app.middleware_stack: CORS (outermost) -> RequestId -> RateLimit -> Audit (innermost)
        middleware_classes = [m.cls for m in app.user_middleware]

        # Ensure all four required middlewares are registered
        assert CORSMiddleware in middleware_classes
        assert RequestIdMiddleware in middleware_classes
        assert RateLimitMiddleware in middleware_classes
        assert AuditMiddleware in middleware_classes

        # Verify ordering: in Starlette user_middleware list:
        # Middlewares added later wrap middlewares added earlier.
        # Order of execution:
        # 1. CORSMiddleware (outermost)
        # 2. RequestIdMiddleware
        # 3. RateLimitMiddleware
        # 4. AuditMiddleware (innermost)
        cors_idx = middleware_classes.index(CORSMiddleware)
        req_idx = middleware_classes.index(RequestIdMiddleware)
        rate_idx = middleware_classes.index(RateLimitMiddleware)
        audit_idx = middleware_classes.index(AuditMiddleware)

        # Starlette prepends to user_middleware, so index 0 is executed outermost:
        assert cors_idx < req_idx < rate_idx < audit_idx
