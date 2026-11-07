"""Unit tests for Mock Integrations and MCP Tool Server.

Verifies:
- External service protocols (Billing, Email, Status, Notification, WorkspaceAdmin).
- Mock service adapters with call tracking, idempotency, and error simulation.
- Service factory singletons and reset helpers.
- MCP Server tool discovery and JSON-RPC dispatch (restricting strictly to read-only tools).
- Security audits: exclusion of consequential tools from MCP discovery (CWE-862)
  and malformed JSON-RPC message handling (CWE-20).
"""

import pytest

from integrations.factory import (
    get_billing_service,
    get_email_service,
    get_notification_service,
    get_status_service,
    get_workspace_admin_service,
    reset_all_mock_services,
)
from integrations.mcp.server import (
    call_mcp_tool,
    handle_jsonrpc_request,
    list_mcp_tools,
)
from integrations.mock.services import (
    MockBillingService,
    MockEmailService,
    MockNotificationService,
    MockStatusService,
    MockWorkspaceAdminService,
)


@pytest.fixture(autouse=True)
def clean_mock_services():
    """Reset all mock service state before and after each test."""
    reset_all_mock_services()
    yield
    reset_all_mock_services()


# ---------------------------------------------------------------------------
# Mock Billing Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_billing_service_refund_and_tracking():
    """MockBillingService records refunds and generates receipt IDs."""
    billing = MockBillingService()
    res = await billing.create_refund(
        customer_id="cust-123",
        amount=49.99,
        reason="Seat reduction",
        ticket_id="CD-1002",
    )
    assert res["status"] == "refunded"
    assert res["amount"] == 49.99
    assert "ref_" in res["refund_id"]
    assert len(billing.refunds_processed) == 1

    history = await billing.get_payment_history("cust-123")
    assert isinstance(history, list)
    assert len(history) >= 1

    billing.reset()
    assert len(billing.refunds_processed) == 0


@pytest.mark.asyncio
async def test_mock_billing_service_simulated_failure():
    """MockBillingService raises error when simulated failure is active."""
    billing = MockBillingService()
    billing.simulate_failure(should_fail=True, error_message="Stripe API gateway unreachable")

    with pytest.raises(RuntimeError, match="Stripe API gateway unreachable"):
        await billing.create_refund(customer_id="cust-123", amount=10.0, reason="test")


# ---------------------------------------------------------------------------
# Mock Email Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_email_service_send_and_tracking():
    """MockEmailService records dispatched emails in-memory."""
    email_svc = MockEmailService()
    res = await email_svc.send_email(
        to_email="customer@example.com",
        subject="Your ticket CD-1001 has been updated",
        body="Hello, your SSO issue has been resolved.",
        ticket_id="CD-1001",
    )
    assert res["status"] == "sent"
    assert res["to"] == "customer@example.com"
    assert len(email_svc.sent_emails) == 1

    email_svc.reset()
    assert len(email_svc.sent_emails) == 0


# ---------------------------------------------------------------------------
# Mock Status Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_status_service_incident_detection():
    """MockStatusService reads incidents and reports health accurately."""
    status_svc = MockStatusService()
    report = await status_svc.check_service_health("clouddesk-identity")
    assert report["service"] == "clouddesk-identity"
    assert report["status"] in ("outage", "degraded", "operational")

    incidents = await status_svc.get_active_incidents()
    assert isinstance(incidents, list)


# ---------------------------------------------------------------------------
# Mock Notification Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_notification_service_send():
    """MockNotificationService records team channel notifications."""
    notif_svc = MockNotificationService()
    res = await notif_svc.send_notification(
        channel="#support-alerts",
        message="Critical incident CD-1005 escalated.",
        ticket_id="CD-1005",
    )
    assert res["status"] == "delivered"
    assert len(notif_svc.sent_notifications) == 1


# ---------------------------------------------------------------------------
# Mock Workspace Admin Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_workspace_admin_reset_setting():
    """MockWorkspaceAdminService records setting mutations."""
    admin_svc = MockWorkspaceAdminService()
    res = await admin_svc.reset_setting(
        workspace_id="ws-999",
        setting_key="sso_enforced",
        reset_value=False,
    )
    assert res["status"] == "updated"
    assert res["setting_key"] == "sso_enforced"
    assert len(admin_svc.mutated_settings) == 1


