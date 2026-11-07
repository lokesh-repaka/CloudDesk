"""Customer Management & 360-Degree Dossier API Routes (P4-3).

Provides:
- GET /api/v1/customers: List customers with plan filtering and pagination
- POST /api/v1/customers: Register new customer entity with duplicate email protection
- GET /api/v1/customers/{id}: Comprehensive 360 dossier (workspaces, subscriptions, tickets, memory)
- POST /api/v1/customers/{id}/memory: Add persistent memory note with automated secret scrubbing (N7)
- GET /api/v1/customers/{id}/memory: List customer memory notes ordered newest first
"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.entities import Customer
from backend.app.repositories.customer_repo import CustomerRepository
from backend.app.repositories.memory_repo import CustomerMemoryRepository
from backend.app.repositories.ticket_repo import TicketRepository
from backend.app.schemas.common import CustomerPlanEnum, RoleEnum
from backend.app.schemas.customers import (
    CustomerCreate,
    CustomerDetailResponse,
    CustomerListResponse,
    CustomerMemoryCreate,
    CustomerMemoryResponse,
    CustomerSummaryResponse,
    SubscriptionResponse,
    WorkspaceResponse,
)
from backend.app.schemas.tickets import TicketSummaryResponse

router = APIRouter(tags=["customers"])

# Secret scrubbing regex patterns for N7 / US-022
CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
API_KEY_PATTERN = re.compile(r"(?:sk-|Bearer\s+|key-)[a-zA-Z0-9_\-]{16,}")
PASSWORD_PATTERN = re.compile(r"((?:password|passwd|pwd)\s*[:=]\s*)\S+", re.IGNORECASE)


def scrub_secrets(text: str) -> str:
    """Scrub sensitive credentials (credit cards, API keys, passwords) from memory text (N7)."""
    # 1. API keys / bearer tokens
    text = API_KEY_PATTERN.sub("[REDACTED]", text)
    # 2. Credit card numbers (13-16 digits with optional spaces or dashes)
    text = CARD_PATTERN.sub("[REDACTED]", text)
    # 3. Passwords in key-value forms
    text = PASSWORD_PATTERN.sub(r"\1[REDACTED]", text)
    return text


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    _current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    plan: Annotated[
        CustomerPlanEnum | None,
        Query(description="Filter customers by subscription plan tier"),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Row offset for pagination")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum items per page")
    ] = 50,
) -> CustomerListResponse:
    """Retrieve a paginated list of customers, optionally filtered by subscription plan."""
    repo = CustomerRepository(session)
    items, total = await repo.list_customers(
        plan=plan.value if plan else None,
        offset=offset,
        limit=limit,
    )
    return CustomerListResponse(
        items=[CustomerSummaryResponse.model_validate(c) for c in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post(
    "", response_model=CustomerSummaryResponse, status_code=status.HTTP_201_CREATED
)
async def create_customer(
    payload: CustomerCreate,
    _current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CustomerSummaryResponse:
    """Register a new customer entity. Rejects duplicate emails with HTTP 409 Conflict."""
    repo = CustomerRepository(session)
    existing = await repo.get_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer with email '{payload.email}' already registered",
        )

    customer = Customer(
        name=payload.name,
        email=payload.email,
        plan=payload.plan.value,
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return CustomerSummaryResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: str,
    _current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CustomerDetailResponse:
    """Retrieve 360-degree customer dossier for agent console (AC-020 to AC-023)."""
    customer_repo = CustomerRepository(session)
    customer = await customer_repo.get_with_workspaces_and_subscription(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )

    # Active subscription
    active_sub = await customer_repo.get_active_subscription(customer_id)
    active_subscription_res = (
        SubscriptionResponse.model_validate(active_sub) if active_sub else None
    )

    # Subscriptions & workspaces (eager-loaded on customer)
    subscriptions = [
        SubscriptionResponse.model_validate(s) for s in (customer.subscriptions or [])
    ]
    workspaces = [
        WorkspaceResponse.model_validate(w) for w in (customer.workspaces or [])
    ]

    # Recent tickets (isolated strictly to this customer, AC-023)
    ticket_repo = TicketRepository(session)
    recent_tickets_entities, _ = await ticket_repo.list_tickets(
        customer_id=customer_id,
        limit=10,
    )
    recent_tickets = [
        TicketSummaryResponse(
            id=t.id,
            customer_id=t.customer_id,
            assigned_to=t.assigned_to,
            subject=t.subject,
            status=t.status,
            severity=t.severity,
            category=t.category,
            channel=t.channel,
            resolution_summary=t.resolution_summary,
            created_at=t.created_at,
            updated_at=t.updated_at,
            customer_name=customer.name,
            customer_plan=customer.plan,
            customer_email=customer.email,
        )
        for t in recent_tickets_entities
    ]

    # Memory notes (up to 10 most recent, AC-022)
    mem_repo = CustomerMemoryRepository(session)
    recent_notes = await mem_repo.get_recent_notes(customer_id=customer_id, limit=10)
    memory_notes = [
        CustomerMemoryResponse.model_validate(note) for note in recent_notes
    ]

    return CustomerDetailResponse(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        plan=customer.plan,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        active_subscription=active_subscription_res,
        subscriptions=subscriptions,
        workspaces=workspaces,
        recent_tickets=recent_tickets,
        memory_notes=memory_notes,
    )


@router.post(
    "/{customer_id}/memory",
    response_model=CustomerMemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_customer_memory(
    customer_id: str,
    payload: CustomerMemoryCreate,
    _current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CustomerMemoryResponse:
    """Store a persistent memory note for a customer with automated secret scrubbing (N7 / AC-056)."""
    customer_repo = CustomerRepository(session)
    customer = await customer_repo.get(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )

    # Scrub sensitive secrets before storage (N7 / US-022)
    cleaned_content = scrub_secrets(payload.content)

    mem_repo = CustomerMemoryRepository(session)
    note = await mem_repo.add_memory_note(
        customer_id=customer_id,
        memory_type=payload.memory_type.value,
        content=cleaned_content,
    )
    await session.commit()
    return CustomerMemoryResponse.model_validate(note)


@router.get("/{customer_id}/memory", response_model=list[CustomerMemoryResponse])
async def list_customer_memory(
    customer_id: str,
    _current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CustomerMemoryResponse]:
    """Retrieve all historical memory notes for a customer ordered descending by creation date."""
    customer_repo = CustomerRepository(session)
    customer = await customer_repo.get(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )

    mem_repo = CustomerMemoryRepository(session)
    notes = await mem_repo.get_recent_notes(customer_id=customer_id, limit=50)
    return [CustomerMemoryResponse.model_validate(n) for n in notes]
