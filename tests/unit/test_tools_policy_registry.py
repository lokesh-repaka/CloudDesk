"""Tests for Tool Registry, Tool Policy, and Base Tool Abstractions.

Verifies:
- F9: Consequential actions need human approval.
- ToolPolicy approval rules for read-only, safe write, consequential write, and unknown tools.
- ToolRegistry execution wrapper, timeout management, exception sandboxing, and policy enforcement.
- ToolResult and ToolDefinition data structures.
"""

import asyncio
from typing import Any

import pytest

from backend.app.core.config import Settings
from backend.app.tools.base import ToolDefinition, ToolResult, tool
from backend.app.tools.policy import ToolPolicy, get_tool_policy
from backend.app.tools.registry import ToolRegistry, get_tool_registry

# ---------------------------------------------------------------------------
# Base Models & Decorators
# ---------------------------------------------------------------------------

def test_tool_result_structure():
    """ToolResult captures ok status, data, error, tool_name, and duration_ms."""
    res_ok = ToolResult(ok=True, data={"ticket_id": "CD-1001"}, tool_name="get_ticket")
    assert res_ok.ok is True
    assert res_ok.data == {"ticket_id": "CD-1001"}
    assert res_ok.error is None
    assert res_ok.tool_name == "get_ticket"

    res_err = ToolResult(ok=False, error="Not found", tool_name="get_ticket")
    assert res_err.ok is False
    assert res_err.data is None
    assert res_err.error == "Not found"
    assert res_err.tool_name == "get_ticket"


def test_tool_definition_and_decorator():
    """@tool decorator creates a ToolDefinition with preserved metadata."""

    @tool(name="custom_echo", description="Echoes back the input text.")
    async def echo_tool(text: str) -> str:
        """Echo docstring."""
        return text

    assert isinstance(echo_tool, ToolDefinition)
    assert echo_tool.name == "custom_echo"
    assert echo_tool.description == "Echoes back the input text."
    assert echo_tool.is_async is True


def test_tool_decorator_defaults():
    """@tool uses function name and docstring by default."""

    @tool
    def simple_sync_tool(x: int) -> int:
        """Doubles an integer."""
        return x * 2

    assert isinstance(simple_sync_tool, ToolDefinition)
    assert simple_sync_tool.name == "simple_sync_tool"
    assert "Doubles an integer." in simple_sync_tool.description
    assert simple_sync_tool.is_async is False


# ---------------------------------------------------------------------------
# Tool Policy
# ---------------------------------------------------------------------------

def test_tool_policy_read_only_tools():
    """Read-only support tools never require approval."""
    policy = ToolPolicy()
    read_only_tools = [
        "get_customer",
        "get_subscription",
        "get_ticket_history",
        "search_docs",
        "check_service_status",
    ]
    for name in read_only_tools:
        assert policy.requires_approval(name) is False
        assert policy.is_consequential(name) is False
        permitted, err = policy.check_execution_permitted(name, approved=False)
        assert permitted is True
        assert err is None


def test_tool_policy_safe_write_tools():
    """Safe write tools (update_ticket, create_escalation) do not require approval."""
    policy = ToolPolicy()
    safe_write_tools = ["update_ticket", "create_escalation"]
    for name in safe_write_tools:
        assert policy.requires_approval(name) is False
        assert policy.is_consequential(name) is False
        permitted, err = policy.check_execution_permitted(name, approved=False)
        assert permitted is True
        assert err is None


def test_tool_policy_consequential_tools():
    """reset_demo_setting and create_refund_request require human approval."""
    policy = ToolPolicy()

    # reset_demo_setting is always consequential
    assert policy.requires_approval("reset_demo_setting") is True
    assert policy.is_consequential("reset_demo_setting") is True
    permitted, err = policy.check_execution_permitted("reset_demo_setting", approved=False)
    assert permitted is False
    assert "requires human approval" in err.lower()

    permitted_approved, err_approved = policy.check_execution_permitted("reset_demo_setting", approved=True)
    assert permitted_approved is True
    assert err_approved is None

    # create_refund_request default policy
    assert policy.requires_approval("create_refund_request", {"amount": 25.0}) is True
    assert policy.is_consequential("create_refund_request") is True


