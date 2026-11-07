"""Model Context Protocol (MCP) Tool Discovery API.

Exposes read-only support tool schemas and parameter contracts to authorized agents
and external MCP client orchestration engines.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.schemas.common import RoleEnum
from backend.app.schemas.mcp import McpToolDefinitionResponse
from integrations.mcp.server import list_mcp_tools

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get(
    "/tools",
    response_model=list[McpToolDefinitionResponse],
    summary="List MCP Tools",
    description="Expose registered read-only support tools for external MCP agent discovery.",
)
async def get_mcp_tools(
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
) -> list[McpToolDefinitionResponse]:
    """Return all read-only support tools discoverable via MCP with parameter schemas."""
    mcp_tools = list_mcp_tools()
    return [
        McpToolDefinitionResponse(
            name=t["name"],
            description=t["description"],
            parameters=t.get("inputSchema", {}),
            is_consequential=False,
            requires_approval=False,
        )
        for t in mcp_tools
    ]
