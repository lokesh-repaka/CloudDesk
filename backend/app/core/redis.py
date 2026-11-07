"""Redis connection factory and fakeredis fallback provider.

Supports real Redis connections (via redis.asyncio) and in-memory fakeredis
for zero-dependency local demonstration and deterministic unit testing.
"""

import logging
from typing import Any

import redis

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

REDIS_EXCEPTIONS = (redis.RedisError, ConnectionError, TimeoutError, OSError)
_redis_client: Any | None = None


def get_redis_client() -> Any:
    """Return an active async Redis client singleton.

    Uses fakeredis.aioredis when USE_FAKE_REDIS is enabled or REDIS_URL is omitted.
    Otherwise establishes a connection pool to the real Redis service.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    settings = get_settings()

    if settings.is_fake_redis:
        import fakeredis.aioredis

        _redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        logger.debug("Initialized in-memory FakeRedis client")
    else:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        logger.debug("Initialized async Redis client connecting to %s", settings.REDIS_URL)

    return _redis_client


async def close_redis_client() -> None:
    """Close and dispose of the active Redis client singleton."""
    global _redis_client
    if _redis_client is not None:
        try:
            if hasattr(_redis_client, "aclose"):
                await _redis_client.aclose()
            elif hasattr(_redis_client, "close"):
                res = _redis_client.close()
                if hasattr(res, "__await__"):
                    await res
        except REDIS_EXCEPTIONS as err:
            logger.warning("Error closing Redis connection: %s", err)
        finally:
            _redis_client = None


async def probe_redis() -> bool:
    """Check connectivity to Redis via PING command."""
    try:
        client = get_redis_client()
        result = await client.ping()
        return bool(result)
    except REDIS_EXCEPTIONS as err:
        logger.warning("Redis probe failed: %s", err)
        return False
