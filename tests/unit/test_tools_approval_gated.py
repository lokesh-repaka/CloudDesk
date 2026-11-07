"""Unit and Security Tests for Approval-Gated and Safe Write Tools.

Verifies:
- F9 & AC-035: Consequential actions (create_refund_request, reset_demo_setting)
  are strictly gated by ToolPolicy approval requirements.
- Unattended safe writes (update_ticket, create_escalation) execute without human intervention.
- Database state persistence in tickets, escalations, and resolution_actions tables.
- Penetration tests: parameter tampering (CWE-770), payload spoofing (CWE-862),
  and SQL injection isolation (CWE-89).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.entities import (
    Base,
    Customer,
    Escalation,
    ResolutionAction,
    Ticket,
    Workspace,
)
from backend.app.schemas.common import (
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    EscalationStatusEnum,
    ResolutionActionStatusEnum,
    SeverityEnum,
    TicketStatusEnum,
)
from backend.app.tools.base import ToolResult
from backend.app.tools.policy import ToolPolicy
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.support_tools import (
    create_escalation,
    create_refund_request,
    register_all_tools,
    register_write_tools,
    reset_demo_setting,
    update_ticket,
)


@pytest.fixture
async def test_db_session():
    """Create an isolated SQLite in-memory database with populated ticket and customer fixtures."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Seed Customer
        cust = Customer(
            id="cust-corp-101",
            name="Globex Tech",
            email="ops@globex.tech",
            plan=CustomerPlanEnum.BUSINESS.value,
        )
        session.add(cust)

        # Seed Workspace
        ws = Workspace(
            id="ws-globex-01",
            customer_id="cust-corp-101",
            name="Globex Primary",
            slug="globex-primary",
        )
        session.add(ws)

        # Seed Tickets
        t1 = Ticket(
            id="t-write-001",
            customer_id="cust-corp-101",
            subject="Billing Discrepancy",
            status=TicketStatusEnum.IN_PROGRESS.value,
            severity=SeverityEnum.MEDIUM.value,
            category=CategoryEnum.BILLING.value,
            channel=ChannelEnum.WEB.value,
        )
        t2 = Ticket(
            id="t-write-002",
            customer_id="cust-corp-101",
            subject="Security Incident Alert",
            status=TicketStatusEnum.NEW.value,
            severity=SeverityEnum.CRITICAL.value,
            category=CategoryEnum.SECURITY.value,
            channel=ChannelEnum.EMAIL.value,
        )
        session.add_all([t1, t2])
        await session.commit()

        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Safe Write Tool Tests: update_ticket
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_ticket_status_and_summary(test_db_session: AsyncSession):
    """update_ticket modifies status and resolution summary in the database."""
    res = await update_ticket(
        ticket_id="t-write-001",
        status=TicketStatusEnum.RESOLVED.value,
        resolution_summary="Applied license credit for 2 unused seats.",
        session=test_db_session,
    )
    assert res is not None
    assert res["id"] == "t-write-001"
    assert res["status"] == TicketStatusEnum.RESOLVED.value
    assert "Applied license credit" in res["resolution_summary"]

    # Verify persisted in database
    stmt = select(Ticket).where(Ticket.id == "t-write-001")
    t = (await test_db_session.execute(stmt)).scalar_one()
    assert t.status == TicketStatusEnum.RESOLVED.value
    assert t.resolution_summary == "Applied license credit for 2 unused seats."


@pytest.mark.asyncio
async def test_update_ticket_not_found(test_db_session: AsyncSession):
    """update_ticket returns None when ticket does not exist."""
    res = await update_ticket(
        ticket_id="t-nonexistent",
        status=TicketStatusEnum.CLOSED.value,
        session=test_db_session,
    )
    assert res is None


@pytest.mark.asyncio
async def test_update_ticket_unattended_via_registry(test_db_session: AsyncSession):
    """update_ticket executes unattended (approved=False) via ToolRegistry."""
    registry = ToolRegistry(policy=ToolPolicy())
    register_write_tools(registry)

    result: ToolResult = await registry.execute(
        "update_ticket",
        {
            "ticket_id": "t-write-001",
            "status": TicketStatusEnum.WAITING_ON_CUSTOMER.value,
            "session": test_db_session,
        },
        approved=False,
    )
    assert result.ok is True
    assert result.data["status"] == TicketStatusEnum.WAITING_ON_CUSTOMER.value


