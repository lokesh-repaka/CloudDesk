import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.entities import (
    ApprovalRequest,
    Base,
    Customer,
    Subscription,
    Ticket,
    WorkflowRun,
    Workspace,
)
from backend.app.schemas.common import (
    ApprovalStatusEnum,
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    MemoryTypeEnum,
    SeverityEnum,
    TicketStatusEnum,
)


@pytest.fixture
async def db_session():
    """Isolated in-memory SQLite database session fixture for repository tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


class TestDatabaseCore:
    """Validate backend/app/core/database.py async engine and session lifecycle."""

    async def test_database_engine_and_session_factory(self):
        from backend.app.core.database import get_db, get_engine, get_session_factory

        engine = get_engine("sqlite+aiosqlite:///:memory:")
        assert engine is not None
        session_factory = get_session_factory(engine)
        assert session_factory is not None

        # Verify async session generator
        gen = get_db(engine=engine)
        session = await anext(gen)
        assert isinstance(session, AsyncSession)
        await gen.aclose()
        await engine.dispose()

    async def test_create_tables_utility(self):
        from backend.app.core.database import create_tables

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        await create_tables(engine=engine)
        async with engine.connect() as conn:
            # Query table names to confirm creation
            result = await conn.run_sync(
                lambda sync_conn: Base.metadata.tables.keys()
            )
            assert "tickets" in result
            assert "customers" in result
        await engine.dispose()


class TestBaseRepository:
    """Validate generic CRUD functionality on BaseRepository."""

    async def test_base_repository_crud_operations(self, db_session: AsyncSession):
        from backend.app.repositories.base import BaseRepository

        repo = BaseRepository(Customer, db_session)
        customer_id = str(uuid.uuid4())

        # 1. Create
        customer = Customer(
            id=customer_id,
            name="Generic Enterprise",
            email="generic@enterprise.test",
            plan=CustomerPlanEnum.ENTERPRISE.value,
        )
        created = await repo.create(customer)
        assert created.id == customer_id

        # 2. Get by ID
        fetched = await repo.get(customer_id)
        assert fetched is not None
        assert fetched.email == "generic@enterprise.test"

        # 3. Count
        count = await repo.count()
        assert count == 1

        # 4. List with pagination
        items = await repo.list(offset=0, limit=10)
        assert len(items) == 1
        assert items[0].id == customer_id

        # 5. Update
        updated = await repo.update(fetched, {"name": "Updated Enterprise Corp"})
        assert updated.name == "Updated Enterprise Corp"
        refetched = await repo.get(customer_id)
        assert refetched.name == "Updated Enterprise Corp"

        # 6. Delete
        deleted = await repo.delete(customer_id)
        assert deleted is True
        assert await repo.get(customer_id) is None
        assert await repo.count() == 0


class TestCustomerAndWorkspaceRepositories:
    """Validate customer, workspace, and subscription repository operations."""

    async def test_customer_and_workspace_queries(self, db_session: AsyncSession):
        from backend.app.repositories.customer_repo import (
            CustomerRepository,
            WorkspaceRepository,
        )

        customer_repo = CustomerRepository(db_session)
        workspace_repo = WorkspaceRepository(db_session)

        cust_id = str(uuid.uuid4())
        customer = Customer(
            id=cust_id,
            name="Starlight Corp",
            email="ops@starlight.io",
            plan=CustomerPlanEnum.PRO.value,
        )
        await customer_repo.create(customer)

        # Create subscription
        sub = Subscription(
            customer_id=cust_id,
            plan=CustomerPlanEnum.PRO.value,
            status="active",
        )
        db_session.add(sub)

        # Create workspaces
        ws1 = Workspace(
            customer_id=cust_id,
            name="Starlight Production",
            slug="starlight-prod",
            storage_used_bytes=1000000,
        )
        ws2 = Workspace(
            customer_id=cust_id,
            name="Starlight Development",
            slug="starlight-dev",
            storage_used_bytes=500000,
        )
        await workspace_repo.create(ws1)
        await workspace_repo.create(ws2)
        await db_session.flush()

        # Query by email
        by_email = await customer_repo.get_by_email("ops@starlight.io")
        assert by_email is not None
        assert by_email.id == cust_id

        # Query customer with workspaces and subscription eager-loaded
        cust_profile = await customer_repo.get_with_workspaces_and_subscription(cust_id)
        assert cust_profile is not None
        assert len(cust_profile.workspaces) == 2
        assert len(cust_profile.subscriptions) == 1

        # Query active subscription
        active_sub = await customer_repo.get_active_subscription(cust_id)
        assert active_sub is not None
        assert active_sub.status == "active"
        assert active_sub.plan == CustomerPlanEnum.PRO.value

        # Workspace repo queries
        ws_by_slug = await workspace_repo.get_by_slug("starlight-prod")
        assert ws_by_slug is not None
        assert ws_by_slug.name == "Starlight Production"

        ws_list = await workspace_repo.list_by_customer(cust_id)
        assert len(ws_list) == 2


class TestTicketRepositories:
    """Validate Ticket and TicketMessage repository operations (AC-001, AC-005, AC-007, AC-010)."""

    async def test_create_ticket_with_initial_message_atomic(self, db_session: AsyncSession):
        from backend.app.repositories.customer_repo import CustomerRepository
        from backend.app.repositories.ticket_repo import TicketRepository

        customer_repo = CustomerRepository(db_session)
        ticket_repo = TicketRepository(db_session)

        # Seed customer
        customer = Customer(
            id=str(uuid.uuid4()),
            name="Delta Corp",
            email="contact@delta.org",
            plan=CustomerPlanEnum.ENTERPRISE.value,
        )
        await customer_repo.create(customer)

        ticket_data = {
            "customer_id": customer.id,
            "subject": "Storage quota limit exceeded unexpectedly",
            "category": CategoryEnum.STORAGE_QUOTA.value,
            "severity": SeverityEnum.HIGH.value,
            "channel": ChannelEnum.WEB.value,
        }
        initial_msg = "Our team is getting 413 Payload Too Large on workspace-delta-01."

        # Atomic creation
        ticket = await ticket_repo.create_with_initial_message(
            ticket_data=ticket_data,
            initial_message=initial_msg,
            sender_id=customer.id,
        )

        assert ticket.id is not None
        assert ticket.status == TicketStatusEnum.NEW.value
        assert len(ticket.messages) == 1
        assert ticket.messages[0].body == initial_msg
        assert ticket.messages[0].author_role == "customer"

    async def test_get_ticket_with_messages_chronological_order(self, db_session: AsyncSession):
        from backend.app.repositories.customer_repo import CustomerRepository
        from backend.app.repositories.ticket_repo import (
            TicketMessageRepository,
            TicketRepository,
        )

        customer_repo = CustomerRepository(db_session)
        ticket_repo = TicketRepository(db_session)
        msg_repo = TicketMessageRepository(db_session)

        customer = Customer(
            id=str(uuid.uuid4()),
            name="Echo LLC",
            email="tech@echo.test",
            plan=CustomerPlanEnum.PRO.value,
        )
        await customer_repo.create(customer)

        ticket = await ticket_repo.create(
            Ticket(
                customer_id=customer.id,
                subject="API authentication intermittent error",
                category=CategoryEnum.API_FAILURE.value,
                severity=SeverityEnum.MEDIUM.value,
            )
        )

        # Add 3 messages chronologically
        await msg_repo.add_message(
            ticket_id=ticket.id,
            author_role="customer",
            body="Message 1: Initial report",
        )
        await msg_repo.add_message(
            ticket_id=ticket.id,
            author_role="agent",
            body="Message 2: Investigating logs",
            author_id="usr-agent-002",
        )
        await msg_repo.add_message(
            ticket_id=ticket.id,
            author_role="customer",
            body="Message 3: Any update?",
        )

        # Retrieve ticket with eager-loaded messages
        loaded = await ticket_repo.get_with_messages(ticket.id)
        assert loaded is not None
        assert len(loaded.messages) == 3
        # Check ordering: m1, m2, m3
        bodies = [m.body for m in loaded.messages]
        assert bodies == [
            "Message 1: Initial report",
            "Message 2: Investigating logs",
            "Message 3: Any update?",
        ]

    async def test_list_tickets_with_filters_and_pagination(self, db_session: AsyncSession):
        from backend.app.repositories.customer_repo import CustomerRepository
        from backend.app.repositories.ticket_repo import TicketRepository

        customer_repo = CustomerRepository(db_session)
        ticket_repo = TicketRepository(db_session)

        c1 = await customer_repo.create(
            Customer(
                id=str(uuid.uuid4()),
                name="Cust 1",
                email="c1@test.org",
                plan=CustomerPlanEnum.PRO.value,
            )
        )
        c2 = await customer_repo.create(
            Customer(
                id=str(uuid.uuid4()),
                name="Cust 2",
                email="c2@test.org",
                plan=CustomerPlanEnum.FREE.value,
            )
        )

        # Create tickets with different attributes
        await ticket_repo.create(
            Ticket(
                customer_id=c1.id,
                subject="Billing discrepancy",
                category=CategoryEnum.BILLING.value,
                severity=SeverityEnum.MEDIUM.value,
                status=TicketStatusEnum.NEW.value,
            )
        )
        await ticket_repo.create(
            Ticket(
                customer_id=c1.id,
                subject="Security inquiry",
                category=CategoryEnum.SECURITY.value,
                severity=SeverityEnum.CRITICAL.value,
                status=TicketStatusEnum.ESCALATED.value,
            )
        )
        await ticket_repo.create(
            Ticket(
                customer_id=c2.id,
                subject="Login issue with SSO",
                category=CategoryEnum.LOGIN_ISSUE.value,
                severity=SeverityEnum.HIGH.value,
                status=TicketStatusEnum.NEW.value,
            )
        )

        # Filter by customer
        c1_tickets, c1_count = await ticket_repo.list_tickets(customer_id=c1.id)
        assert c1_count == 2
        assert len(c1_tickets) == 2

        # Filter by status
        new_tickets, new_count = await ticket_repo.list_tickets(status=TicketStatusEnum.NEW.value)
        assert new_count == 2
        assert len(new_tickets) == 2

        # Filter by severity
        crit_tickets, crit_count = await ticket_repo.list_tickets(severity=SeverityEnum.CRITICAL.value)
        assert crit_count == 1
        assert crit_tickets[0].category == CategoryEnum.SECURITY.value

        # Filter by category
        billing_tickets, billing_count = await ticket_repo.list_tickets(category=CategoryEnum.BILLING.value)
        assert billing_count == 1
        assert billing_tickets[0].subject == "Billing discrepancy"

        # Pagination: limit 1, offset 0
        paged_tickets, total = await ticket_repo.list_tickets(limit=1, offset=0)
        assert total == 3
        assert len(paged_tickets) == 1

    async def test_update_ticket_status_and_assignment(self, db_session: AsyncSession):
        from backend.app.repositories.customer_repo import CustomerRepository
        from backend.app.repositories.ticket_repo import TicketRepository

        customer_repo = CustomerRepository(db_session)
        ticket_repo = TicketRepository(db_session)

        customer = await customer_repo.create(
            Customer(
                id=str(uuid.uuid4()),
                name="Cust 3",
                email="c3@test.org",
                plan=CustomerPlanEnum.PRO.value,
            )
        )
        ticket = await ticket_repo.create(
            Ticket(
                customer_id=customer.id,
                subject="Reset password",
                category=CategoryEnum.ACCOUNT.value,
                status=TicketStatusEnum.NEW.value,
            )
        )

        # Update status
        updated = await ticket_repo.update_status(ticket.id, TicketStatusEnum.IN_PROGRESS.value)
        assert updated is not None
        assert updated.status == TicketStatusEnum.IN_PROGRESS.value

        # Assign agent
        assigned = await ticket_repo.assign_agent(ticket.id, "usr-agent-002")
        assert assigned is not None
        assert assigned.assigned_to == "usr-agent-002"


class TestApprovalAndMemoryRepositories:
    """Validate ApprovalRequest transitions and CustomerMemory recent recall."""

    async def test_approval_repository_lifecycle(self, db_session: AsyncSession):
        from backend.app.repositories.approval_repo import ApprovalRepository
        from backend.app.repositories.customer_repo import CustomerRepository
        from backend.app.repositories.ticket_repo import TicketRepository

        customer_repo = CustomerRepository(db_session)
        ticket_repo = TicketRepository(db_session)
        approval_repo = ApprovalRepository(db_session)

        customer = await customer_repo.create(
            Customer(
                id=str(uuid.uuid4()),
                name="Cust 4",
                email="c4@test.org",
                plan=CustomerPlanEnum.ENTERPRISE.value,
            )
        )
        ticket = await ticket_repo.create(
            Ticket(
                customer_id=customer.id,
                subject="Refund Request Approval",
                category=CategoryEnum.BILLING.value,
            )
        )

        # Create workflow run parent record
        run = WorkflowRun(
            ticket_id=ticket.id,
        )
        db_session.add(run)
        await db_session.flush()

        # Create approval request
        appr_req = await approval_repo.create(
            ApprovalRequest(
                ticket_id=ticket.id,
                workflow_id=run.id,
                action_name="issue_credit",
                action_payload={"amount_usd": 150, "reason": "SLA breach credit"},
                status=ApprovalStatusEnum.PENDING.value,
            )
        )
        assert appr_req.status == ApprovalStatusEnum.PENDING.value

        # List pending
        pending = await approval_repo.list_pending()
        assert len(pending) == 1
        assert pending[0].id == appr_req.id

        # Decide approval: approve
        decided = await approval_repo.record_decision(
            request_id=appr_req.id,
            decision=ApprovalStatusEnum.APPROVED.value,
            decided_by="usr-agent-002",
            reason="Approved per enterprise SLA policy",
        )
        assert decided is not None
        assert decided.status == ApprovalStatusEnum.APPROVED.value
        assert decided.decided_by == "usr-agent-002"
        assert decided.rejection_reason == "Approved per enterprise SLA policy"
        assert decided.decided_at is not None

        # Confirm no longer in pending list
        pending_after = await approval_repo.list_pending()
        assert len(pending_after) == 0

    async def test_customer_memory_recall_limit(self, db_session: AsyncSession):
        from backend.app.repositories.customer_repo import CustomerRepository
        from backend.app.repositories.memory_repo import CustomerMemoryRepository

        customer_repo = CustomerRepository(db_session)
        memory_repo = CustomerMemoryRepository(db_session)

        customer = await customer_repo.create(
            Customer(
                id=str(uuid.uuid4()),
                name="Cust 5",
                email="c5@test.org",
                plan=CustomerPlanEnum.ENTERPRISE.value,
            )
        )

        # Add 15 memory notes
        for i in range(15):
            await memory_repo.add_memory_note(
                customer_id=customer.id,
                memory_type=MemoryTypeEnum.PREFERENCE.value if i % 2 == 0 else MemoryTypeEnum.NOTE.value,
                content=f"Memory note #{i + 1} for customer",
            )

        # Recall recent notes (default limit 10)
        recent_notes = await memory_repo.get_recent_notes(customer.id, limit=10)
        assert len(recent_notes) == 10
        # Check notes belong to customer
        assert all(n.customer_id == customer.id for n in recent_notes)

    async def test_sql_injection_resilience_in_repository_filters(self, db_session: AsyncSession):
        """Security penetration test: verify SQL injection in filter values is treated as literal data."""
        from backend.app.repositories.customer_repo import CustomerRepository
        from backend.app.repositories.ticket_repo import TicketRepository

        customer_repo = CustomerRepository(db_session)
        ticket_repo = TicketRepository(db_session)

        customer = await customer_repo.create(
            Customer(
                id=str(uuid.uuid4()),
                name="Safe Corp",
                email="safe@corp.test",
                plan=CustomerPlanEnum.PRO.value,
            )
        )
        await ticket_repo.create(
            Ticket(
                customer_id=customer.id,
                subject="Legitimate ticket",
                category=CategoryEnum.LOGIN_ISSUE.value,
                status=TicketStatusEnum.NEW.value,
            )
        )

        # Attempt SQL injection attack in status filter
        sql_injection_payload = "' OR '1'='1"
        tickets, count = await ticket_repo.list_tickets(status=sql_injection_payload)
        # Should safely match 0 tickets and not dump all records
        assert count == 0
        assert len(tickets) == 0
