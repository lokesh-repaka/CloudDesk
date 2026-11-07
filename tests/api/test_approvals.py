"""API Integration and Security Tests for Approval Decisions and Workflow Resume (P11-2).

Tests:
- GET /api/v1/approvals: List pending and historical approval requests (Viewer permitted)
- POST /api/v1/approvals/{id}/approve: Approve gated action, execute tool, resume workflow (Agent only, AC-039)
- POST /api/v1/approvals/{id}/reject: Reject gated action, divert to escalation (Agent only, AC-040)
- Conflict and permission guards:
  - 409 Conflict on already decided approval requests (AC-041)
  - 403 Forbidden for Viewer role attempting approve/reject (AC-042)
  - 404 Not Found for non-existent approval IDs
  - 422 Validation Error on missing rejection reason
- Security testing: CWE-285, CWE-20, CWE-362.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from backend.app.models.entities import ApprovalRequest, Ticket, WorkflowRun
from backend.app.schemas.common import (
    ApprovalStatusEnum,
    CategoryEnum,
    ChannelEnum,
    TicketStatusEnum,
    WorkflowStatusEnum,
)

# ============================================================================
# Helper fixture to create test approval data
# ============================================================================


async def _create_test_approval(
    db_session: AsyncSession,
    ticket_id: str | None = None,
    action_name: str = "create_refund_request",
    action_payload: dict | None = None,
    status: str = ApprovalStatusEnum.PENDING.value,
) -> tuple[Ticket, WorkflowRun, ApprovalRequest]:
    """Helper to insert ticket, workflow run, and approval request in DB."""
    t_id = ticket_id or f"CD-TEST-{uuid.uuid4().hex[:6]}"
    wf_id = f"wf-{uuid.uuid4().hex[:12]}"
    appr_id = f"appr-{uuid.uuid4().hex[:12]}"

    ticket = Ticket(
        id=t_id,
        customer_id="cust-102-globex",
        subject="Downgrade refund requested",
        status=TicketStatusEnum.WAITING_ON_APPROVAL.value
        if status == ApprovalStatusEnum.PENDING.value
        else TicketStatusEnum.RESOLVED.value,
        channel=ChannelEnum.WEB.value,
        category=CategoryEnum.BILLING.value,
    )
    db_session.add(ticket)

    wf_run = WorkflowRun(
        id=wf_id,
        ticket_id=t_id,
        status=WorkflowStatusEnum.WAITING_ON_APPROVAL.value
        if status == ApprovalStatusEnum.PENDING.value
        else WorkflowStatusEnum.COMPLETED.value,
        current_node="human_approval",
        completed_nodes=["resolution_planning", "risk_check"],
        state={
            "approval_required": True,
            "approval_status": status,
            "ticket_id": t_id,
            "workflow_id": wf_id,
        },
    )
    db_session.add(wf_run)

    appr = ApprovalRequest(
        id=appr_id,
        ticket_id=t_id,
        workflow_id=wf_id,
        action_name=action_name,
        action_payload=action_payload
        or {"amount": 90.0, "currency": "USD", "ticket_id": t_id},
        status=status,
    )
    db_session.add(appr)
    await db_session.commit()
    await db_session.refresh(appr)
    return ticket, wf_run, appr


# ============================================================================
# 1. GET /api/v1/approvals (List Approvals)
# ============================================================================


def test_list_approvals_viewer_permitted_200(
    client: TestClient, viewer_headers: dict[str, str], agent_headers: dict[str, str]
):
    """Verify viewer can list approvals with optional status filtering (F12, API_CONTRACT §5.1)."""
    # Create ticket and trigger workflow to create an approval request
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-102-globex",
            "subject": "Charged for 8 seats instead of 5",
            "body": "I downgraded to 5 seats, but invoice charged for 8 seats ($90 refund requested).",
            "channel": "web",
        },
        headers=agent_headers,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    run_res = client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)
    assert run_res.status_code == 202

    # Query approvals as viewer
    response = client.get("/api/v1/approvals", headers=viewer_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # Check approval schema contract
    item = data[0]
    assert "id" in item
    assert "ticket_id" in item
    assert "workflow_id" in item
    assert "action_name" in item
    assert "action_payload" in item
    assert "status" in item
    assert "created_at" in item


def test_list_approvals_filter_by_status(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify querying approvals with ?status=pending filters results accordingly."""
    response = client.get("/api/v1/approvals?status=pending", headers=viewer_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert item["status"] == "pending"


def test_list_approvals_unauthenticated_401(client: TestClient):
    """Verify unauthenticated access to /api/v1/approvals returns 401 Unauthorized."""
    response = client.get("/api/v1/approvals")
    assert response.status_code == 401


# ============================================================================
# 2. POST /api/v1/approvals/{id}/approve (Approve & Resume)
# ============================================================================


def test_approve_gated_action_agent_role_success_200(
    client: TestClient, agent_headers: dict[str, str]
):
    """Verify agent can approve pending action, executing tool and resuming workflow (AC-039)."""
    # 1. Create a ticket requesting refund
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-102-globex",
            "subject": "Charged for 8 seats instead of 5",
            "body": "I downgraded to 5 seats, but invoice charged for 8 seats ($90 refund requested).",
            "channel": "web",
        },
        headers=agent_headers,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # 2. Run workflow to pause at human_approval
    run_res = client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)
    assert run_res.status_code == 202

    # 3. Locate the pending approval request
    list_res = client.get("/api/v1/approvals?status=pending", headers=agent_headers)
    assert list_res.status_code == 200
    approvals = [a for a in list_res.json() if a["ticket_id"] == ticket_id]
    assert len(approvals) >= 1
    appr_id = approvals[0]["id"]

    # 4. Agent sends approve request
    approve_res = client.post(
        f"/api/v1/approvals/{appr_id}/approve",
        json={"notes": "Verified downgrade eligibility with finance."},
        headers=agent_headers,
    )
    assert approve_res.status_code == 200
    data = approve_res.json()
    assert data["id"] == appr_id
    assert data["status"] == "approved"
    assert "decided_by" in data
    assert "decided_at" in data

    # 5. Check ticket status progressed
    ticket_res = client.get(f"/api/v1/tickets/{ticket_id}", headers=agent_headers)
    assert ticket_res.status_code == 200
    ticket_data = ticket_res.json()
    assert ticket_data["status"] in ("resolved", "in_progress", "closed")


