import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.schemas.common import (
    ApprovalStatusEnum,
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    MemoryTypeEnum,
    RoleEnum,
    SeverityEnum,
    TicketStatusEnum,
    WorkflowStatusEnum,
)


class TestCommonEnums:
    """Validate all domain constants and enums in common schemas."""

    def test_category_enum_contains_exact_ten_categories(self):
        """Domain rule: exactly 10 ticket categories defined in backend/app/schemas/common.py."""
        expected_categories = {
            "login_issue",
            "billing",
            "api_failure",
            "workspace_permissions",
            "storage_quota",
            "integration",
            "feature_request",
            "account",
            "security",
            "other",
        }
        actual_categories = {c.value for c in CategoryEnum}
        assert actual_categories == expected_categories
        assert len(CategoryEnum) == 10

    def test_ticket_status_enum(self):
        """Ticket statuses defined in CLAUDE.md section 5."""
        expected = {
            "new",
            "in_progress",
            "waiting_on_customer",
            "waiting_on_approval",
            "escalated",
            "resolved",
            "closed",
        }
        actual = {s.value for s in TicketStatusEnum}
        assert actual == expected

    def test_severity_enum(self):
        """Severity levels defined in CLAUDE.md section 5."""
        expected = {"low", "medium", "high", "critical"}
        actual = {s.value for s in SeverityEnum}
        assert actual == expected

    def test_channel_enum(self):
        """Omnichannel intake channels defined in CLAUDE.md section 5."""
        expected = {"email", "chat", "web", "api"}
        actual = {c.value for c in ChannelEnum}
        assert actual == expected

    def test_role_enum_and_hierarchy(self):
        """User roles defined in CLAUDE.md section 2."""
        expected = {"viewer", "agent", "admin"}
        actual = {r.value for r in RoleEnum}
        assert actual == expected

    def test_customer_plan_enum(self):
        """Customer plan tiers defined in CLAUDE.md section 5."""
        expected = {"free", "pro", "business", "enterprise"}
        actual = {p.value for p in CustomerPlanEnum}
        assert actual == expected

    def test_approval_status_enum(self):
        """Approval request statuses."""
        expected = {"pending", "approved", "rejected"}
        actual = {s.value for s in ApprovalStatusEnum}
        assert actual == expected

    def test_memory_type_enum(self):
        """Long-term memory note types."""
        expected = {"past_issue", "troubleshooting", "note", "preference"}
        actual = {m.value for m in MemoryTypeEnum}
        assert actual == expected

    def test_workflow_status_enum(self):
        """Workflow execution run statuses."""
        expected = {
            "queued",
            "running",
            "waiting_on_approval",
            "completed",
            "escalated",
            "failed",
        }
        actual = {w.value for w in WorkflowStatusEnum}
        assert actual == expected


