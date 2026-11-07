"""Unit and penetration tests for Short-Term Redis facade (P8-1).

Tests conversation context (24h TTL), workflow state (24h TTL),
RAG retrieval caching (300s TTL), error resilience, sanitization,
and security penetration attacks.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
import redis

from memory.scrub import REDACTION_MARKER
from memory.short_term import (
    CONVERSATION_TTL,
    RETRIEVAL_CACHE_TTL,
    WORKFLOW_STATE_TTL,
    ShortTermMemory,
    get_short_term_memory,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock async Redis client."""
    client = AsyncMock()
    # Default return values
    client.rpush = AsyncMock(return_value=1)
    client.lrange = AsyncMock(return_value=[])
    client.delete = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.scan_iter = AsyncMock()
    return client


@pytest.fixture
def short_term_memory(mock_redis: AsyncMock) -> ShortTermMemory:
    """Create ShortTermMemory with injected mock redis client."""
    return ShortTermMemory(redis_client=mock_redis)


# ============================================================================
# 1. TTL Constants & Factory Initialization
# ============================================================================


def test_ttl_constants() -> None:
    """Verify TTL specifications match CLAUDE.md §7.5 and architecture.md §5.7."""
    assert CONVERSATION_TTL == 86400  # 24 hours
    assert WORKFLOW_STATE_TTL == 86400  # 24 hours
    assert RETRIEVAL_CACHE_TTL == 300  # 300 seconds (5 minutes)


def test_get_short_term_memory_singleton() -> None:
    """Verify get_short_term_memory provides a singleton instance."""
    instance1 = get_short_term_memory()
    instance2 = get_short_term_memory()
    assert instance1 is instance2

    # Force reinitialization
    instance3 = get_short_term_memory(force_reinit=True)
    assert instance3 is not instance1


# ============================================================================
# 2. Ticket Conversation Context Tests
# ============================================================================


