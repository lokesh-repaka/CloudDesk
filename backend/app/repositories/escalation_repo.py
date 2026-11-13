"""Escalation Repository (P11-3).

Provides data access and lifecycle management for ticket escalations,
queue inspection, team filtering, and status progression.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Escalation, get_utc_now
from backend.app.repositories.base import BaseRepository
from backend.app.schemas.common import EscalationStatusEnum


class EscalationRepository(BaseRepository[Escalation]):
    """Repository handling escalation queue queries and updates."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Escalation, session)

    async def list_all(
        self,
        status: str | None = None,
        target_team: str | None = None,
        ticket_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Escalation]:
        """Fetch escalations with optional status, team, or ticket filters and pagination."""
        stmt = select(Escalation).order_by(Escalation.created_at.desc())

        if status:
            stmt = stmt.where(Escalation.status == status)
        if target_team:
            stmt = stmt.where(Escalation.target_team.ilike(f"%{target_team}%"))
        if ticket_id:
            stmt = stmt.where(Escalation.ticket_id == ticket_id)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticket(self, ticket_id: str) -> list[Escalation]:
        """Fetch all escalations associated with a given ticket."""
        stmt = (
            select(Escalation)
            .where(Escalation.ticket_id == ticket_id)
            .order_by(Escalation.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_open(self, limit: int = 50) -> list[Escalation]:
        """Fetch all open escalations ordered by oldest first."""
        stmt = (
            select(Escalation)
            .where(Escalation.status == EscalationStatusEnum.OPEN.value)
            .order_by(Escalation.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self, escalation_id: str, new_status: str
    ) -> Escalation | None:
        """Update the status of an existing escalation."""
        esc = await self.get(escalation_id)
        if esc is None:
            return None
        esc.status = new_status
        esc.updated_at = get_utc_now()
        await self.session.commit()
        await self.session.refresh(esc)
        return esc

