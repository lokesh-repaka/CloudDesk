"""CloudDesk Customer Memory Subsystem.

Provides short-term Redis state and long-term customer memory storage with secret scrubbing.
"""

from __future__ import annotations

from memory.scrub import (
    REDACTION_MARKER,
    SECRET_PATTERNS,
    ScrubResult,
    is_raw_ticket_body,
    scrub,
    scrub_text,
    validate_memory_content,
)

__all__ = [
    "REDACTION_MARKER",
    "SECRET_PATTERNS",
    "ScrubResult",
    "is_raw_ticket_body",
    "scrub",
    "scrub_text",
    "validate_memory_content",
]
