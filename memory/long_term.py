"""Long-Term Customer Memory Subsystem (P8-2).

Provides persistent customer memory abstractions adhering to CLAUDE.md §7.5 and architecture.md §5.7:
- Stores structured insights: preference, past_issue, troubleshooting, note
- Enforces permanent de-duplication: exact-duplicate notes are skipped without DB insertion (US-014, AC-041)
- Automatic secret scrubbing: redacts API keys, credentials, and payment cards prior to persistence (N7, US-022, AC-070)
- Rejection of raw ticket bodies: prevents conversational transcripts and unparsed email dumps (US-022, AC-071)
- Multi-turn recall: retrieves up to 10 recent notes ordered newest first (AC-008)
- GDPR right-to-be-forgotten customer purge support
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session_factory
from backend.app.models.entities import CustomerMemory
from backend.app.schemas.common import MemoryTypeEnum
from memory.scrub import is_raw_ticket_body, scrub

logger = logging.getLogger(__name__)

DEFAULT_RECALL_LIMIT = 10
VALID_MEMORY_TYPES: frozenset[str] = frozenset(m.value for m in MemoryTypeEnum)


class LongTermMemory:
    """Manager for long-term customer memory storage, de-duplication, and recall."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Resolve the active AsyncSession, raising RuntimeError if unset."""
        if self._session is None:
            raise RuntimeError(
                "LongTermMemory requires an active AsyncSession. Provide one via constructor or context."
            )
        return self._session

    async def add_note(
        self,
        customer_id: str,
        memory_type: str | MemoryTypeEnum,
        content: str,
        scrub_secrets: bool = True,
    ) -> CustomerMemory | None:
        """Add a structured memory note for a customer.

        Enforces:
        - Validation: rejects empty customer_id, empty content, and invalid memory types.
        - Raw Body Filtering: blocks unparsed email bodies or conversational dumps (US-022, AC-071).
        - Secret Redaction: scrubs credentials, API keys, and payment cards (N7, AC-070).
        - De-duplication: skips insertion and returns None if an exact-duplicate note exists (US-014, AC-041).
        """
        if not customer_id or not customer_id.strip():
            raise ValueError("customer_id cannot be empty")

        if not content or not content.strip():
            raise ValueError("content cannot be empty")

        type_str = (
            memory_type.value
            if isinstance(memory_type, MemoryTypeEnum)
            else str(memory_type).strip()
        )
        if type_str not in VALID_MEMORY_TYPES:
            raise ValueError(
                f"Invalid memory_type: '{type_str}'. Must be one of: {sorted(VALID_MEMORY_TYPES)}"
            )

        # 1. Reject full raw ticket / email conversation bodies (US-022, AC-071)
        if is_raw_ticket_body(content):
            raise ValueError(
                "Raw ticket body cannot be stored in customer memory; "
                "only structured troubleshooting notes are allowed (US-022, AC-071)."
            )

        # 2. Scrub secrets prior to persistence (N7, US-022, AC-070)
        clean_content = scrub(content).strip() if scrub_secrets else content.strip()

        # 3. Exact de-duplication check (CLAUDE.md §7.5, US-014 AC-041)
        stmt = (
            select(CustomerMemory)
            .where(
                CustomerMemory.customer_id == customer_id.strip(),
                CustomerMemory.memory_type == type_str,
                CustomerMemory.content == clean_content,
            )
            .limit(1)
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing is not None:
            logger.debug(
                "Exact duplicate customer memory skipped for customer %s [type=%s]",
                customer_id,
                type_str,
            )
            return None

        # 4. Insert and persist new customer memory note
        note = CustomerMemory(
            customer_id=customer_id.strip(),
            memory_type=type_str,
            content=clean_content,
        )
        self.session.add(note)
        await self.session.flush()
        await self.session.refresh(note)
        logger.debug(
            "Persisted customer memory note %s for customer %s [type=%s]",
            note.id,
            customer_id,
            type_str,
        )
        return note

    async def get_notes(
        self,
        customer_id: str,
        limit: int = DEFAULT_RECALL_LIMIT,
        memory_type: str | MemoryTypeEnum | None = None,
    ) -> list[CustomerMemory]:
        """Recall up to limit customer memory notes ordered newest first (CLAUDE.md §7.5, AC-008)."""
        if not customer_id or not customer_id.strip():
            return []

        stmt = (
            select(CustomerMemory)
            .where(CustomerMemory.customer_id == customer_id.strip())
            .order_by(CustomerMemory.created_at.desc())
        )

        if memory_type is not None:
            type_str = (
                memory_type.value
                if isinstance(memory_type, MemoryTypeEnum)
                else str(memory_type).strip()
            )
            stmt = stmt.where(CustomerMemory.memory_type == type_str)

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def record_notes(
        self,
        customer_id: str,
        notes: Sequence[tuple[str | MemoryTypeEnum, str] | dict[str, Any]],
        scrub_secrets: bool = True,
    ) -> list[CustomerMemory]:
        """Batch record structured notes for a customer, skipping any duplicates."""
        saved_notes: list[CustomerMemory] = []
        for item in notes:
            if isinstance(item, tuple):
                m_type, text = item
            elif isinstance(item, dict):
                m_type = item.get("memory_type", MemoryTypeEnum.NOTE)
                text = item.get("content", "")
            else:
                continue

            created = await self.add_note(
                customer_id=customer_id,
                memory_type=m_type,
                content=text,
                scrub_secrets=scrub_secrets,
            )
            if created is not None:
                saved_notes.append(created)

        return saved_notes

    async def delete_note(self, note_id: str) -> bool:
        """Delete an individual memory note by its UUID."""
        stmt = select(CustomerMemory).where(CustomerMemory.id == note_id).limit(1)
        note = (await self.session.execute(stmt)).scalars().first()
        if note is None:
            return False

        await self.session.delete(note)
        await self.session.flush()
        return True

    async def purge_customer_memories(self, customer_id: str) -> int:
        """Purge all memory notes for a given customer (GDPR Right-to-be-Forgotten)."""
        if not customer_id or not customer_id.strip():
            return 0

        stmt = delete(CustomerMemory).where(
            CustomerMemory.customer_id == customer_id.strip()
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        count = int(result.rowcount or 0)
        logger.info(
            "Purged %d customer memory notes for customer %s", count, customer_id
        )
        return count


def get_long_term_memory(session: AsyncSession | None = None) -> LongTermMemory:
    """Return a LongTermMemory facade bound to the given or default AsyncSession."""
    if session is not None:
        return LongTermMemory(session=session)

    factory = get_session_factory()
    return LongTermMemory(session=factory())
