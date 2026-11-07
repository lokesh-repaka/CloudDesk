"""Resolution and risk graph nodes for LangGraph orchestration (P10-4).

Implements the discrete node handlers and conditional router for the resolution stage:
- `resolution_planning`: generates grounded customer reply, internal notes, and planned actions (US-009, AC-032 to AC-034)
- `risk_check`: evaluates policy escalation, approval gating, and execution risk (US-010, US-012, AC-035, AC-043 to AC-045)
- `route_after_risk_check`: conditional edge router selecting escalation, human_approval, or execute_resolution
- `memory_update`: records resolution findings to long-term memory (F11, AC-050, AC-051)

Conforms to CLAUDE.md §5, §7.1, §7.2, §7.3, §7.4, and PLAN.md §Phase 10.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from agents.rules import assess_risk, matching_escalation_rules
from agents.specialists.escalation import EscalationAgent
from agents.specialists.resolution import ResolutionAgent
from agents.state import SupportState
from backend.app.core.guardrails import scan_for_injection, validate_customer_output
from backend.app.schemas.common import SeverityEnum
from backend.app.schemas.workflow import (
    Diagnosis,
    EscalationDecision,
    ResolutionPlan,
)
from memory.service import record_resolution

logger = logging.getLogger(__name__)

# Node identifiers for completed_nodes channel and UI graph tracing
NODE_RESOLUTION_PLANNING = "resolution_planning"
NODE_RISK_CHECK = "risk_check"
NODE_MEMORY_UPDATE = "memory_update"

# Conditional routing branch targets from risk_check
ROUTE_ESCALATION = "escalation"
ROUTE_HUMAN_APPROVAL = "human_approval"
ROUTE_EXECUTE_RESOLUTION = "execute_resolution"

MAX_PAYLOAD_LENGTH = 50_000


async def resolution_planning(state: SupportState) -> dict[str, Any]:
    """Execute resolution planning node (US-009, AC-032).

    1. Extracts ticket text, category, severity, customer context, evidence, and diagnosis.
    2. Invokes ResolutionAgent to draft grounded customer reply and plan system actions.
    3. Enforces customer output safety guardrails (AC-066, AC-067).
    4. Returns partial state dict updating resolution_plan, proposed_reply,
       resolution_actions, approval_required, and completed_nodes.
    """
    raw_text = state.get("text") or state.get("subject") or ""
    text = str(raw_text)[:MAX_PAYLOAD_LENGTH]
    category = state.get("category")
    severity = state.get("severity")
    customer_context = state.get("customer_context")
    evidence = state.get("evidence")
    raw_diagnosis = state.get("diagnosis")
    ticket_id = state.get("ticket_id") or ""
    mock_reply = state.get("_mock_customer_reply")

    diagnosis: Diagnosis | None = None
    if isinstance(raw_diagnosis, Diagnosis):
        diagnosis = raw_diagnosis
    elif isinstance(raw_diagnosis, dict):
        try:
            diagnosis = Diagnosis.model_validate(raw_diagnosis)
        except (ValidationError, TypeError, ValueError):
            diagnosis = None

    agent = ResolutionAgent()

    try:
        plan: ResolutionPlan = await agent.run(
            text=text,
            category=category,
            severity=severity,
            customer_context=customer_context,
            evidence=evidence,
            diagnosis=diagnosis,
            ticket_id=ticket_id,
            _mock_customer_reply=mock_reply,
        )

        actions_list = [
            a.model_dump() if hasattr(a, "model_dump") else a for a in plan.actions
        ]

        return {
            "resolution_plan": plan.model_dump(),
            "proposed_reply": plan.customer_reply,
            "resolution_actions": actions_list,
            "approval_required": plan.requires_approval,
            "current_node": NODE_RESOLUTION_PLANNING,
            "completed_nodes": [NODE_RESOLUTION_PLANNING],
            "token_usage": {
                "prompt_tokens": 180,
                "completion_tokens": 80,
                "total_tokens": 260,
            },
        }
    except Exception as exc:
        logger.exception("Failed during resolution_planning execution")
        fallback_plan = {
            "summary": "Automated resolution planning encountered an issue; applied default response.",
            "customer_reply": (
                "Thank you for contacting CloudDesk support. We have received your request "
                "and our engineering team is reviewing it."
            ),
            "internal_notes": f"Fallback resolution plan generated due to error: {exc}",
            "actions": [
                {
                    "tool_name": "update_ticket",
                    "arguments": {"status": "in_progress"},
                    "requires_approval": False,
                }
            ],
            "requires_approval": False,
            "confidence": 0.50,
        }
        return {
            "resolution_plan": fallback_plan,
            "proposed_reply": fallback_plan["customer_reply"],
            "resolution_actions": fallback_plan["actions"],
            "approval_required": False,
            "current_node": NODE_RESOLUTION_PLANNING,
            "completed_nodes": [NODE_RESOLUTION_PLANNING],
            "errors": [f"resolution_planning_error: {exc}"],
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }


async def risk_check(state: SupportState) -> dict[str, Any]:
    """Execute risk assessment and governance node (US-010, US-012, AC-035, AC-043 to AC-045).

    1. Evaluates ticket against deterministic policy escalation rules and prompt injection.
    2. Inspects resolution plan for consequential actions requiring human approval.
    3. Assesses execution risk level (high / low).
    4. Constructs approval_request payload when consequential actions are scheduled.
    5. Returns partial state dict updating risk_level, escalation_required, approval_required,
       approval_status, and completed_nodes.
    """
    raw_text = state.get("text") or state.get("subject") or ""
    text = str(raw_text)[:MAX_PAYLOAD_LENGTH]
    category = state.get("category")
    severity = state.get("severity")
    customer_ctx = state.get("customer_context")
    plan_dict = state.get("resolution_plan") or {}
    ticket_id = state.get("ticket_id") or ""
    workflow_id = state.get("workflow_id")
    state_approval_req = bool(state.get("approval_required"))
    incident_detected = bool(state.get("incident_detected"))

    try:
        # 1. Prompt injection detection (N4, CD-1013)
        injection_scan = scan_for_injection(text)
        injection_detected = injection_scan.is_suspicious

        # 2. Output validation check
        proposed_reply = state.get("proposed_reply") or plan_dict.get(
            "customer_reply", ""
        )
        cust_id = state.get("customer_id")
        output_val = validate_customer_output(
            proposed_reply, current_customer_id=cust_id
        )
        output_validation_failed = not output_val.is_valid

        # 3. Policy escalation evaluation (AC-043, AC-044)
        escalation_agent = EscalationAgent()
        escalation_decision: EscalationDecision = await escalation_agent.evaluate(
            text=text,
            category=category,
            severity=severity,
            customer_context=customer_ctx,
            is_active_outage=incident_detected,
            plan_name=state.get("customer_plan"),
        )

        escalation_required = bool(escalation_decision.escalation_required)
        if injection_detected:
            escalation_required = True
            escalation_decision.target_team = "Security"
            escalation_decision.reason = (
                "Prompt injection payload detected; routed to Security team."
            )

        # 4. Planned actions inspection for approval gating (AC-035, AC-038)
        actions = plan_dict.get("actions", [])
        plan_approval_req = bool(plan_dict.get("requires_approval"))
        action_approval_req = any(bool(a.get("requires_approval")) for a in actions)
        approval_required = (
            state_approval_req or plan_approval_req or action_approval_req
        )

        # 5. Composite risk assessment (CLAUDE.md §7.3)
        matched_rules = matching_escalation_rules(
            text=text,
            category=category,
            customer_plan=state.get("customer_plan"),
        )
        raw_risk = assess_risk(
            plan=plan_dict,
            matched_rules=matched_rules,
            severity=severity,
            injection_detected=injection_detected,
            output_validation_failed=output_validation_failed,
        )

        # Escalation, approval requirement, critical severity, or incident elevate risk to high
        if (
            escalation_required
            or approval_required
            or (severity == SeverityEnum.CRITICAL.value)
            or incident_detected
        ):
            risk_level = "high"
        else:
            risk_level = raw_risk

        # 6. Build structured approval_request if approval is needed (and not escalating)
        approval_request: dict[str, Any] | None = None
        if approval_required and not escalation_required:
            target_tool = "consequential_action"
            target_args: dict[str, Any] = {}
            target_reason = (
                "Action requires supervisor approval under safety policy (AC-035)."
            )

            # Find specific approval-gated action
            for act in actions:
                if act.get("requires_approval") or act.get("tool_name") in (
                    "create_refund_request",
                    "reset_demo_setting",
                ):
                    target_tool = act.get("tool_name") or act.get("tool", target_tool)
                    target_args = act.get("arguments", {})
                    target_reason = act.get("reason", target_reason)
                    break

            approval_request = {
                "ticket_id": ticket_id,
                "workflow_id": workflow_id,
                "tool_name": target_tool,
                "arguments": target_args,
                "reason": target_reason,
                "status": "pending",
            }

        approval_status = (
            "pending" if (approval_required and not escalation_required) else None
        )

        return {
            "risk_level": risk_level,
            "risk_assessment": {
                "level": risk_level,
                "escalation_required": escalation_required,
                "approval_required": approval_required,
                "injection_detected": injection_detected,
                "output_validation_failed": output_validation_failed,
            },
            "escalation_required": escalation_required,
            "escalation": escalation_decision.model_dump()
            if escalation_required
            else None,
            "escalation_team": escalation_decision.target_team
            if escalation_required
            else None,
            "escalation_reason": escalation_decision.reason
            if escalation_required
            else None,
            "escalation_rule_id": escalation_decision.rule_id
            if escalation_required
            else None,
            "approval_required": approval_required,
            "approval_status": approval_status,
            "approval_request": approval_request,
            "current_node": NODE_RISK_CHECK,
            "completed_nodes": [NODE_RISK_CHECK],
            "token_usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
            },
        }
    except Exception as exc:
        logger.exception("Failed during risk_check execution")
        return {
            "risk_level": "high",
            "risk_assessment": {"level": "high", "error": str(exc)},
            "escalation_required": True,
            "escalation_team": "Engineering",
            "escalation_reason": f"Risk evaluation encountered error: {exc}",
            "approval_required": False,
            "approval_status": None,
            "approval_request": None,
            "current_node": NODE_RISK_CHECK,
            "completed_nodes": [NODE_RISK_CHECK],
            "errors": [f"risk_check_error: {exc}"],
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }


def route_after_risk_check(state: SupportState) -> str:
    """Determine downstream branch target from risk_check evaluation (CLAUDE.md §7.3).

    Priority:
    1. If escalation is required -> ROUTE_ESCALATION ("escalation")
    2. Else if human approval is required -> ROUTE_HUMAN_APPROVAL ("human_approval")
    3. Else low risk -> ROUTE_EXECUTE_RESOLUTION ("execute_resolution")
    """
    if state.get("escalation_required"):
        return ROUTE_ESCALATION
    if state.get("approval_required"):
        return ROUTE_HUMAN_APPROVAL
    return ROUTE_EXECUTE_RESOLUTION


async def memory_update(state: SupportState) -> dict[str, Any]:
    """Execute customer memory update node (F11, AC-050, AC-051).

    Persists past_issue, first 3 troubleshooting steps, and resolution summary
    into customer long-term memory.
    """
    customer_id = state.get("customer_id")
    past_issue = state.get("subject") or state.get("text") or ""
    troubleshooting_steps = state.get("troubleshooting_steps") or []
    resolution_note = state.get("ticket_summary") or state.get("proposed_reply") or ""
    session = state.get("session") or state.get("_session")

    try:
        if customer_id and customer_id.strip():
            await record_resolution(
                customer_id=customer_id.strip(),
                past_issue=past_issue,
                troubleshooting_steps=troubleshooting_steps,
                resolution_note=resolution_note,
                session=session,
            )

        return {
            "current_node": NODE_MEMORY_UPDATE,
            "completed_nodes": [NODE_MEMORY_UPDATE],
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
    except Exception as exc:
        logger.exception("Failed during memory_update execution")
        return {
            "current_node": NODE_MEMORY_UPDATE,
            "completed_nodes": [NODE_MEMORY_UPDATE],
            "errors": [f"memory_update_error: {exc}"],
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }


__all__ = [
    "NODE_MEMORY_UPDATE",
    "NODE_RESOLUTION_PLANNING",
    "NODE_RISK_CHECK",
    "ROUTE_ESCALATION",
    "ROUTE_EXECUTE_RESOLUTION",
    "ROUTE_HUMAN_APPROVAL",
    "memory_update",
    "resolution_planning",
    "risk_check",
    "route_after_risk_check",
]
