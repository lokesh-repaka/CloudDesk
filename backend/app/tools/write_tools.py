"""Write and consequential support tools for CloudDesk.

Provides:
- update_ticket: Updates ticket status, resolution summary, or assignee (safe write).
- create_escalation: Deterministically escalates tickets to specialized teams (safe route).
- create_refund_request: Issues billing refunds, gated by human approval (consequential).
- reset_demo_setting: Resets workspace settings, gated by human approval (consequential).

All functions are decorated with @tool and registered into ToolRegistry.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session_factory
from backend.app.models.entities import Escalation, ResolutionAction, Ticket
from backend.app.schemas.common import (
    EscalationStatusEnum,
    ResolutionActionStatusEnum,
    TicketStatusEnum,
)
from backend.app.tools.base import ToolDefinition, tool
from backend.app.tools.registry import ToolRegistry, get_tool_registry


@tool(
    name="update_ticket",
    description="Update support ticket status, resolution summary, or assignee.",
    is_consequential=False,
    requires_approval=False,
)
async def update_ticket(
    ticket_id: str,
    status: str | None = None,
    resolution_summary: str | None = None,
    assigned_to: str | None = None,
    *,
    session: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Update ticket attributes and persist changes to the database."""
    if not ticket_id:
        return None

    async def _execute(s: AsyncSession) -> dict[str, Any] | None:
        stmt = select(Ticket).where(Ticket.id == ticket_id)
        res = await s.execute(stmt)
        ticket = res.scalar_one_or_none()
        if ticket is None:
            return None

        if status is not None:
            ticket.status = status
        if resolution_summary is not None:
            ticket.resolution_summary = resolution_summary
        if assigned_to is not None:
            ticket.assigned_to = assigned_to

        ticket.updated_at = datetime.now(UTC)
        await s.commit()

        return {
            "id": ticket.id,
            "status": ticket.status,
            "resolution_summary": ticket.resolution_summary,
            "assigned_to": ticket.assigned_to,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        }

    if session is not None:
        return await _execute(session)

    session_factory = get_session_factory()
    async with session_factory() as local_session:
        return await _execute(local_session)


@tool(
    name="create_escalation",
    description="Create an escalation handoff to a designated specialized team.",
    is_consequential=False,
    requires_approval=False,
)
async def create_escalation(
    ticket_id: str,
    target_team: str,
    reason: str,
    severity: str = "high",
    policy_rule: str | None = None,
    workflow_id: str | None = None,
    *,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Escalate a ticket to a specialized team, updating ticket status to escalated."""
    if not ticket_id or not target_team or not reason:
        raise ValueError("ticket_id, target_team, and reason are required to escalate.")

    async def _execute(s: AsyncSession) -> dict[str, Any]:
        # Transition ticket status to escalated
        stmt = select(Ticket).where(Ticket.id == ticket_id)
        res = await s.execute(stmt)
        ticket = res.scalar_one_or_none()
        if ticket is not None:
            ticket.status = TicketStatusEnum.ESCALATED.value
            ticket.updated_at = datetime.now(UTC)

        esc = Escalation(
            id=f"esc-{uuid.uuid4().hex[:8]}",
            ticket_id=ticket_id,
            workflow_id=workflow_id,
            target_team=target_team,
            policy_reason=reason,
            severity=severity,
            status=EscalationStatusEnum.OPEN.value,
        )
        s.add(esc)
        await s.commit()

        return {
            "id": esc.id,
            "ticket_id": esc.ticket_id,
            "target_team": esc.target_team,
            "policy_reason": esc.policy_reason,
            "severity": esc.severity,
            "status": esc.status,
            "policy_rule": policy_rule,
            "created_at": esc.created_at.isoformat() if esc.created_at else None,
        }

    if session is not None:
        return await _execute(session)

    session_factory = get_session_factory()
    async with session_factory() as local_session:
        return await _execute(local_session)


@tool(
    name="create_refund_request",
    description="Create a refund request for customer billing; consequential action requiring human approval.",
    is_consequential=True,
    requires_approval=True,
)
async def create_refund_request(
    ticket_id: str,
    customer_id: str,
    amount: float,
    reason: str,
    workflow_id: str | None = None,
    *,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute customer billing refund and record resolution action."""
    try:
        numeric_amount = float(amount)
        if numeric_amount <= 0:
            raise ValueError
    except (ValueError, TypeError) as err:
        raise ValueError(
            f"Invalid refund amount '{amount}': must be a positive number."
        ) from err

    refund_ref_id = f"ref_{uuid.uuid4().hex[:12]}"
    effective_workflow_id = workflow_id or f"wf-ref-{uuid.uuid4().hex[:8]}"

    async def _execute(s: AsyncSession) -> dict[str, Any]:
        action = ResolutionAction(
            id=f"act-{uuid.uuid4().hex[:8]}",
            workflow_id=effective_workflow_id,
            ticket_id=ticket_id,
            action_name="create_refund_request",
            action_payload={
                "customer_id": customer_id,
                "amount": numeric_amount,
                "reason": reason,
                "refund_id": refund_ref_id,
            },
            status=ResolutionActionStatusEnum.EXECUTED.value,
            result={
                "status": "success",
                "refund_id": refund_ref_id,
                "amount": numeric_amount,
            },
        )
        s.add(action)
        await s.commit()

        return {
            "status": "executed",
            "action_name": "create_refund_request",
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "amount": numeric_amount,
            "reason": reason,
            "refund_id": refund_ref_id,
            "processed_at": datetime.now(UTC).isoformat(),
        }

    if session is not None:
        return await _execute(session)

    session_factory = get_session_factory()
    async with session_factory() as local_session:
        return await _execute(local_session)


@tool(
    name="reset_demo_setting",
    description="Reset a workspace demo configuration or policy setting; consequential action requiring human approval.",
    is_consequential=True,
    requires_approval=True,
)
async def reset_demo_setting(
    ticket_id: str,
    workspace_id: str,
    setting_name: str,
    reset_value: Any = None,
    workflow_id: str | None = None,
    *,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute workspace demo configuration reset and record resolution action."""
    effective_workflow_id = workflow_id or f"wf-reset-{uuid.uuid4().hex[:8]}"

    async def _execute(s: AsyncSession) -> dict[str, Any]:
        action = ResolutionAction(
            id=f"act-{uuid.uuid4().hex[:8]}",
            workflow_id=effective_workflow_id,
            ticket_id=ticket_id,
            action_name="reset_demo_setting",
            action_payload={
                "workspace_id": workspace_id,
                "setting_name": setting_name,
                "reset_value": reset_value,
            },
            status=ResolutionActionStatusEnum.EXECUTED.value,
            result={
                "status": "success",
                "setting_name": setting_name,
                "reset_value": reset_value,
            },
        )
        s.add(action)
        await s.commit()

        return {
            "status": "executed",
            "action_name": "reset_demo_setting",
            "ticket_id": ticket_id,
            "workspace_id": workspace_id,
            "setting_name": setting_name,
            "reset_value": reset_value,
            "processed_at": datetime.now(UTC).isoformat(),
        }

    if session is not None:
        return await _execute(session)

    session_factory = get_session_factory()
    async with session_factory() as local_session:
        return await _execute(local_session)


def register_write_tools(registry: ToolRegistry | None = None) -> list[ToolDefinition]:
    """Register all 4 write tools into the specified or default ToolRegistry."""
    target_registry = registry or get_tool_registry()
    tools = [
        update_ticket,
        create_escalation,
        create_refund_request,
        reset_demo_setting,
    ]
    registered = []
    for t in tools:
        registered.append(target_registry.register(t))
    return registered
