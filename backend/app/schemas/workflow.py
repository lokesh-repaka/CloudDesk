"""Workflow schemas and structured output contracts (P9-1).

Provides Pydantic v2 schemas for all LangGraph specialist agents and workflow stages
adhering to CLAUDE.md §7.1, §7.2, and acceptance criteria US-005, US-006, US-007,
US-008, US-009, US-010, and US-014.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.common import (
    CategoryEnum,
    CustomerPlanEnum,
    SeverityEnum,
)


class Classification(BaseModel):
    """Structured classification output produced by Supervisor agent (US-005, AC-024)."""

    model_config = ConfigDict(extra="ignore")

    category: CategoryEnum = Field(
        ...,
        description="Canonical ticket category strictly matching one of the 10 domain categories.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 and 1.0.",
    )
    reason: str = Field(
        default="",
        description="Justification explaining the classification rationale.",
    )
    summary: str = Field(
        default="",
        description="One-line summary synthesizing the customer inquiry.",
    )


class SeverityAssessment(BaseModel):
    """Structured urgency and severity assessment (US-006, AC-025)."""

    model_config = ConfigDict(extra="ignore")

    severity: SeverityEnum = Field(
        ...,
        description="Assigned ticket severity level: low, medium, high, critical.",
    )
    severity_reason: str = Field(
        ...,
        description="Non-empty explanation detailing why this severity level was assigned.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Assessment confidence score between 0.0 and 1.0.",
    )
    matched_rules: list[str] = Field(
        default_factory=list,
        description="List of rule IDs that contributed to raising or locking the severity.",
    )

    @field_validator("severity_reason")
    @classmethod
    def validate_non_empty_reason(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("severity_reason cannot be empty or whitespace only")
        return v.strip()


class CustomerContext(BaseModel):
    """Customer profile, subscription tier, and historical memory context (US-007, AC-026)."""

    model_config = ConfigDict(extra="ignore")

    customer_id: str = Field(..., description="Unique customer UUID.")
    name: str = Field(..., description="Customer or organization name.")
    email: str = Field(..., description="Primary contact email address.")
    plan: CustomerPlanEnum = Field(
        default=CustomerPlanEnum.FREE,
        description="Customer subscription plan tier.",
    )
    workspace_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Workspace usage quotas, seat allocations, and storage stats.",
    )
    recent_tickets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of recent customer ticket records.",
    )
    memory_notes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recalled long-term customer memory notes (up to 10).",
    )


class Evidence(BaseModel):
    """RAG knowledge base citation chunk shape (CLAUDE.md §8, AC-027)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique chunk identifier.")
    title: str = Field(..., description="Article title.")
    source: str = Field(
        ..., description="Canonical citation source e.g. kb://slug#section."
    )
    snippet: str = Field(..., description="Extracted relevant text excerpt.")
    score: float = Field(..., description="Hybrid retrieval ranking score.")
    url: str = Field(..., description="Frontend relative URL e.g. /knowledge/<id>.")
    article_id: str = Field(..., description="Parent support article UUID.")


class PreviousCase(BaseModel):
    """Similar historical resolved ticket case (CLAUDE.md §7.1, AC-028)."""

    model_config = ConfigDict(extra="ignore")

    ticket_id: str = Field(..., description="Historical ticket identifier.")
    subject: str = Field(..., description="Ticket subject line.")
    category: str = Field(..., description="Category under which the ticket resolved.")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity overlap score.",
    )
    resolution: str = Field(..., description="Resolution summary or outcome.")
    actions: list[str] = Field(
        default_factory=list,
        description="Remediation actions taken during case resolution.",
    )


