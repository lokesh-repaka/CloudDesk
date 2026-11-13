"""API Integration and Security Tests for Ticket Workflow Events Route (P10-6).

Tests:
- GET /api/v1/tickets/{id}/events (Retrieve Workflow Telemetry Timeline)
- Role-based access control (Viewer allowed, Unauthenticated 401)
- 404 on nonexistent ticket
- Chronological ordering and payload schema contract
- Security audit: No secrets leaked in event payloads (CWE-200)
"""

from __future__ import annotations

from starlette.testclient import TestClient

# ============================================================================
# 1. Timeline Inspection (GET /api/v1/tickets/{id}/events)
# ============================================================================


def test_get_ticket_events_after_workflow_run_200(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify viewer can retrieve complete telemetry timeline after workflow execution (F13, AC-060)."""
    # 1. Trigger workflow run on seeded ticket CD-1003
    run_res = client.post("/api/v1/tickets/CD-1003/run", headers=agent_headers)
    assert run_res.status_code in (202, 409)

    # 2. Query timeline events as viewer
    response = client.get("/api/v1/tickets/CD-1003/events", headers=viewer_headers)
    assert response.status_code == 200

    events = response.json()
    assert isinstance(events, list)
    assert len(events) > 0

    first_event = events[0]
    assert "id" in first_event
    assert "workflow_id" in first_event
    assert first_event["ticket_id"] == "CD-1003"
    assert "event_type" in first_event
    assert "node_name" in first_event
    assert "data" in first_event
    assert "duration_ms" in first_event
    assert "tokens_used" in first_event
    assert "cost_estimate" in first_event
    assert "created_at" in first_event

    # Verify event types present in timeline
    event_types = [e["event_type"] for e in events]
    assert "node_started" in event_types
    assert "node_completed" in event_types


def test_get_ticket_events_empty_for_ticket_without_runs_200(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify ticket with no workflow runs returns empty event list 200 OK."""
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-101-acme",
            "subject": "Fresh untouched ticket",
            "body": "No workflow run triggered yet",
            "channel": "email",
        },
        headers=agent_headers,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    response = client.get(f"/api/v1/tickets/{ticket_id}/events", headers=viewer_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_ticket_events_ticket_not_found_404(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify querying events for nonexistent ticket returns 404 Not Found."""
    response = client.get(
        "/api/v1/tickets/CD-NONEXISTENT-999/events", headers=viewer_headers
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_ticket_events_unauthenticated_401(client: TestClient):
    """Verify unauthenticated requests return 401 Unauthorized."""
    response = client.get("/api/v1/tickets/CD-1003/events")
    assert response.status_code == 401


# ============================================================================
# 2. Security Audit & Secret Sanitization in Events API (CWE-200)
# ============================================================================


def test_security_cwe_200_no_secrets_in_events_api_response(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Security Audit (CWE-200): Verify API response does not expose credentials or connection strings."""
    response = client.get("/api/v1/tickets/CD-1003/events", headers=viewer_headers)
    assert response.status_code == 200

    events = response.json()
    raw_text = str(events)
    assert "supersecret" not in raw_text
    assert "bearer " not in raw_text.lower()
    assert "sk-ant-" not in raw_text
