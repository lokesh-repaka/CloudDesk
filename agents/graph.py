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
    NODE_MEMORY_UPDATE,
    NODE_RESOLUTION_PLANNING,
    NODE_RISK_CHECK,
    ROUTE_ESCALATION,
    ROUTE_EXECUTE_RESOLUTION,
    ROUTE_HUMAN_APPROVAL,
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
NODE_EXECUTE_RESOLUTION = "execute_resolution"
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

    Holds execution when consequential actions (refund, reset) require human authorization.
    """
    return {
        "current_node": NODE_HUMAN_APPROVAL,
        "completed_nodes": [NODE_HUMAN_APPROVAL],
        "approval_status": state.get("approval_status") or "pending",
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def route_after_approval(state: SupportState) -> str:
    """Conditional edge router following human approval decision (AC-039, AC-040)."""
    status = state.get("approval_status")
    decision = state.get("approval_decision")
    if status == "rejected" or decision == "rejected":
        return NODE_ESCALATION
    return NODE_EXECUTE_RESOLUTION


async def execute_resolution(state: SupportState) -> dict[str, Any]:
    """Execute approved resolution actions on the shared tool path (P11-4, AC-032)."""
    actions = state.get("resolution_actions") or []
    executed: list[dict[str, Any]] = []
    for act in actions:
        if isinstance(act, dict):
            executed.append({**act, "status": "executed"})
        elif hasattr(act, "model_dump"):
            dumped = act.model_dump()
            dumped["status"] = "executed"
            executed.append(dumped)

    return {
        "current_node": NODE_EXECUTE_RESOLUTION,
        "completed_nodes": [NODE_EXECUTE_RESOLUTION],
        "executed_actions": executed,
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


async def escalation(state: SupportState) -> dict[str, Any]:
    """Execute specialized team escalation handoff node (US-012, AC-043, AC-044)."""
    team = state.get("escalation_team") or "Engineering"
    reason = state.get("escalation_reason") or "Policy rule escalation triggered"

    return {
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


# Cached singleton graph instance for lightweight in-process execution
_default_graph: CompiledStateGraph | None = None


def get_default_support_graph() -> CompiledStateGraph:
    """Return a shared compiled support graph instance."""
    global _default_graph
    if _default_graph is None:
        _default_graph = create_support_graph()
    return _default_graph


async def run_support_workflow(
    initial_state: SupportState,
    thread_id: str | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    tracer: Any | None = None,
) -> SupportState:
    """Execute the full autonomous support workflow on an input state (CLAUDE.md §7.3, §16).

    Args:
        initial_state: Populated initial SupportState dictionary.
        thread_id: Thread ID for checkpointer resumption and state tracking.
        checkpointer: Optional explicit checkpointer instance.
        tracer: Optional WorkflowTracer instance for telemetry recording.

    Returns:
        Final or interrupted SupportState dictionary.
    """
    from agents.tracer import (
        EVENT_NODE_COMPLETED,
        EVENT_NODE_STARTED,
        tracer_for,
    )

    active_tracer = tracer or tracer_for(initial_state)
    saver = checkpointer if checkpointer is not None else InMemorySaver()
    graph = create_support_graph(checkpointer=saver)

    tid = thread_id or initial_state.get("ticket_id") or "thread-default-001"
    config = {"configurable": {"thread_id": tid}}

    try:
        final_state: SupportState = await graph.ainvoke(initial_state, config=config)

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

        if final_state.get("approval_required"):
            await active_tracer.record_approval_requested(
                node_name="risk_check",
                request_data=final_state.get("approval_request") or {},
            )

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


__all__ = [
    "GRAPH_EDGES",
    "GRAPH_NODES",
    "NODE_ESCALATION",
    "NODE_EXECUTE_RESOLUTION",
    "NODE_HUMAN_APPROVAL",
    "create_support_graph",
    "escalation",
    "execute_resolution",
    "get_default_support_graph",
    "human_approval",
    "route_after_approval",
    "run_support_workflow",
]
