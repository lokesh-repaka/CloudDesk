"""Unit, integration, and security tests for Memory Service (P8-3).

Tests recall_customer (up to 10 notes), record_resolution (past_issue, top 3 troubleshooting steps,
resolution note), secret scrubbing, deduplication, short-term proxy coordination,
tenant isolation, and penetration resilience.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.entities import Base, Customer
from backend.app.repositories.customer_repo import CustomerRepository
from backend.app.schemas.common import CustomerPlanEnum, MemoryTypeEnum
from memory.scrub import REDACTION_MARKER
from memory.service import (
    MemoryService,
    format_customer_notes,
    get_memory_service,
    recall_customer,
    record_resolution,
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Isolated in-memory SQLite database session fixture."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def sample_customer(db_session: AsyncSession) -> Customer:
    """Create a sample customer in the database."""
    repo = CustomerRepository(db_session)
    return await repo.create(
        Customer(
            id=str(uuid.uuid4()),
            name="Apex Global Technologies",
            email=f"admin-{uuid.uuid4().hex[:6]}@apexglobal.tech",
            plan=CustomerPlanEnum.ENTERPRISE.value,
        )
    )


@pytest.fixture
async def second_customer(db_session: AsyncSession) -> Customer:
    """Create a second customer for cross-tenant testing."""
    repo = CustomerRepository(db_session)
    return await repo.create(
        Customer(
            id=str(uuid.uuid4()),
            name="Zeta Logistics",
            email=f"ops-{uuid.uuid4().hex[:6]}@zetalog.com",
            plan=CustomerPlanEnum.BUSINESS.value,
        )
    )


@pytest.fixture
def memory_service(db_session: AsyncSession) -> MemoryService:
    """Instantiate MemoryService with test session."""
    return get_memory_service(session=db_session)


# ============================================================================
# 1. Recall Customer Tests (customer_context node integration, AC-008, §7.5)
# ============================================================================


@pytest.mark.asyncio
async def test_recall_customer_up_to_10_notes(
    memory_service: MemoryService, sample_customer: Customer, db_session: AsyncSession
) -> None:
    """Verify recall_customer returns at most 10 recent notes in newest-first order."""
    # Seed 15 notes for customer
    for i in range(15):
        await memory_service.long_term.add_note(
            customer_id=sample_customer.id,
            memory_type=MemoryTypeEnum.NOTE
            if i % 2 == 0
            else MemoryTypeEnum.PAST_ISSUE,
            content=f"Historical note #{i + 1:02d} for customer.",
        )

    # 1. Recall through memory_service instance
    notes = await memory_service.recall_customer(sample_customer.id, limit=10)
    assert len(notes) == 10
    assert all(n.customer_id == sample_customer.id for n in notes)
    # Check descending order: newest note (#15) first
    assert "Historical note #15" in notes[0].content

    # 2. Recall through top-level convenience function
    fn_notes = await recall_customer(sample_customer.id, limit=5, session=db_session)
    assert len(fn_notes) == 5


@pytest.mark.asyncio
async def test_recall_customer_empty_or_unknown(
    memory_service: MemoryService,
) -> None:
    """Verify recall_customer returns empty list for unknown or blank customer IDs."""
    assert await memory_service.recall_customer("") == []
    assert await memory_service.recall_customer("   ") == []
    assert await memory_service.recall_customer(str(uuid.uuid4())) == []


def test_format_customer_notes_helper() -> None:
    """Verify format_customer_notes serializes memory notes into agent prompt text."""

    class DummyNote:
        def __init__(self, m_type: str, content: str):
            self.memory_type = m_type
            self.content = content

    dummy_notes = [
        DummyNote("preference", "Prefers CLI instructions over UI steps"),
        DummyNote("past_issue", "Frequent OAuth token expiration on SSO login"),
    ]

    formatted = format_customer_notes(dummy_notes)  # type: ignore
    assert "Prefers CLI instructions" in formatted
    assert "[PREFERENCE]" in formatted
    assert "[PAST_ISSUE]" in formatted


# ============================================================================
# 2. Record Resolution Tests (memory_update node integration, F11, AC-050)
# ============================================================================


@pytest.mark.asyncio
async def test_record_resolution_complete_flow(
    memory_service: MemoryService, sample_customer: Customer, db_session: AsyncSession
) -> None:
    """Verify record_resolution saves past_issue, first 3 troubleshooting steps, and note."""
    past_issue = "PostgreSQL query connection timeout during spike"
    steps = [
        "1. Check pg_stat_activity for blocked locks",
        "2. Increased max_connections from 100 to 300",
        "3. Restarted pgpool proxy service",
        "4. Unneeded step that must be truncated",
        "5. Another unneeded step",
    ]
    resolution_note = (
        "Resolved by pool sizing increase and connection idle timeout adjustment"
    )

    recorded = await memory_service.record_resolution(
        customer_id=sample_customer.id,
        past_issue=past_issue,
        troubleshooting_steps=steps,
        resolution_note=resolution_note,
    )

    # Exactly 5 notes: 1 past issue + 3 troubleshooting steps (sliced) + 1 resolution note
    assert len(recorded) == 5

    # Verify types
    past_issue_notes = [
        n for n in recorded if n.memory_type == MemoryTypeEnum.PAST_ISSUE.value
    ]
    troubleshooting_notes = [
        n for n in recorded if n.memory_type == MemoryTypeEnum.TROUBLESHOOTING.value
    ]
    general_notes = [n for n in recorded if n.memory_type == MemoryTypeEnum.NOTE.value]

    assert len(past_issue_notes) == 1
    assert past_issue_notes[0].content == past_issue

    # Sliced to strictly first 3 steps
    assert len(troubleshooting_notes) == 3
    assert "1. Check pg_stat_activity" in troubleshooting_notes[0].content
    assert "2. Increased max_connections" in troubleshooting_notes[1].content
    assert "3. Restarted pgpool proxy" in troubleshooting_notes[2].content
    assert not any("4. Unneeded step" in n.content for n in recorded)

    assert len(general_notes) == 1
    assert general_notes[0].content == resolution_note


@pytest.mark.asyncio
async def test_record_resolution_top_level_function(
    sample_customer: Customer, db_session: AsyncSession
) -> None:
    """Verify record_resolution module-level function executes cleanly."""
    recorded = await record_resolution(
        customer_id=sample_customer.id,
        past_issue="SSL cert expired on subdomain",
        troubleshooting_steps=["Renew cert with certbot", "Reload nginx"],
        resolution_note="Auto-renewal cron configured",
        session=db_session,
    )
    assert len(recorded) == 4


@pytest.mark.asyncio
async def test_record_resolution_deduplication(
    memory_service: MemoryService, sample_customer: Customer
) -> None:
    """Verify exact duplicate notes are skipped across repeated record_resolution calls (AC-051)."""
    past_issue = "DNS cache TTL mismatch"
    steps = ["Flush local resolver", "Set NS TTL to 300s"]
    note = "Resolved NS records propagation"

    # First call records 4 notes
    first_run = await memory_service.record_resolution(
        customer_id=sample_customer.id,
        past_issue=past_issue,
        troubleshooting_steps=steps,
        resolution_note=note,
    )
    assert len(first_run) == 4

    # Second call with identical content skips duplicates and returns empty list
    second_run = await memory_service.record_resolution(
        customer_id=sample_customer.id,
        past_issue=past_issue,
        troubleshooting_steps=steps,
        resolution_note=note,
    )
    assert len(second_run) == 0

    # Total notes in database remains 4
    all_notes = await memory_service.recall_customer(sample_customer.id, limit=20)
    assert len(all_notes) == 4


@pytest.mark.asyncio
async def test_record_resolution_secret_scrubbing(
    memory_service: MemoryService, sample_customer: Customer
) -> None:
    """Verify secrets in resolution steps are scrubbed before storage (AC-070, N7)."""
    leaked_issue = "Database failed with password: SecretDBPassword2026!"
    leaked_steps = [
        "Tried resetting API key sk-live-1234567890abcdef1234567890abcdef",
        "Checked credit card charge 4532 0150 1234 5671 for billing error",
    ]
    leaked_note = (
        "Admin token Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDN refreshed"
    )

    recorded = await memory_service.record_resolution(
        customer_id=sample_customer.id,
        past_issue=leaked_issue,
        troubleshooting_steps=leaked_steps,
        resolution_note=leaked_note,
    )

    assert len(recorded) == 4
    for note in recorded:
        assert "SecretDBPassword2026!" not in note.content
        assert "sk-live-" not in note.content
        assert "4532 0150 1234 5671" not in note.content
        assert REDACTION_MARKER in note.content


# ============================================================================
# 3. Short-Term Memory Coordination & Delegation
# ============================================================================


@pytest.mark.asyncio
async def test_short_term_conversation_coordination(
    memory_service: MemoryService,
) -> None:
    """Verify memory service delegates ticket conversation methods to short-term facade."""
    ticket_id = "TCK-SRV-001"

    # 1. Append message
    ok = await memory_service.append_ticket_message(
        ticket_id=ticket_id,
        role="customer",
        content="Testing memory service proxy integration",
        metadata={"channel": "chat"},
    )
    assert ok is True

    # 2. Get conversation
    history = await memory_service.get_ticket_conversation(ticket_id)
    assert len(history) >= 1
    assert history[0]["role"] == "customer"
    assert "Testing memory service proxy" in history[0]["content"]

    # 3. Clear conversation
    cleared = await memory_service.clear_ticket_conversation(ticket_id)
    assert cleared is True
    assert await memory_service.get_ticket_conversation(ticket_id) == []


@pytest.mark.asyncio
async def test_short_term_workflow_state_coordination(
    memory_service: MemoryService,
) -> None:
    """Verify memory service delegates workflow state methods to short-term facade."""
    ticket_id = "TCK-SRV-STATE"
    state = {"node": "resolution", "completed": False, "attempts": 1}

    # Save state
    assert await memory_service.save_workflow_state(ticket_id, state) is True

    # Get state
    loaded = await memory_service.get_workflow_state(ticket_id)
    assert loaded == state

    # Delete state
    assert await memory_service.delete_workflow_state(ticket_id) is True
    assert await memory_service.get_workflow_state(ticket_id) is None


# ============================================================================
# 4. Security Audit & Penetration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_security_cwe_639_customer_isolation_recall(
    memory_service: MemoryService,
    sample_customer: Customer,
    second_customer: Customer,
) -> None:
    """Penetration test: Customer A's recalled notes never leak to Customer B (CWE-639)."""
    await memory_service.record_resolution(
        customer_id=sample_customer.id,
        past_issue="Confidential enterprise SSO architecture",
        resolution_note="Isolated configuration for Customer A",
    )

    # Customer B recall must be empty
    recalled_b = await memory_service.recall_customer(second_customer.id)
    assert len(recalled_b) == 0
    assert not any("Confidential enterprise" in n.content for n in recalled_b)


