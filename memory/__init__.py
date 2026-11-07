"""CloudDesk Customer Memory Subsystem.

Provides short-term Redis state and long-term customer memory storage with secret scrubbing.
"""

from __future__ import annotations

from memory.long_term import (
    DEFAULT_RECALL_LIMIT,
    VALID_MEMORY_TYPES,
    LongTermMemory,
    get_long_term_memory,
)
from memory.scrub import (
    REDACTION_MARKER,
    SECRET_PATTERNS,
    ScrubResult,
    is_raw_ticket_body,
    scrub,
    scrub_text,
    validate_memory_content,
)
from memory.short_term import (
    CONVERSATION_TTL,
    MAX_KEY_QUERY_LEN,
    MAX_TICKET_ID_LEN,
    RETRIEVAL_CACHE_TTL,
    WORKFLOW_STATE_TTL,
    ShortTermMemory,
    get_short_term_memory,
    sanitize_query_for_key,
    sanitize_ticket_id,
)

__all__ = [
    "CONVERSATION_TTL",
    "DEFAULT_RECALL_LIMIT",
    "MAX_KEY_QUERY_LEN",
    "MAX_TICKET_ID_LEN",
    "REDACTION_MARKER",
    "RETRIEVAL_CACHE_TTL",
    "SECRET_PATTERNS",
    "VALID_MEMORY_TYPES",
    "WORKFLOW_STATE_TTL",
    "LongTermMemory",
    "ScrubResult",
    "ShortTermMemory",
    "get_long_term_memory",
    "get_short_term_memory",
    "is_raw_ticket_body",
    "sanitize_query_for_key",
    "sanitize_ticket_id",
    "scrub",
    "scrub_text",
    "validate_memory_content",
]
