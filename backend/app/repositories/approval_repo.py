"""Approval Request Repository.

Provides query abstractions for managing human-in-the-loop approval requests,
pending queue inspection, and decision recording (approve / reject).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import ApprovalRequest
from backend.app.repositories.base import BaseRepository
from backend.app.schemas.common import ApprovalStatusEnum


class ApprovalRepository(BaseRepository[ApprovalRequest]):
    """Repository handling human approval gates and decision recording."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ApprovalRequest, session)

    async def list_pending(self, limit: int = 50) -> list[ApprovalRequest]:
        """Fetch all approval requests awaiting decision, ordered by oldest first."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatusEnum.PENDING.value)
            .order_by(ApprovalRequest.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticket(self, ticket_id: str) -> list[ApprovalRequest]:
        """Fetch all approval requests associated with a ticket."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.ticket_id == ticket_id)
            .order_by(ApprovalRequest.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def record_decision(
        self,
        request_id: str,
        decision: str,
        decided_by: str,
        reason: str | None = None,
    ) -> ApprovalRequest | None:
        """Record an agent or admin decision (approved/rejected) on an approval request."""
        approval = await self.get(request_id)
        if approval is None:
            return None

        approval.status = decision
        approval.decided_by = decided_by
        approval.rejection_reason = reason
        approval.decided_at = datetime.now(UTC)

        await self.session.flush()
        await self.session.refresh(approval)
        return approval
