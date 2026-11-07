"""Example client demonstrating interaction with the CloudDesk MCP Server.

Illustrates:
- Initializing the MCP session.
- Listing available read-only tools.
- Invoking the search_docs tool.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path for direct script execution
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from integrations.mcp.server import handle_jsonrpc_request


async def main() -> None:
    print("--- CloudDesk MCP Client Example ---\n")

    # 1. Initialize session
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "example-client", "version": "1.0"},
        },
    }
    init_res = await handle_jsonrpc_request(init_request)
    print("1. Initialize Response:", init_res.get("result"))

    # 2. Discover tools
    list_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    }
    list_res = await handle_jsonrpc_request(list_request)
    tools = list_res.get("result", {}).get("tools", [])
    print(f"\n2. Discovered {len(tools)} tools:")
    for t in tools:
        print(f"   - {t['name']}: {t['description']}")

    # 3. Call search_docs tool
    call_request: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_docs",
            "arguments": {
                "query": "SAML SSO Okta authentication",
                "top_k": 2,
            },
        },
    }
    call_res = await handle_jsonrpc_request(call_request)
    print("\n3. Tool Call Result (search_docs):", call_res.get("result"))


if __name__ == "__main__":
    asyncio.run(main())
