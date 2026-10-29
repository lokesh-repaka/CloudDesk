"""Ticket and TicketMessage Repositories.

Provides domain query abstractions for Tickets and Messages, supporting omnichannel
ingestion, queue filtering, conversation history retrieval, and status updates.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.entities import Ticket, TicketMessage
from backend.app.repositories.base import BaseRepository
from backend.app.schemas.common import TicketStatusEnum


class TicketRepository(BaseRepository[Ticket]):
    """Repository handling Ticket lifecycle, filtering, and message aggregation."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Ticket, session)

    async def get_with_messages(self, ticket_id: str) -> Ticket | None:
        """Fetch a ticket eager-loading conversation messages and customer in chronological order."""
        stmt = (
            select(Ticket)
            .options(
                selectinload(Ticket.messages),
                selectinload(Ticket.customer),
            )
            .where(Ticket.id == ticket_id)
        )
        result = await self.session.execute(stmt)
        ticket = result.scalar_one_or_none()
        if ticket is not None and ticket.messages:
            ticket.messages.sort(key=lambda m: m.created_at)
        return ticket

    async def list_tickets(
        self,
        status: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        customer_id: str | None = None,
        assigned_to: str | None = None,
        plan: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Ticket], int]:
        """Fetch a paginated list of tickets matching filter criteria and total match count."""
        from backend.app.models.entities import Customer

        base_stmt = select(Ticket).options(selectinload(Ticket.customer))
        count_stmt = select(func.count()).select_from(Ticket)

        if plan is not None:
            base_stmt = base_stmt.join(Ticket.customer).where(Customer.plan == plan)
            count_stmt = count_stmt.join(Ticket.customer).where(Customer.plan == plan)

        filters = []
        if status is not None:
            filters.append(Ticket.status == status)
        if severity is not None:
            filters.append(Ticket.severity == severity)
        if category is not None:
            filters.append(Ticket.category == category)
        if customer_id is not None:
            filters.append(Ticket.customer_id == customer_id)
        if assigned_to is not None:
            filters.append(Ticket.assigned_to == assigned_to)

        for cond in filters:
            base_stmt = base_stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        # Count total matching rows
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one() or 0

        # Retrieve paginated rows ordered by latest first
        base_stmt = base_stmt.order_by(Ticket.created_at.desc()).offset(offset).limit(limit)
        items_result = await self.session.execute(base_stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def create_with_initial_message(
        self,
        ticket_data: dict[str, Any],
        initial_message: str,
        sender_id: str | None = None,
    ) -> Ticket:
        """Atomically create a new ticket with its initial customer message."""
        ticket = Ticket(**ticket_data)
        if not ticket.status:
            ticket.status = TicketStatusEnum.NEW.value

        self.session.add(ticket)
        await self.session.flush()

        msg = TicketMessage(
            ticket_id=ticket.id,
            author_role="customer",
            author_id=sender_id,
            body=initial_message,
        )
        self.session.add(msg)
        await self.session.flush()

        # Eager-load relations for return value
        return await self.get_with_messages(ticket.id) or ticket

    async def update_status(self, ticket_id: str, status: str) -> Ticket | None:
        """Update ticket workflow status."""
        ticket = await self.get(ticket_id)
        if ticket is None:
            return None
        ticket.status = status
        await self.session.flush()
        await self.session.refresh(ticket)
        return ticket

    async def assign_agent(self, ticket_id: str, agent_id: str | None) -> Ticket | None:
        """Assign or reassign an agent profile to a ticket."""
        ticket = await self.get(ticket_id)
        if ticket is None:
            return None
        ticket.assigned_to = agent_id
        await self.session.flush()
        await self.session.refresh(ticket)
        return ticket


class TicketMessageRepository(BaseRepository[TicketMessage]):
    """Repository handling TicketMessage thread append and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TicketMessage, session)

    async def list_by_ticket(self, ticket_id: str) -> list[TicketMessage]:
        """Fetch all messages for a ticket ordered chronologically."""
        stmt = (
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_message(
        self,
        ticket_id: str,
        author_role: str,
        body: str,
        author_id: str | None = None,
    ) -> TicketMessage:
        """Append a new message to a ticket's conversation thread."""
        msg = TicketMessage(
            ticket_id=ticket_id,
            author_role=author_role,
            author_id=author_id,
            body=body,
        )
        self.session.add(msg)
        await self.session.flush()
        await self.session.refresh(msg)
        return msg
