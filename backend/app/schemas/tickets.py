"""Pydantic schemas for Tickets, Ticket Messages, Workflow Runs, and Actions.

Single source of truth for Ticket API data contract (P4-1 / CLAUDE.md §12).
Enforces strict boundary validation, input sanitization, and serialization rules.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.common import (
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    SeverityEnum,
    TicketStatusEnum,
    WorkflowStatusEnum,
)


class TicketCreate(BaseModel):
    """Payload for omnichannel ticket ingestion (POST /api/v1/tickets)."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="UUID or identifier of customer submitting the ticket",
    )
    subject: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Brief summary or subject line of the issue",
    )
    body: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Comprehensive initial issue description or conversation body",
    )
    channel: ChannelEnum = Field(
        default=ChannelEnum.EMAIL,
        description="Origin communication channel ('email', 'chat', 'web', 'api')",
    )

    @field_validator("subject")
    @classmethod
    def validate_non_whitespace_subject(cls, v: str) -> str:
        """Reject empty or whitespace-only subject strings (AC-002)."""
        stripped = v.strip()
        if len(stripped) < 3:
            raise ValueError("Subject must contain at least 3 non-whitespace characters")
        return stripped

    @field_validator("body")
    @classmethod
    def validate_non_whitespace_body(cls, v: str) -> str:
        """Reject empty or whitespace-only issue body strings."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Ticket body cannot be empty or whitespace-only")
        return v


class TicketMessageCreate(BaseModel):
    """Payload for appending a message to an existing ticket conversation."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Message content text",
    )
    author_role: str = Field(
        default="customer",
        max_length=50,
        description="Role of the sender ('customer', 'agent', 'system')",
    )
    author_id: str | None = Field(
        default=None,
        max_length=255,
        description="Optional identity identifier of the message author",
    )

    @field_validator("body")
    @classmethod
    def validate_non_whitespace_body(cls, v: str) -> str:
        """Reject empty message bodies."""
        if not v.strip():
            raise ValueError("Message body cannot be empty or whitespace-only")
        return v


class TicketMessageResponse(BaseModel):
    """Serialized message in a ticket conversation thread."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique message UUID")
    ticket_id: str = Field(..., description="Parent ticket identifier")
    author_role: str = Field(..., description="Message author role ('customer', 'agent', 'system')")
    author_id: str | None = Field(default=None, description="Author identifier if available")
    body: str = Field(..., description="Text content of the message")
    created_at: datetime = Field(..., description="UTC creation timestamp")


class TicketSummaryResponse(BaseModel):
    """Summary representation of a ticket for queue listing (GET /api/v1/tickets)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique ticket identifier (UUID or human key)")
    customer_id: str = Field(..., description="Associated customer UUID")
    assigned_to: str | None = Field(default=None, description="Assigned support agent profile UUID")
    subject: str = Field(..., description="Ticket subject line")
    status: TicketStatusEnum = Field(..., description="Lifecycle status")
    severity: SeverityEnum = Field(..., description="Assessed urgency level")
    category: CategoryEnum = Field(..., description="Canonical classification category")
    channel: ChannelEnum = Field(..., description="Intake communication channel")
    resolution_summary: str | None = Field(default=None, description="Final resolution summary if resolved")
    created_at: datetime = Field(..., description="Ticket creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")
    customer_name: str | None = Field(default=None, description="Name of submitting organization")
    customer_plan: CustomerPlanEnum | None = Field(default=None, description="Customer subscription plan tier")
    customer_email: str | None = Field(default=None, description="Customer contact email")


class TicketDetailResponse(TicketSummaryResponse):
    """Detailed ticket representation with full conversation thread (GET /api/v1/tickets/{id})."""

    messages: list[TicketMessageResponse] = Field(
        default_factory=list,
        description="Chronological conversation message thread",
    )
    active_workflow_id: str | None = Field(
        default=None,
        description="UUID of current or latest LangGraph workflow execution run",
    )


class TicketFilterParams(BaseModel):
    """Query parameters for filtering and paginating ticket queues (AC-007, AC-008)."""

    status: TicketStatusEnum | None = Field(default=None, description="Filter by ticket status")
    severity: SeverityEnum | None = Field(default=None, description="Filter by severity level")
    category: CategoryEnum | None = Field(default=None, description="Filter by category")
    plan: CustomerPlanEnum | None = Field(default=None, description="Filter by customer subscription plan")
    customer_id: str | None = Field(default=None, description="Filter by customer UUID")
    assigned_to: str | None = Field(default=None, description="Filter by assigned agent UUID")
    offset: int = Field(default=0, ge=0, description="Pagination row offset")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum items per page")


class TicketListResponse(BaseModel):
    """Paginated response envelope for ticket queries."""

    items: list[TicketSummaryResponse] = Field(default_factory=list, description="Matching ticket summaries")
    total: int = Field(..., ge=0, description="Total matching items across all pages")
    offset: int = Field(default=0, ge=0, description="Current pagination offset")
    limit: int = Field(default=50, ge=1, description="Current page size limit")


