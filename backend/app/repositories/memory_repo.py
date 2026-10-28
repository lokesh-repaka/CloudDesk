"""Customer Memory Repository.

Provides query abstractions for storing and recalling customer memory notes,
supporting multi-turn memory recall (up to 10 recent notes) and customer context.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import CustomerMemory
from backend.app.repositories.base import BaseRepository


class CustomerMemoryRepository(BaseRepository[CustomerMemory]):
    """Repository handling long-term customer memory storage and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CustomerMemory, session)

    async def get_recent_notes(self, customer_id: str, limit: int = 10) -> list[CustomerMemory]:
        """Fetch the most recent memory notes for a customer ordered newest first."""
        stmt = (
            select(CustomerMemory)
            .where(CustomerMemory.customer_id == customer_id)
            .order_by(CustomerMemory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_memory_note(
        self,
        customer_id: str,
        memory_type: str,
        content: str,
    ) -> CustomerMemory:
        """Append an extracted memory note for a customer."""
        note = CustomerMemory(
            customer_id=customer_id,
            memory_type=memory_type,
            content=content,
        )
        self.session.add(note)
        await self.session.flush()
        await self.session.refresh(note)
        return note
