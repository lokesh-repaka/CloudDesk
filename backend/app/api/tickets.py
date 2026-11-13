"""Support Tickets API Routes (P4-2).

Provides:
- POST /api/v1/tickets: Omnichannel ticket ingestion (email, chat, web, API)
- GET /api/v1/tickets: Queue listing with filtering and pagination
- GET /api/v1/tickets/{id}: Ticket detail dossier and message thread
- POST /api/v1/tickets/{id}/reply: Agent reply dispatch and status transition
- POST /api/v1/tickets/{id}/request-info: Customer clarification request
- POST /api/v1/tickets/{id}/escalate: Manual or policy ticket escalation
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import run_support_workflow
from agents.state import create_initial_support_state
from agents.tracer import WorkflowTracer
from backend.app.core.database import get_db_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.entities import (
    ApprovalRequest,
    Customer,
    Escalation,
    Ticket,
    WorkflowEvent,
    WorkflowRun,
    get_utc_now,
)
from backend.app.repositories.customer_repo import CustomerRepository
from backend.app.repositories.ticket_repo import (
    TicketMessageRepository,
    TicketRepository,
)
from backend.app.schemas.common import (
    ApprovalStatusEnum,
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    EscalationStatusEnum,
    RoleEnum,
    SeverityEnum,
    TicketStatusEnum,
    WorkflowStatusEnum,
)
from backend.app.schemas.tickets import (
    EscalateRequest,
    EscalateResponse,
    ReplyCreate,
    ReplyResponse,
    RequestInfoCreate,
    TicketCreate,
    TicketDetailResponse,
    TicketListResponse,
    TicketMessageResponse,
    TicketSummaryResponse,
    WorkflowEventResponse,
    WorkflowRunResponse,
    WorkflowStateResponse,
)

router = APIRouter(tags=["tickets"])


def _format_ticket_summary(
    ticket: Ticket, customer: Customer | None = None
) -> TicketSummaryResponse:
    """Format ORM Ticket entity into TicketSummaryResponse envelope safely without lazy I/O."""
    cust = customer if customer is not None else ticket.__dict__.get("customer")
    return TicketSummaryResponse(
        id=ticket.id,
        customer_id=ticket.customer_id,
        assigned_to=ticket.assigned_to,
        subject=ticket.subject,
        status=TicketStatusEnum(ticket.status),
        severity=SeverityEnum(ticket.severity),
        category=CategoryEnum(ticket.category),
        channel=ChannelEnum(ticket.channel),
        resolution_summary=ticket.resolution_summary,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        customer_name=cust.name if cust else None,
        customer_plan=CustomerPlanEnum(cust.plan) if cust and cust.plan else None,
        customer_email=cust.email if cust else None,
    )


def _format_ticket_detail(
    ticket: Ticket, customer: Customer | None = None
) -> TicketDetailResponse:
    """Format ORM Ticket entity with conversation messages into TicketDetailResponse."""
    cust = customer if customer is not None else ticket.__dict__.get("customer")
    messages_list = ticket.__dict__.get("messages") or []
    messages = [
        TicketMessageResponse(
            id=m.id,
            ticket_id=m.ticket_id,
            author_role=m.author_role,
            author_id=m.author_id,
            body=m.body,
            created_at=m.created_at,
        )
        for m in messages_list
    ]

    active_wf_id = None
    runs = ticket.__dict__.get("runs")
    if runs:
        active_wf_id = runs[-1].id

    return TicketDetailResponse(
        id=ticket.id,
        customer_id=ticket.customer_id,
        assigned_to=ticket.assigned_to,
        subject=ticket.subject,
        status=TicketStatusEnum(ticket.status),
        severity=SeverityEnum(ticket.severity),
        category=CategoryEnum(ticket.category),
        channel=ChannelEnum(ticket.channel),
        resolution_summary=ticket.resolution_summary,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        customer_name=cust.name if cust else None,
        customer_plan=CustomerPlanEnum(cust.plan) if cust and cust.plan else None,
        customer_email=cust.email if cust else None,
        messages=messages,
        active_workflow_id=active_wf_id,
    )


@router.post(
    "",
    response_model=TicketDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Omnichannel ticket intake",
)
async def create_ticket(
    payload: TicketCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TicketDetailResponse:
    """Ingest a new support ticket from email, chat, web, or API.

    Atomically verifies the customer exists, creates the parent ticket record,
    and appends the initial customer message (AC-001, AC-003, AC-005).
    """
    customer_repo = CustomerRepository(session)
    customer = await customer_repo.get(payload.customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {payload.customer_id} not found",
        )

    ticket_repo = TicketRepository(session)
    ticket_data = {
        "customer_id": payload.customer_id,
        "subject": payload.subject,
        "channel": payload.channel.value
        if hasattr(payload.channel, "value")
        else str(payload.channel),
        "status": TicketStatusEnum.NEW.value,
        "severity": SeverityEnum.MEDIUM.value,
        "category": CategoryEnum.OTHER.value,
    }

    ticket = await ticket_repo.create_with_initial_message(
        ticket_data=ticket_data,
        initial_message=payload.body,
        sender_id=payload.customer_id,
    )
    await session.commit()

    # Re-fetch with eager loaded relations
    full_ticket = await ticket_repo.get_with_messages(ticket.id)
    return _format_ticket_detail(full_ticket or ticket, customer=customer)


@router.get(
    "",
    response_model=TicketListResponse,
    summary="List and filter support ticket queues",
)
async def list_tickets(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
    status_filter: Annotated[TicketStatusEnum | None, Query(alias="status")] = None,
    severity_filter: Annotated[SeverityEnum | None, Query(alias="severity")] = None,
    category_filter: Annotated[CategoryEnum | None, Query(alias="category")] = None,
    plan_filter: Annotated[CustomerPlanEnum | None, Query(alias="plan")] = None,
    customer_id: Annotated[str | None, Query()] = None,
    assigned_to: Annotated[str | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TicketListResponse:
    """Retrieve a paginated queue of support tickets matching filter criteria (AC-007, AC-011)."""
    ticket_repo = TicketRepository(session)
    items, total = await ticket_repo.list_tickets(
        status=status_filter.value if status_filter else None,
        severity=severity_filter.value if severity_filter else None,
        category=category_filter.value if category_filter else None,
        plan=plan_filter.value if plan_filter else None,
        customer_id=customer_id,
        assigned_to=assigned_to,
        offset=offset,
        limit=limit,
    )

    formatted_items = [_format_ticket_summary(t) for t in items]
    return TicketListResponse(
        items=formatted_items,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketDetailResponse,
    summary="Get complete ticket dossier and conversation thread",
)
async def get_ticket(
    ticket_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
) -> TicketDetailResponse:
    """Retrieve ticket details including messages and customer dossier."""
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_with_messages(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )
    return _format_ticket_detail(ticket)


@router.post(
    "/{ticket_id}/reply",
    response_model=ReplyResponse,
    summary="Dispatch agent reply to customer",
)
async def reply_to_ticket(
    ticket_id: str,
    payload: ReplyCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
) -> ReplyResponse:
    """Send human-verified agent reply to customer and update ticket status (AC-052)."""
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    msg_repo = TicketMessageRepository(session)
    msg = await msg_repo.add_message(
        ticket_id=ticket.id,
        author_role="agent",
        author_id=current_user.user_id,
        body=payload.message,
    )

    ticket.status = TicketStatusEnum.WAITING_ON_CUSTOMER.value
    await session.commit()

    return ReplyResponse(
        ticket_id=ticket.id,
        message_id=msg.id,
        status=TicketStatusEnum.WAITING_ON_CUSTOMER,
    )


@router.post(
    "/{ticket_id}/request-info",
    response_model=ReplyResponse,
    summary="Request clarifying information from customer",
)
async def request_info(
    ticket_id: str,
    payload: RequestInfoCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
) -> ReplyResponse:
    """Dispatch clarification request to customer and set ticket to waiting_on_customer (AC-054)."""
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    msg_repo = TicketMessageRepository(session)
    msg = await msg_repo.add_message(
        ticket_id=ticket.id,
        author_role="agent",
        author_id=current_user.user_id,
        body=payload.question,
    )

    ticket.status = TicketStatusEnum.WAITING_ON_CUSTOMER.value
    await session.commit()

    return ReplyResponse(
        ticket_id=ticket.id,
        message_id=msg.id,
        status=TicketStatusEnum.WAITING_ON_CUSTOMER,
    )


@router.post(
    "/{ticket_id}/escalate",
    response_model=EscalateResponse,
    summary="Escalate ticket to a specialized team",
)
async def escalate_ticket(
    ticket_id: str,
    payload: EscalateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
) -> EscalateResponse:
    """Escalate ticket to a target team with documented policy reason (AC-045)."""
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    escalation = Escalation(
        ticket_id=ticket.id,
        target_team=payload.target_team,
        policy_reason=payload.policy_reason,
        severity=payload.severity.value
        if hasattr(payload.severity, "value")
        else str(payload.severity),
        status=EscalationStatusEnum.OPEN.value,
    )
    session.add(escalation)

    ticket.status = TicketStatusEnum.ESCALATED.value
    ticket.severity = (
        payload.severity.value
        if hasattr(payload.severity, "value")
        else str(payload.severity)
    )
    await session.commit()
    await session.refresh(escalation)

    return EscalateResponse(
        escalation_id=escalation.id,
        ticket_id=ticket.id,
        target_team=escalation.target_team,
        policy_reason=escalation.policy_reason,
        severity=payload.severity,
        status=escalation.status,
        created_at=escalation.created_at,
    )


# ============================================================================
# Autonomous LangGraph Workflow Run & State Polling (P10-5)
# ============================================================================


@router.post(
    "/{ticket_id}/run",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger autonomous LangGraph agent workflow",
)
async def run_ticket_workflow(
    ticket_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
) -> WorkflowRunResponse:
    """Initiate an autonomous LangGraph agent workflow run for a ticket (AC-012, API_CONTRACT §3.4)."""
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_with_messages(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    if ticket.status == TicketStatusEnum.WAITING_ON_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket is already waiting on approval",
        )

    wf_id = f"wf-{uuid.uuid4().hex[:12]}"
    now_utc = get_utc_now()
    wf_run = WorkflowRun(
        id=wf_id,
        ticket_id=ticket.id,
        status=WorkflowStatusEnum.RUNNING.value,
        current_node="understand_ticket",
        completed_nodes=[],
        state={},
        started_at=now_utc,
    )
    session.add(wf_run)
    ticket.status = TicketStatusEnum.IN_PROGRESS.value
    await session.commit()

    # Extract ticket text and customer plan
    text = ""
    if ticket.messages:
        text = "\n\n".join(m.body for m in ticket.messages if m.body)
    if not text:
        text = ticket.subject

    plan_name = "free"
    if ticket.customer and ticket.customer.plan:
        plan_name = (
            ticket.customer.plan.value
            if hasattr(ticket.customer.plan, "value")
            else str(ticket.customer.plan)
        )

    initial_state = create_initial_support_state(
        ticket_id=ticket.id,
        customer_id=ticket.customer_id,
        subject=ticket.subject,
        text=text,
        customer_plan=plan_name,
        workflow_id=wf_id,
    )

    try:
        tracer = WorkflowTracer(ticket_id=ticket.id, workflow_id=wf_id, session=session)
        final_state = await run_support_workflow(
            initial_state,
            thread_id=f"thread-{ticket.id}-{wf_id}",
            tracer=tracer,
        )

        completed = final_state.get("completed_nodes", [])
        wf_run.completed_nodes = completed
        wf_run.current_node = final_state.get("current_node") or (
            completed[-1] if completed else None
        )
        wf_run.state = final_state
        wf_run.completed_at = get_utc_now()

        if final_state.get("approval_required"):
            wf_run.status = WorkflowStatusEnum.WAITING_ON_APPROVAL.value
            ticket.status = TicketStatusEnum.WAITING_ON_APPROVAL.value

            # Persist ApprovalRequest in database (AC-036)
            app_req_data = final_state.get("approval_request") or {}
            tool_name = app_req_data.get("tool_name") or "consequential_action"
            action_payload = app_req_data.get("arguments") or {}

            # Idempotently check if an approval request already exists for this workflow
            stmt = select(ApprovalRequest).where(
                ApprovalRequest.ticket_id == ticket.id,
                ApprovalRequest.workflow_id == wf_id,
            )
            existing_appr = (await session.execute(stmt)).scalars().first()
            if existing_appr is None:
                new_appr = ApprovalRequest(
                    id=f"appr-{uuid.uuid4().hex[:12]}",
                    ticket_id=ticket.id,
                    workflow_id=wf_id,
                    action_name=tool_name,
                    action_payload=action_payload,
                    status=ApprovalStatusEnum.PENDING.value,
                )
                session.add(new_appr)
        elif final_state.get("escalation_required"):
            wf_run.status = WorkflowStatusEnum.ESCALATED.value
            ticket.status = TicketStatusEnum.ESCALATED.value
            # Ensure open escalation record exists (AC-044)
            esc_stmt = select(Escalation).where(
                Escalation.ticket_id == ticket.id,
                Escalation.status == EscalationStatusEnum.OPEN.value,
            )
            existing_esc = (await session.execute(esc_stmt)).scalars().first()
            if existing_esc is None:
                new_esc = Escalation(
                    ticket_id=ticket.id,
                    workflow_id=wf_id,
                    target_team=final_state.get("escalation_team") or "Engineering",
                    policy_reason=final_state.get("escalation_reason")
                    or "Policy escalation rule triggered",
                    severity=ticket.severity or "high",
                    status=EscalationStatusEnum.OPEN.value,
                )
                session.add(new_esc)
        else:
            wf_run.status = WorkflowStatusEnum.COMPLETED.value

        if final_state.get("summary"):
            ticket.resolution_summary = str(final_state.get("summary"))

        await session.commit()
    except Exception as exc:  # noqa: BLE001
        wf_run.status = WorkflowStatusEnum.FAILED.value
        wf_run.error = str(exc)
        await session.commit()

    return WorkflowRunResponse(
        ticket_id=ticket.id,
        workflow_id=wf_id,
        status=WorkflowStatusEnum(wf_run.status),
        started_at=wf_run.started_at,
    )


@router.get(
    "/{ticket_id}/workflow",
    response_model=WorkflowStateResponse,
    summary="Poll LangGraph runtime workflow state",
)
async def get_ticket_workflow_state(
    ticket_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
) -> WorkflowStateResponse:
    """Poll the active or completed LangGraph workflow execution state for a ticket (AC-060, AC-061)."""
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    stmt = (
        select(WorkflowRun)
        .where(WorkflowRun.ticket_id == ticket_id)
        .order_by(WorkflowRun.created_at.desc())
    )
    result = await session.execute(stmt)
    wf_run = result.scalars().first()

    if wf_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run for ticket {ticket_id} not found",
        )

    state = wf_run.state or {}

    cls_data = state.get("classification")
    if not isinstance(cls_data, dict) and state.get("category"):
        cls_data = {"category": state.get("category")}

    sev_data = state.get("severity_assessment")
    if not isinstance(sev_data, dict):
        if state.get("severity"):
            sev_data = {"severity": state.get("severity")}
        else:
            sev_data = None

    esc_data = state.get("escalation_decision")
    if not isinstance(esc_data, dict) and state.get("escalation_required"):
        esc_data = {
            "escalation_required": state.get("escalation_required"),
            "target_team": state.get("escalation_team"),
            "reason": state.get("escalation_reason"),
        }

    return WorkflowStateResponse(
        ticket_id=wf_run.ticket_id,
        workflow_id=wf_run.id,
        status=WorkflowStatusEnum(wf_run.status),
        current_node=wf_run.current_node,
        completed_nodes=wf_run.completed_nodes or [],
        classification=cls_data,
        severity=sev_data,
        diagnosis=state.get("diagnosis")
        if isinstance(state.get("diagnosis"), dict)
        else None,
        resolution_plan=state.get("resolution_plan")
        if isinstance(state.get("resolution_plan"), dict)
        else None,
        escalation=esc_data,
        token_usage=state.get("token_usage") or {},
        error=wf_run.error,
    )


@router.get(
    "/{ticket_id}/events",
    response_model=list[WorkflowEventResponse],
    summary="Retrieve workflow execution telemetry timeline",
)
async def get_ticket_events(
    ticket_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
) -> list[WorkflowEventResponse]:
    """Retrieve fine-grained telemetry events for a ticket's workflow runs (F13, AC-060)."""
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    stmt = (
        select(WorkflowEvent)
        .where(WorkflowEvent.ticket_id == ticket_id)
        .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    return [
        WorkflowEventResponse(
            id=event.id,
            workflow_id=event.workflow_id,
            ticket_id=event.ticket_id,
            event_type=event.event_type,
            node_name=event.node_name,
            data=event.payload or {},
            duration_ms=event.duration_ms,
            tokens_used=event.tokens_used,
            cost_estimate=event.cost_estimate,
            created_at=event.created_at,
        )
        for event in events
    ]