def test_tool_policy_refund_threshold():
    """Refund policy obeys APPROVAL_REQUIRED_FOR_REFUNDS and MAX_REFUND_WITHOUT_APPROVAL."""
    custom_settings = Settings(
        APPROVAL_REQUIRED_FOR_REFUNDS=False,
        MAX_REFUND_WITHOUT_APPROVAL=20.0,
    )
    policy = ToolPolicy(settings=custom_settings)

    # Within threshold when approval not required for all refunds
    assert policy.requires_approval("create_refund_request", {"amount": 15.0}) is False

    # Exceeds threshold
    assert policy.requires_approval("create_refund_request", {"amount": 25.0}) is True

    # When APPROVAL_REQUIRED_FOR_REFUNDS is True, even zero or small refunds need approval
    strict_settings = Settings(
        APPROVAL_REQUIRED_FOR_REFUNDS=True,
        MAX_REFUND_WITHOUT_APPROVAL=50.0,
    )
    strict_policy = ToolPolicy(settings=strict_settings)
    assert strict_policy.requires_approval("create_refund_request", {"amount": 10.0}) is True


def test_tool_policy_unknown_tools():
    """Unknown tools always require approval and are considered consequential."""
    policy = ToolPolicy()
    assert policy.requires_approval("unregistered_tool_xyz") is True
    assert policy.is_consequential("unregistered_tool_xyz") is True

    permitted, err = policy.check_execution_permitted("unregistered_tool_xyz", approved=False)
    assert permitted is False
    assert "requires human approval" in err.lower()


# ---------------------------------------------------------------------------
# Tool Registry Execution & Sandboxing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_registry_registration_and_list():
    """Registry correctly registers and catalogs tools."""
    registry = ToolRegistry(policy=ToolPolicy())

    @tool
    async def sample_tool(val: str) -> str:
        """Sample doc."""
        return f"result: {val}"

    registry.register(sample_tool)

    assert registry.has_tool("sample_tool") is True
    assert registry.get("sample_tool") is sample_tool
    assert "sample_tool" in registry.list_tool_names()
    assert len(registry.list_tools()) == 1


@pytest.mark.asyncio
async def test_tool_registry_execute_unattended_success():
    """Permitted tools execute unattended when approved=False."""
    registry = ToolRegistry(policy=ToolPolicy())

    @tool(name="search_docs")
    async def mock_search(query: str) -> dict[str, Any]:
        """Search documentation."""
        return {"hits": [query]}

    registry.register(mock_search)

    res = await registry.execute("search_docs", {"query": "billing"})
    assert res.ok is True
    assert res.data == {"hits": ["billing"]}
    assert res.error is None
    assert res.tool_name == "search_docs"
    assert res.duration_ms is not None
    assert res.duration_ms >= 0


@pytest.mark.asyncio
async def test_tool_registry_blocks_unapproved_consequential():
    """Consequential tools fail with ToolResult(ok=False) if not approved."""
    registry = ToolRegistry(policy=ToolPolicy())

    called = False

    @tool(name="reset_demo_setting")
    async def mock_reset(setting_name: str) -> bool:
        """Reset setting."""
        nonlocal called
        called = True
        return True

    registry.register(mock_reset)

    # Attempt execute without approval
    res = await registry.execute("reset_demo_setting", {"setting_name": "sso"}, approved=False)
    assert res.ok is False
    assert "requires human approval" in res.error.lower()
    assert called is False  # Ensure function was not called!

    # Execute with approval
    res_approved = await registry.execute("reset_demo_setting", {"setting_name": "sso"}, approved=True)
    assert res_approved.ok is True
    assert res_approved.data is True
    assert called is True


@pytest.mark.asyncio
async def test_tool_registry_unknown_tool_behavior():
    """Unknown tools fail cleanly with ToolResult(ok=False) without raising exceptions."""
    registry = ToolRegistry(policy=ToolPolicy())

    # When unapproved, policy blocks unknown tools
    res_unapproved = await registry.execute("missing_tool", {"foo": "bar"}, approved=False)
    assert res_unapproved.ok is False
    assert "requires human approval" in res_unapproved.error.lower()

    # Even if approved flag is provided, missing tool returns not registered error
    res_approved = await registry.execute("missing_tool", {"foo": "bar"}, approved=True)
    assert res_approved.ok is False
    assert "not registered" in res_approved.error.lower()


@pytest.mark.asyncio
async def test_tool_registry_exception_sandboxing():
    """Unhandled exceptions in tools return ToolResult(ok=False) without crashing."""
    registry = ToolRegistry(policy=ToolPolicy())

    @tool(name="update_ticket")
    async def buggy_tool(ticket_id: str) -> None:
        """Simulate unexpected failure."""
        raise RuntimeError("External database connection dropped")

    registry.register(buggy_tool)

    res = await registry.execute("update_ticket", {"ticket_id": "CD-1001"})
    assert res.ok is False
    assert res.data is None
    assert "External database connection dropped" in res.error
    assert res.tool_name == "update_ticket"


