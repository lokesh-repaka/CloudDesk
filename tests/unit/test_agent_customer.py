"""Unit, integration, and security tests for Customer Agent (P9-3).

Tests customer context loading, workspace aggregation, subscription tier resolution,
ticket history retrieval, long-term memory recall, customer data isolation, and boundary safety.
Adheres to CLAUDE.md §5 (F4), §7.1, §7.5, and AC-023, AC-026.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.specialists.customer import CustomerAgent
from backend.app.models.entities import (
    Base,
    Customer,
    CustomerMemory,
    Subscription,
    Ticket,
    Workspace,
)
from backend.app.schemas.common import (
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    SeverityEnum,
    TicketStatusEnum,
)
from backend.app.schemas.workflow import CustomerContext


@pytest.fixture
async def customer_agent() -> CustomerAgent:
    """Instantiate CustomerAgent."""
    return CustomerAgent()


@pytest.fixture
async def test_db_session():
    """Create an isolated SQLite in-memory database with rich customer context fixtures."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        # 1. Customer 1 (Acme - Enterprise with Subscription, Workspace, Tickets, Memory)
        cust1 = Customer(
            id="cust-test-001",
            name="Acme Corporation",
            email="support@acme.corp",
            plan=CustomerPlanEnum.ENTERPRISE.value,
        )
        session.add(cust1)

        ws1 = Workspace(
            id="ws-001",
            customer_id="cust-test-001",
            name="Acme Primary Workspace",
            slug="acme-primary",
            storage_limit_bytes=1_000_000_000,
            storage_used_bytes=250_000_000,
        )
        ws2 = Workspace(
            id="ws-002",
            customer_id="cust-test-001",
            name="Acme Secondary Workspace",
            slug="acme-secondary",
            storage_limit_bytes=500_000_000,
            storage_used_bytes=100_000_000,
        )
        session.add_all([ws1, ws2])

        sub1 = Subscription(
            id="sub-test-001",
            customer_id="cust-test-001",
            plan=CustomerPlanEnum.ENTERPRISE.value,
            status="active",
            seats=150,
        )
        session.add(sub1)

        t1 = Ticket(
            id="t-001",
            customer_id="cust-test-001",
            subject="SSO Login Issue",
            status=TicketStatusEnum.RESOLVED.value,
            severity=SeverityEnum.HIGH.value,
            category=CategoryEnum.LOGIN_ISSUE.value,
            channel=ChannelEnum.WEB.value,
        )
        t2 = Ticket(
            id="t-002",
            customer_id="cust-test-001",
            subject="Storage Quota Warning",
            status=TicketStatusEnum.CLOSED.value,
            severity=SeverityEnum.LOW.value,
            category=CategoryEnum.STORAGE_QUOTA.value,
            channel=ChannelEnum.EMAIL.value,
        )
        session.add_all([t1, t2])

        mem1 = CustomerMemory(
            id="mem-001",
            customer_id="cust-test-001",
            memory_type="preference",
            content="Prefers web portal communications over email.",
        )
        mem2 = CustomerMemory(
            id="mem-002",
            customer_id="cust-test-001",
            memory_type="past_issue",
            content="Past outage resolved by rotating SAML certificates.",
        )
        session.add_all([mem1, mem2])

        # 2. Customer 2 (Beta Corp - Pro without Subscription, isolated data)
        cust2 = Customer(
            id="cust-test-002",
            name="Beta Corp",
            email="admin@beta.org",
            plan=CustomerPlanEnum.PRO.value,
        )
        session.add(cust2)

        t_other = Ticket(
            id="t-099",
            customer_id="cust-test-002",
            subject="Beta Private Incident",
            status=TicketStatusEnum.NEW.value,
            severity=SeverityEnum.CRITICAL.value,
            category=CategoryEnum.SECURITY.value,
            channel=ChannelEnum.API.value,
        )
        session.add(t_other)

        mem_other = CustomerMemory(
            id="mem-099",
            customer_id="cust-test-002",
            memory_type="note",
            content="Confidential private key rotation procedures for Beta Corp.",
        )
        session.add(mem_other)

        await session.commit()
        yield session

    await engine.dispose()


# ============================================================================
# 1. Customer Context Retrieval Tests (F4, AC-026)
# ============================================================================


