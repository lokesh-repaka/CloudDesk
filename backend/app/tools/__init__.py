"""Tools package for CloudDesk.

Provides tool base definitions, execution policy engine, centralized tool registry,
and read-only support tools.
"""

from backend.app.tools.base import ToolDefinition, ToolResult, tool
from backend.app.tools.policy import ToolPolicy, get_tool_policy
from backend.app.tools.read_tools import (
    check_service_status,
    get_customer,
    get_subscription,
    get_ticket_history,
    register_read_only_tools,
    search_docs,
)
from backend.app.tools.registry import ToolRegistry, get_tool_registry

__all__ = [
    "ToolDefinition",
    "ToolPolicy",
    "ToolRegistry",
    "ToolResult",
    "check_service_status",
    "get_customer",
    "get_subscription",
    "get_ticket_history",
    "get_tool_policy",
    "get_tool_registry",
    "register_read_only_tools",
    "search_docs",
    "tool",
]