@pytest.mark.asyncio
async def test_security_cwe_400_troubleshooting_overflow_capping(
    memory_service: MemoryService, sample_customer: Customer
) -> None:
    """Penetration test: Massive number of troubleshooting steps capped to 3 (CWE-400)."""
    # 500 troubleshooting steps submitted
    excessive_steps = [f"Step {i}: Run diagnostic command" for i in range(500)]

    recorded = await memory_service.record_resolution(
        customer_id=sample_customer.id,
        past_issue="System crash under load",
        troubleshooting_steps=excessive_steps,
        resolution_note="Done",
    )

    # 1 past_issue + exactly 3 troubleshooting steps + 1 resolution_note = 5
    assert len(recorded) == 5
    troubleshooting_notes = [
        n for n in recorded if n.memory_type == MemoryTypeEnum.TROUBLESHOOTING.value
    ]
    assert len(troubleshooting_notes) == 3


@pytest.mark.asyncio
async def test_security_cwe_89_sql_injection_resilience(
    memory_service: MemoryService, sample_customer: Customer
) -> None:
    """Penetration test: SQL injection in resolution notes or customer_id is neutralized (CWE-89)."""
    sqli_payload = "'; DROP TABLE customer_memory; --"

    # SQLi in past issue
    recorded = await memory_service.record_resolution(
        customer_id=sample_customer.id,
        past_issue=f"SQL injection attempt: {sqli_payload}",
        resolution_note="Safe parameter handling",
    )
    assert len(recorded) == 2
    assert sqli_payload in recorded[0].content

    # SQLi in customer_id does not drop tables or crash
    assert await memory_service.recall_customer(sqli_payload) == []


