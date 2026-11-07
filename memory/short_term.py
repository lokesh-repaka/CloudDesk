"""Short-term Redis facade for CloudDesk Memory Subsystem (P8-1).

Provides ephemeral storage adhering to CLAUDE.md §7.5 and architecture.md §5.7:
- Multi-turn ticket conversation history with 24-hour TTL and secret scrubbing
- Agent workflow execution state with 24-hour TTL
- Short-term RAG retrieval query cache with 300-second TTL
- Resilient error handling via REDIS_EXCEPTIONS with graceful degradation
- Input sanitization against CRLF injection and resource exhaustion
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from backend.app.core.redis import REDIS_EXCEPTIONS, get_redis_client
from memory.scrub import scrub

logger = logging.getLogger(__name__)

# Standard TTL specifications (CLAUDE.md §7.5)
CONVERSATION_TTL = 86400  # 24 hours in seconds
WORKFLOW_STATE_TTL = 86400  # 24 hours in seconds
RETRIEVAL_CACHE_TTL = 300  # 300 seconds (5 minutes)

MAX_TICKET_ID_LEN = 128
MAX_KEY_QUERY_LEN = 256


def sanitize_ticket_id(ticket_id: str | None) -> str:
    """Sanitize ticket_id against CRLF injection, control chars, and excessive length."""
    if not ticket_id or not ticket_id.strip():
        return "unknown"
    clean = re.sub(r"[\r\n\s\x00]+", "_", ticket_id.strip())
    return clean[:MAX_TICKET_ID_LEN] if clean else "unknown"


def sanitize_query_for_key(query: str) -> str:
    """Sanitize and normalize query string for Redis cache key composition."""
    clean = re.sub(r"[\r\n]+", " ", query.strip())
    return clean[:MAX_KEY_QUERY_LEN]


class ShortTermMemory:
    """Redis-backed short-term memory facade for conversations, workflow states, and RAG cache."""

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis_client = redis_client

    @property
    def redis(self) -> Any:
        """Resolve the active Redis or FakeRedis client."""
        if self._redis_client is None:
            self._redis_client = get_redis_client()
        return self._redis_client

    # =========================================================================
    # 1. Multi-turn Ticket Conversation Context (24h TTL)
    # =========================================================================

    def _conversation_key(self, ticket_id: str) -> str:
        safe_id = sanitize_ticket_id(ticket_id)
        return f"ticket_conversation:{safe_id}"

    async def append_message(
        self,
        ticket_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        scrub_secrets: bool = True,
    ) -> bool:
        """Append a message to the ticket conversation list and refresh 24h TTL.

        Automatically scrubs secrets (API keys, passwords, credit cards) before
        persisting to short-term storage when scrub_secrets is True.
        """
        key = self._conversation_key(ticket_id)
        safe_content = scrub(content) if scrub_secrets else content

        message_payload = {
            "role": role,
            "content": safe_content,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
        }

        try:
            serialized = json.dumps(message_payload)
            await self.redis.rpush(key, serialized)
            await self.redis.expire(key, CONVERSATION_TTL)
            return True
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis error appending message to conversation '%s': %s (degraded)",
                key,
                err,
            )
            return False

    async def get_conversation(self, ticket_id: str) -> list[dict[str, Any]]:
        """Retrieve the chronological conversation history for a ticket.

        Returns an empty list on cache miss or Redis failure.
        """
        key = self._conversation_key(ticket_id)
        try:
            raw_items = await self.redis.lrange(key, 0, -1)
            messages: list[dict[str, Any]] = []
            for item in raw_items:
                try:
                    messages.append(json.loads(item))
                except (json.JSONDecodeError, TypeError) as decode_err:
                    logger.warning(
                        "Corrupted message payload in conversation '%s': %s",
                        key,
                        decode_err,
                    )
            return messages
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis error reading conversation for '%s': %s (degraded)",
                key,
                err,
            )
            return []

    async def clear_conversation(self, ticket_id: str) -> bool:
        """Remove all conversation messages for a ticket."""
        key = self._conversation_key(ticket_id)
        try:
            await self.redis.delete(key)
            return True
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis error clearing conversation for '%s': %s (degraded)",
                key,
                err,
            )
            return False

    # =========================================================================
    # 2. Ephemeral Workflow State (24h TTL)
    # =========================================================================

    def _workflow_state_key(self, ticket_id: str) -> str:
        safe_id = sanitize_ticket_id(ticket_id)
        return f"workflow_state:{safe_id}"

    async def save_workflow_state(
        self,
        ticket_id: str,
        state_data: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """Save ephemeral LangGraph agent/workflow state for a ticket."""
        key = self._workflow_state_key(ticket_id)
        effective_ttl = ttl if ttl is not None else WORKFLOW_STATE_TTL
        try:
            serialized = json.dumps(state_data)
            await self.redis.set(key, serialized, ex=effective_ttl)
            return True
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis error saving workflow state for '%s': %s (degraded)",
                key,
                err,
            )
            return False

    async def get_workflow_state(self, ticket_id: str) -> dict[str, Any] | None:
        """Retrieve ephemeral workflow state for a ticket.

        Returns None if missing, corrupted, or if Redis fails.
        """
        key = self._workflow_state_key(ticket_id)
        try:
            raw_state = await self.redis.get(key)
            if not raw_state:
                return None
            return json.loads(raw_state)
        except (json.JSONDecodeError, TypeError) as decode_err:
            logger.warning(
                "Corrupted workflow state JSON for key '%s': %s",
                key,
                decode_err,
            )
            return None
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis error reading workflow state for '%s': %s (degraded)",
                key,
                err,
            )
            return None

    async def delete_workflow_state(self, ticket_id: str) -> bool:
        """Delete ephemeral workflow state for a ticket."""
        key = self._workflow_state_key(ticket_id)
        try:
            await self.redis.delete(key)
            return True
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis error deleting workflow state for '%s': %s (degraded)",
                key,
                err,
            )
            return False

    # =========================================================================
    # 3. Short-Term Retrieval Query Cache (300s TTL)
    # =========================================================================

    def build_cache_key(
        self,
        mode: str,
        category: str | None,
        top_k: int,
        query: str,
    ) -> str:
        """Construct the canonical RAG cache key: rag:{mode}:{category}:{top_k}:{query}."""
        cat_key = category.strip().lower() if category and category.strip() else "all"
        safe_query_key = sanitize_query_for_key(query)
        return f"rag:{mode}:{cat_key}:{top_k}:{safe_query_key}"

    async def get_cached_retrieval(
        self,
        mode: str,
        category: str | None,
        top_k: int,
        query: str,
    ) -> list[dict[str, Any]] | None:
        """Lookup cached retrieval evidence results from Redis."""
        cache_key = self.build_cache_key(mode, category, top_k, query)
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                logger.debug("Redis retrieval cache HIT for key: %s", cache_key)
                return json.loads(cached_data)
            return None
        except (json.JSONDecodeError, TypeError) as decode_err:
            logger.warning(
                "Corrupted retrieval cache entry for key '%s': %s",
                cache_key,
                decode_err,
            )
            return None
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis cache read failed for key '%s': %s (degraded)",
                cache_key,
                err,
            )
            return None

    async def set_cached_retrieval(
        self,
        mode: str,
        category: str | None,
        top_k: int,
        query: str,
        evidence: list[dict[str, Any]],
        ttl: int | None = None,
    ) -> bool:
        """Store retrieval evidence results into Redis with 300s TTL."""
        cache_key = self.build_cache_key(mode, category, top_k, query)
        effective_ttl = ttl if ttl is not None else RETRIEVAL_CACHE_TTL
        try:
            await self.redis.set(cache_key, json.dumps(evidence), ex=effective_ttl)
            logger.debug("Redis retrieval cache SET for key: %s", cache_key)
            return True
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis cache write failed for key '%s': %s (degraded)",
                cache_key,
                err,
            )
            return False

    async def clear_retrieval_cache(self, mode: str | None = None) -> int:
        """Scan and clear all cached RAG queries matching the pattern."""
        pattern = f"rag:{mode}:*" if mode else "rag:*"
        try:
            keys: list[str] = []
            async for k in self.redis.scan_iter(match=pattern):
                keys.append(k)
            if keys:
                await self.redis.delete(*keys)
            return len(keys)
        except REDIS_EXCEPTIONS as err:
            logger.warning(
                "Redis error scanning/clearing retrieval cache for pattern '%s': %s (degraded)",
                pattern,
                err,
            )
            return 0


_short_term_memory_instance: ShortTermMemory | None = None


def get_short_term_memory(
    redis_client: Any | None = None,
    force_reinit: bool = False,
) -> ShortTermMemory:
    """Return active ShortTermMemory singleton instance."""
    global _short_term_memory_instance
    if _short_term_memory_instance is None or force_reinit:
        _short_term_memory_instance = ShortTermMemory(redis_client=redis_client)
    elif redis_client is not None:
        _short_term_memory_instance._redis_client = redis_client
    return _short_term_memory_instance
