"""Unit, Integration, and Security Tests for Execute Resolution on Shared Tool Path (P11-4).

Verifies:
- Auto-resolved safe action execution through ToolRegistry on shared tool path (CLAUDE.md §7.4).
- Approved consequential action execution (create_refund_request, reset_demo_setting) (AC-032, AC-039).
- Policy enforcement: unapproved consequential actions are blocked by ToolPolicy (CWE-285).
- Error isolation and resilience: tool exceptions never crash the workflow graph.
- Idempotency: already executed actions are safely preserved without re-execution.
- Rejection of unregistered/arbitrary tool invocations (AC-033).
- Fine-grained WorkflowTracer telemetry emission (node_started, tool_called, node_completed).
- End-to-end integration: low-risk auto-execution and pause/approve/resume flow.
- Security audits against CWE-285 (authorization bypass) and CWE-200 (secret scrubbing).
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.graph import (
    NODE_EXECUTE_RESOLUTION,
    NODE_HUMAN_APPROVAL,
    NODE_MEMORY_UPDATE,
    NODE_TICKET_SUMMARY,
    resume_support_workflow,
    run_support_workflow,
)
from agents.nodes.resolution import (
    execute_resolution,
)
from agents.state import create_initial_support_state
from agents.tracer import (
    EVENT_NODE_COMPLETED,
    EVENT_NODE_STARTED,
    EVENT_TOOL_CALLED,
    WorkflowTracer,
)
from backend.app.models.entities import (
    Base,
    Customer,
    ResolutionAction,
    Ticket,
)
from backend.app.schemas.common import (
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    ResolutionActionStatusEnum,
    SeverityEnum,
    TicketStatusEnum,
)


@pytest.fixture
async def resolution_db_session():
    """Create isolated in-memory SQLite database session with seeded ticket and customer."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        cust = Customer(
            id="cust-102-globex",
            name="Globex Corporation",
            email="admin@globex.corp",
            plan=CustomerPlanEnum.BUSINESS.value,
        )
        session.add(cust)

        ticket = Ticket(
            id="CD-1002",
            customer_id="cust-102-globex",
            subject="Charged for 8 seats instead of 5",
            category=CategoryEnum.BILLING.value,
            severity=SeverityEnum.MEDIUM.value,
            channel=ChannelEnum.EMAIL.value,
            status=TicketStatusEnum.NEW.value,
        )
        session.add(ticket)
        await session.commit()
        yield session


# ============================================================================
# 1. Safe Auto-Resolved Action Execution (CLAUDE.md §7.4)
# ============================================================================


@pytest.mark.asyncio
async def test_execute_resolution_safe_action_auto_resolved(
    resolution_db_session: AsyncSession,
):
    """Verify safe action (update_ticket) executes unattended via ToolRegistry (approved=False)."""
    state = {
        "ticket_id": "CD-1002",
        "workflow_id": "wf-exec-safe-01",
        "resolution_actions": [
            {
                "tool_name": "update_ticket",
                "arguments": {
                    "ticket_id": "CD-1002",
                    "status": "in_progress",
                    "resolution_summary": "Auto-applying resolution plan.",
                },
                "requires_approval": False,
            }
        ],
        "approval_status": None,
    }

    result = await execute_resolution(state, session=resolution_db_session)

    assert result["current_node"] == NODE_EXECUTE_RESOLUTION
    assert NODE_EXECUTE_RESOLUTION in result["completed_nodes"]

    executed = result.get("executed_actions") or []
    assert len(executed) == 1
    assert executed[0]["tool_name"] == "update_ticket"
    assert executed[0]["status"] == "executed"
    assert executed[0]["result"] is not None

    # Verify changes in DB
    stmt = select(Ticket).where(Ticket.id == "CD-1002")
    res = await resolution_db_session.execute(stmt)
    ticket = res.scalar_one()
    assert ticket.status == "in_progress"
    assert "Auto-applying" in (ticket.resolution_summary or "")


