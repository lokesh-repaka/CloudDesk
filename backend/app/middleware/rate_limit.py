"""Redis-backed fixed-window rate limiting middleware.

Enforces per-client request ceilings across 60-second windows using Redis INCR/EXPIRE
as defined in CLAUDE.md section 10 and requirements N2.
Exempts health probes and OPTIONS preflight requests.
Fails open on Redis communication failures to preserve service availability.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app.core.config import get_settings
from backend.app.core.redis import REDIS_EXCEPTIONS, get_redis_client

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting (system probes must never be blocked)
EXEMPT_PATHS = {
    "/health",
    "/health/live",
    "/health/ready",
}

WINDOW_SIZE_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter utilizing Redis counters partitioned by client IP."""

    def __init__(self, app, requests_per_minute: int | None = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Exempt CORS preflights and health check probes
        if request.method == "OPTIONS" or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # 2. Extract client IP (handle proxy forwarded headers)
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"

        limit = self.requests_per_minute or get_settings().RATE_LIMIT_PER_MINUTE

        now = int(time.time())
        window = now // WINDOW_SIZE_SECONDS
        window_reset = (window + 1) * WINDOW_SIZE_SECONDS
        retry_after = max(1, window_reset - now)
        key = f"ratelimit:{client_ip}:{window}"

        # 3. Increment counter atomically in Redis
        try:
            redis = get_redis_client()
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, WINDOW_SIZE_SECONDS)
        except REDIS_EXCEPTIONS as err:
            logger.warning("Redis rate limit unavailable; failing open: %s", err)
            return await call_next(request)

        # 4. Check if client exceeded window limit
        if current > limit:
            logger.warning(
                "Rate limit exceeded for client %s: %d/%d requests in window %d",
                client_ip,
                current,
                limit,
                window,
            )
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(window_reset),
            }
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Try again in {retry_after} seconds."},
                headers=headers,
            )

        # 5. Allow request to proceed and attach standard rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
        response.headers["X-RateLimit-Reset"] = str(window_reset)
        return response
