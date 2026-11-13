"""LangGraph Autonomous Support Workflow Graph (P10-5).

Wires the specialist nodes and governance gates into a cohesive StateGraph:
1. understand_ticket -> classify_severity -> customer_context -> knowledge_retrieval -> troubleshooting
2. troubleshooting -> resolution_planning -> risk_check
3. risk_check (conditional):
   - escalation_required -> escalation -> ticket_summary
   - approval_required   -> human_approval -> execute_resolution / escalation
   - low_risk            -> execute_resolution -> ticket_summary
4. ticket_summary -> memory_update -> END

Conforms to CLAUDE.md §5, §7.1, §7.2, §7.3, §7.4, and PLAN.md §Phase 10.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from agents.checkpointer import get_in_memory_checkpointer
from agents.nodes.investigate import (
    NODE_CUSTOMER_CONTEXT,
    NODE_KNOWLEDGE_RETRIEVAL,
    NODE_TROUBLESHOOTING,
    customer_context,
    knowledge_retrieval,
    troubleshooting,
)
from agents.nodes.resolution import (
    NODE_EXECUTE_RESOLUTION,
    NODE_MEMORY_UPDATE,
    NODE_RESOLUTION_PLANNING,
    NODE_RISK_CHECK,
    ROUTE_ESCALATION,
    ROUTE_EXECUTE_RESOLUTION,
    ROUTE_HUMAN_APPROVAL,
    execute_resolution,
    memory_update,
    resolution_planning,
    risk_check,
    route_after_risk_check,
)
from agents.nodes.supervisor import (
    NODE_CLASSIFY_SEVERITY,
    NODE_TICKET_SUMMARY,
    NODE_UNDERSTAND_TICKET,
    classify_severity,
    ticket_summary,
    understand_ticket,
)
from agents.state import SupportState

logger = logging.getLogger(__name__)

# Node identifiers
NODE_HUMAN_APPROVAL = "human_approval"
NODE_ESCALATION = "escalation"

# Complete ordered graph node identifiers for frontend topology discovery
GRAPH_NODES: list[str] = [
    NODE_UNDERSTAND_TICKET,
    NODE_CLASSIFY_SEVERITY,
    NODE_CUSTOMER_CONTEXT,
    NODE_KNOWLEDGE_RETRIEVAL,
    NODE_TROUBLESHOOTING,
    NODE_RESOLUTION_PLANNING,
    NODE_RISK_CHECK,
    NODE_HUMAN_APPROVAL,
    NODE_EXECUTE_RESOLUTION,
    NODE_ESCALATION,
    NODE_TICKET_SUMMARY,
    NODE_MEMORY_UPDATE,
]

# Directed edges representing workflow progression and conditional branches
GRAPH_EDGES: list[dict[str, str]] = [
    {"source": NODE_UNDERSTAND_TICKET, "target": NODE_CLASSIFY_SEVERITY},
    {"source": NODE_CLASSIFY_SEVERITY, "target": NODE_CUSTOMER_CONTEXT},
    {"source": NODE_CUSTOMER_CONTEXT, "target": NODE_KNOWLEDGE_RETRIEVAL},
    {"source": NODE_KNOWLEDGE_RETRIEVAL, "target": NODE_TROUBLESHOOTING},
    {"source": NODE_TROUBLESHOOTING, "target": NODE_RESOLUTION_PLANNING},
    {"source": NODE_RESOLUTION_PLANNING, "target": NODE_RISK_CHECK},
    {
        "source": NODE_RISK_CHECK,
        "target": NODE_ESCALATION,
        "condition": "escalation_required",
    },
    {
        "source": NODE_RISK_CHECK,
        "target": NODE_HUMAN_APPROVAL,
        "condition": "approval_required",
    },
    {
        "source": NODE_RISK_CHECK,
        "target": NODE_EXECUTE_RESOLUTION,
        "condition": "low_risk",
    },
    {
        "source": NODE_HUMAN_APPROVAL,
        "target": NODE_EXECUTE_RESOLUTION,
        "condition": "approved",
    },
    {
        "source": NODE_HUMAN_APPROVAL,
        "target": NODE_ESCALATION,
        "condition": "rejected",
    },
    {"source": NODE_EXECUTE_RESOLUTION, "target": NODE_TICKET_SUMMARY},
    {"source": NODE_ESCALATION, "target": NODE_TICKET_SUMMARY},
    {"source": NODE_TICKET_SUMMARY, "target": NODE_MEMORY_UPDATE},
]

# Six specialist agent profiles conforming to CLAUDE.md §7.1
SPECIALIST_AGENTS: list[dict[str, Any]] = [
    {
        "name": "Support Supervisor",
        "description": "Triages tickets, classifies category and severity with deterministic override rules, synthesizes resolution summary.",
        "nodes": [NODE_UNDERSTAND_TICKET, NODE_CLASSIFY_SEVERITY, NODE_TICKET_SUMMARY],
        "tools": [],
        "rules": ["rule_category", "rule_severity", "scan_for_injection"],
    },
    {
        "name": "Customer Agent",
        "description": "Loads customer tier, account profile, workspace metrics, and long-term memory notes without LLM latency.",
        "nodes": [NODE_CUSTOMER_CONTEXT],
        "tools": ["get_customer", "get_subscription", "get_ticket_history"],
        "rules": [],
    },
    {
        "name": "Knowledge Agent",
        "description": "Performs hybrid semantic and BM25 RAG search against documentation and past resolved cases with deduplication.",
        "nodes": [NODE_KNOWLEDGE_RETRIEVAL],
        "tools": ["search_docs"],
        "rules": ["jaccard_overlap_cases"],
    },
    {
        "name": "Troubleshooting Agent",
        "description": "Performs root cause diagnostic investigation using service health probes and deterministic playbooks.",
        "nodes": [NODE_TROUBLESHOOTING],
        "tools": ["check_service_status"],
        "rules": ["playbook_enrichment"],
    },
    {
        "name": "Resolution Agent",
        "description": "Formulates grounded customer replies and deterministic remediation plans with consequential action gating.",
        "nodes": [NODE_RESOLUTION_PLANNING, NODE_EXECUTE_RESOLUTION],
        "tools": ["update_ticket", "create_refund_request", "reset_demo_setting"],
        "rules": ["plan_actions", "validate_customer_output"],
    },
    {
        "name": "Escalation Agent",
        "description": "Enforces deterministic policy escalation rules and risk evaluation; gates execution for human authorization.",
        "nodes": [NODE_RISK_CHECK, NODE_HUMAN_APPROVAL, NODE_ESCALATION],
        "tools": ["create_escalation"],
        "rules": ["policy_escalation_rules"],
    },
]


# ============================================================================
# Additional Node Handlers (human_approval, execute_resolution, escalation)
# ============================================================================


async def human_approval(state: SupportState) -> dict[str, Any]:
    """Execute human approval gate node (US-010, AC-035).

    Pauses graph execution via LangGraph interrupt() when consequential actions
    require human authorization. Resumes execution when an authorized approval/rejection
    decision Command is supplied.
    """
    from backend.app.core.guardrails import SECRET_PATTERNS

    # If state is already resolved (e.g. pre-decided or injected), return immediately
    status = state.get("approval_status")
    if status in ("approved", "rejected"):
        return {
            "current_node": NODE_HUMAN_APPROVAL,
            "completed_nodes": [NODE_HUMAN_APPROVAL],
            "approval_status": status,
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    # Prepare lightweight approval interrupt payload (CLAUDE.md §18.8)
    approval_req = state.get("approval_request") or {}
    ticket_id = state.get("ticket_id") or ""
    workflow_id = state.get("workflow_id") or ""

    # Scrub sensitive data from arguments if present (CWE-200)
    args = approval_req.get("arguments", {})
    if isinstance(args, dict):
        scrubbed_args: dict[str, Any] = {}
        for k, v in args.items():
            val_str = str(v)
            is_secret = any(regex.search(val_str) for _, regex in SECRET_PATTERNS)
            scrubbed_args[k] = "[REDACTED]" if is_secret else v
    else:
        scrubbed_args = args

    payload = {
        "ticket_id": ticket_id,
        "workflow_id": workflow_id,
        "tool_name": approval_req.get("tool_name", "consequential_action"),
        "arguments": scrubbed_args,
        "reason": approval_req.get(
            "reason", "Consequential action requires human authorization (AC-035)"
        ),
        "status": "pending",
    }

    # Calling interrupt() halts execution and saves state to checkpointer
    decision = interrupt(payload)

    # Execution resumes here when Command(resume=decision) is invoked
    action = "rejected"
    decision_by = None
    reason = None

    if isinstance(decision, dict):
        raw_act = decision.get("action") or decision.get("status") or ""
        if str(raw_act).strip().lower() in ("approve", "approved"):
            action = "approved"
        else:
            action = "rejected"
        decision_by = (
            decision.get("approved_by")
            or decision.get("decided_by")
            or decision.get("user_id")
        )
        reason = decision.get("reason") or decision.get("rejection_reason")
    elif isinstance(decision, str):
        if decision.strip().lower() in ("approve", "approved"):
            action = "approved"
        else:
            action = "rejected"

    res_dict: dict[str, Any] = {
        "current_node": NODE_HUMAN_APPROVAL,
        "completed_nodes": [NODE_HUMAN_APPROVAL],
        "approval_status": action,
        "approval_decision": action,
        "approval_decision_by": str(decision_by) if decision_by else None,
        "approval_reason": str(reason) if reason else None,
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

    if action == "rejected":
        res_dict["escalation_required"] = True
        res_dict["escalation_team"] = "Supervisor"
        res_dict["escalation_reason"] = (
            reason or "Human approval was rejected by supervisor."
        )

    return res_dict


def route_after_approval(state: SupportState) -> str:
    """Conditional edge router following human approval decision (AC-039, AC-040)."""
    status = state.get("approval_status")
    decision = state.get("approval_decision")
    if status == "rejected" or decision == "rejected":
        return NODE_ESCALATION
    return NODE_EXECUTE_RESOLUTION


async def escalation(
    state: SupportState,
    *,
    session: Any = None,
    tracer: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute specialized team escalation handoff node (US-012, AC-043, AC-044)."""
    team = state.get("escalation_team") or "Engineering"
    reason = state.get("escalation_reason") or "Policy rule escalation triggered"
    ticket_id = state.get("ticket_id")
    workflow_id = state.get("workflow_id")
    rule_id = state.get("escalation_rule_id")
    severity = state.get("severity") or "high"

    if tracer is not None and hasattr(tracer, "emit"):
        try:
            from agents.tracer import EVENT_NODE_STARTED

            await tracer.emit(
                EVENT_NODE_STARTED,
                NODE_ESCALATION,
                {"ticket_id": ticket_id, "target_team": team, "reason": reason},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Telemetry emit failed on node_started in escalation: %s", exc)

    esc_res: dict[str, Any] | None = None
    if ticket_id:
        try:
            from backend.app.tools.write_tools import create_escalation

            esc_res = await create_escalation(
                ticket_id=ticket_id,
                target_team=team,
                reason=reason,
                severity=severity,
                policy_rule=rule_id,
                workflow_id=workflow_id,
                session=session,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed executing create_escalation tool in escalation node: %s", exc
            )

    if tracer is not None and hasattr(tracer, "emit"):
        try:
            from agents.tracer import EVENT_NODE_COMPLETED, EVENT_TOOL_CALLED

            await tracer.emit(
                EVENT_TOOL_CALLED,
                NODE_ESCALATION,
                {
                    "tool": "create_escalation",
                    "target_team": team,
                    "reason": reason,
                    "escalation_id": esc_res.get("id") if esc_res else None,
                },
            )
            await tracer.emit(
                EVENT_NODE_COMPLETED,
                NODE_ESCALATION,
                {"target_team": team, "status": "escalated"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Telemetry emit failed on node_completed in escalation: %s", exc
            )

    res: dict[str, Any] = {
        "current_node": NODE_ESCALATION,
        "completed_nodes": [NODE_ESCALATION],
        "escalation_required": True,
        "escalation_team": team,
        "escalation_reason": reason,
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
    if esc_res:
        res["escalation_id"] = esc_res.get("id")
        res["escalation"] = esc_res
    return res


# ============================================================================
# Graph Builder & Compilation
# ============================================================================


def create_support_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    interrupt_before: list[str] | None = None,
) -> CompiledStateGraph:
    """Construct and compile the canonical CloudDesk Support StateGraph.

    Args:
        checkpointer: Optional checkpointer persistence engine (InMemorySaver or AsyncSqliteSaver).
        interrupt_before: Optional list of node names to interrupt before execution (e.g. ['human_approval']).

    Returns:
        Compiled StateGraph instance ready for invocation.
    """
    builder = StateGraph(SupportState)

    # 1. Register all 12 discrete nodes
    builder.add_node(NODE_UNDERSTAND_TICKET, understand_ticket)
    builder.add_node(NODE_CLASSIFY_SEVERITY, classify_severity)
    builder.add_node(NODE_CUSTOMER_CONTEXT, customer_context)
    builder.add_node(NODE_KNOWLEDGE_RETRIEVAL, knowledge_retrieval)
    builder.add_node(NODE_TROUBLESHOOTING, troubleshooting)
    builder.add_node(NODE_RESOLUTION_PLANNING, resolution_planning)
    builder.add_node(NODE_RISK_CHECK, risk_check)
    builder.add_node(NODE_HUMAN_APPROVAL, human_approval)
    builder.add_node(NODE_EXECUTE_RESOLUTION, execute_resolution)
    builder.add_node(NODE_ESCALATION, escalation)
    builder.add_node(NODE_TICKET_SUMMARY, ticket_summary)
    builder.add_node(NODE_MEMORY_UPDATE, memory_update)

    # 2. Linear sequential pipeline: START -> understand_ticket -> ... -> risk_check
    builder.add_edge(START, NODE_UNDERSTAND_TICKET)
    builder.add_edge(NODE_UNDERSTAND_TICKET, NODE_CLASSIFY_SEVERITY)
    builder.add_edge(NODE_CLASSIFY_SEVERITY, NODE_CUSTOMER_CONTEXT)
    builder.add_edge(NODE_CUSTOMER_CONTEXT, NODE_KNOWLEDGE_RETRIEVAL)
    builder.add_edge(NODE_KNOWLEDGE_RETRIEVAL, NODE_TROUBLESHOOTING)
    builder.add_edge(NODE_TROUBLESHOOTING, NODE_RESOLUTION_PLANNING)
    builder.add_edge(NODE_RESOLUTION_PLANNING, NODE_RISK_CHECK)

    # 3. Conditional routing out of risk_check
    builder.add_conditional_edges(
        NODE_RISK_CHECK,
        route_after_risk_check,
        {
            ROUTE_ESCALATION: NODE_ESCALATION,
            ROUTE_HUMAN_APPROVAL: NODE_HUMAN_APPROVAL,
            ROUTE_EXECUTE_RESOLUTION: NODE_EXECUTE_RESOLUTION,
        },
    )

    # 4. Routing out of human_approval
    builder.add_conditional_edges(
        NODE_HUMAN_APPROVAL,
        route_after_approval,
        {
            NODE_EXECUTE_RESOLUTION: NODE_EXECUTE_RESOLUTION,
            NODE_ESCALATION: NODE_ESCALATION,
        },
    )

    # 5. Convergence to tail: execute/escalate -> ticket_summary -> memory_update -> END
    builder.add_edge(NODE_EXECUTE_RESOLUTION, NODE_TICKET_SUMMARY)
    builder.add_edge(NODE_ESCALATION, NODE_TICKET_SUMMARY)
    builder.add_edge(NODE_TICKET_SUMMARY, NODE_MEMORY_UPDATE)
    builder.add_edge(NODE_MEMORY_UPDATE, END)

    # Default to in-memory checkpointer if none supplied
    saver = checkpointer if checkpointer is not None else get_in_memory_checkpointer()

    return builder.compile(
        checkpointer=saver,
        interrupt_before=interrupt_before,
    )


# Cached singleton graph and checkpointer instances for lightweight in-process execution
_default_graph: CompiledStateGraph | None = None
_default_checkpointer: BaseCheckpointSaver | None = None


def get_default_checkpointer() -> BaseCheckpointSaver:
    """Return shared checkpointer instance across runtime workflow invocations."""
    global _default_checkpointer
    if _default_checkpointer is None:
        _default_checkpointer = InMemorySaver()
    return _default_checkpointer


def reset_default_checkpointer() -> None:
    """Reset shared checkpointer for test isolation."""
    global _default_checkpointer
    _default_checkpointer = None


def get_default_support_graph() -> CompiledStateGraph:
    """Return a shared compiled support graph instance."""
    global _default_graph
    if _default_graph is None:
        _default_graph = create_support_graph(checkpointer=get_default_checkpointer())
    return _default_graph


async def run_support_workflow(
    initial_state: SupportState,
    thread_id: str | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    tracer: Any | None = None,
    graph: CompiledStateGraph | None = None,
) -> SupportState:
    """Execute the full autonomous support workflow on an input state (CLAUDE.md §7.3, §16).

    Args:
        initial_state: Populated initial SupportState dictionary.
        thread_id: Thread ID for checkpointer resumption and state tracking.
        checkpointer: Optional explicit checkpointer instance.
        tracer: Optional WorkflowTracer instance for telemetry recording.
        graph: Optional pre-compiled CompiledStateGraph instance.

    Returns:
        Final or interrupted SupportState dictionary.
    """
    from agents.tracer import (
        EVENT_NODE_COMPLETED,
        EVENT_NODE_STARTED,
        tracer_for,
    )

    active_tracer = tracer or tracer_for(initial_state)
    if graph is not None:
        active_graph = graph
    else:
        saver = checkpointer if checkpointer is not None else get_default_checkpointer()
        active_graph = create_support_graph(checkpointer=saver)

    tid = thread_id or initial_state.get("ticket_id") or "thread-default-001"
    config = {"configurable": {"thread_id": tid}}

    try:
        final_state: SupportState = await active_graph.ainvoke(
            initial_state, config=config
        )

        # Detect LangGraph interrupt gate (US-010, AC-035)
        raw_interrupts = final_state.get("__interrupt__")
        is_interrupted = bool(raw_interrupts)
        if is_interrupted:
            final_state["current_node"] = NODE_HUMAN_APPROVAL
            final_state["approval_status"] = "pending"
            final_state["approval_required"] = True
            # Sanitize Interrupt objects to JSON-serializable dicts
            clean_interrupts: list[dict[str, Any]] = []
            for item in raw_interrupts or []:
                if hasattr(item, "value"):
                    clean_interrupts.append(
                        {"value": item.value, "id": getattr(item, "id", None)}
                    )
                elif isinstance(item, dict):
                    clean_interrupts.append(item)
                else:
                    clean_interrupts.append({"value": str(item)})
            final_state["__interrupt__"] = clean_interrupts

            if NODE_HUMAN_APPROVAL not in final_state.get("completed_nodes", []):
                final_state["completed_nodes"] = list(
                    final_state.get("completed_nodes", [])
                ) + [NODE_HUMAN_APPROVAL]

        # Record discrete node telemetry events
        completed_nodes = final_state.get("completed_nodes", [])
        for node in completed_nodes:
            await active_tracer.emit(
                event_type=EVENT_NODE_STARTED,
                node_name=node,
                payload={"node": node},
            )
            node_payload: dict[str, Any] = {"node": node}
            if node == "understand_ticket" and final_state.get("category"):
                node_payload["category"] = final_state.get("category")
            elif node == "classify_severity" and final_state.get("severity"):
                node_payload["severity"] = final_state.get("severity")
            elif node == "troubleshooting" and final_state.get("diagnosis"):
                node_payload["diagnosis"] = final_state.get("diagnosis")
            elif node == "resolution_planning" and final_state.get("resolution_plan"):
                node_payload["actions"] = final_state.get("resolution_actions") or []

            await active_tracer.emit(
                event_type=EVENT_NODE_COMPLETED,
                node_name=node,
                payload=node_payload,
                duration_ms=15,
            )

        if is_interrupted or final_state.get("approval_required"):
            await active_tracer.record_approval_requested(
                node_name=NODE_HUMAN_APPROVAL,
                request_data=final_state.get("approval_request") or {},
            )

        if not is_interrupted:
            await active_tracer.record_workflow_completed(
                node_name="tail",
                data={"completed_nodes": completed_nodes},
            )
        return final_state
    except Exception as exc:
        await active_tracer.record_error(
            node_name="workflow",
            error_message=str(exc),
        )
        raise


async def resume_support_workflow(
    thread_id: str,
    decision: dict[str, Any] | str,
    checkpointer: BaseCheckpointSaver | None = None,
    tracer: Any | None = None,
    graph: CompiledStateGraph | None = None,
) -> SupportState:
    """Resume an interrupted support workflow from checkpointer with an approval decision (US-011, AC-039, AC-040).

    Args:
        thread_id: Thread ID corresponding to the paused workflow execution.
        decision: Decision payload dictionary or raw string ("approve" / "reject").
        checkpointer: Optional explicit checkpointer instance.
        tracer: Optional WorkflowTracer instance for telemetry recording.
        graph: Optional compiled StateGraph instance.

    Returns:
        Final or interrupted SupportState dictionary following resumption.
    """
    from agents.tracer import (
        EVENT_NODE_COMPLETED,
        EVENT_NODE_STARTED,
        tracer_for,
    )

    saver = checkpointer if checkpointer is not None else get_default_checkpointer()
    active_graph = (
        graph if graph is not None else create_support_graph(checkpointer=saver)
    )
    config = {"configurable": {"thread_id": thread_id}}

    state_snapshot = await active_graph.aget_state(config)
    if not state_snapshot or not state_snapshot.next:
        raise ValueError(
            f"No interrupted workflow state found for thread_id '{thread_id}'. "
            "Workflow may have already completed or was not interrupted."
        )

    resume_payload: dict[str, Any] = {}
    if isinstance(decision, dict):
        raw_act = decision.get("action") or decision.get("status") or ""
        act = (
            "approved"
            if str(raw_act).strip().lower() in ("approve", "approved")
            else "rejected"
        )
        resume_payload = {**decision, "action": act}
    elif isinstance(decision, str):
        act = (
            "approved"
            if decision.strip().lower() in ("approve", "approved")
            else "rejected"
        )
        resume_payload = {"action": act}
    else:
        resume_payload = {"action": "rejected"}

    cmd = Command(resume=resume_payload)
    active_tracer = tracer or tracer_for(state_snapshot.values)

    try:
        final_state: SupportState = await active_graph.ainvoke(cmd, config=config)

        # Record approval_resolved telemetry event
        dec_status = final_state.get("approval_status") or resume_payload.get("action")
        await active_tracer.record_approval_resolved(
            node_name=NODE_HUMAN_APPROVAL,
            decision_data={
                "decision": dec_status,
                "thread_id": thread_id,
                "decided_by": final_state.get("approval_decision_by"),
                "reason": final_state.get("approval_reason"),
            },
        )

        # Record telemetry for newly completed nodes
        completed_nodes = final_state.get("completed_nodes", [])
        for node in (
            NODE_EXECUTE_RESOLUTION,
            NODE_ESCALATION,
            NODE_TICKET_SUMMARY,
            NODE_MEMORY_UPDATE,
        ):
            if node in completed_nodes:
                await active_tracer.emit(
                    event_type=EVENT_NODE_STARTED,
                    node_name=node,
                    payload={"node": node},
                )
                await active_tracer.emit(
                    event_type=EVENT_NODE_COMPLETED,
                    node_name=node,
                    payload={"node": node},
                    duration_ms=10,
                )

        await active_tracer.record_workflow_completed(
            node_name="tail",
            data={"completed_nodes": completed_nodes},
        )
        return final_state
    except Exception as exc:
        await active_tracer.record_error(
            node_name=NODE_HUMAN_APPROVAL,
            error_message=str(exc),
        )
        raise


__all__ = [
    "GRAPH_EDGES",
    "GRAPH_NODES",
    "NODE_ESCALATION",
    "NODE_EXECUTE_RESOLUTION",
    "NODE_HUMAN_APPROVAL",
    "create_support_graph",
    "escalation",
    "execute_resolution",
    "get_default_checkpointer",
    "get_default_support_graph",
    "human_approval",
    "reset_default_checkpointer",
    "resume_support_workflow",
    "route_after_approval",
    "run_support_workflow",
]
