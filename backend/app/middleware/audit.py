"""Immutable audit logging middleware for state-changing HTTP requests (N6 / US-021).

Intercepts all non-GET requests (POST, PUT, PATCH, DELETE) and records an immutable
audit log entry in the database with actor identity, client IP, HTTP method, route,
correlation request ID, response status code, and timestamp.
GET, HEAD, and OPTIONS requests are strictly excluded to avoid table bloat (AC-069).
"""

import logging

import jwt
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.app.core.database import get_session_factory
from backend.app.core.logging import get_request_id
from backend.app.core.security import decode_access_token
from backend.app.models.entities import AuditLog

logger = logging.getLogger(__name__)

# HTTP methods that do not alter application state
SAFE_READ_METHODS = {"GET", "HEAD", "OPTIONS"}

AUDIT_DB_EXCEPTIONS = (SQLAlchemyError, OSError, RuntimeError, ConnectionError)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that immutably logs every state-changing API request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Skip read-only requests (GET, HEAD, OPTIONS) to prevent table bloat (AC-069)
        if request.method in SAFE_READ_METHODS:
            return await call_next(request)

        # 2. Extract client IP (handle proxy forwarded headers)
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"

        # 3. Extract actor ID from Bearer token if present
        actor_id = "unauthenticated"
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            try:
                payload = decode_access_token(token)
                actor_id = str(payload.get("sub") or "unauthenticated")
            except (HTTPException, jwt.PyJWTError, ValueError, KeyError):
                # Token decode errors will be caught downstream by security dependencies
                actor_id = "unauthenticated"

        # 4. Execute downstream request pipeline
        response = await call_next(request)

        # 5. Extract correlation request ID
        request_id = (
            response.headers.get("X-Request-ID")
            or request.headers.get("X-Request-ID")
            or get_request_id()
            or "unknown"
        )

        # 6. Record immutable row in audit_logs table (AC-068)
        try:
            factory = get_session_factory()
            async with factory() as session:
                log_entry = AuditLog(
                    actor_id=actor_id,
                    client_ip=client_ip,
                    http_method=request.method,
                    route=request.url.path,
                    request_id=request_id,
                    status_code=response.status_code,
                )
                session.add(log_entry)
                await session.commit()
        except AUDIT_DB_EXCEPTIONS as err:
            logger.error("Failed to persist audit log entry: %s", err)

        return response
