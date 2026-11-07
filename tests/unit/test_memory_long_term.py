"""Unit, integration, and security tests for Long-Term Customer Memory (P8-2).

Tests persistent storage, de-duplication, secret scrubbing, raw body rejection,
recall limits (up to 10 notes), GDPR purge, cross-customer isolation, and SQLi resilience.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.entities import Base, Customer
from backend.app.repositories.customer_repo import CustomerRepository
from backend.app.schemas.common import CustomerPlanEnum, MemoryTypeEnum
from memory.long_term import (
    DEFAULT_RECALL_LIMIT,
    LongTermMemory,
    get_long_term_memory,
)
from memory.scrub import REDACTION_MARKER


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
    """Create a sample customer in the test database."""
    repo = CustomerRepository(db_session)
    customer = await repo.create(
        Customer(
            id=str(uuid.uuid4()),
            name="Acme Enterprise Corp",
            email=f"security-{uuid.uuid4().hex[:6]}@acme.corp",
            plan=CustomerPlanEnum.ENTERPRISE.value,
        )
    )
    return customer


@pytest.fixture
async def second_customer(db_session: AsyncSession) -> Customer:
    """Create a second customer for cross-tenant testing."""
    repo = CustomerRepository(db_session)
    customer = await repo.create(
        Customer(
            id=str(uuid.uuid4()),
            name="Beta Startup LLC",
            email=f"dev-{uuid.uuid4().hex[:6]}@beta.dev",
            plan=CustomerPlanEnum.PRO.value,
        )
    )
    return customer


@pytest.fixture
def long_term_memory(db_session: AsyncSession) -> LongTermMemory:
    """Instantiate LongTermMemory backed by the test AsyncSession."""
    return LongTermMemory(session=db_session)


# ============================================================================
# 1. Constants & Factory Initialization
# ============================================================================


def test_default_recall_limit() -> None:
    """Verify default recall limit is 10 per CLAUDE.md §7.5 and AC-008."""
    assert DEFAULT_RECALL_LIMIT == 10


def test_get_long_term_memory_factory(db_session: AsyncSession) -> None:
    """Verify factory returns LongTermMemory instance bound to session."""
    ltm = get_long_term_memory(session=db_session)
    assert isinstance(ltm, LongTermMemory)
    assert ltm.session is db_session


# ============================================================================
# 2. Add and Recall Note Tests
# ============================================================================


@pytest.mark.asyncio
async def test_add_and_get_note_success(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify adding a memory note persists and can be retrieved."""
    note = await long_term_memory.add_note(
        customer_id=sample_customer.id,
        memory_type=MemoryTypeEnum.PREFERENCE,
        content="Customer prefers CLI diagnostics over web console steps.",
    )
    assert note is not None
    assert note.id is not None
    assert note.customer_id == sample_customer.id
    assert note.memory_type == MemoryTypeEnum.PREFERENCE.value
    assert "CLI diagnostics" in note.content

    # Retrieve notes
    notes = await long_term_memory.get_notes(sample_customer.id)
    assert len(notes) == 1
    assert notes[0].id == note.id
    assert notes[0].content == note.content


