"""SupportState and channel reducers for LangGraph orchestration (P10-1).

Defines the shared graph state schema SupportState, channel reducers (completed_nodes,
errors, token_usage), and initial state construction for the CloudDesk agentic workflow.
Conforms to CLAUDE.md §7.3, §14, and ADR-03.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from typing_extensions import TypedDict


def append_list(existing: list[Any] | None, update: list[Any] | None) -> list[Any]:
    """Channel reducer that appends elements to a list, handling None safely.

    Used by completed_nodes and errors reducers.
    """
    result = list(existing or [])
    if update:
        result.extend(update)
    return result


def merge_usage(
    existing: dict[str, int] | None, update: dict[str, int] | None
) -> dict[str, int]:
    """Channel reducer that sums token usage counters across specialist nodes.

    Sums prompt_tokens, completion_tokens, total_tokens, and any custom usage keys.
    """
    result = dict(existing or {})
    for key, val in (update or {}).items():
        if isinstance(val, (int, float)):
            result[key] = result.get(key, 0) + int(val)
    return result


class SupportState(TypedDict, total=False):
    """Canonical LangGraph workflow state for CloudDesk support tickets.

    Nodes return partial dictionaries that merge into this state.
    Reducer fields (completed_nodes, errors, token_usage) accumulate across nodes.
    """

    # --- Core Ticket Context ---
    ticket_id: str
    customer_id: str
    subject: str
    text: str
    customer_plan: str
    channel: str
    messages: list[dict[str, Any]]
    category: str | None
    severity: str | None

    # --- Specialist Agent Outputs ---
    classification: dict[str, Any] | None
    severity_assessment: dict[str, Any] | None
    customer_context: dict[str, Any] | None
    customer_notes: list[dict[str, Any]] | None
    evidence: list[dict[str, Any]] | None
    similar_cases: list[dict[str, Any]] | None
    diagnosis: dict[str, Any] | str | None
    troubleshooting_steps: list[str] | None
    remediation_playbook: str | None
    incident_detected: bool | None
    resolution_plan: dict[str, Any] | None
    proposed_reply: str | None
    risk_assessment: dict[str, Any] | str | None
    risk_level: str | None

    # --- Governance, Approval & Escalation ---
    approval_required: bool | None
    approval_status: str | None  # "pending", "approved", "rejected"
    approval_reason: str | None
    approval_request: dict[str, Any] | None
    approval_requested_at: str | None
    approval_decision: str | None  # "approved", "rejected"
    approval_decision_by: str | None
    approval_feedback: str | None

    escalation_required: bool | None
    escalation: dict[str, Any] | None
    escalation_team: str | None
    escalation_reason: str | None
    escalation_rule_id: str | None

    # --- Resolution Execution & Summary ---
    resolution_actions: list[dict[str, Any]] | None
    executed_actions: list[dict[str, Any]] | None
    ticket_summary: str | None

    # --- Workflow Telemetry & Tracing ---
    workflow_id: str | None
    thread_id: str | None
    request_id: str | None
    current_node: str | None

    # --- Reducer Channels (Accumulate across execution) ---
    completed_nodes: Annotated[list[str], append_list]
    errors: Annotated[list[str], append_list]
    token_usage: Annotated[dict[str, int], merge_usage]


def create_initial_support_state(
    ticket_id: str,
    customer_id: str,
    subject: str = "",
    text: str = "",
    customer_plan: str = "free",
    channel: str = "web",
    messages: list[dict[str, Any]] | None = None,
    workflow_id: str | None = None,
    thread_id: str | None = None,
    request_id: str | None = None,
    **kwargs: Any,
) -> SupportState:
    """Construct an initialized SupportState ready for graph execution.

    Initializes reducer collections (completed_nodes, errors, token_usage)
    and generates unique workflow/thread identifiers if not provided.
    """
    wid = workflow_id or f"wf-{uuid.uuid4().hex[:12]}"
    tid = thread_id or f"thread-{ticket_id}"

    state: SupportState = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "subject": subject,
        "text": text,
        "customer_plan": customer_plan.lower(),
        "channel": channel.lower(),
        "messages": list(messages or []),
        "workflow_id": wid,
        "thread_id": tid,
        "request_id": request_id,
        "category": None,
        "severity": None,
        "classification": None,
        "severity_assessment": None,
        "customer_context": None,
        "customer_notes": [],
        "evidence": [],
        "similar_cases": [],
        "diagnosis": None,
        "troubleshooting_steps": [],
        "remediation_playbook": None,
        "incident_detected": False,
        "resolution_plan": None,
        "proposed_reply": None,
        "risk_assessment": None,
        "risk_level": "low",
        "approval_required": False,
        "approval_status": None,
        "approval_reason": None,
        "approval_request": None,
        "approval_requested_at": None,
        "approval_decision": None,
        "approval_decision_by": None,
        "approval_feedback": None,
        "escalation_required": False,
        "escalation": None,
        "escalation_team": None,
        "escalation_reason": None,
        "escalation_rule_id": None,
        "resolution_actions": [],
        "executed_actions": [],
        "ticket_summary": None,
        "current_node": None,
        "completed_nodes": [],
        "errors": [],
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

    # Merge any additional optional fields passed in
    for key, value in kwargs.items():
        state[key] = value  # type: ignore[literal-required]

    return state


__all__ = [
    "SupportState",
    "append_list",
    "create_initial_support_state",
    "merge_usage",
]