@pytest.mark.asyncio
async def test_tool_registry_timeout_enforcement():
    """Enforces timeout and returns ToolResult(ok=False) when execution exceeds limit."""
    registry = ToolRegistry(policy=ToolPolicy())

    @tool(name="check_service_status")
    async def slow_service() -> str:
        """Simulate slow third-party service."""
        await asyncio.sleep(0.2)
        return "online"

    registry.register(slow_service)

    # Force a very small timeout of 0.05 seconds
    res = await registry.execute("check_service_status", timeout=0.05)
    assert res.ok is False
    assert "timed out" in res.error.lower()
    assert res.tool_name == "check_service_status"


@pytest.mark.asyncio
async def test_tool_registry_sync_tool_support():
    """Registry supports synchronous tool definitions seamlessly."""
    registry = ToolRegistry(policy=ToolPolicy())

    @tool(name="get_customer")
    def sync_customer(customer_id: str) -> dict[str, str]:
        """Fetch customer data synchronously."""
        return {"id": customer_id, "name": "Acme Corp"}

    registry.register(sync_customer)

    res = await registry.execute("get_customer", {"customer_id": "cust_123"})
    assert res.ok is True
    assert res.data == {"id": "cust_123", "name": "Acme Corp"}


@pytest.mark.asyncio
async def test_get_tool_registry_singleton():
    """get_tool_registry and get_tool_policy return valid cached instances."""
    reg1 = get_tool_registry()
    reg2 = get_tool_registry()
    assert reg1 is reg2

    pol1 = get_tool_policy()
    pol2 = get_tool_policy()
    assert pol1 is pol2


# ---------------------------------------------------------------------------
# Security & Penetration Tests (CWE Validation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_cwe_862_unauthorized_consequential_bypass_rejected():
    """CWE-862: Attacker cannot execute consequential actions without explicit approval."""
    registry = ToolRegistry(policy=ToolPolicy())
    executed = False

    @tool(name="reset_demo_setting")
    async def sensitive_action(workspace_id: str) -> str:
        nonlocal executed
        executed = True
        return "reset"

    registry.register(sensitive_action)

    # Attempt 1: Default unattended (approved=False)
    res = await registry.execute("reset_demo_setting", {"workspace_id": "ws-123"})
    assert res.ok is False
    assert executed is False
    assert "requires human approval" in res.error.lower()

    # Attempt 2: Attacker tries injecting approval flag into args dict
    res_spoof = await registry.execute(
        "reset_demo_setting",
        {"workspace_id": "ws-123", "approved": True},
        approved=False,
    )
    assert res_spoof.ok is False
    assert executed is False
    assert "requires human approval" in res_spoof.error.lower()


@pytest.mark.asyncio
async def test_security_cwe_184_unregistered_arbitrary_tool_injection():
    """CWE-184: Malicious/unregistered tool strings cannot be executed unattended or bypassed."""
    registry = ToolRegistry(policy=ToolPolicy())

    malicious_names = [
        "os.system",
        "rm -rf /",
        "__import__('os').system('ls')",
        "eval",
        "admin_drop_tables",
    ]

    for tool_name in malicious_names:
        # Without approval, must block with approval required
        res = await registry.execute(tool_name, approved=False)
        assert res.ok is False
        assert "requires human approval" in res.error.lower()

        # Even with approved=True, must safely refuse because not registered
        res_approved = await registry.execute(tool_name, approved=True)
        assert res_approved.ok is False
        assert "not registered" in res_approved.error.lower()


def test_security_cwe_770_refund_parameter_tampering_default_safe():
    """CWE-770: Non-numeric, negative, or malformed refund parameters default to requiring approval."""
    custom_settings = Settings(
        APPROVAL_REQUIRED_FOR_REFUNDS=False,
        MAX_REFUND_WITHOUT_APPROVAL=25.0,
    )
    policy = ToolPolicy(settings=custom_settings)

    malformed_payloads = [
        {"amount": "invalid-string"},
        {"amount": None},
        {"amount": [100]},
        {"amount": {"$gt": 0}},
        {},
    ]

    for payload in malformed_payloads:
        assert policy.requires_approval("create_refund_request", payload) is True


@pytest.mark.asyncio
async def test_security_cwe_400_timeout_prevents_dos():
    """CWE-400: Hanging or deadlocked tools are cancelled within timeout to prevent thread exhaustion."""
    registry = ToolRegistry(policy=ToolPolicy())

    @tool(name="check_service_status")
    async def hung_service():
        while True:
            await asyncio.sleep(0.01)

    registry.register(hung_service)

    res = await registry.execute("check_service_status", timeout=0.05)
    assert res.ok is False
    assert "timed out after" in res.error.lower()

