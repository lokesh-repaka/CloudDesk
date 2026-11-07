"""Unit, integration, and security tests for SupportState and Checkpointer (P10-1).

Verifies the state definition, channel reducers, initial state factory,
in-memory and SQLite checkpointers, LangGraph partial updates, and thread resumption in accordance with:
CLAUDE.md §7.3, §14, US-010 (AC-036), US-016, and PLAN.md §Phase 10.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from agents.checkpointer import (
    get_checkpointer,
    get_in_memory_checkpointer,
    get_sqlite_checkpointer,
    resolve_checkpointer_path,
)
from agents.state import (
    SupportState,
    append_list,
    create_initial_support_state,
    merge_usage,
)
from backend.app.core.guardrails import SECRET_PATTERNS

# ============================================================================
# 1. State Schema & Reducer Tests (CLAUDE.md §7.3)
# ============================================================================


def test_append_list_reducer():
    """Verify append_list reducer handles None, empty, and sequential items."""
    assert append_list(None, ["node_1"]) == ["node_1"]
    assert append_list(["node_1"], ["node_2"]) == ["node_1", "node_2"]
    assert append_list(["node_1"], None) == ["node_1"]
    assert append_list([], ["node_1"]) == ["node_1"]
    assert append_list(["node_1"], []) == ["node_1"]


def test_merge_usage_reducer():
    """Verify merge_usage reducer sums token usage metrics across nodes."""
    usage_1 = {"prompt_tokens": 100, "completion_tokens": 25, "total_tokens": 125}
    usage_2 = {"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200}

    merged = merge_usage(usage_1, usage_2)
    assert merged["prompt_tokens"] == 250
    assert merged["completion_tokens"] == 75
    assert merged["total_tokens"] == 325

    # Safe with None
    assert merge_usage(None, usage_1) == usage_1
    assert merge_usage(usage_1, None) == usage_1
    assert merge_usage(None, None) == {}


def test_create_initial_support_state_defaults():
    """Verify create_initial_support_state sets expected default values."""
    state = create_initial_support_state(
        ticket_id="CD-1001",
        customer_id="cust-101-acme",
        subject="SSO Authentication failure",
        text="Users receiving SAML timeout error when logging in.",
        customer_plan="enterprise",
        channel="email",
    )

    assert state["ticket_id"] == "CD-1001"
    assert state["customer_id"] == "cust-101-acme"
    assert state["subject"] == "SSO Authentication failure"
    assert state["text"] == "Users receiving SAML timeout error when logging in."
    assert state["customer_plan"] == "enterprise"
    assert state["channel"] == "email"

    # Reducer channels must be initialized to empty collections
    assert state["completed_nodes"] == []
    assert state["errors"] == []
    assert state["token_usage"] == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    # Tracking IDs are populated
    assert state.get("thread_id") is not None
    assert state.get("workflow_id") is not None
    assert state.get("messages") == []


def test_support_state_typed_dict_annotations():
    """Verify SupportState has expected channel annotations."""
    annotations = SupportState.__annotations__

    # Core ticket attributes
    assert "ticket_id" in annotations
    assert "customer_id" in annotations
    assert "subject" in annotations
    assert "text" in annotations
    assert "customer_plan" in annotations
    assert "channel" in annotations

    # Specialist agent outputs
    assert "classification" in annotations
    assert "severity" in annotations
    assert "customer_context" in annotations
    assert "evidence" in annotations
    assert "similar_cases" in annotations
    assert "diagnosis" in annotations
    assert "troubleshooting_steps" in annotations
    assert "resolution_plan" in annotations
    assert "proposed_reply" in annotations
    assert "risk_assessment" in annotations
    assert "risk_level" in annotations

    # Governance & Approval
    assert "approval_required" in annotations
    assert "approval_status" in annotations
    assert "approval_request" in annotations
    assert "escalation_required" in annotations
    assert "escalation" in annotations

    # Reducers
    assert "completed_nodes" in annotations
    assert "errors" in annotations
    assert "token_usage" in annotations


# ============================================================================
# 2. LangGraph StateGraph & Partial State Update Tests
# ============================================================================


@pytest.mark.asyncio
async def test_langgraph_partial_updates_with_support_state():
    """Verify LangGraph nodes return partial dicts that correctly accumulate in SupportState."""
    builder = StateGraph(SupportState)

    async def node_supervisor(state: SupportState) -> dict[str, Any]:
        return {
            "classification": {"category": "login_issue", "confidence": 0.98},
            "completed_nodes": ["understand_ticket"],
            "current_node": "understand_ticket",
            "token_usage": {
                "prompt_tokens": 50,
                "completion_tokens": 20,
                "total_tokens": 70,
            },
        }

    async def node_troubleshoot(state: SupportState) -> dict[str, Any]:
        return {
            "diagnosis": "SAML assertion expired.",
            "troubleshooting_steps": ["1. Check IdP certificate validity."],
            "completed_nodes": ["troubleshooting"],
            "current_node": "troubleshooting",
            "token_usage": {
                "prompt_tokens": 60,
                "completion_tokens": 30,
                "total_tokens": 90,
            },
        }

    async def node_resolution(state: SupportState) -> dict[str, Any]:
        return {
            "proposed_reply": "Please renew your IdP signing certificate.",
            "completed_nodes": ["resolution_planning"],
            "current_node": "resolution_planning",
            "token_usage": {
                "prompt_tokens": 40,
                "completion_tokens": 25,
                "total_tokens": 65,
            },
        }

    builder.add_node("understand_ticket", node_supervisor)
    builder.add_node("troubleshooting", node_troubleshoot)
    builder.add_node("resolution_planning", node_resolution)

    builder.add_edge(START, "understand_ticket")
    builder.add_edge("understand_ticket", "troubleshooting")
    builder.add_edge("troubleshooting", "resolution_planning")
    builder.add_edge("resolution_planning", END)

    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    initial_state = create_initial_support_state(
        ticket_id="CD-1001",
        customer_id="cust-101",
        subject="SSO Down",
        text="Cannot sign in via SAML",
    )

    config = {"configurable": {"thread_id": "thread-test-001"}}
    final_state = await graph.ainvoke(initial_state, config=config)

    # Verify reducers accumulated correctly
    assert final_state["completed_nodes"] == [
        "understand_ticket",
        "troubleshooting",
        "resolution_planning",
    ]
    assert final_state["token_usage"] == {
        "prompt_tokens": 150,
        "completion_tokens": 75,
        "total_tokens": 225,
    }
    assert final_state["classification"]["category"] == "login_issue"
    assert final_state["diagnosis"] == "SAML assertion expired."
    assert final_state["current_node"] == "resolution_planning"


# ============================================================================
# 3. Checkpointer Initialization & Persistence Tests (CLAUDE.md §7.3, AC-036)
# ============================================================================


def test_get_in_memory_checkpointer():
    """Verify get_in_memory_checkpointer returns an InMemorySaver instance."""
    saver = get_in_memory_checkpointer()
    assert isinstance(saver, InMemorySaver)
    assert isinstance(saver, BaseCheckpointSaver)


@pytest.mark.asyncio
async def test_get_checkpointer_memory_mode():
    """Verify get_checkpointer in :memory: mode provides an InMemorySaver."""
    async with get_checkpointer(":memory:") as saver:
        assert isinstance(saver, InMemorySaver)
        assert isinstance(saver, BaseCheckpointSaver)


@pytest.mark.asyncio
async def test_get_sqlite_checkpointer_persistence(tmp_path: Path):
    """Verify get_sqlite_checkpointer persists state under thread_id to SQLite database (AC-036)."""
    db_path = tmp_path / "checkpoints.db"

    async with get_sqlite_checkpointer(str(db_path)) as saver:
        assert isinstance(saver, AsyncSqliteSaver)

        builder = StateGraph(SupportState)

        async def step_one(state: SupportState) -> dict[str, Any]:
            return {
                "classification": {"category": "billing"},
                "completed_nodes": ["step_one"],
            }

        builder.add_node("step_one", step_one)
        builder.add_edge(START, "step_one")
        builder.add_edge("step_one", END)

        graph = builder.compile(checkpointer=saver)

        thread_id = "thread-sqlite-persisted"
        config = {"configurable": {"thread_id": thread_id}}

        state = create_initial_support_state(
            ticket_id="CD-1002",
            customer_id="cust-102",
            subject="Billing dispute",
            text="Need refund",
        )

        result = await graph.ainvoke(state, config=config)
        assert result["completed_nodes"] == ["step_one"]

        # Read back checkpoint tuple for thread
        checkpoint_tuple = await saver.aget_tuple(config)
        assert checkpoint_tuple is not None
        assert (
            checkpoint_tuple.checkpoint["channel_values"]["classification"]["category"]
            == "billing"
        )
        assert checkpoint_tuple.checkpoint["channel_values"]["completed_nodes"] == [
            "step_one"
        ]

    # Verify SQLite DB file exists on disk
    assert db_path.exists()
    assert db_path.stat().st_size > 0


@pytest.mark.asyncio
async def test_checkpointer_resumption_after_pause(tmp_path: Path):
    """Verify graph execution paused at a node can be resumed using saved thread_id (AC-036)."""
    db_path = tmp_path / "resume_test.db"

    async with get_sqlite_checkpointer(str(db_path)) as saver:
        builder = StateGraph(SupportState)

        async def node_phase_one(state: SupportState) -> dict[str, Any]:
            return {
                "risk_level": "high",
                "approval_required": True,
                "completed_nodes": ["phase_one"],
            }

        async def node_phase_two(state: SupportState) -> dict[str, Any]:
            return {
                "approval_status": "approved",
                "completed_nodes": ["phase_two"],
            }

        builder.add_node("phase_one", node_phase_one)
        builder.add_node("phase_two", node_phase_two)

        builder.add_edge(START, "phase_one")
        builder.add_edge("phase_one", "phase_two")
        builder.add_edge("phase_two", END)

        # Interrupt before phase_two to simulate human approval pause
        graph = builder.compile(checkpointer=saver, interrupt_before=["phase_two"])

        thread_id = "thread-approval-gate-1002"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = create_initial_support_state(
            ticket_id="CD-1002",
            customer_id="cust-102",
            subject="Refund request",
            text="Please refund invoice",
        )

        # First run pauses before phase_two
        state_at_interrupt = await graph.ainvoke(initial_state, config=config)
        assert state_at_interrupt["completed_nodes"] == ["phase_one"]
        assert state_at_interrupt["approval_required"] is True

        # Check next node is phase_two
        state_tuple = await graph.aget_state(config)
        assert state_tuple.next == ("phase_two",)

        # Resume execution using the same thread_id
        resumed_state = await graph.ainvoke(None, config=config)
        assert resumed_state["completed_nodes"] == ["phase_one", "phase_two"]
        assert resumed_state["approval_status"] == "approved"


@pytest.mark.asyncio
async def test_get_sqlite_checkpointer_in_memory():
    """Verify get_sqlite_checkpointer works in-memory without disk I/O."""
    async with get_sqlite_checkpointer(":memory:") as saver:
        assert isinstance(saver, AsyncSqliteSaver)
        builder = StateGraph(SupportState)
        builder.add_node("step", lambda s: {"completed_nodes": ["step"]})
        builder.add_edge(START, "step")
        builder.add_edge("step", END)
        graph = builder.compile(checkpointer=saver)
        res = await graph.ainvoke(
            create_initial_support_state("CD-1003", "cust-103"),
            config={"configurable": {"thread_id": "mem-test"}},
        )
        assert res["completed_nodes"] == ["step"]


def test_agents_package_reexports():
    """Verify agents package exports SupportState and checkpointer utilities."""
    import agents

    assert hasattr(agents, "SupportState")
    assert hasattr(agents, "get_checkpointer")
    assert hasattr(agents, "get_in_memory_checkpointer")
    assert hasattr(agents, "get_sqlite_checkpointer")
    assert hasattr(agents, "create_initial_support_state")
    assert hasattr(agents, "append_list")
    assert hasattr(agents, "merge_usage")


def test_errors_reducer_accumulation():
    """Verify errors channel accumulates multiple error messages."""
    assert append_list([], ["First warning"]) == ["First warning"]
    assert append_list(["First warning"], ["Second warning"]) == [
        "First warning",
        "Second warning",
    ]


def test_resolve_checkpointer_path_with_path_object(tmp_path: Path):
    """Verify resolve_checkpointer_path handles Path instances and creates directories."""
    sub_dir = tmp_path / "deep" / "nested" / "checkpoints.db"
    resolved = resolve_checkpointer_path(sub_dir)
    assert resolved == sub_dir.resolve()
    assert sub_dir.parent.exists()


# ============================================================================
# 4. Security Audit & Penetration Tests (CWE-200, CWE-22, CWE-400)
# ============================================================================


def test_security_cwe_200_no_secrets_in_default_state():
    """Security audit: Default state initialization contains no secrets or leakable attributes (CWE-200)."""
    state = create_initial_support_state(
        ticket_id="CD-1001",
        customer_id="cust-101",
        subject="Routine request",
        text="Normal ticket text",
    )

    for key, value in state.items():
        val_str = str(value)
        for pattern_name, regex in SECRET_PATTERNS:
            assert not regex.search(val_str), (
                f"Secret pattern {pattern_name} leaked in key {key}"
            )


def test_security_cwe_22_checkpointer_path_traversal():
    """Penetration test: Checkpointer path resolution forbids unsafe traversal outside allowable roots (CWE-22)."""
    # Safe paths
    assert resolve_checkpointer_path(":memory:") == ":memory:"
    assert (
        resolve_checkpointer_path("./data/checkpoints.db")
        == Path("./data/checkpoints.db").resolve()
    )

    # Traversal attempts outside project are rejected or safely resolved
    with pytest.raises(ValueError, match="Path traversal"):
        resolve_checkpointer_path("../../../../../etc/passwd.db")


def test_security_cwe_400_reducer_size_bounding():
    """Penetration test: Reducer safely handles large message or error inputs without crashing (CWE-400)."""
    initial = [f"step_{i}" for i in range(1000)]
    update = [f"step_{i}" for i in range(1000, 2000)]

    merged = append_list(initial, update)
    assert len(merged) == 2000

    # Token merge with large numbers
    usage_a = {"prompt_tokens": 10**8, "total_tokens": 10**8}
    usage_b = {"prompt_tokens": 10**8, "total_tokens": 10**8}
    merged_usage = merge_usage(usage_a, usage_b)
    assert merged_usage["total_tokens"] == 2 * 10**8
