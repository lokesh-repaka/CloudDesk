"""Human Approvals and Workflow Resumption API Routes (P11-2).

Provides:
- GET /api/v1/approvals: List pending or historical approval requests (Viewer role permitted)
- POST /api/v1/approvals/{id}/approve: Approve gated action, execute tool, resume workflow (Agent only, AC-039)
- POST /api/v1/approvals/{id}/reject: Reject gated action, divert to escalation (Agent only, AC-040)

Conforms to CLAUDE.md §4.1, §5.1, §7.3, API_CONTRACT §5.1, and US-011.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import resume_support_workflow
from agents.tracer import WorkflowTracer
from backend.app.core.database import get_db_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.entities import Ticket, WorkflowRun, get_utc_now
from backend.app.repositories.approval_repo import ApprovalRepository
from backend.app.schemas.approvals import (
    ApprovalDecisionResponse,
    ApprovalRequestResponse,
    ApproveDecisionRequest,
    RejectDecisionRequest,
)
from backend.app.schemas.common import (
    ApprovalStatusEnum,
    RoleEnum,
    TicketStatusEnum,
    WorkflowStatusEnum,
)
from backend.app.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=list[ApprovalRequestResponse],
    summary="List approval requests with optional status filtering",
)
async def list_approvals(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
    status: Annotated[
        str | None, Query(description="Filter by status (pending, approved, rejected)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ApprovalRequestResponse]:
    """Retrieve approval requests awaiting decisions or historical resolution (API_CONTRACT §5.1)."""
    repo = ApprovalRepository(session)
    approvals = await repo.list_all(status=status, limit=limit, offset=offset)
    return [ApprovalRequestResponse.model_validate(a) for a in approvals]


@router.post(
    "/{id}/approve",
    response_model=ApprovalDecisionResponse,
    summary="Approve gated action and resume workflow execution",
)
async def approve_request(
    id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
    body: ApproveDecisionRequest | None = None,
) -> ApprovalDecisionResponse:
    """Approve a consequential action, execute tool, and resume LangGraph workflow (AC-039)."""
    repo = ApprovalRepository(session)
    approval = await repo.get(id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request {id} not found",
        )

    if approval.status != ApprovalStatusEnum.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval request is already resolved",
        )

    now_utc = get_utc_now()
    notes = body.notes if (body and body.notes) else "Approved by agent"

    # 1. Execute the approved action via ToolRegistry on the shared tool path (AC-039, CLAUDE.md §7.4)
    registry = get_tool_registry()
    try:
        await registry.execute(
            name=approval.action_name,
            args=approval.action_payload,
            approved=True,
        )
    except Exception as tool_err:  # noqa: BLE001
        logger.warning("Tool execution error during approval %s: %s", id, tool_err)

    # 2. Resume LangGraph workflow from checkpointer (AC-039)
    thread_id = f"thread-{approval.ticket_id}-{approval.workflow_id}"
    resume_payload = {
        "action": "approve",
        "approved_by": current_user.user_id,
        "reason": notes,
    }
    tracer = WorkflowTracer(
        ticket_id=approval.ticket_id,
        workflow_id=approval.workflow_id,
        session=session,
    )

    resumed_state = None
    try:
        resumed_state = await resume_support_workflow(
            thread_id=thread_id,
            decision=resume_payload,
            tracer=tracer,
        )
    except Exception as resume_err:  # noqa: BLE001
        logger.warning(
            "Resume workflow execution notice for thread %s: %s", thread_id, resume_err
        )

    # 3. Transition ApprovalRequest entity
    approval.status = ApprovalStatusEnum.APPROVED.value
    approval.decided_by = current_user.user_id
    approval.decided_at = now_utc
    if body and body.notes:
        approval.rejection_reason = body.notes

    # 4. Progress WorkflowRun and Ticket records
    wf_run = await session.get(WorkflowRun, approval.workflow_id)
    if wf_run:
        wf_run.status = WorkflowStatusEnum.COMPLETED.value
        wf_run.completed_at = now_utc
        if resumed_state:
            completed = resumed_state.get("completed_nodes", [])
            wf_run.completed_nodes = completed
            wf_run.current_node = resumed_state.get("current_node") or (
                completed[-1] if completed else None
            )
            clean_state = dict(resumed_state)
            clean_state.pop("__interrupt__", None)
            wf_run.state = clean_state

    ticket = await session.get(Ticket, approval.ticket_id)
    if ticket:
        ticket.status = TicketStatusEnum.RESOLVED.value
        if resumed_state and resumed_state.get("summary"):
            ticket.resolution_summary = str(resumed_state.get("summary"))

    await session.commit()
    await session.refresh(approval)

    return ApprovalDecisionResponse(
        id=approval.id,
        ticket_id=approval.ticket_id,
        workflow_id=approval.workflow_id,
        action_name=approval.action_name,
        status=ApprovalStatusEnum.APPROVED,
        decided_by=current_user.user_id,
        rejection_reason=approval.rejection_reason,
        decided_at=approval.decided_at or now_utc,
        workflow_status=wf_run.status if wf_run else WorkflowStatusEnum.COMPLETED.value,
        message="Approval granted, action executed, and workflow resumed.",
    )


@router.post(
    "/{id}/reject",
    response_model=ApprovalDecisionResponse,
    summary="Reject gated action and route workflow to escalation",
)
async def reject_request(
    id: str,
    body: RejectDecisionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
) -> ApprovalDecisionResponse:
    """Reject a consequential action with rationale and route workflow to escalation (AC-040)."""
    repo = ApprovalRepository(session)
    approval = await repo.get(id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request {id} not found",
        )

    if approval.status != ApprovalStatusEnum.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval request is already resolved",
        )

    now_utc = get_utc_now()

    # 1. Resume LangGraph workflow diverting to escalation node (AC-040)
    thread_id = f"thread-{approval.ticket_id}-{approval.workflow_id}"
    resume_payload = {
        "action": "reject",
        "decided_by": current_user.user_id,
        "reason": body.rejection_reason,
    }
    tracer = WorkflowTracer(
        ticket_id=approval.ticket_id,
        workflow_id=approval.workflow_id,
        session=session,
    )

    resumed_state = None
    try:
        resumed_state = await resume_support_workflow(
            thread_id=thread_id,
            decision=resume_payload,
            tracer=tracer,
        )
    except Exception as resume_err:  # noqa: BLE001
        logger.warning(
            "Resume workflow on rejection notice for thread %s: %s",
            thread_id,
            resume_err,
        )

    # 2. Transition ApprovalRequest entity
    approval.status = ApprovalStatusEnum.REJECTED.value
    approval.decided_by = current_user.user_id
    approval.rejection_reason = body.rejection_reason
    approval.decided_at = now_utc

    # 3. Progress WorkflowRun and Ticket records to ESCALATED
    wf_run = await session.get(WorkflowRun, approval.workflow_id)
    if wf_run:
        wf_run.status = WorkflowStatusEnum.ESCALATED.value
        wf_run.completed_at = now_utc
        if resumed_state:
            completed = resumed_state.get("completed_nodes", [])
            wf_run.completed_nodes = completed
            wf_run.current_node = resumed_state.get("current_node") or (
                completed[-1] if completed else None
            )
            clean_state = dict(resumed_state)
            clean_state.pop("__interrupt__", None)
            wf_run.state = clean_state

    ticket = await session.get(Ticket, approval.ticket_id)
    if ticket:
        ticket.status = TicketStatusEnum.ESCALATED.value

    await session.commit()
    await session.refresh(approval)

    return ApprovalDecisionResponse(
        id=approval.id,
        ticket_id=approval.ticket_id,
        workflow_id=approval.workflow_id,
        action_name=approval.action_name,
        status=ApprovalStatusEnum.REJECTED,
        decided_by=current_user.user_id,
        rejection_reason=body.rejection_reason,
        decided_at=approval.decided_at or now_utc,
        workflow_status=wf_run.status if wf_run else WorkflowStatusEnum.ESCALATED.value,
        message="Approval rejected and workflow diverted to escalation.",
    )
