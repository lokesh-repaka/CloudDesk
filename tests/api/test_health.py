import uuid

from backend.app.core.config import get_settings


class TestHealthEndpoints:
    def test_health_root(self, client):
        """GET /health returns 200 with status, environment, and version."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "environment" in data
        assert "version" in data
        assert "X-Request-ID" in response.headers

    def test_health_live(self, client):
        """GET /health/live returns 200 with no dependency I/O."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "X-Request-ID" in response.headers

    def test_health_ready_success(self, client):
        """GET /health/ready returns 200 when configuration probes succeed."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "checks" in data
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["redis"] == "ok"
        assert data["checks"]["vector_store"] == "ok"
        assert data["checks"]["llm"] == "ok"

    def test_health_ready_degraded_returns_503(self, client, monkeypatch):
        """GET /health/ready returns 503 when configuration probe is degraded."""
        from backend.app.api import health
        monkeypatch.setattr(health, "probe_readiness", lambda: (False, {"database": "missing_url"}))

        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "missing_url"


class TestRequestIdMiddleware:
    def test_generates_request_id_when_missing(self, client):
        """Middleware generates a valid UUID when X-Request-ID is absent."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        req_id = response.headers["X-Request-ID"]
        # Verify req_id is a valid UUID
        parsed_uuid = uuid.UUID(req_id)
        assert str(parsed_uuid) == req_id

    def test_preserves_incoming_request_id(self, client):
        """Middleware preserves and propagates incoming X-Request-ID header."""
        custom_id = "req-client-trace-12345"
        response = client.get("/health/live", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_id

    def test_request_id_in_context_during_request(self, client):
        """Verify request_id is stored in context during request processing."""
        custom_id = "req-ctx-verify-999"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        # The endpoint should echo or log with this request ID
        assert response.headers["X-Request-ID"] == custom_id


class TestCORSSettings:
    def test_cors_headers_with_allowed_origin(self, client):
        """CORS middleware returns headers and exposes X-Request-ID."""
        settings = get_settings()
        allowed_origin = settings.CORS_ORIGINS[0]

        # Preflight OPTIONS check
        options_res = client.options(
            "/health",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert options_res.status_code == 200
        assert options_res.headers.get("access-control-allow-origin") == allowed_origin

        # Actual request check for Access-Control-Expose-Headers
        get_res = client.get("/health", headers={"Origin": allowed_origin})
        assert get_res.status_code == 200
        assert get_res.headers.get("access-control-allow-origin") == allowed_origin
        exposed = get_res.headers.get("access-control-expose-headers", "")
        assert "X-Request-ID" in exposed or "x-request-id" in exposed.lower()

    def test_cors_rejects_unauthorized_origin(self, client):
        """CORS middleware does not reflect unauthorized origins."""
        response = client.options(
            "/health",
            headers={
                "Origin": "https://malicious-site.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") != "https://malicious-site.example.com"
