"""Unit and integration tests for Redis-backed fixed-window rate limiting middleware (N2)."""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.app.core.redis import close_redis_client, get_redis_client
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_id import RequestIdMiddleware


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware fixed window enforcement and response headers."""

    @pytest.fixture(autouse=True)
    async def cleanup_redis(self):
        """Clean up Redis keys before and after each test."""
        client = get_redis_client()
        await client.flushall()
        yield
        await client.flushall()
        await close_redis_client()

    @pytest.fixture
    def app_with_rate_limiter(self):
        """Build test application configured with RateLimitMiddleware and RequestIdMiddleware."""
        app = FastAPI()

        # Add RateLimitMiddleware with limit=5 for deterministic testing
        app.add_middleware(RateLimitMiddleware, requests_per_minute=5)
        app.add_middleware(RequestIdMiddleware)

        @app.get("/health/live")
        def health_live():
            return {"status": "ok"}

        @app.get("/api/v1/resource")
        def sample_resource():
            return {"data": "resource_content"}

        return app

    def test_rate_limit_allows_requests_under_ceiling(self, app_with_rate_limiter):
        """Requests under the rate limit return HTTP 200 with X-RateLimit headers."""
        client = TestClient(app_with_rate_limiter)
        headers = {"X-Forwarded-For": "198.51.100.1"}

        response = client.get("/api/v1/resource", headers=headers)
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "5"
        assert response.headers["X-RateLimit-Remaining"] == "4"
        assert "X-RateLimit-Reset" in response.headers
        assert "X-Request-ID" in response.headers

    def test_rate_limit_blocks_exceeding_ceiling_returns_429(self, app_with_rate_limiter):
        """Requests exceeding ceiling return HTTP 429 Too Many Requests with Retry-After (N2)."""
        client = TestClient(app_with_rate_limiter)
        headers = {"X-Forwarded-For": "198.51.100.2"}

        # Consume 5 allowed requests
        for i in range(5):
            res = client.get("/api/v1/resource", headers=headers)
            assert res.status_code == 200
            assert res.headers["X-RateLimit-Remaining"] == str(4 - i)

        # 6th request must be blocked
        res_blocked = client.get("/api/v1/resource", headers=headers)
        assert res_blocked.status_code == 429
        assert res_blocked.headers["X-RateLimit-Limit"] == "5"
        assert res_blocked.headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in res_blocked.headers
        assert int(res_blocked.headers["Retry-After"]) > 0
        assert "X-Request-ID" in res_blocked.headers

        data = res_blocked.json()
        assert "Rate limit exceeded" in data["detail"]

    def test_rate_limit_isolates_different_client_ips(self, app_with_rate_limiter):
        """Rate limits are partitioned by client IP; client B is not affected by client A."""
        client = TestClient(app_with_rate_limiter)
        headers_a = {"X-Forwarded-For": "198.51.100.10"}
        headers_b = {"X-Forwarded-For": "198.51.100.20"}

        # Exhaust limit for Client A
        for _ in range(5):
            client.get("/api/v1/resource", headers=headers_a)

        assert client.get("/api/v1/resource", headers=headers_a).status_code == 429

        # Client B should still be allowed
        res_b = client.get("/api/v1/resource", headers=headers_b)
        assert res_b.status_code == 200
        assert res_b.headers["X-RateLimit-Remaining"] == "4"

    def test_rate_limit_exempts_health_endpoints(self, app_with_rate_limiter):
        """Probes such as /health/live must never be blocked by rate limiting."""
        client = TestClient(app_with_rate_limiter)
        headers = {"X-Forwarded-For": "198.51.100.3"}

        # Fire 20 requests to /health/live (well beyond limit of 5)
        for _ in range(20):
            res = client.get("/health/live", headers=headers)
            assert res.status_code == 200

    def test_rate_limit_exempts_options_preflight(self, app_with_rate_limiter):
        """CORS OPTIONS preflight requests are exempt from rate limiting."""
        client = TestClient(app_with_rate_limiter)
        headers = {"X-Forwarded-For": "198.51.100.4"}

        for _ in range(10):
            res = client.options("/api/v1/resource", headers=headers)
            assert res.status_code in (200, 405)

    def test_rate_limit_fails_open_on_redis_error(self, app_with_rate_limiter, monkeypatch):
        """Penetration test: If Redis suffers connection failure, middleware fails open (CWE-755)."""
        redis_client = get_redis_client()

        async def _failing_incr(*args, **kwargs):
            raise ConnectionError("Redis server unavailable")

        monkeypatch.setattr(redis_client, "incr", _failing_incr)

        client = TestClient(app_with_rate_limiter)
        res = client.get("/api/v1/resource", headers={"X-Forwarded-For": "198.51.100.5"})

        # Request succeeds despite Redis outage
        assert res.status_code == 200
        assert res.json() == {"data": "resource_content"}