class WorkflowRunResponse(BaseModel):
    """Response returned when initiating an autonomous workflow (POST /api/v1/tickets/{id}/run)."""

    ticket_id: str = Field(..., description="Target ticket ID")
    workflow_id: str = Field(..., description="Unique workflow run UUID")
    status: WorkflowStatusEnum = Field(..., description="Execution status ('queued', 'running', etc.)")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Run start timestamp")


class WorkflowStateResponse(BaseModel):
    """Polled state snapshot of an active or completed workflow (GET /api/v1/tickets/{id}/workflow)."""

    ticket_id: str = Field(..., description="Target ticket ID")
    workflow_id: str = Field(..., description="Workflow execution UUID")
    status: WorkflowStatusEnum = Field(..., description="Current run lifecycle state")
    current_node: str | None = Field(default=None, description="Currently active graph node")
    completed_nodes: list[str] = Field(default_factory=list, description="Ordered list of completed graph nodes")
    classification: dict[str, Any] | None = Field(default=None, description="Category classification output")
    severity: dict[str, Any] | None = Field(default=None, description="Severity assessment output")
    diagnosis: dict[str, Any] | None = Field(default=None, description="Troubleshooting diagnostic output")
    resolution_plan: dict[str, Any] | None = Field(default=None, description="Proposed resolution and action plan")
    escalation: dict[str, Any] | None = Field(default=None, description="Escalation record if escalated")
    token_usage: dict[str, int] = Field(default_factory=dict, description="LLM token consumption metrics")
    error: str | None = Field(default=None, description="Error message if run encountered failure")


class WorkflowEventResponse(BaseModel):
    """Individual workflow telemetry event for timeline inspection (GET /api/v1/tickets/{id}/events)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Event UUID")
    workflow_id: str = Field(..., description="Workflow execution UUID")
    ticket_id: str = Field(..., description="Associated ticket ID")
    event_type: str = Field(..., description="Telemetry event type (node_started, tool_called, etc.)")
    node_name: str = Field(..., description="Source node name")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload and metadata")
    duration_ms: int = Field(default=0, ge=0, description="Execution duration in milliseconds")
    tokens_used: int = Field(default=0, ge=0, description="Tokens consumed during step")
    cost_estimate: float = Field(default=0.0, ge=0.0, description="Estimated financial cost in USD")
    created_at: datetime = Field(..., description="Event timestamp")


class ReplyCreate(BaseModel):
    """Payload for agent dispatching a reply to a customer (POST /api/v1/tickets/{id}/reply)."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Verified customer-facing reply message text",
    )
    internal_note: str | None = Field(
        default=None,
        max_length=5000,
        description="Optional internal agent note accompanying the reply",
    )

    @field_validator("message")
    @classmethod
    def validate_non_whitespace_message(cls, v: str) -> str:
        """Reject empty or whitespace-only reply messages."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Reply message cannot be empty or whitespace-only")
        return stripped


class ReplyResponse(BaseModel):
    """Response returned upon successful dispatch of an agent reply."""

    ticket_id: str = Field(..., description="Target ticket ID")
    message_id: str = Field(..., description="UUID of newly created ticket message")
    status: TicketStatusEnum = Field(
        default=TicketStatusEnum.WAITING_ON_CUSTOMER,
        description="Updated ticket status",
    )


class RequestInfoCreate(BaseModel):
    """Payload for requesting clarifying details from a customer (POST /api/v1/tickets/{id}/request-info)."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Specific clarifying question directed to customer",
    )

    @field_validator("question")
    @classmethod
    def validate_non_whitespace_question(cls, v: str) -> str:
        """Reject empty or whitespace-only questions."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Question cannot be empty or whitespace-only")
        return stripped


class EscalateRequest(BaseModel):
    """Payload for manual or policy ticket escalation (POST /api/v1/tickets/{id}/escalate)."""

    model_config = ConfigDict(extra="forbid")

    target_team: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Designated recipient team (e.g., 'Security Operations', 'Billing')",
    )
    policy_reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Documented rationale and triggered policy rules",
    )
    severity: SeverityEnum = Field(
        default=SeverityEnum.HIGH,
        description="Assigned escalation severity level",
    )


class EscalateResponse(BaseModel):
    """Response returned after recording a ticket escalation."""

    model_config = ConfigDict(from_attributes=True)

    escalation_id: str = Field(..., description="Unique escalation record UUID")
    ticket_id: str = Field(..., description="Escalated ticket ID")
    target_team: str = Field(..., description="Recipient team")
    policy_reason: str = Field(..., description="Escalation reason")
    severity: SeverityEnum = Field(..., description="Escalation severity")
    status: str = Field(default="open", description="Escalation lifecycle status")
    created_at: datetime = Field(..., description="Timestamp escalation was recorded")
