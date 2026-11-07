"""Unit tests for Read-Only Support Tools.

Verifies:
- F4: Customer, subscription, and ticket history lookup tools.
- F5: Knowledge retrieval search_docs tool.
- F7 & AC-030/AC-031: check_service_status incident inspection tool.
- Policy compliance: all tools are read-only and execute unattended (approved=False).
- Security audits: SQL injection isolation (CWE-89), query bounding (CWE-400),
  and service parameter validation (CWE-20).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.entities import (
    Base,
    Customer,
    Incident,
    Subscription,
    Ticket,
)
from backend.app.schemas.common import (
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    SeverityEnum,
    TicketStatusEnum,
)
from backend.app.tools.base import ToolDefinition, ToolResult
from backend.app.tools.policy import ToolPolicy
from backend.app.tools.read_tools import (
    check_service_status,
    get_customer,
    get_subscription,
    get_ticket_history,
    register_read_only_tools,
    search_docs,
)
from backend.app.tools.registry import ToolRegistry


@pytest.fixture
async def test_db_session():
    """Create an isolated SQLite in-memory database with populated test fixtures."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # 1. Customer fixture
        cust = Customer(
            id="cust-test-001",
            name="Acme Corporation",
            email="support@acme.corp",
            plan=CustomerPlanEnum.ENTERPRISE.value,
        )
        session.add(cust)

        # 2. Subscription fixture
        sub = Subscription(
            id="sub-test-001",
            customer_id="cust-test-001",
            plan=CustomerPlanEnum.ENTERPRISE.value,
            status="active",
            seats=150,
        )
        session.add(sub)

        # 3. Tickets fixture
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
            subject="Quota Warning",
            status=TicketStatusEnum.CLOSED.value,
            severity=SeverityEnum.LOW.value,
            category=CategoryEnum.STORAGE_QUOTA.value,
            channel=ChannelEnum.EMAIL.value,
        )
        session.add_all([t1, t2])

        # 4. Incident fixture
        inc = Incident(
            id="inc-test-001",
            title="Okta SAML SSO Outage",
            service="clouddesk-identity",
            status="investigating",
            severity="critical",
            impact_summary="Enterprise users encountering authentication failures.",
        )
        session.add(inc)

        await session.commit()
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Functional Tests: get_customer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_customer_by_id(test_db_session: AsyncSession):
    """Retrieve existing customer profile by customer_id."""
    res = await get_customer(customer_id="cust-test-001", session=test_db_session)
    assert res is not None
    assert res["id"] == "cust-test-001"
    assert res["name"] == "Acme Corporation"
    assert res["email"] == "support@acme.corp"
    assert res["plan"] == "enterprise"


@pytest.mark.asyncio
async def test_get_customer_by_email(test_db_session: AsyncSession):
    """Retrieve existing customer profile by email."""
    res = await get_customer(email="support@acme.corp", session=test_db_session)
    assert res is not None
    assert res["id"] == "cust-test-001"
    assert res["name"] == "Acme Corporation"


@pytest.mark.asyncio
async def test_get_customer_not_found(test_db_session: AsyncSession):
    """Querying non-existent customer returns None."""
    res = await get_customer(customer_id="cust-nonexistent", session=test_db_session)
    assert res is None


@pytest.mark.asyncio
async def test_get_customer_missing_args(test_db_session: AsyncSession):
    """Calling get_customer with neither id nor email returns None."""
    res = await get_customer(session=test_db_session)
    assert res is None


# ---------------------------------------------------------------------------
# Functional Tests: get_subscription
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_subscription_active(test_db_session: AsyncSession):
    """Retrieve active subscription for an enterprise customer."""
    res = await get_subscription(customer_id="cust-test-001", session=test_db_session)
    assert res is not None
    assert res["customer_id"] == "cust-test-001"
    assert res["plan"] == "enterprise"
    assert res["status"] == "active"
    assert res["seats"] == 150


@pytest.mark.asyncio
async def test_get_subscription_not_found(test_db_session: AsyncSession):
    """Customer with no active subscription returns None."""
    res = await get_subscription(customer_id="cust-nonexistent", session=test_db_session)
    assert res is None


# ---------------------------------------------------------------------------
# Functional Tests: get_ticket_history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_ticket_history_success_and_limit(test_db_session: AsyncSession):
    """Fetch ticket history respecting the limit parameter."""
    tickets = await get_ticket_history(customer_id="cust-test-001", limit=1, session=test_db_session)
    assert isinstance(tickets, list)
    assert len(tickets) == 1
    assert "subject" in tickets[0]

    all_tickets = await get_ticket_history(customer_id="cust-test-001", limit=10, session=test_db_session)
    assert len(all_tickets) == 2


@pytest.mark.asyncio
async def test_get_ticket_history_empty(test_db_session: AsyncSession):
    """Customer without past tickets returns empty list."""
    tickets = await get_ticket_history(customer_id="cust-other", session=test_db_session)
    assert tickets == []


