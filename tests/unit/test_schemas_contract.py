"""Unit and Contract Tests for Ticket and Customer API Schemas (P4-1).

Validates Pydantic schema validation rules, boundary conditions, serialization,
domain enum integrity, and security against malformed or malicious payloads.
Satisfies AC-001, AC-002, AC-004, AC-008, AC-020, AC-022, AC-052, and F1/F4.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.schemas.common import (
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    MemoryTypeEnum,
    RoleEnum,
    SeverityEnum,
    TicketStatusEnum,
    WorkflowStatusEnum,
)
from backend.app.schemas.customers import (
    CustomerCreate,
    CustomerDetailResponse,
    CustomerListResponse,
    CustomerMemoryCreate,
    CustomerMemoryResponse,
    CustomerSummaryResponse,
    CustomerUpdate,
    SubscriptionResponse,
    WorkspaceResponse,
)
from backend.app.schemas.tickets import (
    EscalateRequest,
    EscalateResponse,
    ReplyCreate,
    ReplyResponse,
    RequestInfoCreate,
    TicketCreate,
    TicketDetailResponse,
    TicketFilterParams,
    TicketListResponse,
    TicketMessageCreate,
    TicketMessageResponse,
    TicketSummaryResponse,
    WorkflowEventResponse,
    WorkflowRunResponse,
    WorkflowStateResponse,
)

# -----------------------------------------------------------------------------
# Ticket Ingestion & Creation Schemas (US-001 / AC-001, AC-002, AC-004)
# -----------------------------------------------------------------------------


def test_ticket_create_valid_defaults():
    """Verify TicketCreate initializes with valid inputs and default channel='email' (AC-001)."""
    payload = {
        "customer_id": "cust-101-acme",
        "subject": "SSO authentication failure",
        "body": "Users are unable to log in via Okta SAML.",
    }
    ticket = TicketCreate(**payload)
    assert ticket.customer_id == "cust-101-acme"
    assert ticket.subject == "SSO authentication failure"
    assert ticket.body == "Users are unable to log in via Okta SAML."
    assert ticket.channel == ChannelEnum.EMAIL
    assert ticket.channel.value == "email"


def test_ticket_create_all_supported_channels():
    """Verify all canonical channels ('email', 'chat', 'web', 'api') are accepted (AC-001)."""
    for ch in ["email", "chat", "web", "api"]:
        ticket = TicketCreate(
            customer_id="cust-102-globex",
            subject="Rate limit exceeded",
            body="429 Too Many Requests encountered.",
            channel=ch,
        )
        assert ticket.channel.value == ch


def test_ticket_create_rejects_invalid_channel():
    """Verify invalid channels like 'sms' or 'phone' raise validation error (AC-002)."""
    with pytest.raises(ValidationError) as exc_info:
        TicketCreate(
            customer_id="cust-102-globex",
            subject="Rate limit exceeded",
            body="429 Too Many Requests encountered.",
            channel="sms",  # invalid
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("channel",) for err in errors)


def test_ticket_create_rejects_empty_or_whitespace_subject():
    """Verify empty or whitespace-only subject is rejected with ValidationError (AC-002)."""
    for bad_subject in ["", "  ", "\t\n  "]:
        with pytest.raises(ValidationError):
            TicketCreate(
                customer_id="cust-103-initech",
                subject=bad_subject,
                body="Valid body content.",
            )


def test_ticket_create_subject_length_boundaries():
    """Verify subject min_length=3 and max_length=255 boundaries."""
    # Min length boundary: 2 chars fails, 3 chars passes
    with pytest.raises(ValidationError):
        TicketCreate(customer_id="c1", subject="AB", body="Valid body")

    valid_min = TicketCreate(customer_id="c1", subject="ABC", body="Valid body")
    assert valid_min.subject == "ABC"

    # Max length boundary: 255 chars passes, 256 chars fails
    subject_255 = "A" * 255
    valid_max = TicketCreate(customer_id="c1", subject=subject_255, body="Valid body")
    assert valid_max.subject == subject_255

    with pytest.raises(ValidationError):
        TicketCreate(customer_id="c1", subject="A" * 256, body="Valid body")


def test_ticket_create_large_payload_unicode_and_emojis():
    """Verify body handles up to 50,000 characters with unicode and emojis (AC-004)."""
    unicode_snippet = "🔥 Alert! System Error 500 in 日本語 and Español: "
    multiplier = (50000 // len(unicode_snippet)) + 1
    large_body = (unicode_snippet * multiplier)[:50000]

    ticket = TicketCreate(
        customer_id="cust-104-umbrella",
        subject="Large Unicode Crash Log",
        body=large_body,
        channel="web",
    )
    assert len(ticket.body) == 50000
    assert "🔥" in ticket.body
    assert "日本語" in ticket.body


def test_ticket_create_rejects_oversized_body():
    """Verify body exceeding 50,000 characters is rejected with ValidationError."""
    oversized_body = "x" * 50001
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_id="cust-104-umbrella",
            subject="Oversized Ticket",
            body=oversized_body,
        )


def test_ticket_create_forbids_extra_fields():
    """Verify unexpected fields are rejected to prevent mass-assignment attacks."""
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_id="cust-101-acme",
            subject="Security Inquiry",
            body="Details here",
            status="resolved",  # Client cannot force status on create
        )


# -----------------------------------------------------------------------------
# Ticket Message Schemas
# -----------------------------------------------------------------------------


def test_ticket_message_create_and_response():
    """Verify TicketMessageCreate and TicketMessageResponse serialization."""
    msg_create = TicketMessageCreate(
        body="Here is the traceroute log.",
        author_role="customer",
        author_id="cust-101-acme",
    )
    assert msg_create.body == "Here is the traceroute log."

    now = datetime.now(UTC)
    msg_resp = TicketMessageResponse(
        id="msg-uuid-1",
        ticket_id="CD-1001",
        author_role="customer",
        author_id="cust-101-acme",
        body="Here is the traceroute log.",
        created_at=now,
    )
    assert msg_resp.id == "msg-uuid-1"
    assert msg_resp.ticket_id == "CD-1001"
    assert msg_resp.author_role == "customer"
    assert msg_resp.created_at == now


# -----------------------------------------------------------------------------
# Ticket Summary & Detail Responses (US-002 / AC-007, AC-011)
# -----------------------------------------------------------------------------


def test_ticket_summary_response_serialization():
    """Verify TicketSummaryResponse serialization with all required status and severity fields."""
    now = datetime.now(UTC)
    data = {
        "id": "CD-1001",
        "customer_id": "cust-101-acme",
        "assigned_to": None,
        "subject": "SSO login fails for whole team",
        "status": TicketStatusEnum.NEW,
        "severity": SeverityEnum.CRITICAL,
        "category": CategoryEnum.LOGIN_ISSUE,
        "channel": ChannelEnum.WEB,
        "resolution_summary": None,
        "created_at": now,
        "updated_at": now,
        "customer_name": "Acme Corporation",
        "customer_plan": CustomerPlanEnum.ENTERPRISE,
    }
    summary = TicketSummaryResponse(**data)
    assert summary.id == "CD-1001"
    assert summary.status == TicketStatusEnum.NEW
    assert summary.severity == SeverityEnum.CRITICAL
    assert summary.category == CategoryEnum.LOGIN_ISSUE
    assert summary.customer_plan == CustomerPlanEnum.ENTERPRISE


def test_ticket_detail_response_with_messages_and_customer():
    """Verify TicketDetailResponse aggregates messages and customer dossier references."""
    now = datetime.now(UTC)
    ticket_detail = TicketDetailResponse(
        id="CD-1001",
        customer_id="cust-101-acme",
        assigned_to="user-agent-1",
        subject="SSO login fails for whole team",
        status=TicketStatusEnum.IN_PROGRESS,
        severity=SeverityEnum.CRITICAL,
        category=CategoryEnum.LOGIN_ISSUE,
        channel=ChannelEnum.WEB,
        resolution_summary="SAML certificate renewed.",
        created_at=now,
        updated_at=now,
        customer_name="Acme Corporation",
        customer_email="support@acme.test",
        customer_plan=CustomerPlanEnum.ENTERPRISE,
        messages=[
            TicketMessageResponse(
                id="msg-1",
                ticket_id="CD-1001",
                author_role="customer",
                body="Help, we cannot login",
                created_at=now,
            )
        ],
        active_workflow_id="wf-run-123",
    )
    assert len(ticket_detail.messages) == 1
    assert ticket_detail.messages[0].body == "Help, we cannot login"
    assert ticket_detail.active_workflow_id == "wf-run-123"


def test_ticket_filter_params_validation():
    """Verify TicketFilterParams accepts valid enums and pagination boundaries (AC-007)."""
    params = TicketFilterParams(
        status="new",
        severity="high",
        category="billing",
        plan="enterprise",
        limit=25,
        offset=0,
    )
    assert params.status == TicketStatusEnum.NEW
    assert params.severity == SeverityEnum.HIGH
    assert params.category == CategoryEnum.BILLING
    assert params.plan == CustomerPlanEnum.ENTERPRISE
    assert params.limit == 25


def test_ticket_filter_params_rejects_invalid_enums():
    """Verify invalid enum query parameters raise ValidationError (AC-008)."""
    with pytest.raises(ValidationError):
        TicketFilterParams(status="pending_review")

    with pytest.raises(ValidationError):
        TicketFilterParams(severity="urgent")

    with pytest.raises(ValidationError):
        TicketFilterParams(category="hardware_failure")


def test_ticket_list_response_empty_and_populated():
    """Verify TicketListResponse serializes empty list as [] and total: 0 (AC-009)."""
    empty_list = TicketListResponse(items=[], total=0, limit=50, offset=0)
    assert empty_list.items == []
    assert empty_list.total == 0

    serialized = empty_list.model_dump()
    assert serialized["items"] == []
    assert serialized["total"] == 0


# -----------------------------------------------------------------------------
# Workflow & Telemetry Schemas (AC-015, AC-019, AC-064)
# -----------------------------------------------------------------------------


def test_workflow_run_response():
    """Verify WorkflowRunResponse serializes ticket_id, workflow_id, and 202 status."""
    now = datetime.now(UTC)
    resp = WorkflowRunResponse(
        ticket_id="CD-1001",
        workflow_id="wf-uuid-999",
        status=WorkflowStatusEnum.RUNNING,
        started_at=now,
    )
    assert resp.ticket_id == "CD-1001"
    assert resp.workflow_id == "wf-uuid-999"
    assert resp.status == WorkflowStatusEnum.RUNNING
    assert resp.started_at == now


def test_workflow_state_response():
    """Verify WorkflowStateResponse contains completed_nodes, telemetry, and diagnostics."""
    state = WorkflowStateResponse(
        ticket_id="CD-1001",
        workflow_id="wf-uuid-999",
        status=WorkflowStatusEnum.WAITING_ON_APPROVAL,
        current_node="human_approval",
        completed_nodes=[
            "understand_ticket",
            "classify_severity",
            "customer_context",
            "knowledge_retrieval",
            "troubleshooting",
            "resolution_planning",
            "risk_check",
        ],
        classification={"category": "billing", "confidence": 0.95},
        severity={"severity": "medium", "reason": "Refund request under threshold"},
        diagnosis={"probable_causes": ["Duplicate seat billing"]},
        resolution_plan={
            "action": "create_refund_request",
            "amount": 90.0,
            "requires_approval": True,
        },
        escalation=None,
        token_usage={"prompt_tokens": 1250, "completion_tokens": 300, "total_tokens": 1550},
        error=None,
    )
    assert len(state.completed_nodes) == 7
    assert state.current_node == "human_approval"
    assert state.token_usage["total_tokens"] == 1550


def test_workflow_event_response():
    """Verify WorkflowEventResponse captures node telemetry, timing, and token metrics (F13)."""
    now = datetime.now(UTC)
    event = WorkflowEventResponse(
        id="evt-1",
        workflow_id="wf-uuid-999",
        ticket_id="CD-1001",
        event_type="node_completed",
        node_name="knowledge_retrieval",
        data={"query": "SAML Okta error", "retrieved_count": 3},
        duration_ms=420,
        tokens_used=650,
        cost_estimate=0.0013,
        created_at=now,
    )
    assert event.event_type == "node_completed"
    assert event.duration_ms == 420
    assert event.tokens_used == 650


# -----------------------------------------------------------------------------
# Ticket Action Schemas (Reply, Request-Info, Escalate)
# -----------------------------------------------------------------------------


def test_reply_create_and_response():
    """Verify ReplyCreate validates body and ReplyResponse reflects dispatch status (AC-052)."""
    reply = ReplyCreate(
        message="We have refreshed your workspace credentials. Please test again.",
        internal_note="Verified with security team.",
    )
    assert reply.message.startswith("We have refreshed")
    assert reply.internal_note == "Verified with security team."

    # Blank reply should fail validation
    with pytest.raises(ValidationError):
        ReplyCreate(message="   ")

    resp = ReplyResponse(
        ticket_id="CD-1001",
        message_id="msg-new-1",
        status=TicketStatusEnum.WAITING_ON_CUSTOMER,
    )
    assert resp.status == TicketStatusEnum.WAITING_ON_CUSTOMER


def test_request_info_create():
    """Verify RequestInfoCreate validates question length."""
    req_info = RequestInfoCreate(question="Could you share the error code in console?")
    assert len(req_info.question) > 5

    with pytest.raises(ValidationError):
        RequestInfoCreate(question="   ")


def test_escalate_request_and_response():
    """Verify EscalateRequest enforces target_team, policy_reason, and severity."""
    escalate = EscalateRequest(
        target_team="Security Operations",
        policy_reason="Potential credential stuffing and account compromise (CD-1005)",
        severity=SeverityEnum.CRITICAL,
    )
    assert escalate.target_team == "Security Operations"
    assert escalate.severity == SeverityEnum.CRITICAL

    now = datetime.now(UTC)
    resp = EscalateResponse(
        escalation_id="esc-1",
        ticket_id="CD-1005",
        target_team="Security Operations",
        policy_reason="Potential credential stuffing",
        severity=SeverityEnum.CRITICAL,
        status="open",
        created_at=now,
    )
    assert resp.escalation_id == "esc-1"
    assert resp.status == "open"


# -----------------------------------------------------------------------------
# Customer Schemas (US-005 / AC-020, AC-022, AC-023)
# -----------------------------------------------------------------------------


def test_customer_create_and_update():
    """Verify CustomerCreate validates email and CustomerUpdate handles partial fields."""
    cust_create = CustomerCreate(
        name="Wayne Tech",
        email="contact@wayne.test",
        plan=CustomerPlanEnum.PRO,
    )
    assert cust_create.name == "Wayne Tech"
    assert cust_create.email == "contact@wayne.test"
    assert cust_create.plan == CustomerPlanEnum.PRO

    # Bad email fails
    with pytest.raises(ValidationError):
        CustomerCreate(name="Bad", email="not-an-email")

    # Blank name fails
    with pytest.raises(ValidationError):
        CustomerCreate(name="   ", email="test@test.com")

    # CustomerUpdate handles partial updates
    cust_update = CustomerUpdate(name="Wayne Enterprises")
    assert cust_update.name == "Wayne Enterprises"
    assert cust_update.plan is None


def test_customer_summary_and_list_response():
    """Verify CustomerSummaryResponse and CustomerListResponse serialization."""
    now = datetime.now(UTC)
    cust = CustomerSummaryResponse(
        id="cust-101-acme",
        name="Acme Corporation",
        email="support@acme.test",
        plan=CustomerPlanEnum.ENTERPRISE,
        created_at=now,
        updated_at=now,
    )
    assert cust.id == "cust-101-acme"
    assert cust.plan == CustomerPlanEnum.ENTERPRISE

    cust_list = CustomerListResponse(
        items=[cust],
        total=1,
        limit=50,
        offset=0,
    )
    assert len(cust_list.items) == 1
    assert cust_list.total == 1


def test_customer_detail_response_aggregates_context():
    """Verify CustomerDetailResponse aggregates subscriptions, workspaces, tickets, and memory (AC-020)."""
    now = datetime.now(UTC)
    sub = SubscriptionResponse(
        id="sub-1",
        customer_id="cust-101-acme",
        plan=CustomerPlanEnum.ENTERPRISE.value,
        status="active",
        seats=50,
        current_period_end=now,
        created_at=now,
        updated_at=now,
    )
    ws = WorkspaceResponse(
        id="ws-1",
        customer_id="cust-101-acme",
        name="Acme HQ",
        slug="acme-hq",
        storage_used_bytes=5368709120,
        storage_limit_bytes=107374182400,
        created_at=now,
        updated_at=now,
    )
    mem = CustomerMemoryResponse(
        id="mem-1",
        customer_id="cust-101-acme",
        memory_type=MemoryTypeEnum.PREFERENCE,
        content="Customer requires SSO login only.",
        created_at=now,
        updated_at=now,
    )

    detail = CustomerDetailResponse(
        id="cust-101-acme",
        name="Acme Corporation",
        email="support@acme.test",
        plan=CustomerPlanEnum.ENTERPRISE,
        created_at=now,
        updated_at=now,
        active_subscription=sub,
        subscriptions=[sub],
        workspaces=[ws],
        recent_tickets=[],
        memory_notes=[mem],
    )
    assert detail.active_subscription.seats == 50
    assert len(detail.workspaces) == 1
    assert detail.workspaces[0].slug == "acme-hq"
    assert len(detail.memory_notes) == 1


def test_customer_memory_create_and_validation():
    """Verify CustomerMemoryCreate validates memory_type enum and content length."""
    mem_create = CustomerMemoryCreate(
        memory_type=MemoryTypeEnum.TROUBLESHOOTING,
        content="Okta tenant ID is okta-acme-prod.",
    )
    assert mem_create.memory_type == MemoryTypeEnum.TROUBLESHOOTING
    assert mem_create.content == "Okta tenant ID is okta-acme-prod."

    # Blank content fails
    with pytest.raises(ValidationError):
        CustomerMemoryCreate(
            memory_type=MemoryTypeEnum.NOTE,
            content="   ",
        )

    # Invalid memory_type fails
    with pytest.raises(ValidationError):
        CustomerMemoryCreate(
            memory_type="invalid_type",
            content="Valid content",
        )


def test_customer_detail_bounds_memory_notes_to_ten():
    """Verify memory_notes field validator enforces the 10 most recent notes limit (AC-022)."""
    now = datetime.now(UTC)
    eleven_notes = [
        CustomerMemoryResponse(
            id=f"mem-{i}",
            customer_id="cust-101-acme",
            memory_type=MemoryTypeEnum.NOTE,
            content=f"Note entry {i}",
            created_at=now,
            updated_at=now,
        )
        for i in range(11)
    ]
    detail = CustomerDetailResponse(
        id="cust-101-acme",
        name="Acme Corporation",
        email="support@acme.test",
        plan=CustomerPlanEnum.ENTERPRISE,
        created_at=now,
        updated_at=now,
        memory_notes=eleven_notes,
    )
    assert len(detail.memory_notes) == 10
    assert detail.memory_notes[0].id == "mem-0"
    assert detail.memory_notes[9].id == "mem-9"


# -----------------------------------------------------------------------------
# Security & Penetration Tests for API Contract Schemas
# -----------------------------------------------------------------------------


def test_security_schema_sanitizes_or_encapsulates_xss():
    """Penetration test: XSS script tags in subject and body are preserved safely without escaping hazards."""
    xss_payload = "<script>alert('XSS-Exploit')</script><img src=x onerror=alert(1)>"
    ticket = TicketCreate(
        customer_id="cust-101-acme",
        subject=xss_payload[:250],
        body=xss_payload,
        channel="web",
    )
    assert ticket.body == xss_payload
    dumped = ticket.model_dump()
    assert dumped["body"] == xss_payload


def test_security_schema_handles_sql_injection_strings():
    """Penetration test: SQL injection sequences in search and filter inputs are treated as literal strings."""
    sqli_payload = "' OR '1'='1' UNION SELECT * FROM customers; --"
    params = TicketFilterParams(
        customer_id=sqli_payload,
        status="new",
    )
    assert params.customer_id == sqli_payload


def test_security_schema_prototype_pollution_resistance():
    """Penetration test: Schema rejects prototype/attribute pollution keys (__proto__, __class__)."""
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_id="cust-101-acme",
            subject="Valid Subject",
            body="Valid body content",
            __proto__={"admin": True},
        )


def test_role_enum_values_match_contract():
    """Verify role enum values match contract specifications (viewer, agent, admin)."""
    assert RoleEnum.VIEWER.value == "viewer"
    assert RoleEnum.AGENT.value == "agent"
    assert RoleEnum.ADMIN.value == "admin"
