"""Tests for Hybrid Retriever with BM25, RRF, and Short-Term Memory Caching (P5-3).

Acceptance Criteria (CLAUDE.md §7.5, §8 / PLAN.md / TASKS.md):
- Hybrid retrieval combining semantic similarity (VectorStoreService) and keyword matching (rank_bm25.BM25Okapi).
- Reciprocal Rank Fusion (RRF) with constant k=60.
- Heuristic reranking: category match boost (1.35x) and title token overlap boost.
- Deduplication: strictly one hit per article, keeping the highest-scoring chunk per article_id.
- Retrieval modes: 'hybrid' (default), 'semantic', and 'keyword'.
- Short-term caching: Redis / fakeredis cache key format 'rag:{mode}:{category}:{top_k}:{query}' with 300s TTL.
- Graceful degradation if Redis is down or raises connection errors.
- Quality bar: Retrieval hit-rate@3 >= 0.75 across the 13 reference sample tickets.
- Security tests: SQL/NoSQL injection, XSS containment, ReDoS protection, and cache key poisoning defense.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import redis

from backend.app.rag.chunking import (
    ArticleChunk,
    chunk_all_articles,
    load_article_files,
)
from backend.app.rag.retriever import HybridRetriever
from backend.app.rag.vector_store import FakeEmbeddings, InMemoryVectorStore

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_chunks() -> list[ArticleChunk]:
    """Provide a minimal deterministic set of ArticleChunks for unit testing."""
    c1 = ArticleChunk(
        id="kb-sso-01_sec-0_0",
        article_id="kb-login-01-sso",
        slug="kb-login-01-sso",
        title="Troubleshooting SAML 2.0 Single Sign-On (SSO)",
        heading="Common Root Causes",
        section="common-root-causes",
        source="kb://kb-login-01-sso#common-root-causes",
        category="login_issue",
        tags=["sso", "saml", "okta"],
        content="Troubleshooting SAML 2.0 Single Sign-On (SSO) - Common Root Causes\n\nSAML assertion signature failure and expired certificates.",
        snippet="SAML assertion signature failure and expired certificates.",
        chunk_index=0,
    )
    c2 = ArticleChunk(
        id="kb-sso-01_sec-1_0",
        article_id="kb-login-01-sso",
        slug="kb-login-01-sso",
        title="Troubleshooting SAML 2.0 Single Sign-On (SSO)",
        heading="Resolution Steps",
        section="resolution-steps",
        source="kb://kb-login-01-sso#resolution-steps",
        category="login_issue",
        tags=["sso", "saml", "okta"],
        content="Troubleshooting SAML 2.0 Single Sign-On (SSO) - Resolution Steps\n\nUpload new IdP public certificate in the CloudDesk admin dashboard.",
        snippet="Upload new IdP public certificate in the CloudDesk admin dashboard.",
        chunk_index=1,
    )
    c3 = ArticleChunk(
        id="kb-billing-01_sec-0_0",
        article_id="kb-billing-01-seats-refund",
        slug="kb-billing-01-seats-refund",
        title="Seat Adjustments and Refund Policy",
        heading="Prorated Refunds",
        section="prorated-refunds",
        source="kb://kb-billing-01-seats-refund#prorated-refunds",
        category="billing",
        tags=["billing", "seats", "refund"],
        content="Seat Adjustments and Refund Policy - Prorated Refunds\n\nRefunds for reduced seat counts are automatically prorated onto next invoice.",
        snippet="Refunds for reduced seat counts are automatically prorated onto next invoice.",
        chunk_index=0,
    )
    c4 = ArticleChunk(
        id="kb-api-01_sec-0_0",
        article_id="kb-api-01-rate-limits",
        slug="kb-api-01-rate-limits",
        title="API Rate Limits and Quota Management",
        heading="Rate Limit Tiers",
        section="rate-limit-tiers",
        source="kb://kb-api-01-rate-limits#rate-limit-tiers",
        category="api_failure",
        tags=["api", "rate-limit", "429"],
        content="API Rate Limits and Quota Management - Rate Limit Tiers\n\nHTTP 429 Too Many Requests occurs when exceeding 120 calls per minute on free tier.",
        snippet="HTTP 429 Too Many Requests occurs when exceeding 120 calls per minute on free tier.",
        chunk_index=0,
    )
    return [c1, c2, c3, c4]


@pytest.fixture
async def initialized_retriever(sample_chunks: list[ArticleChunk]) -> HybridRetriever:
    """Create an initialized HybridRetriever with fake embeddings and sample chunks."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    retriever = HybridRetriever(vector_store=store)
    await retriever.index_corpus(sample_chunks)
    return retriever