@pytest.mark.asyncio
async def test_customer_agent_get_context_by_id(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify CustomerAgent loads profile, workspaces, subscription, tickets, and memory by ID."""
    ctx = await customer_agent.get_context(
        customer_id="cust-test-001",
        session=test_db_session,
    )

    assert isinstance(ctx, CustomerContext)
    assert ctx.customer_id == "cust-test-001"
    assert ctx.name == "Acme Corporation"
    assert ctx.email == "support@acme.corp"
    assert ctx.plan == CustomerPlanEnum.ENTERPRISE

    # Workspace summary check
    assert ctx.workspace_summary["workspace_count"] == 2
    assert ctx.workspace_summary["total_storage_quota_bytes"] == 1_500_000_000
    assert ctx.workspace_summary["total_storage_used_bytes"] == 350_000_000
    assert ctx.workspace_summary["seats"] == 150

    # Recent tickets check
    assert len(ctx.recent_tickets) == 2
    ticket_ids = [t["id"] for t in ctx.recent_tickets]
    assert "t-001" in ticket_ids
    assert "t-002" in ticket_ids

    # Memory notes check (AC-008, CLAUDE.md §7.5)
    assert len(ctx.memory_notes) == 2
    mem_contents = [m["content"] for m in ctx.memory_notes]
    assert any("web portal" in c for c in mem_contents)


@pytest.mark.asyncio
async def test_customer_agent_get_context_by_email(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify CustomerAgent can resolve customer context by email."""
    ctx = await customer_agent.get_context(
        email="support@acme.corp",
        session=test_db_session,
    )

    assert isinstance(ctx, CustomerContext)
    assert ctx.customer_id == "cust-test-001"
    assert ctx.name == "Acme Corporation"


@pytest.mark.asyncio
async def test_customer_agent_run_method(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify CustomerAgent.run returns CustomerContext directly (CLAUDE.md §5 F4, §7.1)."""
    ctx = await customer_agent.run(
        customer_id="cust-test-001",
        session=test_db_session,
    )

    assert isinstance(ctx, CustomerContext)
    assert ctx.customer_id == "cust-test-001"
    assert ctx.plan == CustomerPlanEnum.ENTERPRISE


@pytest.mark.asyncio
async def test_customer_agent_no_llm_call(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify CustomerAgent performs zero LLM calls (CLAUDE.md §7.1 non-negotiable)."""
    with patch(
        "backend.app.core.llm.call_structured",
        side_effect=RuntimeError("LLM call attempted!"),
    ) as mock_llm:
        ctx = await customer_agent.run(
            customer_id="cust-test-001",
            session=test_db_session,
        )
        assert isinstance(ctx, CustomerContext)
        mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_customer_agent_plan_fallback_to_free_or_customer_plan(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify customer without an active subscription uses customer entity plan."""
    ctx = await customer_agent.run(
        customer_id="cust-test-002",
        session=test_db_session,
    )

    assert isinstance(ctx, CustomerContext)
    assert ctx.customer_id == "cust-test-002"
    assert ctx.plan == CustomerPlanEnum.PRO
    assert ctx.workspace_summary["workspace_count"] == 0


@pytest.mark.asyncio
async def test_customer_agent_ticket_history_limit(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify ticket_history_limit restricts returned recent ticket count."""
    ctx = await customer_agent.run(
        customer_id="cust-test-001",
        ticket_history_limit=1,
        session=test_db_session,
    )

    assert len(ctx.recent_tickets) == 1


@pytest.mark.asyncio
async def test_customer_agent_memory_notes_limit(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify memory_limit parameter restricts recalled memory notes count."""
    ctx = await customer_agent.run(
        customer_id="cust-test-001",
        memory_limit=1,
        session=test_db_session,
    )

    assert len(ctx.memory_notes) == 1


# ============================================================================
# 2. Error & Input Validation Tests (CWE-20)
# ============================================================================


@pytest.mark.asyncio
async def test_customer_agent_customer_not_found_raises(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify querying non-existent customer ID raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        await customer_agent.run(
            customer_id="cust-nonexistent-999",
            session=test_db_session,
        )


@pytest.mark.asyncio
async def test_customer_agent_missing_identifiers_raises(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Verify invoking run without customer_id and without email raises ValueError."""
    with pytest.raises(ValueError, match="must be provided"):
        await customer_agent.run(
            customer_id="",
            email="",
            session=test_db_session,
        )


# ============================================================================
# 3. Security Audit & Penetration Tests (CWE-284, CWE-400)
# ============================================================================


@pytest.mark.asyncio
async def test_security_cwe_284_cross_customer_isolation(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Penetration test: Verify strict multi-tenant isolation with zero cross-tenant leak (AC-023, CWE-284)."""
    ctx = await customer_agent.run(
        customer_id="cust-test-001",
        session=test_db_session,
    )

    # Ensure no tickets or memory notes belonging to cust-test-002 are present
    assert not any(t["id"] == "t-099" for t in ctx.recent_tickets)
    assert not any(
        "Beta Corp" in m.get("content", "") or "private key" in m.get("content", "")
        for m in ctx.memory_notes
    )


@pytest.mark.asyncio
async def test_security_cwe_400_query_limit_bounds(
    customer_agent: CustomerAgent,
    test_db_session: AsyncSession,
) -> None:
    """Penetration test: Massive query limits are capped to prevent Denial of Service (CWE-400)."""
    ctx = await customer_agent.run(
        customer_id="cust-test-001",
        ticket_history_limit=100_000,
        memory_limit=100_000,
        session=test_db_session,
    )

    assert isinstance(ctx, CustomerContext)
    # Caps ensure bounded execution
    assert len(ctx.recent_tickets) <= 50
    assert len(ctx.memory_notes) <= 10