class Diagnosis(BaseModel):
    """Automated root cause diagnosis and troubleshooting steps (US-008, AC-030)."""

    model_config = ConfigDict(extra="ignore")

    probable_causes: list[str] = Field(
        default_factory=list,
        description="Ranked probable technical root causes.",
    )
    service_status: str | dict[str, Any] | None = Field(
        default=None,
        description="Result of service health check tool inspection.",
    )
    troubleshooting_steps: list[str] = Field(
        default_factory=list,
        description="Ordered, numbered diagnostic and remediation steps.",
    )
    summary: str = Field(
        default="",
        description="Executive diagnosis overview synthesizing causes and next steps.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Diagnosis confidence score between 0.0 and 1.0.",
    )


class ResolutionActionPlan(BaseModel):
    """Deterministic remediation action planned for execution (CLAUDE.md §7.4)."""

    model_config = ConfigDict(extra="ignore")

    tool_name: str = Field(
        ..., description="Target tool name e.g. update_ticket, create_refund_request."
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool invocation.",
    )
    requires_approval: bool = Field(
        default=False,
        description="True if tool policy mandates human approval before execution.",
    )
    reason: str = Field(
        default="",
        description="Justification explaining why this action is required.",
    )


class ResolutionPlan(BaseModel):
    """Comprehensive resolution proposal prepared by Resolution Agent (US-009, AC-032)."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(
        ...,
        description="Internal executive summary of the resolution proposal.",
    )
    customer_reply: str = Field(
        ...,
        description="Drafted response intended for customer communication.",
    )
    internal_notes: str = Field(
        default="",
        description="Technical internal documentation and agent notes.",
    )
    actions: list[ResolutionActionPlan] = Field(
        default_factory=list,
        description="List of planned tool actions required to resolve the ticket.",
    )
    requires_approval: bool = Field(
        default=False,
        description="True if any planned action requires human approval or high risk.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Plan confidence score.",
    )


class EscalationDecision(BaseModel):
    """Escalation routing decision (US-010, AC-035, CLAUDE.md §7.2)."""

    model_config = ConfigDict(extra="ignore")

    escalation_required: bool = Field(
        ...,
        description="True if ticket must be handed off to a specialized human team.",
    )
    target_team: str | None = Field(
        default=None,
        description="Department or team assigned e.g. billing_team, security_team, tier_3_engineering.",
    )
    reason: str = Field(
        default="",
        description="Policy or judgement justification for escalation.",
    )
    severity: SeverityEnum | None = Field(
        default=None,
        description="Elevated severity if modified by escalation.",
    )
    policy_matched: bool = Field(
        default=False,
        description="True if decision originated from a deterministic policy rule.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Decision confidence score.",
    )


class WorkflowEventSchema(BaseModel):
    """Telemetry event recorded during graph execution (CLAUDE.md §12)."""

    model_config = ConfigDict(extra="ignore")

    event_type: str = Field(
        ...,
        description="Event classification: node_started, node_completed, tool_called, llm_called, etc.",
    )
    node_name: str | None = Field(
        default=None, description="Active graph node identifier."
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary event payload data."
    )
    token_usage: dict[str, int] | None = Field(
        default=None, description="Input/output/total token counts."
    )
    duration_ms: float | None = Field(
        default=None, description="Execution duration in milliseconds."
    )


class WorkflowStateSchema(BaseModel):
    """Comprehensive runtime state representation of a support workflow run."""

    model_config = ConfigDict(extra="ignore")

    ticket_id: str = Field(..., description="Ticket UUID being processed.")
    workflow_id: str | None = Field(
        default=None, description="Workflow execution run ID."
    )
    current_node: str | None = Field(
        default=None, description="Active or latest completed node."
    )
    completed_nodes: list[str] = Field(
        default_factory=list, description="Ordered list of executed nodes."
    )
    category: str | None = Field(default=None, description="Classified category.")
    severity: str | None = Field(default=None, description="Assigned severity.")
    classification: Classification | None = Field(default=None)
    severity_assessment: SeverityAssessment | None = Field(default=None)
    diagnosis: Diagnosis | None = Field(default=None)
    resolution_plan: ResolutionPlan | None = Field(default=None)
    escalation_decision: EscalationDecision | None = Field(default=None)
    errors: list[str] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(
        default_factory=lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
    )
