"""SQLAlchemy 2.0 Declarative Models for CloudDesk Support Platform.

Portable across SQLite (in-memory demo/testing) and PostgreSQL (production).
Uses String(36) UUIDs and standard JSON column types.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.app.schemas.common import (
    ApprovalStatusEnum,
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    EscalationStatusEnum,
    MemoryTypeEnum,
    ResolutionActionStatusEnum,
    RoleEnum,
    SeverityEnum,
    TicketStatusEnum,
    WorkflowStatusEnum,
)


def generate_uuid() -> str:
    """Generate a 36-character canonical UUID string."""
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base declarative model for all CloudDesk database tables."""



class TimestampedModel(Base):
    """Abstract model adding UUID primary key and UTC timestamp tracking."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=get_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )

    def __init__(self, **kwargs: Any) -> None:
        if "id" not in kwargs or kwargs["id"] is None:
            kwargs["id"] = generate_uuid()
        if "created_at" not in kwargs or kwargs["created_at"] is None:
            kwargs["created_at"] = get_utc_now()
        if "updated_at" not in kwargs or kwargs["updated_at"] is None:
            kwargs["updated_at"] = get_utc_now()
        super().__init__(**kwargs)


class Profile(TimestampedModel):
    """User profile associated with authentication identity."""

    __tablename__ = "profiles"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(50), default=RoleEnum.AGENT.value, nullable=False
    )
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="assignee"
    )
    decided_approvals: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="approver"
    )


class Customer(TimestampedModel):
    """SaaS customer / organization entity."""

    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    plan: Mapped[str] = mapped_column(
        String(50), default=CustomerPlanEnum.FREE.value, nullable=False
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    memory_notes: Mapped[list["CustomerMemory"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class Subscription(TimestampedModel):
    """Customer subscription plan, billing status, and seat allocation."""

    __tablename__ = "subscriptions"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    seats: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    customer: Mapped["Customer"] = relationship(back_populates="subscriptions")


class Workspace(TimestampedModel):
    """Team workspace and storage quota tracking."""

    __tablename__ = "workspaces"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    storage_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_limit_bytes: Mapped[int] = mapped_column(
        BigInteger, default=10737418240, nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="workspaces")


class Product(TimestampedModel):
    """CloudDesk software product / module catalog."""

    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Ticket(TimestampedModel):
    """Support ticket submitted by or on behalf of a customer."""

    __tablename__ = "tickets"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=TicketStatusEnum.NEW.value, index=True, nullable=False
    )
    severity: Mapped[str] = mapped_column(
        String(50), default=SeverityEnum.MEDIUM.value, index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(50), default=CategoryEnum.OTHER.value, index=True, nullable=False
    )
    channel: Mapped[str] = mapped_column(
        String(50), default=ChannelEnum.EMAIL.value, nullable=False
    )
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="tickets")
    assignee: Mapped["Profile | None"] = relationship(back_populates="assigned_tickets")
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    runs: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    escalations: Mapped[list["Escalation"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class TicketMessage(TimestampedModel):
    """Individual message in a ticket conversation thread."""

    __tablename__ = "ticket_messages"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # customer, agent, system
    author_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")


class SupportArticle(TimestampedModel):
    """Knowledge base article for RAG retrieval."""

    __tablename__ = "support_articles"

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Incident(TimestampedModel):
    """Active or historical platform infrastructure incident."""

    __tablename__ = "incidents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    service: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="investigating", nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    impact_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkflowRun(TimestampedModel):
    """Execution run of an autonomous LangGraph agent workflow."""

    __tablename__ = "workflow_runs"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default=WorkflowStatusEnum.QUEUED.value, index=True, nullable=False
    )
    current_node: Mapped[str | None] = mapped_column(String(100), nullable=True)
    completed_nodes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=get_utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="runs")
    events: Mapped[list["WorkflowEvent"]] = relationship(
        back_populates="workflow_run", cascade="all, delete-orphan"
    )
    actions: Mapped[list["ResolutionAction"]] = relationship(
        back_populates="workflow_run", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="workflow_run", cascade="all, delete-orphan"
    )


class WorkflowEvent(TimestampedModel):
    """Fine-grained telemetry event emitted during workflow execution."""

    __tablename__ = "workflow_events"

    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="events")


class ResolutionAction(TimestampedModel):
    """Specific remediation action formulated in a resolution plan."""

    __tablename__ = "resolution_actions"

    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=ResolutionActionStatusEnum.PLANNED.value, nullable=False
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="actions")


class ApprovalRequest(TimestampedModel):
    """Human-in-the-loop approval gate for consequential actions."""

    __tablename__ = "approval_requests"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=ApprovalStatusEnum.PENDING.value, index=True, nullable=False
    )
    decided_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="approvals")
    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="approvals")
    approver: Mapped["Profile | None"] = relationship(back_populates="decided_approvals")


class Escalation(TimestampedModel):
    """Deterministic policy handoff to a designated specialized team."""

    __tablename__ = "escalations"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    target_team: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_reason: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=EscalationStatusEnum.OPEN.value, index=True, nullable=False
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="escalations")


class CustomerMemory(TimestampedModel):
    """Persistent customer memory note scrubbed of secrets."""

    __tablename__ = "customer_memory"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    memory_type: Mapped[str] = mapped_column(
        String(50), default=MemoryTypeEnum.NOTE.value, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="memory_notes")


class AuditLog(Base):
    """Immutable audit trail for all state-changing API operations."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    client_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    http_method: Mapped[str] = mapped_column(String(10), nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=get_utc_now, nullable=False
    )

    def __init__(self, **kwargs: Any) -> None:
        if "id" not in kwargs or kwargs["id"] is None:
            kwargs["id"] = generate_uuid()
        if "created_at" not in kwargs or kwargs["created_at"] is None:
            kwargs["created_at"] = get_utc_now()
        super().__init__(**kwargs)
