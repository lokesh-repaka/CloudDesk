"""Read-only support tools for CloudDesk.

Provides tools for:
- Customer 360 lookup (get_customer, get_subscription, get_ticket_history)
- Knowledge retrieval (search_docs)
- Incident and service status inspection (check_service_status)

All tools are decorated with @tool, permitted unattended (no human approval needed),
and integrated with ToolRegistry.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.database import get_session_factory
from backend.app.models.entities import Incident
from backend.app.rag.retriever import get_retriever
from backend.app.repositories.customer_repo import CustomerRepository
from backend.app.repositories.ticket_repo import TicketRepository
from backend.app.tools.base import ToolDefinition, tool
from backend.app.tools.registry import ToolRegistry, get_tool_registry

logger = logging.getLogger(__name__)


@tool(name="get_customer", description="Retrieve customer profile details by customer ID or email.")
async def get_customer(
    customer_id: str | None = None,
    email: str | None = None,
    *,
    session: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Retrieve customer record by unique ID or email address.

    Eager-loads customer metadata, tenant workspaces, and active subscription.
    """
    if not customer_id and not email:
        return None

    async def _fetch(s: AsyncSession) -> dict[str, Any] | None:
        repo = CustomerRepository(s)
        customer = None
        if customer_id:
            customer = await repo.get_with_workspaces_and_subscription(customer_id)
        if not customer and email:
            customer = await repo.get_by_email(email.strip().lower())
            if customer:
                customer = await repo.get_with_workspaces_and_subscription(customer.id)

        if not customer:
            return None

        active_sub = None
        if customer.subscriptions:
            for sub in customer.subscriptions:
                if sub.status == "active":
                    active_sub = {
                        "id": sub.id,
                        "plan": sub.plan,
                        "status": sub.status,
                        "seats": sub.seats,
                        "current_period_end": (
                            sub.current_period_end.isoformat()
                            if sub.current_period_end
                            else None
                        ),
                    }
                    break

        workspaces_data = []
        if customer.workspaces:
            for ws in customer.workspaces:
                workspaces_data.append({
                    "id": ws.id,
                    "name": ws.name,
                    "slug": ws.slug,
                    "storage_quota_bytes": ws.storage_quota_bytes,
                    "storage_used_bytes": ws.storage_used_bytes,
                })

        return {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "plan": customer.plan,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
            "workspaces": workspaces_data,
            "active_subscription": active_sub,
        }

    if session is not None:
        return await _fetch(session)

    session_factory = get_session_factory()
    async with session_factory() as local_session:
        return await _fetch(local_session)


@tool(name="get_subscription", description="Retrieve active subscription and tier details for a customer.")
async def get_subscription(
    customer_id: str,
    *,
    session: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Retrieve the current active subscription for a specified customer ID."""
    if not customer_id:
        return None

    async def _fetch(s: AsyncSession) -> dict[str, Any] | None:
        repo = CustomerRepository(s)
        sub = await repo.get_active_subscription(customer_id)
        if not sub:
            return None
        return {
            "id": sub.id,
            "customer_id": sub.customer_id,
            "plan": sub.plan,
            "status": sub.status,
            "seats": sub.seats,
            "current_period_end": (
                sub.current_period_end.isoformat() if sub.current_period_end else None
            ),
        }

    if session is not None:
        return await _fetch(session)

    session_factory = get_session_factory()
    async with session_factory() as local_session:
        return await _fetch(local_session)


@tool(name="get_ticket_history", description="Retrieve past support tickets and statuses for a customer.")
async def get_ticket_history(
    customer_id: str,
    limit: int = 5,
    *,
    session: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """Retrieve historical tickets for a customer, ordered latest first."""
    if not customer_id:
        return []

    safe_limit = max(1, min(limit, 50))

    async def _fetch(s: AsyncSession) -> list[dict[str, Any]]:
        repo = TicketRepository(s)
        tickets, _ = await repo.list_tickets(customer_id=customer_id, limit=safe_limit)
        return [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status,
                "severity": t.severity,
                "category": t.category,
                "channel": t.channel,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ]

    if session is not None:
        return await _fetch(session)

    session_factory = get_session_factory()
    async with session_factory() as local_session:
        return await _fetch(local_session)


@tool(name="search_docs", description="Search the CloudDesk knowledge base using hybrid dense/sparse retrieval.")
async def search_docs(
    query: str,
    category: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search published documentation and troubleshooting guides for relevant evidence."""
    if not query:
        return []

    # Bound inputs against excessive token/memory usage
    bounded_query = query[:50000].strip()
    safe_top_k = max(1, min(top_k, 20))

    retriever = get_retriever()
    results = await retriever.retrieve(
        query=bounded_query,
        category=category,
        top_k=safe_top_k,
        mode="hybrid",
    )
    return results


@tool(
    name="check_service_status",
    description="Check operational health and active incidents for CloudDesk platform services.",
)
async def check_service_status(
    service_name: str | None = None,
    *,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Check active platform infrastructure incidents and operational health status."""
    target_service = service_name.strip() if service_name else None
    active_incidents: list[dict[str, Any]] = []

    async def _query_db_incidents(s: AsyncSession) -> list[Incident]:
        stmt = select(Incident).where(
            Incident.status.in_(["investigating", "identified", "monitoring"])
        )
        if target_service:
            stmt = stmt.where(Incident.service == target_service)
        res = await s.execute(stmt)
        return list(res.scalars().all())

    db_incidents: list[Incident] = []
    if session is not None:
        db_incidents = await _query_db_incidents(session)
    else:
        try:
            session_factory = get_session_factory()
            async with session_factory() as local_session:
                db_incidents = await _query_db_incidents(local_session)
        except SQLAlchemyError as err:
            logger.debug("Database error querying incidents: %s", err)
            db_incidents = []

    if db_incidents:
        for inc in db_incidents:
            active_incidents.append({
                "id": inc.id,
                "title": inc.title,
                "service": inc.service,
                "status": inc.status,
                "severity": inc.severity,
                "impact_summary": inc.impact_summary,
            })
    else:
        # Fallback to sample_data/incidents.json for demo and offline test environments
        settings = get_settings()
        sample_file = Path(settings.SAMPLE_DATA_DIR) / "incidents.json"
        if sample_file.exists():
            try:
                raw_data = json.loads(sample_file.read_text(encoding="utf-8"))
                for inc in raw_data:
                    inc_status = inc.get("status", "").lower()
                    if inc_status in ("investigating", "identified", "monitoring"):
                        inc_service = inc.get("service", "")
                        if not target_service or inc_service == target_service:
                            active_incidents.append(inc)
            except (json.JSONDecodeError, OSError) as err:
                logger.debug("Failed reading sample incidents file: %s", err)

    # Determine overall service status
    has_critical = any(inc.get("severity") == "critical" for inc in active_incidents)
    if has_critical:
        status_code = "outage"
    elif active_incidents:
        status_code = "degraded"
    else:
        status_code = "operational"

    return {
        "service": target_service or "all",
        "status": status_code,
        "active_incidents": active_incidents,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def register_read_only_tools(registry: ToolRegistry | None = None) -> list[ToolDefinition]:
    """Register all 5 read-only tools into the specified or default ToolRegistry."""
    target_registry = registry or get_tool_registry()
    tools = [
        get_customer,
        get_subscription,
        get_ticket_history,
        search_docs,
        check_service_status,
    ]
    registered = []
    for t in tools:
        registered.append(target_registry.register(t))
    return registered
