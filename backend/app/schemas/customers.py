"""Pydantic schemas for Customers, Subscriptions, Workspaces, and Memory Notes.

Single source of truth for Customer API data contract (P4-1 / CLAUDE.md §12).
Enforces 360-degree customer context schemas, memory retention rules, and input boundaries.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.common import CustomerPlanEnum, MemoryTypeEnum
from backend.app.schemas.tickets import TicketSummaryResponse


class CustomerCreate(BaseModel):
    """Payload for registering a new customer entity."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255, description="Customer or organization name")
    email: str = Field(..., min_length=3, max_length=255, description="Primary customer contact email")
    plan: CustomerPlanEnum = Field(default=CustomerPlanEnum.FREE, description="Subscription plan tier")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Reject whitespace-only names."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Customer name cannot be empty or whitespace-only")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Basic email structure sanity check."""
        stripped = v.strip()
        if "@" not in stripped or "." not in stripped:
            raise ValueError("Invalid email address format")
        return stripped.lower()


class CustomerUpdate(BaseModel):
    """Payload for updating existing customer details."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    plan: CustomerPlanEnum | None = Field(default=None)


class CustomerSummaryResponse(BaseModel):
    """Summary view of a customer for lists and references."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique customer UUID")
    name: str = Field(..., description="Customer organization name")
    email: str = Field(..., description="Primary contact email")
    plan: CustomerPlanEnum = Field(..., description="Subscription plan tier")
    created_at: datetime = Field(..., description="Customer creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")


class CustomerListResponse(BaseModel):
    """Paginated response envelope for customer queries."""

    items: list[CustomerSummaryResponse] = Field(default_factory=list, description="Matching customer records")
    total: int = Field(..., ge=0, description="Total matching customer count")
    offset: int = Field(default=0, ge=0, description="Pagination row offset")
    limit: int = Field(default=50, ge=1, description="Page size limit")


class SubscriptionResponse(BaseModel):
    """Active or historic customer subscription tier and quota details."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Subscription UUID")
    customer_id: str = Field(..., description="Parent customer UUID")
    plan: str = Field(..., description="Plan tier string ('free', 'pro', etc.)")
    status: str = Field(..., description="Billing status ('active', 'canceled', etc.)")
    seats: int = Field(default=1, ge=1, description="Allocated user seats")
    current_period_end: datetime | None = Field(default=None, description="Current billing period end")
    created_at: datetime = Field(..., description="Subscription creation timestamp")
    updated_at: datetime = Field(..., description="Subscription update timestamp")


class WorkspaceResponse(BaseModel):
    """Team workspace entity and storage utilization metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Workspace UUID")
    customer_id: str = Field(..., description="Parent customer UUID")
    name: str = Field(..., description="Workspace display name")
    slug: str = Field(..., description="URL slug / unique identifier")
    storage_used_bytes: int = Field(default=0, ge=0, description="Current storage used in bytes")
    storage_limit_bytes: int = Field(default=10737418240, ge=0, description="Total storage capacity in bytes")
    created_at: datetime = Field(..., description="Workspace creation timestamp")
    updated_at: datetime = Field(..., description="Workspace update timestamp")


class CustomerMemoryResponse(BaseModel):
    """Persistent customer memory note for institutional support history."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Memory note UUID")
    customer_id: str = Field(..., description="Parent customer UUID")
    memory_type: MemoryTypeEnum = Field(..., description="Note classification category")
    content: str = Field(..., description="Scrubbed note content text")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class CustomerMemoryCreate(BaseModel):
    """Payload for creating a new permanent customer memory note."""

    model_config = ConfigDict(extra="forbid")

    memory_type: MemoryTypeEnum = Field(
        default=MemoryTypeEnum.NOTE,
        description="Note type ('preference', 'past_issue', 'troubleshooting', 'note')",
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text content of the memory note (secrets scrubbed before storage)",
    )

    @field_validator("content")
    @classmethod
    def validate_non_whitespace_content(cls, v: str) -> str:
        """Reject empty or whitespace-only memory notes."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Memory note content cannot be empty or whitespace-only")
        return stripped


class CustomerDetailResponse(CustomerSummaryResponse):
    """Complete 360-degree customer dossier for agent console (GET /api/v1/customers/{id})."""

    active_subscription: SubscriptionResponse | None = Field(
        default=None,
        description="Currently active subscription plan",
    )
    subscriptions: list[SubscriptionResponse] = Field(
        default_factory=list,
        description="All customer subscriptions",
    )
    workspaces: list[WorkspaceResponse] = Field(
        default_factory=list,
        description="All customer workspaces and storage stats",
    )
    recent_tickets: list[TicketSummaryResponse] = Field(
        default_factory=list,
        description="Recent support tickets submitted by this customer",
    )
    memory_notes: list[CustomerMemoryResponse] = Field(
        default_factory=list,
        description="Up to 10 most recent persistent memory notes (AC-022)",
    )

    @field_validator("memory_notes")
    @classmethod
    def enforce_memory_notes_limit(cls, v: list[CustomerMemoryResponse]) -> list[CustomerMemoryResponse]:
        """Strictly bound memory notes to at most 10 items (AC-022 / CLAUDE.md §5)."""
        if len(v) > 10:
            return v[:10]
        return v
