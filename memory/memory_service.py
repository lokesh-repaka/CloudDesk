"""Alias for memory.service conforming to CLAUDE.md layout."""

from memory.service import (
    MemoryService,
    format_customer_notes,
    get_memory_service,
    recall_customer,
    record_resolution,
)

__all__ = [
    "MemoryService",
    "format_customer_notes",
    "get_memory_service",
    "recall_customer",
    "record_resolution",
]