# ============================================================================
# 2. Approved Consequential Action Execution (AC-032, AC-039)
# ============================================================================


@pytest.mark.asyncio
async def test_execute_resolution_approved_consequential_action(
    resolution_db_session: AsyncSession,
):
    """Verify approved consequential action (create_refund_request) executes and records ResolutionAction."""
    state = {
        "ticket_id": "CD-1002",
        "customer_id": "cust-102-globex",
        "workflow_id": "wf-exec-appr-02",
        "approval_status": "approved",
        "approval_decision": "approved",
        "resolution_actions": [
            {
                "tool_name": "create_refund_request",
                "arguments": {
                    "ticket_id": "CD-1002",
                    "customer_id": "cust-102-globex",
                    "amount": 90.0,
                    "reason": "Seat downgrade pro-rata credit ($90).",
                },
                "requires_approval": True,
            }
        ],
    }

    result = await execute_resolution(state, session=resolution_db_session)

    executed = result.get("executed_actions") or []
    assert len(executed) == 1
    assert executed[0]["tool_name"] == "create_refund_request"
    assert executed[0]["status"] == "executed"
    assert executed[0]["result"]["amount"] == 90.0

    # Verify ResolutionAction persisted in database
    stmt = select(ResolutionAction).where(ResolutionAction.ticket_id == "CD-1002")
    res = await resolution_db_session.execute(stmt)
    action_records = res.scalars().all()
    assert len(action_records) == 1
    assert action_records[0].action_name == "create_refund_request"
    assert action_records[0].status == ResolutionActionStatusEnum.EXECUTED.value


# ============================================================================
# 3. Policy Enforcement & Blocked Unapproved Actions (CWE-285)
# ============================================================================


@pytest.mark.asyncio
async def test_execute_resolution_blocks_unapproved_consequential_action(
    resolution_db_session: AsyncSession,
):
    """Verify unapproved consequential action is blocked by ToolPolicy and recorded as failed."""
    state = {
        "ticket_id": "CD-1002",
        "customer_id": "cust-102-globex",
        "workflow_id": "wf-exec-block-03",
        "approval_status": None,  # NOT approved
        "resolution_actions": [
            {
                "tool_name": "create_refund_request",
                "arguments": {
                    "ticket_id": "CD-1002",
                    "customer_id": "cust-102-globex",
                    "amount": 90.0,
                    "reason": "Attempting unauthorized refund execution.",
                },
                "requires_approval": True,
            }
        ],
    }

    result = await execute_resolution(state, session=resolution_db_session)

    executed = result.get("executed_actions") or []
    assert len(executed) == 1
    assert executed[0]["tool_name"] == "create_refund_request"
    assert executed[0]["status"] == "failed"
    assert "approval" in executed[0]["error"].lower()

    # Verify errors channel recorded the failure
    assert len(result.get("errors", [])) > 0


# ============================================================================
# 4. Resilience to Tool Exceptions & Unknown Tools
# ============================================================================


@pytest.mark.asyncio
async def test_execute_resolution_resilient_to_tool_exception(
    resolution_db_session: AsyncSession,
):
    """Verify tool runtime failure (e.g. negative refund amount) is isolated without crashing the node."""
    state = {
        "ticket_id": "CD-1002",
        "workflow_id": "wf-exec-err-04",
        "approval_status": "approved",
        "resolution_actions": [
            {
                "tool_name": "create_refund_request",
                "arguments": {
                    "ticket_id": "CD-1002",
                    "customer_id": "cust-102-globex",
                    "amount": -50.0,  # Invalid amount
                    "reason": "Negative refund test",
                },
                "requires_approval": True,
            }
        ],
    }

    # Should not raise exception
    result = await execute_resolution(state, session=resolution_db_session)

    executed = result.get("executed_actions") or []
    assert len(executed) == 1
    assert executed[0]["status"] == "failed"
    assert "invalid refund amount" in executed[0]["error"].lower()


