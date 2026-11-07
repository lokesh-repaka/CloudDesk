"""Unit tests for the Redis connection factory and fakeredis fallback."""

import pytest

from backend.app.core.config import Settings
from backend.app.core.redis import close_redis_client, get_redis_client, probe_redis


class TestRedisCore:
    """Tests for Redis client factory, singleton lifecycle, and health probes."""

    @pytest.mark.asyncio
    async def test_get_redis_client_fake(self, settings: Settings):
        """In offline/test mode, factory returns a functional FakeRedis client."""
        client = get_redis_client()
        assert client is not None

        # Verify async operations
        await client.set("test_key", "test_value")
        val = await client.get("test_key")
        assert val == "test_value"

        # Verify numeric operations and expiration
        await client.delete("counter_key")
        count = await client.incr("counter_key")
        assert count == 1
        await client.expire("counter_key", 60)
        ttl = await client.ttl("counter_key")
        assert 0 < ttl <= 60

        await client.delete("test_key", "counter_key")

    @pytest.mark.asyncio
    async def test_get_redis_client_singleton(self):
        """Consecutive calls return the same singleton client instance."""
        client1 = get_redis_client()
        client2 = get_redis_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_redis_client(self):
        """close_redis_client closes connection and clears singleton reference."""
        client1 = get_redis_client()
        await close_redis_client()
        client2 = get_redis_client()
        assert client1 is not client2
        await close_redis_client()

    @pytest.mark.asyncio
    async def test_probe_redis_success(self):
        """probe_redis returns True when ping succeeds."""
        is_alive = await probe_redis()
        assert is_alive is True

    @pytest.mark.asyncio
    async def test_probe_redis_failure(self, monkeypatch):
        """probe_redis returns False when Redis raises an exception."""
        client = get_redis_client()

        async def _mock_ping():
            raise ConnectionError("Simulated Redis outage")

        monkeypatch.setattr(client, "ping", _mock_ping)
        is_alive = await probe_redis()
        assert is_alive is False