# ---------------------------------------------------------------------------
# Integration Factory Tests
# ---------------------------------------------------------------------------

def test_integration_factory_singletons():
    """Factory returns cached singleton instances."""
    b1 = get_billing_service()
    b2 = get_billing_service()
    assert b1 is b2

    e1 = get_email_service()
    e2 = get_email_service()
    assert e1 is e2

    s1 = get_status_service()
    s2 = get_status_service()
    assert s1 is s2

    n1 = get_notification_service()
    n2 = get_notification_service()
    assert n1 is n2

    w1 = get_workspace_admin_service()
    w2 = get_workspace_admin_service()
    assert w1 is w2


# ---------------------------------------------------------------------------
# MCP Server Tool Discovery and Execution Tests
# ---------------------------------------------------------------------------

def test_mcp_tool_discovery_strictly_read_only():
    """MCP server tool discovery exposes ONLY read-only tools and excludes write actions."""
    tools = list_mcp_tools()
    tool_names = {t["name"] for t in tools}

    expected_read_only = {
        "get_customer",
        "get_subscription",
        "get_ticket_history",
        "search_docs",
        "check_service_status",
    }
    assert expected_read_only.issubset(tool_names)

    # Consequential / write tools MUST NOT be exposed to MCP
    forbidden_tools = {
        "create_refund_request",
        "reset_demo_setting",
        "update_ticket",
        "create_escalation",
    }
    assert forbidden_tools.isdisjoint(tool_names)


@pytest.mark.asyncio
async def test_mcp_call_read_only_tool_success():
    """call_mcp_tool executes read-only tools and returns structured content."""
    res = await call_mcp_tool("search_docs", {"query": "SSO login", "top_k": 2})
    assert res["is_error"] is False
    assert isinstance(res["content"], list)


@pytest.mark.asyncio
async def test_mcp_call_forbidden_tool_rejected():
    """call_mcp_tool rejects attempts to run consequential write actions."""
    res = await call_mcp_tool("create_refund_request", {"amount": 100.0})
    assert res["is_error"] is True
    assert "not permitted via mcp" in res["error"].lower()


@pytest.mark.asyncio
async def test_mcp_jsonrpc_protocol_handlers():
    """handle_jsonrpc_request handles tools/list, tools/call, and ping according to spec."""
    # 1. tools/list
    list_req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    list_resp = await handle_jsonrpc_request(list_req)
    assert list_resp["id"] == 1
    assert "tools" in list_resp["result"]

    # 2. tools/call
    call_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "search_docs", "arguments": {"query": "billing", "top_k": 1}},
    }
    call_resp = await handle_jsonrpc_request(call_req)
    assert call_resp["id"] == 2
    assert "content" in call_resp["result"]

    # 3. ping
    ping_req = {"jsonrpc": "2.0", "id": 3, "method": "ping"}
    ping_resp = await handle_jsonrpc_request(ping_req)
    assert ping_resp["id"] == 3
    assert ping_resp["result"] == {}

    # 4. Unknown method
    bad_req = {"jsonrpc": "2.0", "id": 4, "method": "unsupported/method"}
    bad_resp = await handle_jsonrpc_request(bad_req)
    assert "error" in bad_resp
    assert bad_resp["error"]["code"] == -32601


# ---------------------------------------------------------------------------
# Security & Penetration Tests (CWE Validation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_cwe_862_mcp_write_tool_execution_bypass_rejected():
    """CWE-862: Attacker attempting JSON-RPC call for write tool is strictly blocked."""
    malicious_call = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "reset_demo_setting",
            "arguments": {"workspace_id": "ws-1", "setting_name": "sso"},
        },
    }
    resp = await handle_jsonrpc_request(malicious_call)
    assert "error" in resp or resp.get("result", {}).get("is_error") is True


@pytest.mark.asyncio
async def test_security_cwe_20_malformed_jsonrpc_handling():
    """CWE-20: Malformed JSON-RPC requests return standard -32600 error without crash."""
    malformed_payloads = [
        {},
        {"jsonrpc": "1.0"},
        {"method": 123},
        None,
    ]
    for payload in malformed_payloads:
        resp = await handle_jsonrpc_request(payload)
        assert "error" in resp
        assert resp["error"]["code"] in (-32600, -32700)