# ---------------------------------------------------------------------------
# Safe Write Tool Tests: create_escalation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_escalation_records_handoff(test_db_session: AsyncSession):
    """create_escalation updates ticket status to escalated and writes an escalation record."""
    res = await create_escalation(
        ticket_id="t-write-002",
        target_team="security_ops",
        reason="Suspicious cross-tenant credential stuffing attempts observed.",
        severity="critical",
        workflow_id="wf-sec-999",
        session=test_db_session,
    )
    assert res is not None
    assert res["ticket_id"] == "t-write-002"
    assert res["target_team"] == "security_ops"
    assert res["status"] == EscalationStatusEnum.OPEN.value

    # Verify ticket state is escalated
    stmt_t = select(Ticket).where(Ticket.id == "t-write-002")
    t = (await test_db_session.execute(stmt_t)).scalar_one()
    assert t.status == TicketStatusEnum.ESCALATED.value

    # Verify escalation row exists
    stmt_e = select(Escalation).where(Escalation.ticket_id == "t-write-002")
    esc = (await test_db_session.execute(stmt_e)).scalar_one()
    assert esc.target_team == "security_ops"
    assert esc.policy_reason == "Suspicious cross-tenant credential stuffing attempts observed."


@pytest.mark.asyncio
async def test_create_escalation_unattended_via_registry(test_db_session: AsyncSession):
    """create_escalation executes unattended (approved=False) via ToolRegistry."""
    registry = ToolRegistry(policy=ToolPolicy())
    register_write_tools(registry)

    result: ToolResult = await registry.execute(
        "create_escalation",
        {
            "ticket_id": "t-write-001",
            "target_team": "billing_specialists",
            "reason": "Payment dispute escalation rule matched.",
            "session": test_db_session,
        },
        approved=False,
    )
    assert result.ok is True
    assert result.data["target_team"] == "billing_specialists"


# ---------------------------------------------------------------------------
# Consequential Write Tool Tests: create_refund_request
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_refund_request_blocked_without_approval(test_db_session: AsyncSession):
    """create_refund_request execution is halted by policy if approved=False."""
    registry = ToolRegistry(policy=ToolPolicy())
    register_write_tools(registry)

    result: ToolResult = await registry.execute(
        "create_refund_request",
        {
            "ticket_id": "t-write-001",
            "customer_id": "cust-corp-101",
            "amount": 75.0,
            "reason": "Accidental seat expansion",
            "session": test_db_session,
        },
        approved=False,
    )
    assert result.ok is False
    assert "requires human approval" in result.error.lower()


@pytest.mark.asyncio
async def test_create_refund_request_success_with_approval(test_db_session: AsyncSession):
    """create_refund_request executes and writes resolution_action when approved=True."""
    registry = ToolRegistry(policy=ToolPolicy())
    register_write_tools(registry)

    result: ToolResult = await registry.execute(
        "create_refund_request",
        {
            "ticket_id": "t-write-001",
            "customer_id": "cust-corp-101",
            "amount": 75.0,
            "reason": "Accidental seat expansion",
            "workflow_id": "wf-ref-123",
            "session": test_db_session,
        },
        approved=True,
    )
    assert result.ok is True
    data = result.data
    assert data["status"] == "executed"
    assert data["amount"] == 75.0
    assert "ref_" in data["refund_id"]

    # Verify recorded in resolution_actions
    stmt = select(ResolutionAction).where(ResolutionAction.ticket_id == "t-write-001")
    action = (await test_db_session.execute(stmt)).scalar_one()
    assert action.action_name == "create_refund_request"
    assert action.status == ResolutionActionStatusEnum.EXECUTED.value
    assert action.action_payload["amount"] == 75.0


# ---------------------------------------------------------------------------
# Consequential Write Tool Tests: reset_demo_setting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_demo_setting_blocked_without_approval(test_db_session: AsyncSession):
    """reset_demo_setting execution is halted by policy if approved=False."""
    registry = ToolRegistry(policy=ToolPolicy())
    register_write_tools(registry)

    result: ToolResult = await registry.execute(
        "reset_demo_setting",
        {
            "ticket_id": "t-write-001",
            "workspace_id": "ws-globex-01",
            "setting_name": "sso_enforced",
            "reset_value": False,
            "session": test_db_session,
        },
        approved=False,
    )
    assert result.ok is False
    assert "requires human approval" in result.error.lower()


