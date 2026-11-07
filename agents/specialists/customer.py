"""Customer Specialist Agent (P9-3).

Implements the Customer Agent responsible for loading customer 360 dossiers,
subscription tiers, workspace quotas, historical ticket summaries, and long-term
memory notes adhering to CLAUDE.md §5 (F4), §7.1, §7.5, and AC-023, AC-026.
Non-negotiable rule: Strictly deterministic execution with zero LLM calls.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.prompts import CUSTOMER_AGENT_SYSTEM_PROMPT
from backend.app.schemas.common import CustomerPlanEnum
from backend.app.schemas.workflow import CustomerContext
from backend.app.tools.read_tools import (
    get_customer,
    get_subscription,
    get_ticket_history,
)
from memory.service import recall_customer

logger = logging.getLogger(__name__)

# Bounded retrieval limits to prevent CPU/memory exhaustion (CWE-400)
MAX_TICKET_HISTORY_LIMIT: int = 50
MAX_MEMORY_NOTES_LIMIT: int = 10


class CustomerAgent:
    """Specialist Customer Agent for aggregating customer 360 profile and memory context."""

    def __init__(self, system_prompt: str = CUSTOMER_AGENT_SYSTEM_PROMPT) -> None:
        self.system_prompt = system_prompt

    async def get_context(
        self,
        customer_id: str | None = None,
        email: str | None = None,
        *,
        session: AsyncSession | None = None,
        ticket_history_limit: int = 5,
        memory_limit: int = 10,
    ) -> CustomerContext:
        """Retrieve and synthesize customer profile, subscription, workspaces, tickets, and memory.

        Args:
            customer_id: Unique customer UUID.
            email: Primary customer contact email address.
            session: Optional active SQLAlchemy async database session.
            ticket_history_limit: Maximum recent tickets to retrieve (capped at 50).
            memory_limit: Maximum long-term memory notes to recall (capped at 10 per AC-022).

        Returns:
            Populated CustomerContext domain schema.

        Raises:
            ValueError: If neither customer_id nor email is provided, or customer not found.
        """
        # 1. Input validation (CWE-20)
        clean_cust_id = customer_id.strip() if customer_id else None
        clean_email = email.strip() if email else None
        if not clean_cust_id and not clean_email:
            raise ValueError(
                "Either customer_id or email must be provided to resolve customer context."
            )

        # 2. Customer profile & workspace retrieval (Read-only tool)
        customer_data = await get_customer(
            customer_id=clean_cust_id,
            email=clean_email,
            session=session,
        )
        if not customer_data:
            lookup_key = clean_cust_id or clean_email
            raise ValueError(f"Customer '{lookup_key}' not found.")

        resolved_customer_id = customer_data["id"]

        # 3. Active subscription inspection (Read-only tool)
        active_sub = await get_subscription(
            customer_id=resolved_customer_id,
            session=session,
        )

        # Plan resolution: active subscription plan takes precedence over profile plan
        raw_plan = (
            active_sub.get("plan")
            if (active_sub and active_sub.get("plan"))
            else customer_data.get("plan", "free")
        )
        try:
            plan_enum = CustomerPlanEnum(raw_plan.lower())
        except (ValueError, AttributeError):
            plan_enum = CustomerPlanEnum.FREE

        # 4. Workspace aggregation
        workspaces = customer_data.get("workspaces", [])
        workspace_count = len(workspaces)
        total_storage_quota_bytes = sum(
            int(ws.get("storage_quota_bytes") or ws.get("storage_limit_bytes") or 0)
            for ws in workspaces
        )
        total_storage_used_bytes = sum(
            int(ws.get("storage_used_bytes") or 0) for ws in workspaces
        )
        seats = (
            active_sub.get("seats")
            if (active_sub and active_sub.get("seats") is not None)
            else 1
        )
        primary_name = workspaces[0].get("name", "") if workspaces else ""

        workspace_summary: dict[str, Any] = {
            "workspace_count": workspace_count,
            "primary_workspace": primary_name,
            "total_storage_quota_bytes": total_storage_quota_bytes,
            "total_storage_used_bytes": total_storage_used_bytes,
            "seats": seats,
            "workspaces": workspaces,
        }

        # 5. Recent ticket history retrieval (Read-only tool, bounded limit)
        safe_ticket_limit = max(1, min(ticket_history_limit, MAX_TICKET_HISTORY_LIMIT))
        recent_tickets = await get_ticket_history(
            customer_id=resolved_customer_id,
            limit=safe_ticket_limit,
            session=session,
        )

        # 6. Long-term customer memory recall (CLAUDE.md §7.5, max 10 notes)
        safe_memory_limit = max(1, min(memory_limit, MAX_MEMORY_NOTES_LIMIT))
        memory_records = await recall_customer(
            customer_id=resolved_customer_id,
            limit=safe_memory_limit,
            session=session,
        )

        memory_notes: list[dict[str, Any]] = []
        for mem in memory_records:
            if hasattr(mem, "content"):
                mem_type = (
                    mem.memory_type.value
                    if hasattr(mem.memory_type, "value")
                    else str(mem.memory_type)
                )
                memory_notes.append(
                    {
                        "id": getattr(mem, "id", None),
                        "customer_id": getattr(mem, "customer_id", None),
                        "memory_type": mem_type,
                        "content": mem.content,
                        "created_at": (
                            mem.created_at.isoformat()
                            if getattr(mem, "created_at", None)
                            else None
                        ),
                    }
                )
            elif isinstance(mem, dict):
                memory_notes.append(mem)

        # 7. Construct isolated CustomerContext (AC-023, AC-026)
        return CustomerContext(
            customer_id=resolved_customer_id,
            name=customer_data["name"],
            email=customer_data["email"],
            plan=plan_enum,
            workspace_summary=workspace_summary,
            recent_tickets=recent_tickets,
            memory_notes=memory_notes,
        )

    async def run(
        self,
        customer_id: str | None = None,
        email: str | None = None,
        *,
        session: AsyncSession | None = None,
        ticket_history_limit: int = 5,
        memory_limit: int = 10,
    ) -> CustomerContext:
        """Execute CustomerAgent workflow node without LLM invocation (F4, CLAUDE.md §7.1).

        Returns:
            CustomerContext domain schema for LangGraph customer_context node.
        """
        return await self.get_context(
            customer_id=customer_id,
            email=email,
            session=session,
            ticket_history_limit=ticket_history_limit,
            memory_limit=memory_limit,
        )
