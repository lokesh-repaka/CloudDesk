"""Escalation Schemas and Transfer Objects (P11-3).

Defines strongly-typed request and response models for the escalations queue,
status updates, and telemetry representations conforming to API_CONTRACT §2 and §3.9.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import EscalationStatusEnum


class EscalationResponse(BaseModel):
    """Response envelope for an escalation record in the queue."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str = Field(..., description="Unique escalation record identifier")
    ticket_id: str = Field(..., description="Referenced ticket identifier")
    workflow_id: str | None = Field(
        default=None, description="Referenced workflow execution run ID"
    )
    target_team: str = Field(
        ..., description="Designated specialist team (e.g., Security, Billing, Legal)"
    )
    policy_reason: str = Field(
        ..., description="Deterministic or justified reason for escalation"
    )
    severity: str = Field(..., description="Assigned severity level")
    status: str = Field(..., description="Current status of the escalation")
    created_at: datetime = Field(
        ..., description="Timestamp when escalation was recorded"
    )
    updated_at: datetime | None = Field(
        default=None, description="Timestamp of most recent update"
    )


class EscalationStatusUpdateRequest(BaseModel):
    """Request payload for updating the status of an escalation record."""

    model_config = ConfigDict(extra="forbid")

    status: EscalationStatusEnum = Field(
        ..., description="New lifecycle status for the escalation"
    )
