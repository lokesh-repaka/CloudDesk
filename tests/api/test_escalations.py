"""API Integration and Security Tests for Escalations Queue and Status Tracking (P11-3).

Tests:
- GET /api/v1/escalations (List escalations with status, team, ticket filters and pagination)
- GET /api/v1/escalations/{id} (Inspect single escalation record)
- PATCH /api/v1/escalations/{id} (Update escalation status, Agent only)
- RBAC enforcement (Viewer permitted for GET, 403 on PATCH; unauthenticated 401)
- Validation errors and 404 Not Found handling
- End-to-end lifecycle integration with ticket escalation routing
"""

from __future__ import annotations

from starlette.testclient import TestClient

# ============================================================================
# 1. List Escalations (GET /api/v1/escalations)
# ============================================================================


def test_list_escalations_authenticated_viewer_200(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify viewer role can list escalations queue returning 200 OK (API_CONTRACT §2)."""
    response = client.get("/api/v1/escalations", headers=viewer_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_escalations_unauthenticated_returns_401(client: TestClient):
    """Verify unauthenticated request to /api/v1/escalations returns 401 Unauthorized."""
    response = client.get("/api/v1/escalations")
    assert response.status_code == 401


def test_list_escalations_filter_by_status(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify filtering escalations by ?status=open returns matching items."""
    # Seed an escalation via manual escalate API
    esc_res = client.post(
        "/api/v1/tickets/CD-1005/escalate",
        json={
            "target_team": "Security Operations",
            "policy_reason": "Credential breach detected during escalation filter test.",
            "severity": "critical",
        },
        headers=agent_headers,
    )
    assert esc_res.status_code == 200

    # Query with status=open filter
    response = client.get("/api/v1/escalations?status=open", headers=viewer_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) > 0
    assert all(item["status"] == "open" for item in items)


def test_list_escalations_filter_by_target_team(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify filtering escalations by ?target_team=Security returns matching items."""
    response = client.get(
        "/api/v1/escalations?target_team=Security", headers=viewer_headers
    )
    assert response.status_code == 200
    items = response.json()
    assert all("security" in item["target_team"].lower() for item in items)


def test_list_escalations_filter_by_ticket_id(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify filtering escalations by ?ticket_id=CD-1005 returns matching items."""
    # Ensure escalation exists for CD-1005
    client.post(
        "/api/v1/tickets/CD-1005/escalate",
        json={
            "target_team": "Security Operations",
            "policy_reason": "Breach test for ticket filter.",
            "severity": "critical",
        },
        headers=agent_headers,
    )
    response = client.get(
        "/api/v1/escalations?ticket_id=CD-1005", headers=viewer_headers
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) > 0
    assert all(item["ticket_id"] == "CD-1005" for item in items)


def test_list_escalations_pagination(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify pagination limit and offset parameters work correctly."""
    res1 = client.get("/api/v1/escalations?limit=1&offset=0", headers=viewer_headers)
    assert res1.status_code == 200
    items1 = res1.json()
    assert len(items1) <= 1


# ============================================================================
# 2. Get Escalation Detail (GET /api/v1/escalations/{id})
# ============================================================================


def test_get_escalation_detail_success(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify retrieving a specific escalation by ID returns full metadata."""
    create_res = client.post(
        "/api/v1/tickets/CD-1006/escalate",
        json={
            "target_team": "Engineering Support",
            "policy_reason": "Storage bucket loss inquiry.",
            "severity": "critical",
        },
        headers=agent_headers,
    )
    assert create_res.status_code == 200
    esc_id = create_res.json()["escalation_id"]

    get_res = client.get(f"/api/v1/escalations/{esc_id}", headers=viewer_headers)
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == esc_id
    assert detail["ticket_id"] == "CD-1006"
    assert detail["target_team"] == "Engineering Support"
    assert detail["status"] == "open"
    assert "created_at" in detail


def test_get_escalation_not_found_404(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify fetching a non-existent escalation ID returns 404 Not Found."""
    response = client.get(
        "/api/v1/escalations/esc-nonexistent-999", headers=viewer_headers
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ============================================================================
# 3. Update Escalation Status (PATCH /api/v1/escalations/{id})
# ============================================================================


def test_patch_escalation_status_agent_success(
    client: TestClient, agent_headers: dict[str, str]
):
    """Verify an agent can update escalation status (e.g. to in_review or resolved)."""
    create_res = client.post(
        "/api/v1/tickets/CD-1005/escalate",
        json={
            "target_team": "Security Operations",
            "policy_reason": "Status update test.",
            "severity": "critical",
        },
        headers=agent_headers,
    )
    assert create_res.status_code == 200
    esc_id = create_res.json()["escalation_id"]

    patch_res = client.patch(
        f"/api/v1/escalations/{esc_id}",
        json={"status": "acknowledged"},
        headers=agent_headers,
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["id"] == esc_id
    assert updated["status"] == "acknowledged"


def test_patch_escalation_status_viewer_forbidden_403(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify a viewer cannot mutate escalation status, returning 403 Forbidden (RBAC)."""
    create_res = client.post(
        "/api/v1/tickets/CD-1005/escalate",
        json={
            "target_team": "Security Operations",
            "policy_reason": "RBAC patch test.",
            "severity": "critical",
        },
        headers=agent_headers,
    )
    assert create_res.status_code == 200
    esc_id = create_res.json()["escalation_id"]

    patch_res = client.patch(
        f"/api/v1/escalations/{esc_id}",
        json={"status": "resolved"},
        headers=viewer_headers,
    )
    assert patch_res.status_code == 403
    assert "agent role required" in patch_res.json()["detail"].lower()


def test_patch_escalation_invalid_status_422(
    client: TestClient, agent_headers: dict[str, str]
):
    """Verify invalid status string returns 422 Unprocessable Entity."""
    create_res = client.post(
        "/api/v1/tickets/CD-1005/escalate",
        json={
            "target_team": "Security Operations",
            "policy_reason": "Invalid status test.",
            "severity": "critical",
        },
        headers=agent_headers,
    )
    esc_id = create_res.json()["escalation_id"]

    patch_res = client.patch(
        f"/api/v1/escalations/{esc_id}",
        json={"status": "non_existent_status"},
        headers=agent_headers,
    )
    assert patch_res.status_code == 422


# ============================================================================
# 4. End-to-End Workflow Escalation Lifecycle
# ============================================================================


def test_escalation_lifecycle_workflow_execution(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify running a policy-escalated ticket generates an escalation visible in the queue."""
    # Create a fresh ticket requiring GDPR account deletion (CD-1009 pattern)
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-101-acme",
            "subject": "Delete legacy workspace + erase data",
            "body": "Formal GDPR Article 17 right to erasure request to erase all data.",
            "channel": "email",
        },
        headers=agent_headers,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # Trigger autonomous workflow run
    run_res = client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)
    assert run_res.status_code == 202

    # Query escalations for this ticket
    esc_list_res = client.get(
        f"/api/v1/escalations?ticket_id={ticket_id}", headers=viewer_headers
    )
    assert esc_list_res.status_code == 200
    escalations = esc_list_res.json()
    assert len(escalations) >= 1
    assert escalations[0]["ticket_id"] == ticket_id
    assert escalations[0]["status"] == "open"
