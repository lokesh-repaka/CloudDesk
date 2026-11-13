"""Escalations API Router (P11-3).

Provides:
- GET /api/v1/escalations: Dedicated escalation queue and status tracking (Viewer / Agent, API_CONTRACT §2).
- GET /api/v1/escalations/{id}: Detail inspection of an escalation record (Viewer).
- PATCH /api/v1/escalations/{id}: Update escalation status (Agent only, RBAC).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories.escalation_repo import EscalationRepository
from backend.app.schemas.common import RoleEnum
from backend.app.schemas.escalations import (
    EscalationResponse,
    EscalationStatusUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["escalations"])


@router.get(
    "",
    response_model=list[EscalationResponse],
    summary="List ticket escalations with optional filtering",
)
async def list_escalations(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
    status: str | None = Query(
        None, description="Filter by status (open, in_review, resolved, dismissed)"
    ),
    target_team: str | None = Query(
        None,
        description="Filter by designated team (Security, Billing, Engineering, Legal)",
    ),
    ticket_id: str | None = Query(
        None, description="Filter by specific ticket ID (e.g. CD-1005)"
    ),
    limit: int = Query(50, ge=1, le=100, description="Pagination record ceiling"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> list[EscalationResponse]:
    """Retrieve escalations queue with optional filtering by status, team, or ticket (API_CONTRACT §2)."""
    repo = EscalationRepository(session)
    items = await repo.list_all(
        status=status,
        target_team=target_team,
        ticket_id=ticket_id,
        limit=limit,
        offset=offset,
    )
    return [EscalationResponse.model_validate(item) for item in items]


@router.get(
    "/{escalation_id}",
    response_model=EscalationResponse,
    summary="Get single escalation record by ID",
)
async def get_escalation(
    escalation_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
) -> EscalationResponse:
    """Retrieve detailed metadata for an escalation by ID."""
    repo = EscalationRepository(session)
    item = await repo.get(escalation_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Escalation {escalation_id} not found",
        )
    return EscalationResponse.model_validate(item)


@router.patch(
    "/{escalation_id}",
    response_model=EscalationResponse,
    summary="Update escalation status",
)
async def update_escalation_status(
    escalation_id: str,
    payload: EscalationStatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.AGENT))],
) -> EscalationResponse:
    """Update lifecycle status of an escalation (Agent only, AC-044)."""
    repo = EscalationRepository(session)
    updated = await repo.update_status(
        escalation_id=escalation_id,
        new_status=payload.status.value,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Escalation {escalation_id} not found",
        )
    return EscalationResponse.model_validate(updated)
