"""Support tools aggregate module for CloudDesk.

Provides all 9 support tools (5 read-only + 4 write) and centralized registration
functions for ToolRegistry and LangGraph workflows.
"""

from backend.app.tools.base import ToolDefinition, ToolResult, tool
from backend.app.tools.read_tools import (
    check_service_status,
    get_customer,
    get_subscription,
    get_ticket_history,
    register_read_only_tools,
    search_docs,
)
from backend.app.tools.registry import ToolRegistry, get_tool_registry
from backend.app.tools.write_tools import (
    create_escalation,
    create_refund_request,
    register_write_tools,
    reset_demo_setting,
    update_ticket,
)


def register_all_tools(registry: ToolRegistry | None = None) -> list[ToolDefinition]:
    """Register all 9 support tools (read-only and write) into the registry."""
    target_registry = registry or get_tool_registry()
    read_tools = register_read_only_tools(target_registry)
    write_tools = register_write_tools(target_registry)
    return read_tools + write_tools


__all__ = [
    "ToolDefinition",
    "ToolResult",
    "check_service_status",
    "create_escalation",
    "create_refund_request",
    "get_customer",
    "get_subscription",
    "get_ticket_history",
    "register_all_tools",
    "register_read_only_tools",
    "register_write_tools",
    "reset_demo_setting",
    "search_docs",
    "tool",
    "update_ticket",
]