@pytest.mark.asyncio
async def test_execute_resolution_rejects_arbitrary_unregistered_tool():
    """Verify model-invented/unregistered actions are rejected safely (AC-033)."""
    state = {
        "ticket_id": "CD-1002",
        "workflow_id": "wf-exec-unregistered-05",
        "resolution_actions": [
            {
                "tool_name": "arbitrary_custom_tool",
                "arguments": {"command": "drop table"},
                "requires_approval": False,
            }
        ],
    }

    result = await execute_resolution(state)
    executed = result.get("executed_actions") or []
    assert len(executed) == 1
    assert executed[0]["status"] == "failed"
    assert (
        "not registered" in executed[0]["error"].lower()
        or "blocked" in executed[0]["error"].lower()
        or "approval" in executed[0]["error"].lower()
    )


# ============================================================================
# 5. Idempotency (Skip Already Executed Actions)
# ============================================================================


@pytest.mark.asyncio
async def test_execute_resolution_idempotent_skips_already_executed(
    resolution_db_session: AsyncSession,
):
    """Verify actions with status='executed' are preserved and not re-executed."""
    state = {
        "ticket_id": "CD-1002",
        "workflow_id": "wf-exec-idempotent-06",
        "approval_status": "approved",
        "resolution_actions": [
            {
                "tool_name": "update_ticket",
                "status": "executed",
                "result": {"id": "CD-1002", "status": "resolved"},
                "arguments": {"ticket_id": "CD-1002", "status": "resolved"},
            }
        ],
    }

    result = await execute_resolution(state, session=resolution_db_session)
    executed = result.get("executed_actions") or []
    assert len(executed) == 1
    assert executed[0]["status"] == "executed"
    assert executed[0]["result"]["status"] == "resolved"


# ============================================================================
# 6. Telemetry Event Tracing
# ============================================================================


@pytest.mark.asyncio
async def test_execute_resolution_telemetry_events(
    resolution_db_session: AsyncSession,
):
    """Verify WorkflowTracer records node_started, tool_called, and node_completed."""
    tracer = WorkflowTracer(
        ticket_id="CD-1002",
        workflow_id="wf-trace-resolution",
        session=resolution_db_session,
    )

    state = {
        "ticket_id": "CD-1002",
        "workflow_id": "wf-trace-resolution",
        "resolution_actions": [
            {
                "tool_name": "update_ticket",
                "arguments": {"ticket_id": "CD-1002", "status": "in_progress"},
                "requires_approval": False,
            }
        ],
    }

    await execute_resolution(state, session=resolution_db_session, tracer=tracer)

    event_types = [e["event_type"] for e in tracer.events_buffer]
    assert EVENT_NODE_STARTED in event_types
    assert EVENT_TOOL_CALLED in event_types
    assert EVENT_NODE_COMPLETED in event_types

    tool_event = next(
        e for e in tracer.events_buffer if e["event_type"] == EVENT_TOOL_CALLED
    )
    assert tool_event["node_name"] == NODE_EXECUTE_RESOLUTION
    assert tool_event["payload"]["tool"] == "update_ticket"


# ============================================================================
# 7. End-to-End Workflow Execution (Auto-Resolved & Approval-Resumed)
# ============================================================================


@pytest.mark.asyncio
async def test_workflow_e2e_low_risk_auto_execution():
    """Verify safe low-risk ticket executes resolution automatically and completes."""
    checkpointer = InMemorySaver()
    thread_id = "test-thread-low-risk-auto-exec"

    initial_state = create_initial_support_state(
        ticket_id="CD-1004",
        customer_id="cust-102-globex",
        subject="How to configure webhooks in Slack integration",
        text="Can you explain how to set up webhook notifications for our Slack bot?",
        customer_plan="pro",
        workflow_id="wf-auto-exec-e2e",
    )

    final_state = await run_support_workflow(
        initial_state,
        thread_id=thread_id,
        checkpointer=checkpointer,
    )

    completed = final_state.get("completed_nodes", [])
    assert NODE_EXECUTE_RESOLUTION in completed
    assert NODE_TICKET_SUMMARY in completed
    assert NODE_MEMORY_UPDATE in completed
    assert final_state.get("approval_required") in (False, None)