# ============================================================================
# 5. Additional Lifecycle, Alias, and Cache Tests
# ============================================================================


@pytest.mark.asyncio
async def test_memory_service_standalone_session_lifecycle() -> None:
    """Verify recall_customer and record_resolution work without caller-provided session."""
    from backend.app.core.database import create_tables, get_session_factory

    await create_tables()
    factory = get_session_factory()
    async with factory() as sess:
        repo = CustomerRepository(sess)
        cust = await repo.create(
            Customer(
                id=str(uuid.uuid4()),
                name="Standalone Lifecycle Co",
                email=f"standalone-{uuid.uuid4().hex[:6]}@test.org",
                plan=CustomerPlanEnum.PRO.value,
            )
        )
        await sess.commit()

    service = MemoryService()  # no session provided

    # Record resolution using standalone session factory
    recorded = await service.record_resolution(
        customer_id=cust.id,
        past_issue="Standalone session past issue",
        troubleshooting_steps=["Step A", "Step B"],
        resolution_note="Standalone resolution note",
    )
    assert len(recorded) >= 1

    # Recall using standalone session factory
    recalled = await service.recall_customer(cust.id, limit=5)
    assert len(recalled) >= 1
    assert any("Standalone session" in n.content for n in recalled)


def test_memory_service_alias_import() -> None:
    """Verify memory.memory_service imports match memory.service."""
    import memory.memory_service as alias_module

    assert alias_module.MemoryService is MemoryService
    assert alias_module.recall_customer is recall_customer
    assert alias_module.record_resolution is record_resolution


