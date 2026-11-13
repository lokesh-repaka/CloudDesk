"""Knowledge Specialist Agent (P9-4).

Implements the Knowledge Agent responsible for dense/sparse hybrid knowledge retrieval,
citation synthesis, and similar historical resolved case matching using Jaccard token overlap
adhering to CLAUDE.md §5 (F6), §7.1, §8, and AC-027, AC-028.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from agents.prompts import KNOWLEDGE_AGENT_SYSTEM_PROMPT
from backend.app.core.config import get_settings
from backend.app.core.database import get_session_factory
from backend.app.core.guardrails import scan_for_injection
from backend.app.models.entities import Ticket
from backend.app.schemas.common import TicketStatusEnum
from backend.app.schemas.workflow import Evidence, PreviousCase
from backend.app.tools.read_tools import search_docs

logger = logging.getLogger(__name__)

# Bounded inputs against resource exhaustion (CWE-400)
MAX_QUERY_LENGTH: int = 50_000
MAX_TOP_K_EVIDENCE: int = 10
MAX_SIMILAR_CASES_LIMIT: int = 20

# Common non-informative stopwords excluded from Jaccard token sets
_STOP_WORDS: set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
    "i",
    "we",
    "our",
    "you",
    "your",
}


def _tokenize_for_jaccard(text: str) -> set[str]:
    """Extract normalized alphanumeric word token set for Jaccard overlap computation."""
    if not text:
        return set()
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS}


def _read_sample_tickets(path: Path) -> list[Any]:
    """Synchronous file reader dispatched to worker thread via asyncio.to_thread."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class KnowledgeAgent:
    """Specialist Knowledge Agent for documentation search and historical case retrieval."""

    def __init__(self, system_prompt: str = KNOWLEDGE_AGENT_SYSTEM_PROMPT) -> None:
        self.system_prompt = system_prompt

    async def retrieve_evidence(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 3,
    ) -> list[Evidence]:
        """Search documentation and retrieve authoritative evidence citations (CLAUDE.md §8, AC-027).

        Args:
            query: User/ticket issue description.
            category: Optional ticket category for heuristic reranking boost.
            top_k: Number of evidence chunks to retrieve (capped at 10).

        Returns:
            List of Evidence schemas with canonical citations.
        """
        if not query or not query.strip():
            return []

        # 1. Guardrail scan & query bounds (CWE-116, CWE-400)
        bounded_query = query[:MAX_QUERY_LENGTH].strip()
        injection_scan = scan_for_injection(bounded_query)
        if injection_scan.is_suspicious:
            logger.warning(
                "Prompt injection indicator in knowledge query (patterns=%s); treating strictly as passive query text.",
                injection_scan.detected_patterns,
            )

        safe_top_k = max(1, min(top_k, MAX_TOP_K_EVIDENCE))

        # 2. Invoke hybrid retriever via search_docs tool
        raw_results = await search_docs(
            query=bounded_query,
            category=category,
            top_k=safe_top_k,
        )

        evidence_list: list[Evidence] = []
        for item in raw_results:
            try:
                evidence_list.append(Evidence.model_validate(item))
            except (ValidationError, TypeError, ValueError) as err:
                logger.warning(
                    "Skipping malformed evidence chunk from retriever: %s", err
                )

        return evidence_list

    async def similar_cases(
        self,
        text: str,
        category: str | None = None,
        limit: int = 3,
        threshold: float = 0.05,
        *,
        session: AsyncSession | None = None,
        candidate_tickets: Sequence[Ticket | dict[str, Any]] | None = None,
        exclude_ticket_id: str | None = None,
    ) -> list[PreviousCase]:
        """Find previously resolved historical tickets using Jaccard token overlap (F6, AC-028).

        Args:
            text: Current ticket content / subject text.
            category: Optional category filter / boost.
            limit: Maximum number of similar cases to return (default 3, max 20).
            threshold: Minimum Jaccard similarity score to consider (default 0.05).
            session: Optional database session for loading candidate tickets.
            candidate_tickets: Optional pre-loaded ticket candidates (useful for unit tests & customer context).
            exclude_ticket_id: Ticket ID to exclude from similarity results (prevents self-matching).

        Returns:
            Ranked list of PreviousCase domain models.
        """
        query_tokens = _tokenize_for_jaccard(text)
        if not query_tokens:
            return []

        safe_limit = max(1, min(limit, MAX_SIMILAR_CASES_LIMIT))

        # 1. Obtain candidates
        candidates = await self._load_candidate_tickets(
            session=session, candidate_tickets=candidate_tickets
        )
        if not candidates:
            return []

        scored_cases: list[tuple[float, PreviousCase]] = []
        clean_category = category.strip().lower() if category else None

        for cand in candidates:
            # Extract attributes regardless of dict or ORM entity
            cand_id = (
                cand.get("id") if isinstance(cand, dict) else getattr(cand, "id", "")
            )
            if exclude_ticket_id and cand_id == exclude_ticket_id:
                continue

            cand_subject = (
                cand.get("subject", "")
                if isinstance(cand, dict)
                else getattr(cand, "subject", "")
            )
            cand_cat = (
                cand.get("category", "")
                if isinstance(cand, dict)
                else getattr(cand, "category", "")
            )
            cand_status = (
                cand.get("status", "")
                if isinstance(cand, dict)
                else getattr(cand, "status", "")
            )
            cand_res = (
                cand.get("resolution_summary", "")
                if isinstance(cand, dict)
                else getattr(cand, "resolution_summary", "")
            )
            cand_actions = (
                cand.get("actions", [])
                if isinstance(cand, dict)
                else getattr(cand, "actions", [])
            )
            if not isinstance(cand_actions, list):
                cand_actions = []

            # Focus candidate matching on subject, category, and resolution notes
            cand_corpus = f"{cand_subject} {cand_cat} {cand_res or ''}"
            cand_tokens = _tokenize_for_jaccard(cand_corpus)
            if not cand_tokens:
                continue

            # Jaccard overlap formula: |A ∩ B| / |A ∪ B|
            intersection = len(query_tokens & cand_tokens)
            union = len(query_tokens | cand_tokens)
            jaccard = intersection / union if union > 0 else 0.0

            # Category concordance boost
            score = jaccard
            if clean_category and cand_cat.lower() == clean_category:
                score += 0.05

            score = round(min(1.0, score), 3)

            if score >= threshold:
                default_res = (
                    cand_res
                    if (cand_res and cand_res.strip())
                    else f"Ticket {cand_id} marked as {cand_status}."
                )
                prev_case = PreviousCase(
                    ticket_id=cand_id,
                    subject=cand_subject,
                    category=cand_cat,
                    similarity_score=score,
                    resolution=default_res,
                    actions=cand_actions,
                )
                scored_cases.append((score, prev_case))

        # Sort highest similarity first
        scored_cases.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored_cases[:safe_limit]]

    async def _load_candidate_tickets(
        self,
        session: AsyncSession | None = None,
        candidate_tickets: Sequence[Ticket | dict[str, Any]] | None = None,
    ) -> list[Any]:
        """Helper to resolve ticket candidates from parameter, database, or sample fixtures."""
        if candidate_tickets is not None:
            return list(candidate_tickets)

        # Query database session if available
        if session is not None:
            stmt = select(Ticket).where(
                Ticket.status.in_(
                    [
                        TicketStatusEnum.RESOLVED.value,
                        TicketStatusEnum.CLOSED.value,
                    ]
                )
            )
            res = (await session.execute(stmt)).scalars().all()
            if res:
                return list(res)

        # Fallback to local session factory or sample dataset
        try:
            session_factory = get_session_factory()
            async with session_factory() as local_session:
                stmt = select(Ticket).where(
                    Ticket.status.in_(
                        [
                            TicketStatusEnum.RESOLVED.value,
                            TicketStatusEnum.CLOSED.value,
                        ]
                    )
                )
                res = (await local_session.execute(stmt)).scalars().all()
                if res:
                    return list(res)
        except (SQLAlchemyError, RuntimeError) as err:
            logger.debug(
                "Database query for ticket candidates failed (%s); loading from sample_data/tickets.json",
                err,
            )

        # Static sample data fallback
        settings = get_settings()
        sample_path = Path(settings.SAMPLE_DATA_DIR) / "tickets.json"
        if sample_path.is_file():
            try:
                return await asyncio.to_thread(_read_sample_tickets, sample_path)
            except (OSError, json.JSONDecodeError) as read_err:
                logger.warning("Failed to read sample tickets fallback: %s", read_err)

        return []

    async def run(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 3,
        *,
        session: AsyncSession | None = None,
        candidate_tickets: Sequence[Ticket | dict[str, Any]] | None = None,
        ticket_id: str | None = None,
    ) -> tuple[list[Evidence], list[PreviousCase]]:
        """Execute knowledge retrieval and similar case correlation for graph node (CLAUDE.md §7.1).

        Returns:
            Tuple of (list[Evidence], list[PreviousCase]).
        """
        evidence_task = self.retrieve_evidence(
            query=query,
            category=category,
            top_k=top_k,
        )
        cases_task = self.similar_cases(
            text=query,
            category=category,
            limit=top_k,
            session=session,
            candidate_tickets=candidate_tickets,
            exclude_ticket_id=ticket_id,
        )

        evidence = await evidence_task
        previous_cases = await cases_task
        return evidence, previous_cases