@pytest.mark.asyncio
async def test_reset_demo_setting_success_with_approval(test_db_session: AsyncSession):
    """reset_demo_setting executes and writes resolution_action when approved=True."""
    registry = ToolRegistry(policy=ToolPolicy())
    register_write_tools(registry)

    result: ToolResult = await registry.execute(
        "reset_demo_setting",
        {
            "ticket_id": "t-write-001",
            "workspace_id": "ws-globex-01",
            "setting_name": "sso_enforced",
            "reset_value": False,
            "workflow_id": "wf-reset-456",
            "session": test_db_session,
        },
        approved=True,
    )
    assert result.ok is True
    data = result.data
    assert data["status"] == "executed"
    assert data["setting_name"] == "sso_enforced"
    assert data["reset_value"] is False

    # Verify recorded in resolution_actions
    stmt = select(ResolutionAction).where(ResolutionAction.action_name == "reset_demo_setting")
    action = (await test_db_session.execute(stmt)).scalar_one()
    assert action.status == ResolutionActionStatusEnum.EXECUTED.value
    assert action.action_payload["workspace_id"] == "ws-globex-01"


@pytest.mark.asyncio
async def test_reset_demo_setting_direct_invocation(test_db_session: AsyncSession):
    """reset_demo_setting executes directly when called by workflow logic."""
    res = await reset_demo_setting(
        ticket_id="t-write-001",
        workspace_id="ws-globex-01",
        setting_name="demo_banner",
        reset_value=True,
        session=test_db_session,
    )
    assert res["status"] == "executed"
    assert res["setting_name"] == "demo_banner"
    assert res["reset_value"] is True


# ---------------------------------------------------------------------------
# Support Tools Comprehensive Registration Test
# ---------------------------------------------------------------------------

def test_register_all_tools_registers_all_nine():
    """register_all_tools registers exactly 9 support tools (5 read + 4 write)."""
    registry = ToolRegistry()
    tools = register_all_tools(registry)
    assert len(tools) == 9

    expected_tools = {
        # 5 Read
        "get_customer",
        "get_subscription",
        "get_ticket_history",
        "search_docs",
        "check_service_status",
        # 4 Write
        "update_ticket",
        "create_escalation",
        "create_refund_request",
        "reset_demo_setting",
    }
    registered_names = set(registry.list_tool_names())
    assert expected_tools == registered_names


# ---------------------------------------------------------------------------
# Security & Penetration Tests (CWE Validation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_cwe_862_parameter_injection_cannot_grant_approval(test_db_session: AsyncSession):
    """CWE-862: Passing approved=True in args dictionary cannot bypass policy gate."""
    registry = ToolRegistry(policy=ToolPolicy())
    register_write_tools(registry)

    # Attacker injects 'approved': True in JSON args, but registry call has approved=False
    result: ToolResult = await registry.execute(
        "create_refund_request",
        {
            "ticket_id": "t-write-001",
            "customer_id": "cust-corp-101",
            "amount": 999.0,
            "approved": True,
            "session": test_db_session,
        },
        approved=False,
    )
    assert result.ok is False
    assert "requires human approval" in result.error.lower()


@pytest.mark.asyncio
async def test_security_cwe_770_invalid_and_negative_refund_amounts(test_db_session: AsyncSession):
    """CWE-770: Negative, zero, or non-numeric refund amounts are rejected."""
    invalid_amounts = [-50.0, 0.0, "not-a-number"]

    for amt in invalid_amounts:
        with pytest.raises(ValueError, match="Invalid refund amount"):
            await create_refund_request(
                ticket_id="t-write-001",
                customer_id="cust-corp-101",
                amount=amt,  # type: ignore
                reason="Invalid testing",
                session=test_db_session,
            )


@pytest.mark.asyncio
async def test_security_cwe_89_sql_injection_in_write_parameters(test_db_session: AsyncSession):
    """CWE-89: SQL injection payloads in ticket_id or target_team execute safely via parameterized statements."""
    malicious_ids = [
        "' OR '1'='1",
        "'; DROP TABLE tickets; --",
    ]

    for evil_id in malicious_ids:
        # update_ticket safely returns None without database corruption
        res = await update_ticket(
            ticket_id=evil_id,
            status=TicketStatusEnum.RESOLVED.value,
            session=test_db_session,
        )
        assert res is None
