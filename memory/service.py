"""Recall and Record Memory Service (P8-3).

Coordinates short-term Redis facade and long-term customer memory storage
adhering to CLAUDE.md §7.5 and architecture.md §5.7:
- Read: customer_context node -> recall_customer() (up to 10 notes)
- Write: memory_update node -> record_resolution() (past_issue, first 3 troubleshooting steps, resolution note)
- Secret scrubbing and exact deduplication
- Short-term conversation and workflow state delegation
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session_factory
from backend.app.models.entities import CustomerMemory
from backend.app.schemas.common import MemoryTypeEnum
from memory.long_term import LongTermMemory, get_long_term_memory
from memory.short_term import ShortTermMemory, get_short_term_memory

logger = logging.getLogger(__name__)


def format_customer_notes(notes: Sequence[CustomerMemory | Any]) -> str:
    """Format customer memory notes into a formatted bulleted block for prompt injection."""
    if not notes:
        return "No previous customer notes found."

    lines: list[str] = []
    for note in notes:
        m_type = getattr(note, "memory_type", "note").upper()
        content = getattr(note, "content", "").strip()
        lines.append(f"- [{m_type}] {content}")
    return "\n".join(lines)


class MemoryService:
    """Unified service coordinating short-term Redis state and long-term customer memory."""

    def __init__(
        self,
        long_term: LongTermMemory | None = None,
        short_term: ShortTermMemory | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self._session = session
        self._long_term = long_term
        self._short_term = short_term

    @property
    def long_term(self) -> LongTermMemory:
        """Resolve active LongTermMemory facade."""
        if self._long_term is not None:
            return self._long_term
        if self._session is not None:
            self._long_term = LongTermMemory(session=self._session)
            return self._long_term
        return get_long_term_memory()

    @property
    def short_term(self) -> ShortTermMemory:
        """Resolve active ShortTermMemory facade."""
        if self._short_term is None:
            self._short_term = get_short_term_memory()
        return self._short_term

    # =========================================================================
    # 1. High-Level Recall (customer_context node integration, AC-008)
    # =========================================================================

    async def recall_customer(
        self,
        customer_id: str,
        limit: int = 10,
        session: AsyncSession | None = None,
    ) -> list[CustomerMemory]:
        """Recall up to limit (default 10) newest memory notes for a customer.

        Consumed by the customer_context agent node.
        """
        if not customer_id or not customer_id.strip():
            return []

        active_session = session or self._session
        if active_session is not None:
            ltm = LongTermMemory(session=active_session)
            return await ltm.get_notes(customer_id.strip(), limit=limit)

        # Standalone transaction fallback
        session_factory = get_session_factory()
        try:
            async with session_factory() as sess:
                ltm = LongTermMemory(session=sess)
                return await ltm.get_notes(customer_id.strip(), limit=limit)
        except (SQLAlchemyError, RuntimeError, OSError) as err:
            logger.debug(
                "Database query for memory notes failed (%s); returning empty notes",
                err,
            )
            return []

    # =========================================================================
    # 2. High-Level Record Resolution (memory_update node integration, F11, AC-050)
    # =========================================================================

    async def record_resolution(
        self,
        customer_id: str,
        past_issue: str | None = None,
        troubleshooting_steps: Sequence[str] | None = None,
        resolution_note: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[CustomerMemory]:
        """Record structured resolution findings to long-term memory (CLAUDE.md §7.5).

        Persists:
        - past_issue as MemoryTypeEnum.PAST_ISSUE
        - strictly the first 3 troubleshooting steps as MemoryTypeEnum.TROUBLESHOOTING
        - resolution_note as MemoryTypeEnum.NOTE
        All notes are scrubbed of secrets and exact duplicates are skipped.
        """
        if not customer_id or not customer_id.strip():
            return []

        items_to_record: list[tuple[MemoryTypeEnum, str]] = []

        # 1. Past Issue
        if past_issue and past_issue.strip():
            items_to_record.append((MemoryTypeEnum.PAST_ISSUE, past_issue.strip()))

        # 2. First 3 troubleshooting steps strictly (CLAUDE.md §7.5, AC-050)
        if troubleshooting_steps:
            for step in list(troubleshooting_steps)[:3]:
                if step and step.strip():
                    items_to_record.append(
                        (MemoryTypeEnum.TROUBLESHOOTING, step.strip())
                    )

        # 3. Resolution note
        if resolution_note and resolution_note.strip():
            items_to_record.append((MemoryTypeEnum.NOTE, resolution_note.strip()))

        if not items_to_record:
            return []

        active_session = session or self._session
        if active_session is not None:
            ltm = LongTermMemory(session=active_session)
            return await ltm.record_notes(
                customer_id.strip(), items_to_record, scrub_secrets=True
            )

        try:
            session_factory = get_session_factory()
            async with session_factory() as sess:
                ltm = LongTermMemory(session=sess)
                saved = await ltm.record_notes(
                    customer_id.strip(), items_to_record, scrub_secrets=True
                )
                await sess.commit()
                return saved
        except (SQLAlchemyError, RuntimeError, OSError) as exc:
            logger.warning("Failed to record resolution memory in DB session: %s", exc)
            return []

    # =========================================================================
    # 3. Short-Term Memory Coordination
    # =========================================================================

    async def append_ticket_message(
        self,
        ticket_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        scrub_secrets: bool = True,
    ) -> bool:
        """Append a message to the ticket conversation in short-term Redis."""
        return await self.short_term.append_message(
            ticket_id=ticket_id,
            role=role,
            content=content,
            metadata=metadata,
            scrub_secrets=scrub_secrets,
        )

    async def get_ticket_conversation(self, ticket_id: str) -> list[dict[str, Any]]:
        """Retrieve ticket conversation history from short-term Redis."""
        return await self.short_term.get_conversation(ticket_id)

    async def clear_ticket_conversation(self, ticket_id: str) -> bool:
        """Clear ticket conversation history from short-term Redis."""
        return await self.short_term.clear_conversation(ticket_id)

    async def save_workflow_state(
        self,
        ticket_id: str,
        state_data: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """Save ephemeral LangGraph workflow state to Redis."""
        return await self.short_term.save_workflow_state(ticket_id, state_data, ttl=ttl)

    async def get_workflow_state(self, ticket_id: str) -> dict[str, Any] | None:
        """Retrieve ephemeral LangGraph workflow state from Redis."""
        return await self.short_term.get_workflow_state(ticket_id)

    async def delete_workflow_state(self, ticket_id: str) -> bool:
        """Delete ephemeral LangGraph workflow state from Redis."""
        return await self.short_term.delete_workflow_state(ticket_id)

    async def get_cached_retrieval(
        self,
        mode: str,
        category: str | None,
        top_k: int,
        query: str,
    ) -> list[dict[str, Any]] | None:
        """Retrieve cached RAG retrieval evidence from Redis."""
        return await self.short_term.get_cached_retrieval(mode, category, top_k, query)

    async def set_cached_retrieval(
        self,
        mode: str,
        category: str | None,
        top_k: int,
        query: str,
        evidence: list[dict[str, Any]],
        ttl: int | None = None,
    ) -> bool:
        """Store RAG retrieval evidence into Redis with 300s TTL."""
        return await self.short_term.set_cached_retrieval(
            mode, category, top_k, query, evidence, ttl=ttl
        )

    async def clear_retrieval_cache(self, mode: str | None = None) -> int:
        """Clear cached RAG queries matching the pattern."""
        return await self.short_term.clear_retrieval_cache(mode=mode)


_memory_service_instance: MemoryService | None = None


def get_memory_service(
    session: AsyncSession | None = None,
    short_term: ShortTermMemory | None = None,
    long_term: LongTermMemory | None = None,
    force_reinit: bool = False,
) -> MemoryService:
    """Return an active MemoryService instance."""
    global _memory_service_instance
    if session is not None or short_term is not None or long_term is not None:
        return MemoryService(
            session=session, short_term=short_term, long_term=long_term
        )

    if _memory_service_instance is None or force_reinit:
        _memory_service_instance = MemoryService()
    return _memory_service_instance


async def recall_customer(
    customer_id: str,
    limit: int = 10,
    session: AsyncSession | None = None,
) -> list[CustomerMemory]:
    """Module-level convenience function for customer_context node."""
    service = get_memory_service(session=session)
    return await service.recall_customer(customer_id, limit=limit, session=session)


async def record_resolution(
    customer_id: str,
    past_issue: str | None = None,
    troubleshooting_steps: Sequence[str] | None = None,
    resolution_note: str | None = None,
    session: AsyncSession | None = None,
) -> list[CustomerMemory]:
    """Module-level convenience function for memory_update node."""
    service = get_memory_service(session=session)
    return await service.record_resolution(
        customer_id=customer_id,
        past_issue=past_issue,
        troubleshooting_steps=troubleshooting_steps,
        resolution_note=resolution_note,
        session=session,
    )