@pytest.mark.asyncio
async def test_short_term_rag_cache_coordination(
    memory_service: MemoryService,
) -> None:
    """Verify memory service delegates RAG retrieval cache operations."""
    mode = "hybrid"
    category = "general"
    top_k = 3
    query = "memory service rag cache query"
    evidence = [{"id": "chunk_1", "score": 0.99}]

    # Set cache
    ok = await memory_service.set_cached_retrieval(
        mode, category, top_k, query, evidence
    )
    assert ok is True

    # Get cache
    cached = await memory_service.get_cached_retrieval(mode, category, top_k, query)
    assert cached == evidence

    # Clear cache
    cleared = await memory_service.clear_retrieval_cache(mode=mode)
    assert cleared >= 1
    assert (
        await memory_service.get_cached_retrieval(mode, category, top_k, query) is None
    )


def test_format_customer_notes_empty() -> None:
    """Verify format_customer_notes with empty list returns clean placeholder."""
    assert format_customer_notes([]) == "No previous customer notes found."


@pytest.mark.asyncio
async def test_record_resolution_empty_inputs(
    memory_service: MemoryService, sample_customer: Customer
) -> None:
    """Verify record_resolution with empty strings or None returns empty list."""
    # Blank customer_id
    assert await memory_service.record_resolution("") == []
    # No notes provided
    assert await memory_service.record_resolution(sample_customer.id) == []
    # Whitespace only
    assert (
        await memory_service.record_resolution(
            sample_customer.id,
            past_issue="   ",
            troubleshooting_steps=["   ", ""],
            resolution_note="   ",
        )
        == []
    )