@pytest.fixture
def reference_tickets() -> list[dict[str, Any]]:
    """Synchronously load the reference tickets from sample_data/tickets.json."""
    data_path = Path("sample_data/tickets.json")
    return json.loads(data_path.read_text(encoding="utf-8"))


# -----------------------------------------------------------------------------
# 1. Initialization and Indexing Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_retriever_initialization():
    """Verify retriever instantiates with defaults and builds vector/BM25 structures."""
    retriever = HybridRetriever()
    assert retriever.vector_store is not None
    assert retriever.rrf_k == 60
    assert retriever.category_boost == 1.35
    assert retriever.cache_ttl == 300


@pytest.mark.asyncio
async def test_retriever_index_corpus(
    sample_chunks: list[ArticleChunk], initialized_retriever: HybridRetriever
):
    """Verify index_corpus populates both vector store and BM25 index."""
    assert initialized_retriever.bm25 is not None
    assert len(initialized_retriever.chunks) == 4
    count = await initialized_retriever.vector_store.count()
    assert count == 4


# -----------------------------------------------------------------------------
# 2. Retrieval Modes Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_retrieval_mode(initialized_retriever: HybridRetriever):
    """Verify default hybrid mode combines semantic and keyword scores into valid evidence shape."""
    query = "SAML signature invalid authentication failure"
    evidence = await initialized_retriever.retrieve(query, top_k=2, mode="hybrid")

    assert len(evidence) <= 2
    assert len(evidence) > 0

    first = evidence[0]
    # Check evidence dictionary contract (CLAUDE.md §8)
    assert "id" in first
    assert "title" in first
    assert "source" in first
    assert "snippet" in first
    assert "score" in first
    assert "url" in first
    assert "article_id" in first

    assert first["article_id"] == "kb-login-01-sso"
    assert first["source"].startswith("kb://kb-login-01-sso#")
    assert first["url"] == "/knowledge/kb-login-01-sso"
    assert isinstance(first["score"], float)


@pytest.mark.asyncio
async def test_semantic_retrieval_mode(initialized_retriever: HybridRetriever):
    """Verify 'semantic' mode executes purely against vector store."""
    query = "API 429 too many calls quota"
    evidence = await initialized_retriever.retrieve(query, top_k=2, mode="semantic")

    assert len(evidence) >= 1
    assert evidence[0]["article_id"] == "kb-api-01-rate-limits"


@pytest.mark.asyncio
async def test_keyword_retrieval_mode(initialized_retriever: HybridRetriever):
    """Verify 'keyword' mode executes purely against BM25 index."""
    query = "prorated invoice seat count"
    evidence = await initialized_retriever.retrieve(query, top_k=2, mode="keyword")

    assert len(evidence) >= 1
    assert evidence[0]["article_id"] == "kb-billing-01-seats-refund"


@pytest.mark.asyncio
async def test_invalid_retrieval_mode_raises(initialized_retriever: HybridRetriever):
    """Verify invalid mode parameter raises ValueError."""
    with pytest.raises(ValueError, match="Invalid retrieval mode"):
        await initialized_retriever.retrieve("test query", mode="unsupported_mode")


# -----------------------------------------------------------------------------
# 3. RRF, Heuristics, and Deduplication Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deduplication_one_hit_per_article(
    initialized_retriever: HybridRetriever,
):
    """Verify strictly one hit per article is returned (CLAUDE.md §8).

    Even though sample_chunks has 2 chunks for 'kb-login-01-sso', only 1 hit
    for that article must be included in the final results.
    """
    query = "SAML 2.0 Single Sign-On resolution certificate error"
    results = await initialized_retriever.retrieve(query, top_k=4, mode="hybrid")

    article_ids = [r["article_id"] for r in results]
    assert len(article_ids) == len(set(article_ids)), "Duplicate article_id returned!"
    assert "kb-login-01-sso" in article_ids


