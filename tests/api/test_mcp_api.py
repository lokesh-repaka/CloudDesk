"""API tests for Model Context Protocol (MCP) Tool Discovery Endpoint.

Verifies:
- GET /api/v1/mcp/tools requires authentication (401).
- Minimum role is Agent (Viewer receives 403 Forbidden).
- Returns list of read-only support tools with schemas, parameter models, and policy flags.
- Write/consequential actions are excluded from the output.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app


@pytest.mark.asyncio
async def test_mcp_tools_unauthenticated_returns_401():
    """Unauthenticated request to /api/v1/mcp/tools is rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/mcp/tools")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mcp_tools_viewer_forbidden_rbac(viewer_headers: dict[str, str]):
    """Viewer token receives 403 Forbidden on /api/v1/mcp/tools."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/mcp/tools", headers=viewer_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mcp_tools_agent_authorized_success(agent_headers: dict[str, str]):
    """Agent receives 200 OK with list of read-only tool schemas."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/mcp/tools", headers=agent_headers)
    assert response.status_code == 200
    tools = response.json()
    assert isinstance(tools, list)
    assert len(tools) >= 5

    names = {t["name"] for t in tools}
    assert "search_docs" in names
    assert "get_customer" in names
    assert "check_service_status" in names

    # Consequential / write tools MUST NOT be listed
    assert "create_refund_request" not in names
    assert "reset_demo_setting" not in names
    assert "update_ticket" not in names