# ---------------------------------------------------------------------------
# Functional Tests: search_docs (Knowledge RAG)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_docs_hybrid_success():
    """search_docs returns relevant evidence hits from the knowledge base."""
    hits = await search_docs(query="SAML SSO login authentication", top_k=3)
    assert isinstance(hits, list)
    assert len(hits) > 0
    first_hit = hits[0]
    assert "id" in first_hit
    assert "title" in first_hit
    assert "snippet" in first_hit
    assert "score" in first_hit


@pytest.mark.asyncio
async def test_search_docs_category_filter():
    """search_docs applies category filter to scope evidence."""
    hits = await search_docs(query="storage quota", category="storage_quota", top_k=2)
    assert isinstance(hits, list)
    assert len(hits) > 0


# ---------------------------------------------------------------------------
# Functional Tests: check_service_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_service_status_all_services(test_db_session: AsyncSession):
    """check_service_status reports active incidents when checking all services."""
    status_report = await check_service_status(session=test_db_session)
    assert status_report["service"] == "all"
    assert status_report["status"] in ("degraded", "outage")
    assert len(status_report["active_incidents"]) >= 1


@pytest.mark.asyncio
async def test_check_service_status_specific_active_incident(test_db_session: AsyncSession):
    """check_service_status detects active critical incident on clouddesk-identity."""
    status_report = await check_service_status(service_name="clouddesk-identity", session=test_db_session)
    assert status_report["service"] == "clouddesk-identity"
    assert status_report["status"] == "outage"
    assert len(status_report["active_incidents"]) == 1
    assert "SAML" in status_report["active_incidents"][0]["title"]


@pytest.mark.asyncio
async def test_check_service_status_healthy_service(test_db_session: AsyncSession):
    """check_service_status returns operational for an unaffected service."""
    status_report = await check_service_status(service_name="clouddesk-billing", session=test_db_session)
    assert status_report["service"] == "clouddesk-billing"
    assert status_report["status"] == "operational"
    assert status_report["active_incidents"] == []


# ---------------------------------------------------------------------------
# Registry Integration & Policy Verification
# ---------------------------------------------------------------------------

def test_read_only_tools_registered_and_metadata():
    """All 5 read-only tools are properly registered and wrapped in ToolDefinition."""
    registry = ToolRegistry()
    register_read_only_tools(registry)

    expected_tools = [
        "get_customer",
        "get_subscription",
        "get_ticket_history",
        "search_docs",
        "check_service_status",
    ]

    for tool_name in expected_tools:
        assert registry.has_tool(tool_name) is True
        tool_def = registry.get(tool_name)
        assert isinstance(tool_def, ToolDefinition)
        assert len(tool_def.description) > 0


@pytest.mark.asyncio
async def test_registry_executes_read_only_unattended():
    """Read-only tools execute successfully via ToolRegistry without approval."""
    registry = ToolRegistry(policy=ToolPolicy())
    register_read_only_tools(registry)

    # Policy requires_approval must be False
    assert registry.policy.requires_approval("search_docs") is False
    assert registry.policy.is_consequential("search_docs") is False

    # Execute search_docs unattended (approved=False)
    res: ToolResult = await registry.execute("search_docs", {"query": "pricing", "top_k": 2}, approved=False)
    assert res.ok is True
    assert isinstance(res.data, list)
    assert res.error is None
    assert res.tool_name == "search_docs"


# ---------------------------------------------------------------------------
# Security & Penetration Tests (CWE Validation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_cwe_89_sql_injection_isolation(test_db_session: AsyncSession):
    """CWE-89: SQL injection payloads in customer lookup parameters do not leak records."""
    malicious_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE customers; --",
        "cust-test-001' UNION SELECT * FROM customers --",
    ]

    for payload in malicious_payloads:
        res = await get_customer(customer_id=payload, session=test_db_session)
        assert res is None

        res_email = await get_customer(email=payload, session=test_db_session)
        assert res_email is None


@pytest.mark.asyncio
async def test_security_cwe_400_search_docs_oversized_query_safeguard():
    """CWE-400: Massive search queries are truncated/bounded without memory exhaustion."""
    oversized_query = "A" * 60000
    hits = await search_docs(query=oversized_query, top_k=2)
    assert isinstance(hits, list)


@pytest.mark.asyncio
async def test_security_cwe_20_service_name_path_traversal(test_db_session: AsyncSession):
    """CWE-20: Path traversal or command-like strings in service_name are safely filtered."""
    traversal_services = [
        "../../etc/passwd",
        "/etc/shadow",
        "service; rm -rf /",
    ]

    for s_name in traversal_services:
        res = await check_service_status(service_name=s_name, session=test_db_session)
        assert res["service"] == s_name
        assert res["status"] == "operational"
        assert res["active_incidents"] == []
