"""Support Tickets API Routes (P4-2).

Provides:
- POST /api/v1/tickets: Omnichannel ticket ingestion (email, chat, web, API)
- GET /api/v1/tickets: Queue listing with filtering and pagination
- GET /api/v1/tickets/{id}: Ticket detail dossier and message thread
- POST /api/v1/tickets/{id}/reply: Agent reply dispatch and status transition
- POST /api/v1/tickets/{id}/request-info: Customer clarification request
- POST /api/v1/tickets/{id}/escalate: Manual or policy ticket escalation
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.entities import Customer, Escalation, Ticket
from backend.app.repositories.customer_repo import CustomerRepository
from backend.app.repositories.ticket_repo import (
    TicketMessageRepository,
    TicketRepository,
)
from backend.app.schemas.common import (
    CategoryEnum,
    ChannelEnum,
    CustomerPlanEnum,
    EscalationStatusEnum,
    RoleEnum,
    SeverityEnum,
    TicketStatusEnum,
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
)

router = APIRouter(tags=["tickets"])


def _format_ticket_summary(ticket: Ticket, customer: Customer | None = None) -> TicketSummaryResponse:
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


def _format_ticket_detail(ticket: Ticket, customer: Customer | None = None) -> TicketDetailResponse:
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
        "channel": payload.channel.value if hasattr(payload.channel, "value") else str(payload.channel),
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
        severity=payload.severity.value if hasattr(payload.severity, "value") else str(payload.severity),
        status=EscalationStatusEnum.OPEN.value,
    )
    session.add(escalation)

    ticket.status = TicketStatusEnum.ESCALATED.value
    ticket.severity = payload.severity.value if hasattr(payload.severity, "value") else str(payload.severity)
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
