"""API Integration and Security Tests for Ticket API Routes (P4-2).

Tests endpoints under /api/v1/tickets:
- POST /api/v1/tickets (Omnichannel Ingestion)
- GET /api/v1/tickets (Queue Listing & Multi-Param Filtering)
- GET /api/v1/tickets/{id} (Ticket Dossier & Message Thread)
- POST /api/v1/tickets/{id}/reply (Agent Reply Dispatch & Status Transition)
- POST /api/v1/tickets/{id}/request-info (Clarification Request)
- POST /api/v1/tickets/{id}/escalate (Manual/Policy Escalation)

Verifies AC-001 through AC-011, AC-045, AC-052, AC-054, RBAC hierarchies,
and security resilience against injection, DoS payloads, and unauthorized access.
"""

from starlette.testclient import TestClient

# -----------------------------------------------------------------------------
# 1. Omnichannel Ticket Ingestion (US-001 / AC-001 to AC-006)
# -----------------------------------------------------------------------------


def test_create_ticket_success_ac_001(client: TestClient):
    """Verify POST /api/v1/tickets creates a ticket and initial message atomically (AC-001)."""
    payload = {
        "customer_id": "cust-101-acme",
        "subject": "VPN connection dropping repeatedly",
        "body": "Our remote workers cannot stay connected to the primary VPN gateway.",
        "channel": "email",
    }
    response = client.post("/api/v1/tickets", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["customer_id"] == "cust-101-acme"
    assert data["subject"] == "VPN connection dropping repeatedly"
    assert data["channel"] == "email"
    assert data["status"] == "new"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["body"] == "Our remote workers cannot stay connected to the primary VPN gateway."
    assert data["messages"][0]["author_role"] == "customer"
    assert "X-Request-ID" in response.headers


def test_create_ticket_all_supported_channels(client: TestClient):
    """Verify ticket ingestion succeeds across all canonical channels (AC-001)."""
    for ch in ["email", "chat", "web", "api"]:
        payload = {
            "customer_id": "cust-102-globex",
            "subject": f"Inquiry via {ch}",
            "body": f"Testing ticket intake over channel {ch}.",
            "channel": ch,
        }
        res = client.post("/api/v1/tickets", json=payload)
        assert res.status_code == 201
        assert res.json()["channel"] == ch


def test_create_ticket_invalid_channel_rejected_ac_002(client: TestClient):
    """Verify invalid channel returns 422 Unprocessable Entity (AC-002)."""
    payload = {
        "customer_id": "cust-101-acme",
        "subject": "Valid Subject Line",
        "body": "Valid body text.",
        "channel": "sms",  # Unsupported
    }
    res = client.post("/api/v1/tickets", json=payload)
    assert res.status_code == 422
    assert "channel" in str(res.json()["detail"])


def test_create_ticket_empty_or_whitespace_subject_rejected_ac_002(client: TestClient):
    """Verify empty or whitespace-only subject returns 422 (AC-002)."""
    for bad_subject in ["", "   ", "\t\n  "]:
        payload = {
            "customer_id": "cust-101-acme",
            "subject": bad_subject,
            "body": "Valid body text.",
        }
        res = client.post("/api/v1/tickets", json=payload)
        assert res.status_code == 422


def test_create_ticket_nonexistent_customer_returns_404_ac_003(client: TestClient):
    """Verify referencing a non-existent customer_id returns HTTP 404 (AC-003)."""
    payload = {
        "customer_id": "cust-999-nonexistent",
        "subject": "Missing Customer Error",
        "body": "This ticket belongs to an unknown customer.",
        "channel": "web",
    }
    res = client.post("/api/v1/tickets", json=payload)
    assert res.status_code == 404
    assert "Customer cust-999-nonexistent not found" in res.json()["detail"]


def test_create_ticket_large_unicode_body_ac_004(client: TestClient):
    """Verify body handles 50,000 characters with unicode and emojis without corruption (AC-004)."""
    snippet = "🚀 Multi-language alert: 日本語, Español, and emojis! "
    multiplier = (50000 // len(snippet)) + 1
    large_body = (snippet * multiplier)[:50000]

    payload = {
        "customer_id": "cust-101-acme",
        "subject": "Large Diagnostic Dump",
        "body": large_body,
        "channel": "api",
    }
    res = client.post("/api/v1/tickets", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert len(created["messages"][0]["body"]) == 50000
    assert "🚀" in created["messages"][0]["body"]
    assert "日本語" in created["messages"][0]["body"]


def test_create_ticket_oversized_body_rejected(client: TestClient):
    """Verify bodies exceeding 50,000 characters are rejected with 422."""
    payload = {
        "customer_id": "cust-101-acme",
        "subject": "Oversized Payload",
        "body": "x" * 50001,
    }
    res = client.post("/api/v1/tickets", json=payload)
    assert res.status_code == 422


def test_create_ticket_extra_fields_rejected_mass_assignment(client: TestClient):
    """Verify extra/unknown parameters return 422 preventing mass assignment (CWE-915)."""
    payload = {
        "customer_id": "cust-101-acme",
        "subject": "Valid Subject",
        "body": "Valid Body",
        "status": "resolved",  # Client cannot force status
    }
    res = client.post("/api/v1/tickets", json=payload)
    assert res.status_code == 422


# -----------------------------------------------------------------------------
# 2. Ticket Queue Listing & Filtering (US-002 / AC-007 to AC-011)
# -----------------------------------------------------------------------------


def test_list_tickets_unauthenticated_returns_401_ac_010(client: TestClient):
    """Verify GET /api/v1/tickets without authorization token returns 401 Unauthorized (AC-010)."""
    res = client.get("/api/v1/tickets")
    assert res.status_code == 401
    assert "detail" in res.json()


def test_list_tickets_all_roles_authorized_ac_011(
    client: TestClient,
    viewer_headers: dict[str, str],
    agent_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    """Verify viewer, agent, and admin roles can all view the ticket queue (AC-011)."""
    for headers in [viewer_headers, agent_headers, admin_headers]:
        res = client.get("/api/v1/tickets", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


def test_list_tickets_filtering_by_status_and_severity_ac_007(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify queue filtering by status and severity returns matching subset (AC-007)."""
    res = client.get("/api/v1/tickets?status=new&severity=critical", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["status"] == "new"
        assert item["severity"] == "critical"


def test_list_tickets_filtering_by_category_and_plan_ac_007(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify queue filtering by category and customer plan (AC-007)."""
    res = client.get("/api/v1/tickets?category=login_issue&plan=enterprise", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["category"] == "login_issue"
        assert item["customer_plan"] == "enterprise"


def test_list_tickets_invalid_enum_returns_422_ac_008(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify invalid enum parameters return 422 Unprocessable Entity (AC-008)."""
    res = client.get("/api/v1/tickets?status=pending_review", headers=viewer_headers)
    assert res.status_code == 422

    res2 = client.get("/api/v1/tickets?severity=urgent", headers=viewer_headers)
    assert res2.status_code == 422


def test_list_tickets_zero_match_returns_empty_list_ac_009(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify valid criteria with zero matches returns 200 with [] and total: 0 (AC-009)."""
    res = client.get("/api/v1/tickets?status=closed&severity=low", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_tickets_pagination(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify limit and offset pagination controls."""
    res = client.get("/api/v1/tickets?limit=3&offset=0", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) <= 3
    assert data["limit"] == 3
    assert data["offset"] == 0


# -----------------------------------------------------------------------------
# 3. Ticket Detail & Conversation Dossier
# -----------------------------------------------------------------------------


def test_get_ticket_detail_success(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify GET /api/v1/tickets/{id} returns ticket dossier with chronological messages."""
    res = client.get("/api/v1/tickets/CD-1001", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "CD-1001"
    assert data["customer_id"] == "cust-101-acme"
    assert "messages" in data
    assert len(data["messages"]) >= 1
    assert data["customer_name"] == "Acme Corporation"
    assert data["customer_plan"] == "enterprise"


def test_get_ticket_detail_not_found(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify non-existent ticket ID returns 404 Not Found."""
    res = client.get("/api/v1/tickets/CD-9999-missing", headers=viewer_headers)
    assert res.status_code == 404
    assert "Ticket CD-9999-missing not found" in res.json()["detail"]


def test_get_ticket_detail_unauthenticated(client: TestClient):
    """Verify unauthenticated GET /api/v1/tickets/{id} returns 401."""
    res = client.get("/api/v1/tickets/CD-1001")
    assert res.status_code == 401


# -----------------------------------------------------------------------------
# 4. Agent Reply Dispatch (US-013 / AC-052, AC-053)
# -----------------------------------------------------------------------------


def test_agent_reply_success_ac_052(
    client: TestClient,
    agent_headers: dict[str, str],
    viewer_headers: dict[str, str],
):
    """Verify agent can dispatch reply, appending message and setting waiting_on_customer (AC-052)."""
    payload = {
        "message": "We have refreshed your workspace credentials. Please log in again.",
        "internal_note": "Verified with Okta SAML admin.",
    }
    res = client.post("/api/v1/tickets/CD-1001/reply", json=payload, headers=agent_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ticket_id"] == "CD-1001"
    assert data["status"] == "waiting_on_customer"
    assert "message_id" in data

    # Verify status changed in ticket detail and message is present
    detail = client.get("/api/v1/tickets/CD-1001", headers=viewer_headers).json()
    assert detail["status"] == "waiting_on_customer"
    latest_msg = detail["messages"][-1]
    assert latest_msg["body"] == payload["message"]
    assert latest_msg["author_role"] == "agent"


def test_viewer_reply_forbidden_rbac(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify viewer role is strictly forbidden from dispatching replies (HTTP 403)."""
    payload = {"message": "Viewer trying to reply."}
    res = client.post("/api/v1/tickets/CD-1001/reply", json=payload, headers=viewer_headers)
    assert res.status_code == 403


def test_reply_blank_message_rejected(
    client: TestClient,
    agent_headers: dict[str, str],
):
    """Verify blank or whitespace-only reply message returns 422."""
    payload = {"message": "   "}
    res = client.post("/api/v1/tickets/CD-1001/reply", json=payload, headers=agent_headers)
    assert res.status_code == 422


def test_reply_nonexistent_ticket_returns_404(
    client: TestClient,
    agent_headers: dict[str, str],
):
    """Verify replying to non-existent ticket returns 404."""
    payload = {"message": "Hello"}
    res = client.post("/api/v1/tickets/CD-9999/reply", json=payload, headers=agent_headers)
    assert res.status_code == 404


# -----------------------------------------------------------------------------
# 5. Clarification Request (US-013 / AC-054)
# -----------------------------------------------------------------------------


def test_request_info_success_ac_054(
    client: TestClient,
    agent_headers: dict[str, str],
    viewer_headers: dict[str, str],
):
    """Verify agent can request clarification, appending message and setting waiting_on_customer (AC-054)."""
    payload = {"question": "Could you provide the exact correlation ID from the error screen?"}
    res = client.post("/api/v1/tickets/CD-1002/request-info", json=payload, headers=agent_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ticket_id"] == "CD-1002"
    assert data["status"] == "waiting_on_customer"

    # Verify conversation thread reflects clarification request
    detail = client.get("/api/v1/tickets/CD-1002", headers=viewer_headers).json()
    assert detail["status"] == "waiting_on_customer"
    latest_msg = detail["messages"][-1]
    assert latest_msg["body"] == payload["question"]


def test_viewer_request_info_forbidden_rbac(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify viewer role is forbidden from requesting clarification (HTTP 403)."""
    payload = {"question": "Viewer question"}
    res = client.post("/api/v1/tickets/CD-1002/request-info", json=payload, headers=viewer_headers)
    assert res.status_code == 403


# -----------------------------------------------------------------------------
# 6. Ticket Escalation (US-011 / AC-045, AC-046)
# -----------------------------------------------------------------------------


def test_escalate_ticket_success_ac_045(
    client: TestClient,
    agent_headers: dict[str, str],
    viewer_headers: dict[str, str],
):
    """Verify agent can escalate ticket to target team with policy reason (AC-045)."""
    payload = {
        "target_team": "Security Operations",
        "policy_reason": "Suspected account compromise and anomalous foreign logins (CD-1005).",
        "severity": "critical",
    }
    res = client.post("/api/v1/tickets/CD-1005/escalate", json=payload, headers=agent_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ticket_id"] == "CD-1005"
    assert data["target_team"] == "Security Operations"
    assert data["severity"] == "critical"
    assert data["status"] == "open"
    assert "escalation_id" in data

    # Verify ticket status reflects escalation
    detail = client.get("/api/v1/tickets/CD-1005", headers=viewer_headers).json()
    assert detail["status"] == "escalated"
    assert detail["severity"] == "critical"


def test_viewer_escalate_forbidden_rbac(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify viewer role is forbidden from escalating tickets (HTTP 403)."""
    payload = {
        "target_team": "Security",
        "policy_reason": "Viewer attempting escalation",
        "severity": "high",
    }
    res = client.post("/api/v1/tickets/CD-1005/escalate", json=payload, headers=viewer_headers)
    assert res.status_code == 403


# -----------------------------------------------------------------------------
# 7. Security Penetration Tests
# -----------------------------------------------------------------------------


def test_security_xss_injection_contained_as_data_n4(client: TestClient):
    """Penetration test: XSS payload in ticket body is stored safely as untrusted data without execution (N4)."""
    xss_payload = "<script>alert('DOM-XSS-Injection')</script><img src=x onerror=alert(1)>"
    payload = {
        "customer_id": "cust-101-acme",
        "subject": "XSS Probe",
        "body": xss_payload,
        "channel": "web",
    }
    res = client.post("/api/v1/tickets", json=payload)
    assert res.status_code == 201
    created = res.json()
    # Stored and returned without corruption or execution
    assert created["messages"][0]["body"] == xss_payload


def test_security_sql_injection_in_ticket_filters_safe(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Penetration test: SQL injection in customer_id filter parameter is parameterized safely (CWE-89)."""
    sqli_param = "' OR '1'='1' UNION SELECT * FROM customers; --"
    res = client.get(f"/api/v1/tickets?customer_id={sqli_param}", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    # Must safely match 0 records without executing injected SQL
    assert data["total"] == 0
    assert data["items"] == []