@pytest.mark.asyncio
async def test_append_and_get_conversation(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify appending and retrieving conversation messages."""
    ticket_id = "TCK-1001"

    # 1. Append first message
    ok1 = await short_term_memory.append_message(
        ticket_id=ticket_id,
        role="customer",
        content="I am having trouble resetting my API key.",
        metadata={"channel": "email"},
    )
    assert ok1 is True
    mock_redis.rpush.assert_called_once()
    mock_redis.expire.assert_called_with(
        "ticket_conversation:TCK-1001", CONVERSATION_TTL
    )

    # 2. Append second message
    mock_redis.rpush.reset_mock()
    ok2 = await short_term_memory.append_message(
        ticket_id=ticket_id,
        role="assistant",
        content="I can help you regenerate your API key in the developer console.",
    )
    assert ok2 is True
    mock_redis.rpush.assert_called_once()

    # 3. Retrieve conversation
    serialized_msgs = [
        json.dumps(
            {
                "role": "customer",
                "content": "I am having trouble resetting my API key.",
                "timestamp": "2026-11-07T10:00:00Z",
                "metadata": {"channel": "email"},
            }
        ),
        json.dumps(
            {
                "role": "assistant",
                "content": "I can help you regenerate your API key in the developer console.",
                "timestamp": "2026-11-07T10:01:00Z",
                "metadata": {},
            }
        ),
    ]
    mock_redis.lrange.return_value = serialized_msgs

    messages = await short_term_memory.get_conversation(ticket_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "customer"
    assert messages[0]["metadata"]["channel"] == "email"
    assert messages[1]["role"] == "assistant"
    mock_redis.lrange.assert_called_once_with("ticket_conversation:TCK-1001", 0, -1)


@pytest.mark.asyncio
async def test_get_conversation_empty(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify empty list is returned for ticket with no conversation."""
    mock_redis.lrange.return_value = []
    messages = await short_term_memory.get_conversation("TCK-EMPTY")
    assert messages == []


@pytest.mark.asyncio
async def test_clear_conversation(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify clearing conversation removes the key."""
    ticket_id = "TCK-1001"
    ok = await short_term_memory.clear_conversation(ticket_id)
    assert ok is True
    mock_redis.delete.assert_called_once_with("ticket_conversation:TCK-1001")


@pytest.mark.asyncio
async def test_conversation_secret_scrubbing(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify secrets are scrubbed before saving to Redis conversation history."""
    ticket_id = "TCK-SECRETS"
    leaked_content = (
        "Here is my OpenAI key: sk-live-9876543210abcdef9876543210abcdef "
        "and my card 4532 0150 1234 5671 for the invoice."
    )

    await short_term_memory.append_message(
        ticket_id=ticket_id,
        role="customer",
        content=leaked_content,
        scrub_secrets=True,
    )

    # Check payload pushed to Redis
    pushed_payload = mock_redis.rpush.call_args[0][1]
    data = json.loads(pushed_payload)
    assert "sk-live-" not in data["content"]
    assert "4532 0150 1234 5671" not in data["content"]
    assert REDACTION_MARKER in data["content"]


# ============================================================================
# 3. Ephemeral Workflow State Tests
# ============================================================================


@pytest.mark.asyncio
async def test_save_and_get_workflow_state(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify saving, retrieving, and deleting workflow state."""
    ticket_id = "TCK-STATE-1"
    state_payload = {
        "current_node": "troubleshooting",
        "category": "database",
        "severity": "high",
        "retry_count": 2,
        "evidence_ids": ["doc_1", "doc_2"],
    }

    # Save
    ok = await short_term_memory.save_workflow_state(ticket_id, state_payload)
    assert ok is True
    mock_redis.set.assert_called_once_with(
        "workflow_state:TCK-STATE-1",
        json.dumps(state_payload),
        ex=WORKFLOW_STATE_TTL,
    )

    # Get
    mock_redis.get.return_value = json.dumps(state_payload)
    retrieved = await short_term_memory.get_workflow_state(ticket_id)
    assert retrieved == state_payload
    mock_redis.get.assert_called_once_with("workflow_state:TCK-STATE-1")

    # Delete
    deleted = await short_term_memory.delete_workflow_state(ticket_id)
    assert deleted is True
    mock_redis.delete.assert_called_once_with("workflow_state:TCK-STATE-1")


@pytest.mark.asyncio
async def test_save_workflow_state_custom_ttl(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify saving workflow state with a custom TTL."""
    ticket_id = "TCK-TTL-TEST"
    state_payload = {"step": "verification"}

    await short_term_memory.save_workflow_state(ticket_id, state_payload, ttl=1800)
    mock_redis.set.assert_called_once_with(
        "workflow_state:TCK-TTL-TEST",
        json.dumps(state_payload),
        ex=1800,
    )


@pytest.mark.asyncio
async def test_get_workflow_state_missing(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify get_workflow_state returns None when key is absent."""
    mock_redis.get.return_value = None
    retrieved = await short_term_memory.get_workflow_state("NONEXISTENT")
    assert retrieved is None


# ============================================================================
# 4. RAG Retrieval Query Cache Tests
# ============================================================================


def test_build_cache_key_normalization(short_term_memory: ShortTermMemory) -> None:
    """Verify build_cache_key normalizes category, mode, and query."""
    key1 = short_term_memory.build_cache_key(
        mode="hybrid", category=" billing ", top_k=3, query="refund request"
    )
    assert key1 == "rag:hybrid:billing:3:refund request"

    # Category defaults to 'all' when empty or None
    key2 = short_term_memory.build_cache_key(
        mode="semantic", category=None, top_k=5, query="database crash"
    )
    assert key2 == "rag:semantic:all:5:database crash"

    key3 = short_term_memory.build_cache_key(
        mode="keyword", category="   ", top_k=1, query="status code 500"
    )
    assert key3 == "rag:keyword:all:1:status code 500"


@pytest.mark.asyncio
async def test_set_and_get_cached_retrieval(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify caching and retrieving RAG evidence results."""
    mode = "hybrid"
    category = "security"
    top_k = 2
    query = "ssl handshake failure"

    evidence: list[dict[str, Any]] = [
        {
            "id": "chunk_42",
            "title": "TLS Troubleshooting",
            "source": "kb://networking#tls",
            "snippet": "Check TLS 1.3 cipher suites...",
            "score": 0.88,
        }
    ]

    # Set cache
    ok = await short_term_memory.set_cached_retrieval(
        mode=mode,
        category=category,
        top_k=top_k,
        query=query,
        evidence=evidence,
    )
    assert ok is True
    expected_key = "rag:hybrid:security:2:ssl handshake failure"
    mock_redis.set.assert_called_once_with(
        expected_key,
        json.dumps(evidence),
        ex=RETRIEVAL_CACHE_TTL,
    )

    # Get cache hit
    mock_redis.get.return_value = json.dumps(evidence)
    cached = await short_term_memory.get_cached_retrieval(
        mode=mode,
        category=category,
        top_k=top_k,
        query=query,
    )
    assert cached == evidence


@pytest.mark.asyncio
async def test_get_cached_retrieval_miss(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify cache miss returns None."""
    mock_redis.get.return_value = None
    cached = await short_term_memory.get_cached_retrieval(
        mode="hybrid",
        category="general",
        top_k=5,
        query="unknown query",
    )
    assert cached is None


@pytest.mark.asyncio
async def test_clear_retrieval_cache(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Verify clear_retrieval_cache scans and deletes matching keys."""

    # Set up async generator for scan_iter
    async def async_scan_iter(match: str):
        for k in ["rag:hybrid:all:3:q1", "rag:semantic:billing:5:q2"]:
            yield k

    mock_redis.scan_iter = async_scan_iter
    deleted_count = await short_term_memory.clear_retrieval_cache()
    assert deleted_count == 2
    mock_redis.delete.assert_called_once_with(
        "rag:hybrid:all:3:q1", "rag:semantic:billing:5:q2"
    )


# ============================================================================
# 5. Fault Tolerance & Graceful Degradation Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc", [redis.RedisError("Connection refused"), ConnectionError(), TimeoutError()]
)
async def test_redis_exceptions_graceful_conversation(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock, exc: Exception
) -> None:
    """Verify conversation operations degrade gracefully without raising."""
    mock_redis.rpush.side_effect = exc
    mock_redis.lrange.side_effect = exc
    mock_redis.delete.side_effect = exc

    # append_message should return False, not crash
    assert (
        await short_term_memory.append_message("TCK-ERR", "customer", "hello") is False
    )

    # get_conversation should return [], not crash
    assert await short_term_memory.get_conversation("TCK-ERR") == []

    # clear_conversation should return False, not crash
    assert await short_term_memory.clear_conversation("TCK-ERR") is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc", [redis.RedisError("Out of memory"), ConnectionError(), OSError()]
)
async def test_redis_exceptions_graceful_workflow_state(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock, exc: Exception
) -> None:
    """Verify workflow state operations degrade gracefully without raising."""
    mock_redis.set.side_effect = exc
    mock_redis.get.side_effect = exc
    mock_redis.delete.side_effect = exc

    assert await short_term_memory.save_workflow_state("TCK-ERR", {"step": 1}) is False
    assert await short_term_memory.get_workflow_state("TCK-ERR") is None
    assert await short_term_memory.delete_workflow_state("TCK-ERR") is False


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [redis.RedisError("Network partition"), TimeoutError()])
async def test_redis_exceptions_graceful_retrieval_cache(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock, exc: Exception
) -> None:
    """Verify RAG cache operations degrade gracefully without raising."""
    mock_redis.set.side_effect = exc
    mock_redis.get.side_effect = exc

    assert (
        await short_term_memory.set_cached_retrieval("hybrid", "cat", 3, "query", [])
        is False
    )
    assert (
        await short_term_memory.get_cached_retrieval("hybrid", "cat", 3, "query")
        is None
    )


# ============================================================================
# 6. Security & Penetration Testing
# ============================================================================


def test_pen_test_crlf_key_injection(short_term_memory: ShortTermMemory) -> None:
    """Pen-test: Ensure CRLF sequences in ticket_id or queries are sanitized (CWE-93)."""
    malicious_query = "legit query\r\nSET hijacked_key admin\r\n"
    key = short_term_memory.build_cache_key("hybrid", "all", 3, malicious_query)

    # Confirm \r and \n are completely eliminated from the key
    assert "\r" not in key
    assert "\n" not in key
    assert key.startswith("rag:hybrid:all:3:legit query SET hijacked_key admin")


@pytest.mark.asyncio
async def test_pen_test_ticket_id_crlf_sanitization(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Pen-test: Ensure ticket_id with CRLF is sanitized to prevent Redis command injection."""
    malicious_ticket_id = "TCK-1001\r\nFLUSHALL\r\n"
    await short_term_memory.append_message(
        ticket_id=malicious_ticket_id,
        role="customer",
        content="hello",
    )

    # Inspect the key passed to rpush
    used_key = mock_redis.rpush.call_args[0][0]
    assert "\r" not in used_key
    assert "\n" not in used_key
    assert used_key == "ticket_conversation:TCK-1001_FLUSHALL"


def test_pen_test_query_key_length_capping(short_term_memory: ShortTermMemory) -> None:
    """Pen-test: Query string capping prevents resource exhaustion/ReDoS in keys (CWE-400)."""
    giant_query = "x" * 50000
    key = short_term_memory.build_cache_key("hybrid", "all", 3, giant_query)

    # Key should be capped at reasonable length (<= 320 chars total)
    assert len(key) <= 320


@pytest.mark.asyncio
async def test_pen_test_invalid_json_in_redis_payload(
    short_term_memory: ShortTermMemory, mock_redis: AsyncMock
) -> None:
    """Pen-test: Corrupted or tampered JSON in Redis degrades safely (CWE-502)."""
    ticket_id = "TCK-CORRUPT"

    # Corrupted workflow state JSON
    mock_redis.get.return_value = "{malformed json... not valid"
    state = await short_term_memory.get_workflow_state(ticket_id)
    assert state is None

    # Corrupted conversation message JSON
    mock_redis.lrange.return_value = [
        "{bad message json",
        json.dumps({"role": "user", "content": "ok"}),
    ]
    msgs = await short_term_memory.get_conversation(ticket_id)
    # The malformed message is skipped, valid message is retained
    assert len(msgs) == 1
    assert msgs[0]["content"] == "ok"

    # Corrupted retrieval cache JSON
    mock_redis.get.return_value = "invalid-rag-json"
    cached = await short_term_memory.get_cached_retrieval("hybrid", "all", 3, "query")
    assert cached is None


# ============================================================================
# 7. Live FakeRedis Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fakeredis_live_conversation_flow() -> None:
    """Integration test: Multi-turn conversation roundtrip using live FakeRedis."""
    stm = ShortTermMemory()
    ticket_id = "TCK-FAKEREDIS-001"

    # Ensure clean slate
    await stm.clear_conversation(ticket_id)

    # 1. Append messages
    await stm.append_message(ticket_id, "user", "Message 1", metadata={"turn": 1})
    await stm.append_message(ticket_id, "assistant", "Message 2", metadata={"turn": 2})

    # 2. Retrieve messages
    history = await stm.get_conversation(ticket_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Message 1"
    assert history[0]["metadata"]["turn"] == 1
    assert "timestamp" in history[0]

    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Message 2"
    assert history[1]["metadata"]["turn"] == 2

    # 3. Clear conversation
    cleared = await stm.clear_conversation(ticket_id)
    assert cleared is True
    assert await stm.get_conversation(ticket_id) == []


@pytest.mark.asyncio
async def test_fakeredis_live_workflow_state_flow() -> None:
    """Integration test: Workflow state roundtrip using live FakeRedis."""
    stm = ShortTermMemory()
    ticket_id = "TCK-FAKEREDIS-STATE"

    # 1. Save state
    test_state = {"status": "in_progress", "actions": ["reset_pwd"], "attempt": 1}
    saved = await stm.save_workflow_state(ticket_id, test_state)
    assert saved is True

    # 2. Retrieve state
    loaded = await stm.get_workflow_state(ticket_id)
    assert loaded == test_state

    # 3. Delete state
    deleted = await stm.delete_workflow_state(ticket_id)
    assert deleted is True
    assert await stm.get_workflow_state(ticket_id) is None


@pytest.mark.asyncio
async def test_fakeredis_live_retrieval_cache_flow() -> None:
    """Integration test: RAG query cache roundtrip using live FakeRedis."""
    stm = ShortTermMemory()
    mode = "hybrid"
    category = "network"
    top_k = 3
    query = "fakeredis test query"
    evidence = [{"id": "doc1", "score": 0.95}]

    # 1. Set cache
    saved = await stm.set_cached_retrieval(mode, category, top_k, query, evidence)
    assert saved is True

    # 2. Get cache
    retrieved = await stm.get_cached_retrieval(mode, category, top_k, query)
    assert retrieved == evidence

    # 3. Clear cache
    cleared_count = await stm.clear_retrieval_cache()
    assert cleared_count >= 1

    # 4. Verify miss after clear
    assert await stm.get_cached_retrieval(mode, category, top_k, query) is None


def test_sanitize_ticket_id_extremes() -> None:
    """Verify sanitization handles empty strings, nulls, and extreme lengths."""
    from memory.short_term import sanitize_ticket_id

    assert sanitize_ticket_id("") == "unknown"
    assert sanitize_ticket_id("   ") == "unknown"
    assert sanitize_ticket_id(None) == "unknown"  # type: ignore

    oversized = "a" * 500
    sanitized = sanitize_ticket_id(oversized)
    assert len(sanitized) == 128
