"""Model Context Protocol (MCP) Server for CloudDesk Support Platform.

Exposes read-only support tools over standard JSON-RPC protocol to external agents.
Consequential write actions are strictly excluded from MCP tool discovery and execution.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path for direct script execution
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.tools.registry import get_tool_registry
from backend.app.tools.support_tools import register_all_tools

logger = logging.getLogger(__name__)

# Ensure all platform tools are registered in default registry
register_all_tools()

# Explicitly whitelisted read-only tools permitted over MCP
MCP_READ_ONLY_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_customer": {
        "name": "get_customer",
        "description": "Retrieve customer profile details by customer ID or email.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer UUID"},
                "email": {"type": "string", "description": "Customer email address"},
            },
        },
    },
    "get_subscription": {
        "name": "get_subscription",
        "description": "Retrieve active subscription and tier details for a customer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer UUID"},
            },
            "required": ["customer_id"],
        },
    },
    "get_ticket_history": {
        "name": "get_ticket_history",
        "description": "Retrieve past support tickets and statuses for a customer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer UUID"},
                "limit": {
                    "type": "integer",
                    "default": 5,
                    "description": "Max tickets to return",
                },
            },
            "required": ["customer_id"],
        },
    },
    "search_docs": {
        "name": "search_docs",
        "description": "Search the CloudDesk knowledge base using hybrid dense/sparse retrieval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "category": {"type": "string", "description": "Optional category filter"},
                "top_k": {"type": "integer", "default": 5, "description": "Max results"},
            },
            "required": ["query"],
        },
    },
    "check_service_status": {
        "name": "check_service_status",
        "description": "Check operational health and active incidents for CloudDesk platform services.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Service name to check (e.g. clouddesk-identity)",
                },
            },
        },
    },
}


def list_mcp_tools() -> list[dict[str, Any]]:
    """Return tool descriptions exposed to MCP clients (read-only tools only)."""
    return list(MCP_READ_ONLY_TOOL_SCHEMAS.values())


async def call_mcp_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool request from an MCP client with security boundary enforcement."""
    # Security Boundary: Write and consequential tools are forbidden via MCP
    if name not in MCP_READ_ONLY_TOOL_SCHEMAS:
        return {
            "is_error": True,
            "error": f"Tool '{name}' is not permitted via MCP. Only read-only tools are exposed.",
        }

    registry = get_tool_registry()
    result = await registry.execute(name=name, args=arguments, approved=False)

    if result.ok:
        content_val = (
            result.data
            if isinstance(result.data, list)
            else [{"type": "text", "text": json.dumps(result.data)}]
        )
        return {
            "is_error": False,
            "content": content_val,
        }

    return {
        "is_error": True,
        "error": result.error or "Tool execution failed",
    }


async def handle_jsonrpc_request(request: Any) -> dict[str, Any]:
    """Process a JSON-RPC 2.0 protocol request message."""
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id") if isinstance(request, dict) else None,
            "error": {"code": -32600, "message": "Invalid Request: expected JSON-RPC 2.0"},
        }

    req_id = request.get("id")
    method = request.get("method")

    if not isinstance(method, str):
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32600, "message": "Invalid Request: method must be a string"},
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": list_mcp_tools()},
        }

    if method == "tools/call":
        params = request.get("params") or {}
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}

        if not tool_name:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Invalid params: 'name' is required"},
            }

        res = await call_mcp_tool(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": res,
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "clouddesk-mcp-server", "version": "0.1.0"},
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: '{method}'"},
    }


async def run_stdio_server() -> None:
    """Run interactive MCP server over stdio streams."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        text = line.decode("utf-8").strip()
        if not text:
            continue

        try:
            req = json.loads(text)
            resp = await handle_jsonrpc_request(req)
        except json.JSONDecodeError:
            resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(run_stdio_server())