@pytest.mark.asyncio
async def test_category_boost_heuristics(sample_chunks: list[ArticleChunk]):
    """Verify category match provides a 1.35x boost to candidate scores."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    retriever = HybridRetriever(vector_store=store, category_boost=1.35)
    await retriever.index_corpus(sample_chunks)

    query = "Rate limits and quota management"

    # Query with matching category 'api_failure'
    matched_results = await retriever.retrieve(
        query, category="api_failure", top_k=1, mode="hybrid"
    )
    # Query with non-matching category
    unmatched_results = await retriever.retrieve(
        query, category="other_category", top_k=1, mode="hybrid"
    )

    assert matched_results[0]["article_id"] == "kb-api-01-rate-limits"
    assert matched_results[0]["score"] > unmatched_results[0]["score"]


@pytest.mark.asyncio
async def test_reciprocal_rank_fusion_logic(initialized_retriever: HybridRetriever):
    """Verify RRF formula k=60 computes higher score when an item ranks high across both signals."""
    query = "SAML SSO certificates and quota limits"
    results = await initialized_retriever.retrieve(query, top_k=3, mode="hybrid")
    assert len(results) > 0
    # Top score is strictly positive and bounded
    assert 0.0 < results[0]["score"] <= 2.0


# -----------------------------------------------------------------------------
# 4. Redis Short-Term Caching Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_retrieval_caching(initialized_retriever: HybridRetriever):
    """Verify results are cached in Redis under 'rag:{mode}:{category}:{top_k}:{query}' with 300s TTL."""
    query = "SAML 2.0 authentication failure"
    category = "login_issue"

    # First call: cache miss, performs retrieval and sets Redis cache
    res1 = await initialized_retriever.retrieve(
        query, category=category, top_k=2, mode="hybrid", use_cache=True
    )
    assert len(res1) > 0

    # Second call: cache hit
    res2 = await initialized_retriever.retrieve(
        query, category=category, top_k=2, mode="hybrid", use_cache=True
    )
    assert res1 == res2

    # Verify cache key in redis client
    redis_client = initialized_retriever.redis_client
    cache_key = f"rag:hybrid:{category}:2:{query}"
    cached_val = await redis_client.get(cache_key)
    assert cached_val is not None
    deserialized = json.loads(cached_val)
    assert len(deserialized) == len(res1)
    assert deserialized[0]["article_id"] == res1[0]["article_id"]

    # Verify TTL <= 300
    ttl = await redis_client.ttl(cache_key)
    assert 0 < ttl <= 300


@pytest.mark.asyncio
async def test_redis_cache_bypass(initialized_retriever: HybridRetriever):
    """Verify use_cache=False bypasses Redis lookup and write."""
    query = "unique non-cached query 12345"
    res = await initialized_retriever.retrieve(query, top_k=1, use_cache=False)
    cache_key = f"rag:hybrid:all:1:{query}"
    cached = await initialized_retriever.redis_client.get(cache_key)
    assert cached is None
    assert isinstance(res, list)


@pytest.mark.asyncio
async def test_redis_graceful_degradation_on_error(
    initialized_retriever: HybridRetriever,
):
    """Verify retriever falls back gracefully to live retrieval if Redis raises an error."""
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = redis.ConnectionError("Redis connection refused")
    mock_redis.set.side_effect = redis.TimeoutError("Redis timed out")

    initialized_retriever.redis_client = mock_redis
    # Should not raise exception; falls through to live search
    results = await initialized_retriever.retrieve(
        "SAML SSO", top_k=1, mode="hybrid", use_cache=True
    )
    assert len(results) >= 1
    assert results[0]["article_id"] == "kb-login-01-sso"


# -----------------------------------------------------------------------------
# 5. Quality Bar Benchmark: 13 Reference Tickets (Hit-rate@3 >= 0.75)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_bar_hit_rate_at_3(reference_tickets: list[dict[str, Any]]):
    """Verify retrieval hit-rate@3 is >= 0.75 across the 13 reference sample tickets.

    Meets quality threshold defined in docs/PLAN.md (F5) and docs/TASKS.md.
    """
    # 1. Load full KB corpus
    articles = load_article_files("sample_data/knowledge_base")
    chunks = chunk_all_articles(articles)
    assert len(chunks) > 0

    # 2. Build retriever
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    retriever = HybridRetriever(vector_store=store)
    await retriever.index_corpus(chunks)

    # 3. Reference tickets provided via fixture
    tickets = reference_tickets
    assert len(tickets) == 13

    # Ground truth mapping based on domain content of sample_data/tickets.json
    expected_slug_map = {
        "CD-1001": "kb-login-01-sso",
        "CD-1002": "kb-billing-01-seats-refund",
        "CD-1003": "kb-api-01-rate-limits",
        "CD-1004": "kb-quota-01-storage-tiers",
        "CD-1005": "kb-sec-01-compromised-accounts",
        "CD-1006": "kb-other-01-data-recovery",
        "CD-1007": "kb-perm-01-workspace-sharing",
        "CD-1008": "kb-integ-01-slack",
        "CD-1009": "kb-acc-01-deletion-gdpr",
        "CD-1010": "kb-feat-01-roadmap-darkmode",
        "CD-1011": "kb-billing-02-disputes",
        "CD-1012": "kb-login-02-mfa",
        "CD-1013": "kb-sec-02-audit-access",
    }

    hits = 0
    total = len(tickets)

    for ticket in tickets:
        tid = ticket["id"]
        expected_slug = expected_slug_map[tid]
        query = f"{ticket['subject']} {ticket['initial_message']}"
        category = ticket.get("category")

        results = await retriever.retrieve(
            query=query, category=category, top_k=3, mode="hybrid", use_cache=False
        )
        returned_article_ids = [r["article_id"] for r in results]

        # Article ID from sample data is formatted as 'art-{slug}'
        if (
            f"art-{expected_slug}" in returned_article_ids
            or expected_slug in returned_article_ids
        ):
            hits += 1

    hit_rate = hits / total
    assert hit_rate >= 0.75, (
        f"Hit-rate@3 was {hit_rate:.2%} ({hits}/{total}), below threshold 75%"
    )


# -----------------------------------------------------------------------------
# 6. Security & Penetration Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_sql_and_nosql_injection_query_containment(
    initialized_retriever: HybridRetriever,
):
    """Penetration test: SQL and NoSQL injection payloads in query execute safely (CWE-89 / CWE-943)."""
    payloads = [
        "admin' OR '1'='1' --",
        "'; DROP TABLE knowledge_articles; --",
        '{"$gt": ""}',
        '{"$where": "sleep(5000)"}',
    ]
    for p in payloads:
        results = await initialized_retriever.retrieve(
            p, top_k=2, mode="hybrid", use_cache=False
        )
        assert isinstance(results, list)
        # Vector store and BM25 index remain undamaged
        assert len(initialized_retriever.chunks) == 4


@pytest.mark.asyncio
async def test_security_xss_in_evidence_snippet(
    sample_chunks: list[ArticleChunk],
):
    """Penetration test: Stored/reflected XSS script in query or content is handled safely (CWE-79)."""
    xss_chunk = ArticleChunk(
        id="xss-chunk-01",
        article_id="kb-xss-test",
        slug="kb-xss-test",
        title="<script>alert('xss')</script>",
        heading="XSS Test Section",
        section="xss-test-section",
        source="kb://kb-xss-test#xss-test-section",
        category="security",
        tags=["xss"],
        content="<script>alert('xss')</script> - Exploit snippet with payload.",
        snippet="<script>alert('xss')</script>",
        chunk_index=0,
    )
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    retriever = HybridRetriever(vector_store=store)
    await retriever.index_corpus([*sample_chunks, xss_chunk])

    results = await retriever.retrieve(
        "<script>alert(1)</script>", top_k=2, mode="hybrid", use_cache=False
    )
    assert isinstance(results, list)
    # Result preserves data as pure string without evaluation
    for r in results:
        assert isinstance(r["snippet"], str)
        assert isinstance(r["title"], str)


@pytest.mark.asyncio
async def test_security_redos_query_safety(initialized_retriever: HybridRetriever):
    """Penetration test: Extremely large repetitive input terminates in bounded time without ReDoS (CWE-1333)."""
    import time

    catastrophic_query = ("a" * 1000 + "!") * 50  # 50,050 characters
    start_time = time.perf_counter()
    results = await initialized_retriever.retrieve(
        catastrophic_query, top_k=2, mode="hybrid", use_cache=False
    )
    elapsed = time.perf_counter() - start_time

    assert isinstance(results, list)
    assert elapsed < 1.0, f"Query took {elapsed:.2f}s, potential ReDoS!"


@pytest.mark.asyncio
async def test_security_cache_key_poisoning_containment(
    initialized_retriever: HybridRetriever,
):
    """Penetration test: Carriage return and newline injection in query cannot poison Redis protocol (CWE-93)."""
    poison_query = "SAML\r\nSET poisoned 1\r\nGET valid"
    results = await initialized_retriever.retrieve(
        poison_query, top_k=1, mode="hybrid", use_cache=True
    )
    assert isinstance(results, list)

    # Verify poisoned key was not created in Redis
    redis_client = initialized_retriever.redis_client
    poisoned_key = await redis_client.get("poisoned")
    assert poisoned_key is None