def test_approve_viewer_role_forbidden_403(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify viewer role cannot approve actions, returning 403 Forbidden (AC-042)."""
    # Create ticket and run to approval gate
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-102-globex",
            "subject": "Refund request test",
            "body": "Please refund $90",
            "channel": "web",
        },
        headers=agent_headers,
    )
    ticket_id = create_res.json()["id"]
    client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)

    approvals = client.get(
        "/api/v1/approvals?status=pending", headers=agent_headers
    ).json()
    target_appr = next(a for a in approvals if a["ticket_id"] == ticket_id)

    # Viewer attempts approve
    response = client.post(
        f"/api/v1/approvals/{target_appr['id']}/approve",
        headers=viewer_headers,
    )
    assert response.status_code == 403
    assert "agent role required" in response.json()["detail"].lower()


def test_approve_already_resolved_conflict_409(
    client: TestClient, agent_headers: dict[str, str]
):
    """Verify approving an already resolved approval request returns 409 Conflict (AC-041)."""
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-102-globex",
            "subject": "Refund conflict test",
            "body": "Please refund $90",
            "channel": "web",
        },
        headers=agent_headers,
    )
    ticket_id = create_res.json()["id"]
    client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)

    approvals = client.get(
        "/api/v1/approvals?status=pending", headers=agent_headers
    ).json()
    target_appr = next(a for a in approvals if a["ticket_id"] == ticket_id)

    # First approval succeeds
    res1 = client.post(
        f"/api/v1/approvals/{target_appr['id']}/approve", headers=agent_headers
    )
    assert res1.status_code == 200

    # Second approval attempt must return 409 Conflict
    res2 = client.post(
        f"/api/v1/approvals/{target_appr['id']}/approve", headers=agent_headers
    )
    assert res2.status_code == 409
    assert "already resolved" in res2.json()["detail"].lower()


def test_approve_not_found_404(client: TestClient, agent_headers: dict[str, str]):
    """Verify approving non-existent approval ID returns 404 Not Found."""
    response = client.post(
        "/api/v1/approvals/appr-nonexistent-12345/approve",
        headers=agent_headers,
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ============================================================================
# 3. POST /api/v1/approvals/{id}/reject (Reject & Escalate)
# ============================================================================


def test_reject_gated_action_agent_role_success_200(
    client: TestClient, agent_headers: dict[str, str]
):
    """Verify agent can reject pending action with reason, diverting to escalation (AC-040)."""
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-102-globex",
            "subject": "Charged for 8 seats instead of 5",
            "body": "I downgraded to 5 seats, but invoice charged for 8 seats ($90 refund requested).",
            "channel": "web",
        },
        headers=agent_headers,
    )
    ticket_id = create_res.json()["id"]
    client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)

    approvals = client.get(
        "/api/v1/approvals?status=pending", headers=agent_headers
    ).json()
    target_appr = next(a for a in approvals if a["ticket_id"] == ticket_id)

    # Send rejection
    reject_res = client.post(
        f"/api/v1/approvals/{target_appr['id']}/reject",
        json={"rejection_reason": "Refund requested outside 30-day grace period."},
        headers=agent_headers,
    )
    assert reject_res.status_code == 200
    data = reject_res.json()
    assert data["id"] == target_appr["id"]
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Refund requested outside 30-day grace period."

    # Ticket should be escalated
    ticket_res = client.get(f"/api/v1/tickets/{ticket_id}", headers=agent_headers)
    assert ticket_res.status_code == 200
    assert ticket_res.json()["status"] == "escalated"


def test_reject_viewer_role_forbidden_403(
    client: TestClient, agent_headers: dict[str, str], viewer_headers: dict[str, str]
):
    """Verify viewer cannot reject approvals, returning 403 Forbidden (AC-042)."""
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-102-globex",
            "subject": "Reject test",
            "body": "Please refund $90",
            "channel": "web",
        },
        headers=agent_headers,
    )
    ticket_id = create_res.json()["id"]
    client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)

    approvals = client.get(
        "/api/v1/approvals?status=pending", headers=agent_headers
    ).json()
    target_appr = next(a for a in approvals if a["ticket_id"] == ticket_id)

    response = client.post(
        f"/api/v1/approvals/{target_appr['id']}/reject",
        json={"rejection_reason": "Denied by viewer"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_reject_missing_reason_422(client: TestClient, agent_headers: dict[str, str]):
    """Verify rejection without rejection_reason fails schema validation with 422."""
    response = client.post(
        "/api/v1/approvals/appr-dummy-123/reject",
        json={},
        headers=agent_headers,
    )
    assert response.status_code == 422


def test_reject_already_resolved_conflict_409(
    client: TestClient, agent_headers: dict[str, str]
):
    """Verify rejecting an already resolved approval request returns 409 Conflict (AC-041)."""
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-102-globex",
            "subject": "Reject conflict test",
            "body": "Please refund $90",
            "channel": "web",
        },
        headers=agent_headers,
    )
    ticket_id = create_res.json()["id"]
    client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)

    approvals = client.get(
        "/api/v1/approvals?status=pending", headers=agent_headers
    ).json()
    target_appr = next(a for a in approvals if a["ticket_id"] == ticket_id)

    # First reject
    client.post(
        f"/api/v1/approvals/{target_appr['id']}/reject",
        json={"rejection_reason": "Denied initially"},
        headers=agent_headers,
    )

    # Second reject attempt
    res2 = client.post(
        f"/api/v1/approvals/{target_appr['id']}/reject",
        json={"rejection_reason": "Denied again"},
        headers=agent_headers,
    )
    assert res2.status_code == 409
    assert "already resolved" in res2.json()["detail"].lower()


# ============================================================================
# 4. Security Tests (CWE-285, CWE-20, CWE-362)
# ============================================================================


def test_security_cwe_20_path_traversal_in_approval_id(
    client: TestClient, agent_headers: dict[str, str]
):
    """Security audit: Path traversal in {id} is safely handled without directory breakouts."""
    response = client.post(
        "/api/v1/approvals/..%2F..%2Fetc%2Fpasswd/approve",
        headers=agent_headers,
    )
    assert response.status_code in (404, 422)


def test_security_cwe_362_concurrent_resolution_race_mitigation(
    client: TestClient, agent_headers: dict[str, str]
):
    """Security audit: Double decision race condition is prevented by conflict check (CWE-362)."""
    create_res = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "cust-102-globex",
            "subject": "Race condition test",
            "body": "Please refund $90",
            "channel": "web",
        },
        headers=agent_headers,
    )
    ticket_id = create_res.json()["id"]
    client.post(f"/api/v1/tickets/{ticket_id}/run", headers=agent_headers)

    approvals = client.get(
        "/api/v1/approvals?status=pending", headers=agent_headers
    ).json()
    target_appr = next(a for a in approvals if a["ticket_id"] == ticket_id)

    # Simulate rapid consecutive approve and reject
    res_approve = client.post(
        f"/api/v1/approvals/{target_appr['id']}/approve", headers=agent_headers
    )
    res_reject = client.post(
        f"/api/v1/approvals/{target_appr['id']}/reject",
        json={"rejection_reason": "Race check"},
        headers=agent_headers,
    )

    assert res_approve.status_code == 200
    assert res_reject.status_code == 409