@pytest.mark.asyncio
async def test_workflow_e2e_approval_resume_executes_resolution():
    """Verify paused consequential ticket resumes on approval and executes resolution actions."""
    checkpointer = InMemorySaver()
    thread_id = "test-thread-approval-resume-exec"

    initial_state = create_initial_support_state(
        ticket_id="CD-1002",
        customer_id="cust-102-globex",
        subject="Charged for 8 seats instead of 5",
        text="I downgraded to 5 seats, but invoice charged for 8 seats ($90 refund requested).",
        customer_plan="business",
        workflow_id="wf-resume-exec-e2e",
    )

    # 1. First run halts at human_approval
    paused_state = await run_support_workflow(
        initial_state,
        thread_id=thread_id,
        checkpointer=checkpointer,
    )
    assert paused_state.get("approval_status") == "pending"

    # 2. Resume with approval decision
    resumed_state = await resume_support_workflow(
        thread_id=thread_id,
        decision={
            "action": "approve",
            "approved_by": "agent-supervisor-01",
            "reason": "Verified pro-rata discrepancy.",
        },
        checkpointer=checkpointer,
    )

    completed = resumed_state.get("completed_nodes", [])
    assert NODE_HUMAN_APPROVAL in completed
    assert NODE_EXECUTE_RESOLUTION in completed
    assert NODE_TICKET_SUMMARY in completed
    assert NODE_MEMORY_UPDATE in completed

    executed = resumed_state.get("executed_actions") or []
    assert len(executed) > 0


# ============================================================================
# 8. Security Audits: CWE-285 (Authorization) and CWE-200 (Scrubbing)
# ============================================================================


@pytest.mark.asyncio
async def test_security_cwe_285_policy_gating_in_execute_resolution():
    """Security Audit (CWE-285): Confirm unapproved consequential tool is never executed."""
    state = {
        "ticket_id": "CD-1002",
        "workflow_id": "wf-sec-cwe285",
        "approval_status": None,
        "resolution_actions": [
            {
                "tool_name": "reset_demo_setting",
                "arguments": {
                    "ticket_id": "CD-1002",
                    "workspace_id": "ws-101",
                    "setting_name": "security_policy",
                },
                "requires_approval": True,
            }
        ],
    }

    result = await execute_resolution(state)
    executed = result.get("executed_actions", [])
    assert len(executed) == 1
    assert executed[0]["status"] == "failed"
    assert (
        "approval" in executed[0]["error"].lower()
        or "blocked" in executed[0]["error"].lower()
    )


@pytest.mark.asyncio
async def test_security_cwe_200_no_secrets_in_executed_action_telemetry(
    resolution_db_session: AsyncSession,
):
    """Security Audit (CWE-200): Ensure secrets inside tool arguments are scrubbed from telemetry."""
    tracer = WorkflowTracer(
        ticket_id="CD-1002",
        workflow_id="wf-sec-cwe200",
        session=resolution_db_session,
    )

    state = {
        "ticket_id": "CD-1002",
        "workflow_id": "wf-sec-cwe200",
        "resolution_actions": [
            {
                "tool_name": "update_ticket",
                "arguments": {
                    "ticket_id": "CD-1002",
                    "resolution_summary": "Password: SecretPassw0rd! and key sk-live-1234567890abcdef12345678",
                },
                "requires_approval": False,
            }
        ],
    }

    await execute_resolution(state, session=resolution_db_session, tracer=tracer)

    tool_events = [
        e for e in tracer.events_buffer if e["event_type"] == EVENT_TOOL_CALLED
    ]
    assert len(tool_events) == 1
    payload_str = str(tool_events[0]["payload"])
    assert "sk-live-" not in payload_str
    assert "***REDACTED***" in payload_str
    assert "SecretPassw0rd" not in payload_str
