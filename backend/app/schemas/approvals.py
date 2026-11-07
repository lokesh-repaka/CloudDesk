"""Pydantic schemas for Human Approval Gate and Resumption API (P11-2).

Defines request and response schemas for listing approval requests, submitting approval/rejection
decisions, and resuming the LangGraph workflow execution engine in accordance with
CLAUDE.md §4.1, §5.1, §7.3, API_CONTRACT §5.1, and US-011.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import ApprovalStatusEnum


class ApprovalRequestResponse(BaseModel):
    """Schema representing an approval request item in queues or dossiers."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique approval request identifier (appr-...)")
    ticket_id: str = Field(..., description="Target support ticket identifier")
    workflow_id: str = Field(
        ..., description="Target LangGraph workflow run identifier"
    )
    action_name: str = Field(
        ..., description="Name of the gated tool or action (e.g. create_refund_request)"
    )
    action_payload: dict[str, Any] = Field(
        default_factory=dict, description="Arguments and parameters for the action"
    )
    status: ApprovalStatusEnum = Field(
        ..., description="Current status of the approval request"
    )
    decided_by: str | None = Field(
        default=None, description="Profile ID of the agent/admin who made the decision"
    )
    rejection_reason: str | None = Field(
        default=None, description="Mandatory explanation if rejected or decision notes"
    )
    decided_at: datetime | None = Field(
        default=None, description="Timestamp when decision was recorded"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when approval request was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when approval request was last updated"
    )


class ApproveDecisionRequest(BaseModel):
    """Optional payload when approving a gated consequential action."""

    notes: str | None = Field(
        default=None,
        description="Optional supervisory notes or approval justification",
    )


class RejectDecisionRequest(BaseModel):
    """Payload required when rejecting a gated consequential action."""

    rejection_reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Mandatory explanation describing why the requested action was rejected",
    )


class ApprovalDecisionResponse(BaseModel):
    """Response payload returned following an approve or reject decision."""

    id: str = Field(..., description="Approval request identifier")
    ticket_id: str = Field(..., description="Ticket identifier")
    workflow_id: str = Field(..., description="Workflow run identifier")
    action_name: str = Field(..., description="Target action name")
    status: ApprovalStatusEnum = Field(
        ..., description="Resulting status (approved or rejected)"
    )
    decided_by: str = Field(..., description="Profile ID of the deciding agent")
    rejection_reason: str | None = Field(
        default=None, description="Rejection reason or notes if applicable"
    )
    decided_at: datetime = Field(..., description="Decision timestamp")
    workflow_status: str | None = Field(
        default=None, description="Resulting status of the associated workflow run"
    )
    message: str = Field(default="", description="Human-readable outcome description")