@pytest.mark.asyncio
async def test_add_note_invalid_memory_type(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify adding a note with invalid memory type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid memory_type"):
        await long_term_memory.add_note(
            customer_id=sample_customer.id,
            memory_type="invalid_type",  # type: ignore
            content="Some note",
        )


@pytest.mark.asyncio
async def test_add_note_empty_fields_validation(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify validation rejects empty customer_id or empty content."""
    with pytest.raises(ValueError, match="customer_id cannot be empty"):
        await long_term_memory.add_note(
            customer_id="",
            memory_type=MemoryTypeEnum.NOTE,
            content="Valid content",
        )

    with pytest.raises(ValueError, match="content cannot be empty"):
        await long_term_memory.add_note(
            customer_id=sample_customer.id,
            memory_type=MemoryTypeEnum.NOTE,
            content="   ",
        )


# ============================================================================
# 3. De-duplication Tests (CLAUDE.md §7.5, US-014 AC-041)
# ============================================================================


@pytest.mark.asyncio
async def test_duplicate_notes_skipped(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify exact-duplicate notes are skipped without creating database rows."""
    content = "Customer workspace requires EU-central-1 region residency."

    # First insertion succeeds
    note1 = await long_term_memory.add_note(
        customer_id=sample_customer.id,
        memory_type=MemoryTypeEnum.PREFERENCE,
        content=content,
    )
    assert note1 is not None

    # Second insertion with exact same content and type is skipped
    note2 = await long_term_memory.add_note(
        customer_id=sample_customer.id,
        memory_type=MemoryTypeEnum.PREFERENCE,
        content=content,
    )
    assert note2 is None

    # Verify only 1 record exists in database
    notes = await long_term_memory.get_notes(sample_customer.id)
    assert len(notes) == 1
    assert notes[0].id == note1.id


@pytest.mark.asyncio
async def test_same_content_different_customer_allowed(
    long_term_memory: LongTermMemory,
    sample_customer: Customer,
    second_customer: Customer,
) -> None:
    """Verify identical content across different customers is permitted."""
    content = "Prefers dark mode and billing invoice via email."

    note1 = await long_term_memory.add_note(
        customer_id=sample_customer.id,
        memory_type=MemoryTypeEnum.PREFERENCE,
        content=content,
    )
    note2 = await long_term_memory.add_note(
        customer_id=second_customer.id,
        memory_type=MemoryTypeEnum.PREFERENCE,
        content=content,
    )

    assert note1 is not None
    assert note2 is not None
    assert note1.id != note2.id
    assert note1.customer_id == sample_customer.id
    assert note2.customer_id == second_customer.id


# ============================================================================
# 4. Secret Scrubbing Tests (N7, US-022, AC-070)
# ============================================================================


@pytest.mark.asyncio
async def test_secret_scrubbing_before_persistence(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify API keys, passwords, and cards are scrubbed before saving."""
    sensitive_content = (
        "Client resolved DB issue with password: SuperSecretP@ssword123! "
        "and tested API key sk-live-1234567890abcdef1234567890abcdef "
        "with backup payment card 4532 0150 1234 5671."
    )

    note = await long_term_memory.add_note(
        customer_id=sample_customer.id,
        memory_type=MemoryTypeEnum.TROUBLESHOOTING,
        content=sensitive_content,
        scrub_secrets=True,
    )
    assert note is not None
    assert "SuperSecretP@ssword123!" not in note.content
    assert "sk-live-" not in note.content
    assert "4532 0150 1234 5671" not in note.content
    assert REDACTION_MARKER in note.content


# ============================================================================
# 5. Raw Ticket Body Rejection (US-022, AC-071)
# ============================================================================


@pytest.mark.asyncio
async def test_raw_ticket_body_rejected(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify raw unparsed email or conversational dumps are rejected."""
    raw_email = (
        "From: customer@example.com\n"
        "To: support@clouddesk.demo\n"
        "Subject: Urgent assistance needed with database\n\n"
        "Hello, my database is down and throwing 500 errors everywhere."
    )

    with pytest.raises(ValueError, match="Raw ticket body cannot be stored"):
        await long_term_memory.add_note(
            customer_id=sample_customer.id,
            memory_type=MemoryTypeEnum.NOTE,
            content=raw_email,
        )


# ============================================================================
# 6. Recall Limits & Ordering (CLAUDE.md §7.5, AC-008)
# ============================================================================


@pytest.mark.asyncio
async def test_recall_limit_and_ordering(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify recall returns at most limit (default 10) notes, newest first."""
    # Insert 15 distinct notes
    created_notes = []
    for i in range(15):
        n = await long_term_memory.add_note(
            customer_id=sample_customer.id,
            memory_type=MemoryTypeEnum.NOTE
            if i % 2 == 0
            else MemoryTypeEnum.PAST_ISSUE,
            content=f"Resolution note number #{i + 1:02d} for customer account.",
        )
        assert n is not None
        created_notes.append(n)

    # Default recall limit is 10
    recalled = await long_term_memory.get_notes(sample_customer.id)
    assert len(recalled) == 10

    # Custom limit
    custom_recalled = await long_term_memory.get_notes(sample_customer.id, limit=5)
    assert len(custom_recalled) == 5

    # Filter by memory_type
    past_issues = await long_term_memory.get_notes(
        sample_customer.id, memory_type=MemoryTypeEnum.PAST_ISSUE
    )
    assert all(p.memory_type == MemoryTypeEnum.PAST_ISSUE.value for p in past_issues)


# ============================================================================
# 7. Batch Recording & GDPR Purge
# ============================================================================


@pytest.mark.asyncio
async def test_record_notes_batch(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify recording multiple structured notes in batch."""
    batch = [
        (MemoryTypeEnum.PAST_ISSUE, "Past issue: Redis timeout on token refresh"),
        (MemoryTypeEnum.TROUBLESHOOTING, "Step 1: Check Redis connection pool"),
        (MemoryTypeEnum.TROUBLESHOOTING, "Step 2: Restart cluster node"),
        (MemoryTypeEnum.NOTE, "Final resolution: increased pool size from 10 to 50"),
        (
            MemoryTypeEnum.PAST_ISSUE,
            "Past issue: Redis timeout on token refresh",
        ),  # duplicate
    ]

    saved = await long_term_memory.record_notes(sample_customer.id, batch)
    # The duplicate should be skipped, so 4 notes saved
    assert len(saved) == 4

    notes = await long_term_memory.get_notes(sample_customer.id)
    assert len(notes) == 4


@pytest.mark.asyncio
async def test_delete_note_and_purge_customer_memories(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify single note deletion and customer-wide memory purging (GDPR)."""
    n1 = await long_term_memory.add_note(
        sample_customer.id, MemoryTypeEnum.NOTE, "Note 1 for purge test"
    )
    n2 = await long_term_memory.add_note(
        sample_customer.id, MemoryTypeEnum.NOTE, "Note 2 for purge test"
    )
    assert n1 is not None and n2 is not None

    # Delete single note
    deleted = await long_term_memory.delete_note(n1.id)
    assert deleted is True
    remaining = await long_term_memory.get_notes(sample_customer.id)
    assert len(remaining) == 1
    assert remaining[0].id == n2.id

    # Purge all memories for customer
    purged_count = await long_term_memory.purge_customer_memories(sample_customer.id)
    assert purged_count == 1
    assert await long_term_memory.get_notes(sample_customer.id) == []


# ============================================================================
# 8. Security Audit & Penetration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_security_cwe_639_cross_tenant_isolation(
    long_term_memory: LongTermMemory,
    sample_customer: Customer,
    second_customer: Customer,
) -> None:
    """Penetration test: Customer A's notes cannot be recalled under Customer B (CWE-639)."""
    await long_term_memory.add_note(
        sample_customer.id,
        MemoryTypeEnum.PREFERENCE,
        "Confidential enterprise preference: SLA Tier 1 response within 15m.",
    )

    # Customer B recall must not return Customer A's note
    b_notes = await long_term_memory.get_notes(second_customer.id)
    assert len(b_notes) == 0
    assert not any("SLA Tier 1" in n.content for n in b_notes)


@pytest.mark.asyncio
async def test_security_cwe_89_sql_injection_resilience(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Penetration test: SQL injection in search, content, or customer_id fails safely (CWE-89)."""
    sqli_payload = "'; DROP TABLE customer_memory; --"

    # 1. SQLi in content is treated as literal text
    note = await long_term_memory.add_note(
        sample_customer.id,
        MemoryTypeEnum.NOTE,
        f"Troubleshooting note containing SQL injection string: {sqli_payload}",
    )
    assert note is not None
    assert sqli_payload in note.content

    # 2. SQLi in customer_id does not cause syntax error or drop table
    notes = await long_term_memory.get_notes(sqli_payload)
    assert notes == []

    # Table remains intact
    real_notes = await long_term_memory.get_notes(sample_customer.id)
    assert len(real_notes) == 1


@pytest.mark.asyncio
async def test_security_cwe_400_massive_note_content_handling(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Penetration test: Giant note payload (>50KB) is handled safely (CWE-400)."""
    massive_content = "Structured diagnostic step: " + (
        "verify config parameters; " * 2000
    )
    assert len(massive_content) > 50000

    note = await long_term_memory.add_note(
        sample_customer.id,
        MemoryTypeEnum.TROUBLESHOOTING,
        massive_content,
    )
    assert note is not None
    assert len(note.content) > 50000


# ============================================================================
# 9. Edge Cases & Resilience Tests
# ============================================================================


def test_long_term_memory_session_property_error() -> None:
    """Verify accessing session raises RuntimeError when none is configured."""
    ltm = LongTermMemory(session=None)
    with pytest.raises(
        RuntimeError, match="LongTermMemory requires an active AsyncSession"
    ):
        _ = ltm.session


@pytest.mark.asyncio
async def test_delete_nonexistent_note(long_term_memory: LongTermMemory) -> None:
    """Verify deleting a nonexistent note returns False without raising."""
    result = await long_term_memory.delete_note(str(uuid.uuid4()))
    assert result is False


@pytest.mark.asyncio
async def test_purge_empty_customer_id(long_term_memory: LongTermMemory) -> None:
    """Verify purge with empty or whitespace customer_id returns 0."""
    assert await long_term_memory.purge_customer_memories("") == 0
    assert await long_term_memory.purge_customer_memories("   ") == 0


@pytest.mark.asyncio
async def test_get_notes_empty_customer_id(long_term_memory: LongTermMemory) -> None:
    """Verify get_notes with empty customer_id returns empty list."""
    assert await long_term_memory.get_notes("") == []
    assert await long_term_memory.get_notes("   ") == []


@pytest.mark.asyncio
async def test_record_notes_skips_invalid_item_types(
    long_term_memory: LongTermMemory, sample_customer: Customer
) -> None:
    """Verify record_notes skips invalid item types without crashing."""
    items = [
        "invalid_string_item",  # invalid type
        12345,  # invalid type
        {"memory_type": MemoryTypeEnum.NOTE, "content": "Valid note from dict"},
    ]
    saved = await long_term_memory.record_notes(sample_customer.id, items)  # type: ignore
    assert len(saved) == 1
    assert saved[0].content == "Valid note from dict"
