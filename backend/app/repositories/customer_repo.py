"""Customer and Workspace Repositories.

Provides domain query abstractions for Customers, Subscriptions, and Workspaces,
supporting customer 360 profiling, workspace lookup, and active subscription checks.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.entities import Customer, Subscription, Workspace
from backend.app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Repository handling Customer profile, subscription, and workspace queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Customer, session)

    async def get_by_email(self, email: str) -> Customer | None:
        """Fetch a customer profile by unique email address."""
        stmt = select(Customer).where(Customer.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_workspaces_and_subscription(self, customer_id: str) -> Customer | None:
        """Fetch a customer eager-loading related workspaces and subscriptions."""
        stmt = (
            select(Customer)
            .options(
                selectinload(Customer.workspaces),
                selectinload(Customer.subscriptions),
            )
            .where(Customer.id == customer_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_workspaces(self, customer_id: str) -> list[Workspace]:
        """Fetch all workspaces associated with a given customer."""
        stmt = select(Workspace).where(Workspace.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_subscription(self, customer_id: str) -> Subscription | None:
        """Fetch the most recent active subscription for a customer."""
        stmt = (
            select(Subscription)
            .where(
                Subscription.customer_id == customer_id,
                Subscription.status == "active",
            )
            .order_by(Subscription.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()


class WorkspaceRepository(BaseRepository[Workspace]):
    """Repository handling Workspace domain lookup and tenant isolation queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Workspace, session)

    async def get_by_slug(self, slug: str) -> Workspace | None:
        """Fetch a workspace by its unique tenant slug."""
        stmt = select(Workspace).where(Workspace.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_customer(self, customer_id: str) -> list[Workspace]:
        """Fetch all workspaces registered under a specific customer."""
        stmt = select(Workspace).where(Workspace.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
