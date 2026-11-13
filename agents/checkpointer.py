"""Checkpointer factory and lifecycle management for LangGraph (P10-1).

Provides InMemorySaver for testing/demo offline mode (CHECKPOINT_DB_PATH=:memory:)
and AsyncSqliteSaver for persistent file storage (./data/checkpoints.db).
Conforms to CLAUDE.md §7.3, §14, US-010 (AC-036), and ADR-03.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def resolve_checkpointer_path(db_path: str | Path | None = None) -> str | Path:
    """Validate and resolve checkpointer storage path safely against path traversal (CWE-22).

    Returns ':memory:' for in-memory mode, or a resolved Path with parent directories created.
    """
    if db_path is None:
        db_path = get_settings().CHECKPOINT_DB_PATH

    if isinstance(db_path, str) and db_path.strip() == ":memory:":
        return ":memory:"

    p = Path(db_path)
    resolved = p.resolve()
    base_dir = Path.cwd().resolve()

    # Reject path traversal attempts resolving outside the project workspace
    if ".." in str(db_path):
        try:
            resolved.relative_to(base_dir)
        except ValueError as err:
            raise ValueError(
                f"Path traversal detected: '{db_path}' resolves outside allowed workspace."
            ) from err

    # Ensure parent directory exists safely
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def get_in_memory_checkpointer() -> InMemorySaver:
    """Return a standalone InMemorySaver instance for tests and offline evaluation."""
    return InMemorySaver()


@asynccontextmanager
async def get_sqlite_checkpointer(
    db_path: str | Path | None = None,
) -> AsyncIterator[AsyncSqliteSaver]:
    """Async context manager initializing an AsyncSqliteSaver with schema setup."""
    target_path = resolve_checkpointer_path(db_path)
    conn_str = str(target_path)

    async with AsyncSqliteSaver.from_conn_string(conn_str) as saver:
        await saver.setup()
        yield saver


@asynccontextmanager
async def get_checkpointer(
    db_path: str | Path | None = None,
) -> AsyncIterator[BaseCheckpointSaver]:
    """Provide a LangGraph checkpointer instance matching configuration or parameter.

    - When db_path is ':memory:' (or settings.CHECKPOINT_DB_PATH == ':memory:'):
      Yields an InMemorySaver instance.
    - Otherwise:
      Yields an active AsyncSqliteSaver connected to the target database file.
    """
    target = resolve_checkpointer_path(db_path)

    if target == ":memory:":
        yield get_in_memory_checkpointer()
    else:
        async with get_sqlite_checkpointer(target) as sqlite_saver:
            yield sqlite_saver


__all__ = [
    "AsyncSqliteSaver",
    "BaseCheckpointSaver",
    "InMemorySaver",
    "get_checkpointer",
    "get_in_memory_checkpointer",
    "get_sqlite_checkpointer",
    "resolve_checkpointer_path",
]
