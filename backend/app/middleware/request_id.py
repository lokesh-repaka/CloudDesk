import re
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from backend.app.core.logging import set_request_id, clear_context

# Allow alphanumeric, dashes, and underscores up to 128 chars; strip CRLF to prevent header injection
SAFE_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns or preserves X-Request-ID for every request and sets logging context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_id = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")

        if incoming_id and SAFE_REQUEST_ID_REGEX.match(incoming_id.strip()):
            request_id = incoming_id.strip()
        else:
            request_id = str(uuid.uuid4())

        set_request_id(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_context()