class TestSQLAlchemyEntities:
    """Validate SQLAlchemy 2.0 declarative models and database interactions."""

    @pytest.fixture
    async def async_db_session(self):
        """Provide an in-memory SQLite async session with all tables created."""
        from backend.app.models.entities import Base

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            future=True,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            yield session

        await engine.dispose()

    async def test_table_registry_contains_all_sixteen_tables(self):
        """CLAUDE.md section 6 mandates 16 specific entities."""
        from backend.app.models.entities import Base

        expected_tables = {
            "profiles",
            "customers",
            "subscriptions",
            "workspaces",
            "products",
            "tickets",
            "ticket_messages",
            "support_articles",
            "incidents",
            "workflow_runs",
            "workflow_events",
            "resolution_actions",
            "approval_requests",
            "escalations",
            "customer_memory",
            "audit_logs",
        }
        actual_tables = set(Base.metadata.tables.keys())
        assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"

    async def test_create_customer_and_workspace(self, async_db_session: AsyncSession):
        """Verify Customer and Workspace entities and relations."""
        from backend.app.models.entities import Customer, Workspace

        customer_id = str(uuid.uuid4())
        customer = Customer(
            id=customer_id,
            name="Acme Corp",
            email="support@acme.test",
            plan=CustomerPlanEnum.ENTERPRISE.value,
        )
        async_db_session.add(customer)
        await async_db_session.flush()

        workspace = Workspace(
            customer_id=customer_id,
            name="Acme Primary",
            slug="acme-primary",
            storage_used_bytes=1024,
            storage_limit_bytes=107374182400,
        )
        async_db_session.add(workspace)
        await async_db_session.commit()

        # Query back
        res = await async_db_session.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        loaded_customer = res.scalar_one()
        assert loaded_customer.name == "Acme Corp"
        assert loaded_customer.plan == "enterprise"
        assert len(loaded_customer.id) == 36

    async def test_create_ticket_with_messages(self, async_db_session: AsyncSession):
        """Verify Ticket and TicketMessage relationship and defaults."""
        from backend.app.models.entities import Customer, Ticket, TicketMessage

        customer = Customer(name="Beta LLC", email="contact@beta.test", plan="pro")
        async_db_session.add(customer)
        await async_db_session.flush()

        ticket = Ticket(
            customer_id=customer.id,
            subject="Cannot connect to SSO",
            category=CategoryEnum.LOGIN_ISSUE.value,
            severity=SeverityEnum.CRITICAL.value,
            channel=ChannelEnum.WEB.value,
        )
        async_db_session.add(ticket)
        await async_db_session.flush()

        msg = TicketMessage(
            ticket_id=ticket.id,
            author_role="customer",
            body="Our entire team cannot log in through Okta.",
        )
        async_db_session.add(msg)
        await async_db_session.commit()

        # Retrieve ticket and verify default status and relations
        result = await async_db_session.execute(
            select(Ticket).where(Ticket.id == ticket.id)
        )
        loaded_ticket = result.scalar_one()
        assert loaded_ticket.status == "new"
        assert loaded_ticket.category == "login_issue"
        assert loaded_ticket.severity == "critical"
        assert loaded_ticket.channel == "web"
        assert loaded_ticket.created_at is not None

    async def test_workflow_run_and_approval_request(self, async_db_session: AsyncSession):
        """Verify WorkflowRun JSON state storage and ApprovalRequest entity."""
        from backend.app.models.entities import (
            ApprovalRequest,
            Customer,
            Ticket,
            WorkflowRun,
        )

        customer = Customer(name="Gamma Inc", email="gamma@test.io", plan="business")
        async_db_session.add(customer)
        await async_db_session.flush()

        ticket = Ticket(
            customer_id=customer.id,
            subject="Requesting refund for unused seats",
            category=CategoryEnum.BILLING.value,
        )
        async_db_session.add(ticket)
        await async_db_session.flush()

        workflow_run = WorkflowRun(
            ticket_id=ticket.id,
            status=WorkflowStatusEnum.WAITING_ON_APPROVAL.value,
            current_node="human_approval",
            completed_nodes=["understand_ticket", "classify_severity", "resolution_planning"],
            state={"refund_amount": 150.0, "currency": "USD"},
        )
        async_db_session.add(workflow_run)
        await async_db_session.flush()

        approval = ApprovalRequest(
            ticket_id=ticket.id,
            workflow_id=workflow_run.id,
            action_name="create_refund_request",
            action_payload={"amount": 150.0, "reason": "Unused seats"},
            status=ApprovalStatusEnum.PENDING.value,
        )
        async_db_session.add(approval)
        await async_db_session.commit()

        # Query back and verify JSON deserialization
        result = await async_db_session.execute(
            select(WorkflowRun).where(WorkflowRun.id == workflow_run.id)
        )
        loaded_run = result.scalar_one()
        assert loaded_run.status == "waiting_on_approval"
        assert loaded_run.completed_nodes == ["understand_ticket", "classify_severity", "resolution_planning"]
        assert loaded_run.state["refund_amount"] == 150.0

        app_res = await async_db_session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval.id)
        )
        loaded_app = app_res.scalar_one()
        assert loaded_app.action_payload["amount"] == 150.0
        assert loaded_app.status == "pending"

    async def test_customer_memory_and_audit_log(self, async_db_session: AsyncSession):
        """Verify CustomerMemory and AuditLog entity persistence."""
        from backend.app.models.entities import AuditLog, Customer, CustomerMemory

        customer = Customer(name="Delta Corp", email="delta@corp.test", plan="pro")
        async_db_session.add(customer)
        await async_db_session.flush()

        memory = CustomerMemory(
            customer_id=customer.id,
            memory_type=MemoryTypeEnum.PAST_ISSUE.value,
            content="Customer previously resolved MFA lockout via recovery codes.",
        )
        async_db_session.add(memory)

        audit = AuditLog(
            actor_id="usr-agent-002",
            client_ip="192.168.1.50",
            http_method="POST",
            route="/api/v1/tickets/123/run",
            request_id=str(uuid.uuid4()),
            status_code=202,
        )
        async_db_session.add(audit)
        await async_db_session.commit()

        # Verify query
        res = await async_db_session.execute(
            select(CustomerMemory).where(CustomerMemory.customer_id == customer.id)
        )
        loaded_mem = res.scalar_one()
        assert loaded_mem.memory_type == "past_issue"
        assert "MFA lockout" in loaded_mem.content

        audit_res = await async_db_session.execute(
            select(AuditLog).where(AuditLog.actor_id == "usr-agent-002")
        )
        loaded_audit = audit_res.scalar_one()
        assert loaded_audit.status_code == 202
        assert loaded_audit.http_method == "POST"

    def test_base_model_uuid_and_timestamps(self):
        """Test default UUID generator and timestamps on instantiating models without DB."""
        from backend.app.models.entities import Customer

        customer = Customer(name="Test Entity", email="entity@test.io")
        assert customer.id is not None
        assert len(customer.id) == 36
        uuid.UUID(customer.id)  # Throws ValueError if not valid UUID
        assert customer.created_at is not None
        assert isinstance(customer.created_at, datetime)
        assert customer.created_at.tzinfo is not None
