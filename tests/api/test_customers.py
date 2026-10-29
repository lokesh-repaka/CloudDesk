"""API Integration and Security Tests for Customer API Routes (P4-3).

Tests endpoints under /api/v1/customers:
- GET /api/v1/customers (List Customers with Plan Filtering & Pagination)
- POST /api/v1/customers (Register Customer Entity)
- GET /api/v1/customers/{id} (Customer 360 Dossier & Context)
- POST /api/v1/customers/{id}/memory (Add Persistent Memory Note with Secret Scrubbing)
- GET /api/v1/customers/{id}/memory (List Customer Memory Notes)

Verifies AC-020, AC-021, AC-022, AC-023, AC-056, N7, RBAC role hierarchies,
and security resilience against injection, IDOR, data leakage, and unauthorized access.
"""

from starlette.testclient import TestClient

# -----------------------------------------------------------------------------
# 1. Customer Listing & Plan Filtering
# -----------------------------------------------------------------------------


def test_list_customers_unauthenticated_returns_401(client: TestClient):
    """Verify GET /api/v1/customers without authorization returns 401 Unauthorized."""
    res = client.get("/api/v1/customers")
    assert res.status_code == 401
    assert "detail" in res.json()


def test_list_customers_all_roles_authorized(
    client: TestClient,
    viewer_headers: dict[str, str],
    agent_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    """Verify viewer, agent, and admin can all list customer records."""
    for headers in [viewer_headers, agent_headers, admin_headers]:
        res = client.get("/api/v1/customers", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 8  # 8 demo customers seeded
        assert len(data["items"]) >= 8


def test_list_customers_filter_by_plan(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify filtering customers by subscription plan tier ('enterprise', 'pro', 'free')."""
    # Filter enterprise (Acme and Umbrella)
    res_ent = client.get("/api/v1/customers?plan=enterprise", headers=viewer_headers)
    assert res_ent.status_code == 200
    ent_data = res_ent.json()
    assert ent_data["total"] >= 2
    for item in ent_data["items"]:
        assert item["plan"] == "enterprise"

    # Filter pro (Initech and Wayne Tech)
    res_pro = client.get("/api/v1/customers?plan=pro", headers=viewer_headers)
    assert res_pro.status_code == 200
    pro_data = res_pro.json()
    assert pro_data["total"] >= 2
    for item in pro_data["items"]:
        assert item["plan"] == "pro"

    # Filter free (Cyberdyne and Pied Piper)
    res_free = client.get("/api/v1/customers?plan=free", headers=viewer_headers)
    assert res_free.status_code == 200
    free_data = res_free.json()
    assert free_data["total"] >= 2
    for item in free_data["items"]:
        assert item["plan"] == "free"


def test_list_customers_invalid_plan_returns_422(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify invalid plan query parameter returns 422 Unprocessable Entity."""
    res = client.get("/api/v1/customers?plan=unlimited_vip", headers=viewer_headers)
    assert res.status_code == 422


def test_list_customers_pagination(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify pagination limit and offset controls."""
    res = client.get("/api/v1/customers?limit=3&offset=0", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 3
    assert data["limit"] == 3
    assert data["offset"] == 0
    assert data["total"] >= 8


# -----------------------------------------------------------------------------
# 2. Customer 360-Degree Dossier (US-005 / AC-020 to AC-023)
# -----------------------------------------------------------------------------


def test_get_customer_dossier_success_ac_020(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify GET /api/v1/customers/{id} aggregates 360 dossier with context (AC-020)."""
    res = client.get("/api/v1/customers/cust-101-acme", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()

    # Customer profile
    assert data["id"] == "cust-101-acme"
    assert data["name"] == "Acme Corporation"
    assert data["email"] == "support@acme.test"
    assert data["plan"] == "enterprise"

    # Active subscription
    assert data["active_subscription"] is not None
    assert data["active_subscription"]["plan"] == "enterprise"
    assert data["active_subscription"]["seats"] == 50

    # Workspaces
    assert "workspaces" in data
    assert len(data["workspaces"]) >= 1
    assert data["workspaces"][0]["name"] == "Acme Main"
    assert data["workspaces"][0]["storage_limit_bytes"] > 0

    # Recent tickets
    assert "recent_tickets" in data
    assert isinstance(data["recent_tickets"], list)
    ticket_ids = [t["id"] for t in data["recent_tickets"]]
    assert "CD-1001" in ticket_ids

    # Memory notes list
    assert "memory_notes" in data
    assert isinstance(data["memory_notes"], list)


def test_get_customer_dossier_not_found(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify non-existent customer ID returns HTTP 404 Not Found."""
    res = client.get("/api/v1/customers/cust-999-missing", headers=viewer_headers)
    assert res.status_code == 404
    assert "Customer cust-999-missing not found" in res.json()["detail"]


def test_get_customer_dossier_unauthenticated(client: TestClient):
    """Verify unauthenticated request to customer dossier returns 401."""
    res = client.get("/api/v1/customers/cust-101-acme")
    assert res.status_code == 401


def test_customer_context_strict_isolation_ac_023(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify queries filter strictly on customer ID without leaking other customers' data (AC-023)."""
    # Check Globex customer dossier
    res = client.get("/api/v1/customers/cust-102-globex", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "cust-102-globex"

    # Every ticket in recent_tickets must belong only to Globex
    for t in data["recent_tickets"]:
        assert t["customer_id"] == "cust-102-globex"

    # Every workspace must belong only to Globex
    for ws in data["workspaces"]:
        assert ws["customer_id"] == "cust-102-globex"


# -----------------------------------------------------------------------------
# 3. Persistent Customer Memory & Secret Scrubbing (US-014 / AC-056, N7)
# -----------------------------------------------------------------------------


def test_add_customer_memory_success_ac_056(
    client: TestClient,
    agent_headers: dict[str, str],
    viewer_headers: dict[str, str],
):
    """Verify agent can add permanent memory note, visible in subsequent dossier lookups (AC-056)."""
    payload = {
        "memory_type": "troubleshooting",
        "content": "Okta SSO integration requires manual certificate upload after IdP renewal.",
    }
    res = client.post(
        "/api/v1/customers/cust-101-acme/memory", json=payload, headers=agent_headers
    )
    assert res.status_code == 201
    created = res.json()
    assert created["customer_id"] == "cust-101-acme"
    assert created["memory_type"] == "troubleshooting"
    assert created["content"] == payload["content"]
    assert "id" in created

    # Verify visible in customer dossier
    dossier = client.get(
        "/api/v1/customers/cust-101-acme", headers=viewer_headers
    ).json()
    note_contents = [n["content"] for n in dossier["memory_notes"]]
    assert any(
        "Okta SSO integration requires manual certificate" in c for c in note_contents
    )


def test_add_customer_memory_scrubs_secrets_n7(
    client: TestClient,
    agent_headers: dict[str, str],
):
    """Verify secrets (credit cards, API keys, passwords) are scrubbed before storage (N7 / US-022)."""
    raw_content = (
        "Customer provided temporary debugging key: sk-live-998877665544332211 "
        "and payment card 4111-2222-3333-4444 with password: AdminP@ssword! for verification."
    )
    payload = {
        "memory_type": "troubleshooting",
        "content": raw_content,
    }
    res = client.post(
        "/api/v1/customers/cust-101-acme/memory", json=payload, headers=agent_headers
    )
    assert res.status_code == 201
    stored = res.json()["content"]

    # Verify sensitive data was redacted
    assert "4111-2222-3333-4444" not in stored
    assert "sk-live-998877665544332211" not in stored
    assert "AdminP@ssword!" not in stored
    assert "[REDACTED]" in stored


def test_viewer_add_memory_forbidden_rbac(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify viewer role is strictly forbidden from recording memory notes (HTTP 403)."""
    payload = {
        "memory_type": "note",
        "content": "Viewer attempt to modify memory.",
    }
    res = client.post(
        "/api/v1/customers/cust-101-acme/memory", json=payload, headers=viewer_headers
    )
    assert res.status_code == 403


def test_add_memory_nonexistent_customer_returns_404(
    client: TestClient,
    agent_headers: dict[str, str],
):
    """Verify adding memory to non-existent customer returns 404."""
    payload = {"memory_type": "note", "content": "Valid note"}
    res = client.post(
        "/api/v1/customers/cust-999-missing/memory", json=payload, headers=agent_headers
    )
    assert res.status_code == 404


def test_add_memory_empty_content_rejected(
    client: TestClient,
    agent_headers: dict[str, str],
):
    """Verify empty or whitespace-only memory note content returns 422."""
    payload = {"memory_type": "note", "content": "   "}
    res = client.post(
        "/api/v1/customers/cust-101-acme/memory", json=payload, headers=agent_headers
    )
    assert res.status_code == 422


def test_customer_dossier_bounds_memory_notes_to_ten_ac_022(
    client: TestClient,
    agent_headers: dict[str, str],
    viewer_headers: dict[str, str],
):
    """Verify customer dossier strictly limits recalled memory notes to 10 (AC-022)."""
    # Add multiple distinct notes to Initech
    for i in range(12):
        client.post(
            "/api/v1/customers/cust-103-initech/memory",
            json={
                "memory_type": "note",
                "content": f"Automated test note #{i} for Initech",
            },
            headers=agent_headers,
        )

    # Fetch dossier
    dossier = client.get(
        "/api/v1/customers/cust-103-initech", headers=viewer_headers
    ).json()
    assert len(dossier["memory_notes"]) <= 10


def test_list_customer_memory_notes_endpoint(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify dedicated GET /api/v1/customers/{id}/memory lists customer memory notes."""
    res = client.get("/api/v1/customers/cust-101-acme/memory", headers=viewer_headers)
    assert res.status_code == 200
    notes = res.json()
    assert isinstance(notes, list)


# -----------------------------------------------------------------------------
# 4. Customer Creation & Integrity
# -----------------------------------------------------------------------------


def test_create_customer_success(
    client: TestClient,
    agent_headers: dict[str, str],
):
    """Verify agent can create a new customer entity."""
    payload = {
        "name": "Massive Dynamic",
        "email": "contact@massivedynamic.test",
        "plan": "business",
    }
    res = client.post("/api/v1/customers", json=payload, headers=agent_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Massive Dynamic"
    assert data["email"] == "contact@massivedynamic.test"
    assert data["plan"] == "business"
    assert "id" in data


def test_create_customer_duplicate_email_conflict(
    client: TestClient,
    agent_headers: dict[str, str],
):
    """Verify registering duplicate customer email returns HTTP 409 Conflict."""
    payload = {
        "name": "Acme Copycat",
        "email": "support@acme.test",  # Already exists
        "plan": "free",
    }
    res = client.post("/api/v1/customers", json=payload, headers=agent_headers)
    assert res.status_code == 409
    assert "already registered" in res.json()["detail"].lower()


def test_viewer_create_customer_forbidden_rbac(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Verify viewer role is forbidden from registering new customers (HTTP 403)."""
    payload = {
        "name": "Unauthorized Company",
        "email": "unauth@company.test",
        "plan": "free",
    }
    res = client.post("/api/v1/customers", json=payload, headers=viewer_headers)
    assert res.status_code == 403


# -----------------------------------------------------------------------------
# 5. Security & Penetration Tests
# -----------------------------------------------------------------------------


def test_security_sql_injection_in_customer_filters(
    client: TestClient,
    viewer_headers: dict[str, str],
):
    """Penetration test: SQL injection in plan query parameter is rejected by enum validation (CWE-89)."""
    sqli_param = "' OR '1'='1' UNION SELECT * FROM customers; --"
    res = client.get(f"/api/v1/customers?plan={sqli_param}", headers=viewer_headers)
    assert res.status_code == 422  # Enum blocks invalid plan strings


def test_security_xss_in_customer_memory_stored_safely(
    client: TestClient,
    agent_headers: dict[str, str],
):
    """Penetration test: XSS script in memory note is encapsulated as plain text data without execution (CWE-79)."""
    xss_content = "<script>alert('Stored-Memory-XSS')</script><iframe src=javascript:alert(1)></iframe>"
    res = client.post(
        "/api/v1/customers/cust-101-acme/memory",
        json={"memory_type": "note", "content": xss_content},
        headers=agent_headers,
    )
    assert res.status_code == 201
    assert res.json()["content"] == xss_content
