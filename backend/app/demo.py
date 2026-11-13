"""Terminal Demo Workflow Runner for CloudDesk Autonomous Support System (P11-5).

Demonstrates the two critical Phase 11 governance and orchestration pathways:
1. CD-1002: Human-in-the-Loop approval gate on consequential operations
   (`create_refund_request`), graph pause via `interrupt()`, operator prompt,
   and checkpointer resumption executing resolution on the shared tool path (US-010, US-011).
2. CD-1005: Deterministic policy escalation for security incidents, bypassing
   model hallucination and routing directly to specialized security engineering (US-012).

Usage:
    make demo
    make demo TICKET=CD-1005
    python -m backend.app.demo [--ticket TICKET_ID] [--all] [--non-interactive]
    python scripts/demo.py [--ticket TICKET_ID]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure repository root is on sys.path when executed directly
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.graph import (
    NODE_ESCALATION,
    NODE_EXECUTE_RESOLUTION,
    NODE_MEMORY_UPDATE,
    NODE_TICKET_SUMMARY,
    resume_support_workflow,
    run_support_workflow,
)
from agents.state import SupportState, create_initial_support_state
from agents.tracer import WorkflowTracer
from backend.app.core.database import create_tables, get_session_factory
from backend.app.core.guardrails import scrub
from backend.app.models.entities import (
    ApprovalRequest,
    Escalation,
    Ticket,
)
from backend.app.schemas.common import (
    ApprovalStatusEnum,
    EscalationStatusEnum,
    TicketStatusEnum,
)
from backend.app.services.seed_service import bootstrap_demo_data

logger = logging.getLogger(__name__)


@dataclass
class DemoResult:
    """Structured result of a demo workflow run."""

    ticket_id: str
    workflow_id: str
    subject: str = ""
    category: str = ""
    severity: str = ""
    customer_plan: str = "free"
    interrupted: bool = False
    resumed: bool = False
    approval_status: str | None = None
    escalation_required: bool = False
    escalation_team: str | None = None
    escalation_id: str | None = None
    completed_nodes: list[str] = field(default_factory=list)
    executed_actions: list[dict[str, Any]] = field(default_factory=list)
    ticket_status: str = "new"
    summary: str = ""
    customer_reply: str = ""
    error: str | None = None


def format_demo_output(data: Any) -> str:
    """Format and scrub data for safe terminal output (CWE-200).

    Recursively replaces all secrets, credit card PANs, and passwords with ***REDACTED***.
    """
    if isinstance(data, str):
        return scrub(data)
    if isinstance(data, dict):
        return "\n".join(f"  {k}: {format_demo_output(v)}" for k, v in data.items())
    if isinstance(data, list):
        return "\n".join(f"  - {format_demo_output(item)}" for item in data)
    return str(data)


def _print_banner(title: str, char: str = "=") -> None:
    line = char * 68
    print(f"\n{line}\n  {title}\n{line}")


def _print_step(icon: str, label: str, detail: str = "") -> None:
    if detail:
        print(f"  {icon}  \033[1m{label}\033[0m: {detail}")
    else:
        print(f"  {icon}  \033[1m{label}\033[0m")


async def run_demo(
    ticket_id: str = "CD-1002",
    session: AsyncSession | None = None,
    auto_approve: bool = False,
    decision: str = "approved",
    interactive: bool = True,
    verbose: bool = False,
) -> DemoResult:
    """Execute end-to-end support workflow demonstration for a specified ticket.

    Args:
        ticket_id: Ticket ID to triage and resolve (e.g. CD-1002, CD-1005).
        session: Optional SQLAlchemy AsyncSession. When omitted, default session is created.
        auto_approve: If True, bypasses terminal input prompt and auto-confirms approval.
        decision: Decision to resume with ('approved' or 'rejected'). Defaults to 'approved'.
        interactive: If False, skips terminal prompt when interrupted.
        verbose: If True, outputs detailed telemetry traces.

    Returns:
        Populated DemoResult containing execution status and evidence.
    """
    if session is not None:
        return await _run_demo_with_session(
            ticket_id=ticket_id,
            session=session,
            auto_approve=auto_approve,
            decision=decision,
            interactive=interactive,
            verbose=verbose,
        )

    # CLI path: create database connection and ensure seed data exists
    await create_tables()
    session_factory = get_session_factory()
    async with session_factory() as local_session:
        # Check if tickets exist, seed if database is empty
        t_check = await local_session.execute(select(Ticket).limit(1))
        if t_check.scalars().first() is None:
            await bootstrap_demo_data(local_session)

        return await _run_demo_with_session(
            ticket_id=ticket_id,
            session=local_session,
            auto_approve=auto_approve,
            decision=decision,
            interactive=interactive,
            verbose=verbose,
        )


async def _run_demo_with_session(
    ticket_id: str,
    session: AsyncSession,
    auto_approve: bool,
    decision: str,
    interactive: bool,
    verbose: bool,
) -> DemoResult:
    """Internal implementation of demo execution using an active database session."""
    # 1. Fetch ticket and initial customer message
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    ticket: Ticket | None = (await session.execute(stmt)).scalars().first()
    if ticket is None:
        err_msg = f"Ticket '{ticket_id}' not found in database."
        print(f"\n[ERROR] {err_msg}")
        return DemoResult(
            ticket_id=ticket_id,
            workflow_id="",
            error=err_msg,
        )

    # Collect ticket message text
    from backend.app.models.entities import TicketMessage

    msg_stmt = (
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc())
    )
    messages = (await session.execute(msg_stmt)).scalars().all()
    text = (
        "\n\n".join(m.body for m in messages if m.body) if messages else ticket.subject
    )

    plan_name = "pro"
    if ticket.customer_id:
        from backend.app.models.entities import Customer

        cust_stmt = select(Customer).where(Customer.id == ticket.customer_id)
        cust = (await session.execute(cust_stmt)).scalars().first()
        if cust and cust.plan:
            plan_name = getattr(cust.plan, "value", str(cust.plan))

    wf_id = f"wf-demo-{uuid.uuid4().hex[:8]}"
    thread_id = f"thread-demo-{ticket.id}-{wf_id}"

    _print_banner(f"CloudDesk Support Platform — Demo: {ticket.id}")
    _print_step("🎫", "Ticket ID", ticket.id)
    _print_step("📌", "Subject", ticket.subject)
    _print_step("🏷️", "Initial Category", ticket.category)
    _print_step("🏢", "Customer Tier", plan_name.upper())
    _print_step("💬", "Customer Message", f'"{scrub(text.splitlines()[0])}"')

    # 2. Initialize workflow state and telemetry tracer
    initial_state = create_initial_support_state(
        ticket_id=ticket.id,
        customer_id=ticket.customer_id,
        subject=ticket.subject,
        text=text,
        customer_plan=plan_name,
        workflow_id=wf_id,
    )
    tracer = WorkflowTracer(ticket_id=ticket.id, workflow_id=wf_id, session=session)

    print("\n  🚀  \033[1mLaunching Autonomous Support StateGraph Pipeline...\033[0m")

    # 3. Execute support workflow
    state: SupportState = await run_support_workflow(
        initial_state=initial_state,
        thread_id=thread_id,
        tracer=tracer,
    )

    completed_nodes: list[str] = list(state.get("completed_nodes", []))
    is_interrupted = (
        bool(state.get("__interrupt__")) or state.get("approval_status") == "pending"
    )

    # Print node execution telemetry
    for node in completed_nodes:
        if node == "understand_ticket":
            _print_step(
                "🔍", "Understand Ticket", f"Category -> {state.get('category')}"
            )
        elif node == "classify_severity":
            _print_step(
                "⚡",
                "Classify Severity",
                f"Severity -> {state.get('severity', '').upper()}",
            )
        elif node == "customer_context":
            _print_step(
                "👤",
                "Customer Context",
                f"Customer {state.get('customer_id')} ({state.get('customer_plan')})",
            )
        elif node == "knowledge_retrieval":
            evidence = state.get("evidence", [])
            _print_step(
                "📚", "Knowledge Retrieval", f"Retrieved {len(evidence)} articles"
            )
        elif node == "troubleshooting":
            diag = state.get("diagnosis", {})
            cause = diag.get("root_cause") if isinstance(diag, dict) else str(diag)
            _print_step("🛠️", "Troubleshooting", f"Diagnosis -> {cause or 'Analyzed'}")
        elif node == "resolution_planning":
            actions = state.get("resolution_actions") or []
            tool_names = [a.get("tool_name") for a in actions if isinstance(a, dict)]
            _print_step("📋", "Resolution Planning", f"Planned Actions: {tool_names}")
        elif node == "risk_check":
            risk = state.get("risk_level", "low")
            _print_step("⚖️", "Risk Evaluation", f"Risk Level -> {risk.upper()}")

    # 4. Handle Pathway A: Human Approval Interrupt (e.g. CD-1002)
    resumed = False
    final_status = "new"
    executed_actions = list(state.get("executed_actions") or [])

    if is_interrupted or state.get("approval_required"):
        app_req = state.get("approval_request") or {}
        gated_tool = app_req.get("tool_name") or "consequential_action"
        tool_args = app_req.get("arguments") or {}

        _print_banner("⏸  HUMAN APPROVAL INTERRUPT TRIGGERED (AC-035, US-010)", "-")
        _print_step("🛑", "Gated Tool", f"{gated_tool} (Consequential Operation)")
        _print_step("📦", "Arguments", format_demo_output(tool_args))
        _print_step("🔒", "Status", "WAITING_ON_APPROVAL (State checkpointed)")

        # Persist ApprovalRequest in database if not already present
        stmt_appr = select(ApprovalRequest).where(
            ApprovalRequest.ticket_id == ticket.id,
            ApprovalRequest.workflow_id == wf_id,
        )
        existing_appr = (await session.execute(stmt_appr)).scalars().first()
        if existing_appr is None:
            new_appr = ApprovalRequest(
                id=f"appr-{uuid.uuid4().hex[:10]}",
                ticket_id=ticket.id,
                workflow_id=wf_id,
                action_name=gated_tool,
                action_payload=tool_args,
                status=ApprovalStatusEnum.PENDING.value,
            )
            session.add(new_appr)
            ticket.status = TicketStatusEnum.WAITING_ON_APPROVAL.value
            await session.commit()

        # Decide whether to resume
        should_resume = auto_approve
        dec_action = decision

        if not auto_approve and interactive and sys.stdin.isatty():
            try:
                print(
                    f"\n  👉  Authorize '{gated_tool}' for ticket {ticket.id}? [Y/n/r]: ",
                    end="",
                    flush=True,
                )
                user_choice = input().strip().lower()
                if user_choice in ("r", "reject", "no", "n"):
                    dec_action = "rejected"
                    should_resume = True
                else:
                    dec_action = "approved"
                    should_resume = True
            except (EOFError, KeyboardInterrupt):
                should_resume = False

        if should_resume:
            _print_banner(
                f"▶  RESUMING WORKFLOW WITH DECISION: {dec_action.upper()} (AC-039)",
                "-",
            )
            resume_payload = {
                "action": dec_action,
                "decided_by": "demo_operator@clouddesk.demo",
                "reason": f"Authorized in terminal demo for {ticket.id}",
            }

            # Resume workflow from checkpoint
            state = await resume_support_workflow(
                thread_id=thread_id,
                decision=resume_payload,
                tracer=tracer,
            )
            resumed = True
            completed_nodes = list(state.get("completed_nodes", []))
            executed_actions = list(state.get("executed_actions") or [])

            # Print newly completed nodes
            if NODE_EXECUTE_RESOLUTION in completed_nodes:
                _print_step(
                    "⚙️",
                    "Execute Resolution",
                    f"Executed {len(executed_actions)} action(s) via ToolRegistry",
                )
            if NODE_ESCALATION in completed_nodes:
                _print_step(
                    "🚨",
                    "Escalation Node",
                    f"Diverted to {state.get('escalation_team', 'Engineering')} (Approval Rejected)",
                )
            if NODE_TICKET_SUMMARY in completed_nodes:
                _print_step(
                    "📝", "Ticket Summary", "Generated final resolution summary"
                )
            if NODE_MEMORY_UPDATE in completed_nodes:
                _print_step(
                    "💾", "Customer Memory", f"Saved findings for {ticket.customer_id}"
                )

            final_status = "resolved" if dec_action == "approved" else "escalated"
            ticket.status = final_status
            await session.commit()
        else:
            final_status = "waiting_on_approval"

    # 5. Handle Pathway B: Deterministic Policy Escalation (e.g. CD-1005)
    elif state.get("escalation_required") or NODE_ESCALATION in completed_nodes:
        esc_team = state.get("escalation_team") or "Security"
        esc_reason = state.get("escalation_reason") or "Policy escalation triggered"
        esc_rule = state.get("escalation_rule_id") or "rule_security_incident"

        _print_banner("🚨 DETERMINISTIC POLICY ESCALATION TRIGGERED (AC-043)", "-")
        _print_step("🛡️", "Target Specialist Team", esc_team.upper())
        _print_step("📜", "Policy Rule", esc_rule)
        _print_step("⚠️", "Escalation Reason", scrub(esc_reason))

        # Check / create escalation record in DB
        stmt_esc = select(Escalation).where(
            Escalation.ticket_id == ticket.id,
            Escalation.status == EscalationStatusEnum.OPEN.value,
        )
        existing_esc = (await session.execute(stmt_esc)).scalars().first()
        esc_id = existing_esc.id if existing_esc else state.get("escalation_id")

        if existing_esc is None and not esc_id:
            new_esc = Escalation(
                ticket_id=ticket.id,
                target_team=esc_team,
                policy_reason=esc_reason,
                severity=ticket.severity,
                status=EscalationStatusEnum.OPEN.value,
            )
            session.add(new_esc)
            await session.flush()
            esc_id = new_esc.id

        ticket.status = TicketStatusEnum.ESCALATED.value
        await session.commit()

        if NODE_TICKET_SUMMARY in completed_nodes:
            _print_step("📝", "Ticket Summary", "Recorded executive escalation summary")
        if NODE_MEMORY_UPDATE in completed_nodes:
            _print_step(
                "💾", "Customer Memory", f"Saved findings for {ticket.customer_id}"
            )

        final_status = "escalated"

    else:
        final_status = "resolved"
        ticket.status = TicketStatusEnum.RESOLVED.value
        await session.commit()

    # 6. Summary wrap up
    _print_banner("✅ DEMO WORKFLOW COMPLETED", "=")
    _print_step("📊", "Final Ticket Status", final_status.upper())
    _print_step("🏁", "Completed Nodes", " -> ".join(completed_nodes))

    res = DemoResult(
        ticket_id=ticket.id,
        workflow_id=wf_id,
        subject=ticket.subject,
        category=ticket.category,
        severity=ticket.severity,
        customer_plan=plan_name,
        interrupted=is_interrupted,
        resumed=resumed,
        approval_status=state.get("approval_status") or state.get("approval_decision"),
        escalation_required=bool(state.get("escalation_required")),
        escalation_team=state.get("escalation_team"),
        escalation_id=state.get("escalation_id")
        or (existing_esc.id if "existing_esc" in locals() and existing_esc else None),
        completed_nodes=completed_nodes,
        executed_actions=executed_actions,
        ticket_status=final_status,
        summary=state.get("ticket_summary") or "",
        customer_reply=state.get("customer_reply") or "",
    )
    return res


async def run_demo_all(
    session: AsyncSession | None = None,
    auto_approve: bool = True,
    decision: str = "approved",
    verbose: bool = False,
) -> list[DemoResult]:
    """Execute both CD-1002 (Approval flow) and CD-1005 (Escalation flow) in sequence."""
    _print_banner("🌟 CLOUDDESK AUTONOMOUS SUPPORT — FULL DEMO SUITE (P11-5) 🌟")
    print("  Demonstrating both Human-in-the-Loop Approval and Policy Escalation.\n")

    res_1002 = await run_demo(
        ticket_id="CD-1002",
        session=session,
        auto_approve=auto_approve,
        decision=decision,
        interactive=False,
        verbose=verbose,
    )

    res_1005 = await run_demo(
        ticket_id="CD-1005",
        session=session,
        auto_approve=auto_approve,
        decision=decision,
        interactive=False,
        verbose=verbose,
    )

    return [res_1002, res_1005]


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for demo script."""
    parser = argparse.ArgumentParser(
        description="CloudDesk Autonomous Support Agent Terminal Demo (P11-5)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ticket",
        "-t",
        default="CD-1002",
        help="Ticket ID to execute in demo (e.g. CD-1002 for approval, CD-1005 for escalation)",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Run both CD-1002 and CD-1005 demo flows consecutively",
    )
    parser.add_argument(
        "--decision",
        "-d",
        choices=["approved", "rejected"],
        default="approved",
        help="Decision to supply when resuming an interrupted workflow",
    )
    parser.add_argument(
        "--non-interactive",
        "-y",
        action="store_true",
        help="Auto-confirm human approval prompt without interactive terminal wait",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed diagnostic telemetry output",
    )
    return parser.parse_args(args)


async def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint for terminal demo runner."""
    parsed = parse_args(argv)

    if parsed.verbose:
        logging.basicConfig(level=logging.DEBUG)

    try:
        if parsed.all:
            results = await run_demo_all(
                auto_approve=parsed.non_interactive,
                decision=parsed.decision,
                verbose=parsed.verbose,
            )
            success = all(r.error is None for r in results)
            return 0 if success else 1
        else:
            result = await run_demo(
                ticket_id=parsed.ticket,
                auto_approve=parsed.non_interactive,
                decision=parsed.decision,
                interactive=not parsed.non_interactive,
                verbose=parsed.verbose,
            )
            return 0 if result.error is None else 1
    except Exception as exc:  # noqa: BLE001
        print(f"\n[FATAL] Demo execution failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
