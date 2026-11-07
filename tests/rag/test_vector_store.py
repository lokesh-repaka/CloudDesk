"""Tests for Vector Store and Fake Embeddings (P5-2).

Tests the core semantic retrieval building blocks:
- FakeEmbeddings: 384-dimensional hashed bag-of-words offline embeddings.
- VectorStoreService protocol: add_documents, search, delete, count, health.
- InMemoryVectorStore: in-memory cosine similarity search, metadata filtering, chunk indexing.
- QdrantVectorStore: protocol compliance and provider selection.
- Factory function: get_vector_store() choosing implementation by VECTOR_STORE setting.
- Security tests: Input sanitization, DoS prevention on huge inputs, metadata injection containment.
"""

import math

import pytest

from backend.app.core.config import Settings
from backend.app.rag.chunking import ArticleDocument, chunk_article
from backend.app.rag.vector_store import (
    FakeEmbeddings,
    InMemoryVectorStore,
    VectorDocument,
    VectorSearchResult,
    VectorStoreService,
    get_vector_store,
)

# -----------------------------------------------------------------------------
# 1. FakeEmbeddings Tests
# -----------------------------------------------------------------------------


def test_fake_embeddings_dimensions():
    """Verify FakeEmbeddings generates vectors with exact dimensions (default 384) and unit norm."""
    embedder = FakeEmbeddings(dimensions=384)
    assert embedder.dimension == 384

    vec = embedder.embed_query("Troubleshooting SAML 2.0 Single Sign-On")
    assert len(vec) == 384
    assert isinstance(vec[0], float)

    # Unit norm: ||v|| = 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-5)


def test_fake_embeddings_deterministic():
    """Verify embedding the same string repeatedly produces identical vectors."""
    embedder = FakeEmbeddings(dimensions=384)
    text = "Expired IdP Signing Certificate in Okta"
    vec1 = embedder.embed_query(text)
    vec2 = embedder.embed_query(text)
    assert vec1 == vec2


def test_fake_embeddings_semantic_similarity():
    """Verify texts sharing vocabulary have higher cosine similarity than unrelated texts."""
    embedder = FakeEmbeddings(dimensions=384)

    # Query and relevant document share keywords
    q_vec = embedder.embed_query("Okta SSO SAML authentication failure")
    doc_match = embedder.embed_query(
        "Troubleshooting SAML 2.0 Single Sign-On SSO Failures with Okta"
    )
    doc_unrelated = embedder.embed_query(
        "Prorated refund policy for license seats and billing invoices"
    )

    sim_match = sum(q * d for q, d in zip(q_vec, doc_match, strict=False))
    sim_unrelated = sum(q * d for q, d in zip(q_vec, doc_unrelated, strict=False))

    assert sim_match > sim_unrelated
    assert sim_match > 0.40


def test_fake_embeddings_empty_string_safe():
    """Verify empty or whitespace-only strings produce a zero or safe unit vector without division error."""
    embedder = FakeEmbeddings(dimensions=384)
    vec = embedder.embed_query("   ")
    assert len(vec) == 384
    assert not any(math.isnan(x) for x in vec)


def test_fake_embeddings_batch_embedding():
    """Verify embed_documents returns vectors for all input texts in batch."""
    embedder = FakeEmbeddings(dimensions=384)
    texts = ["Document one", "Document two", "Document three"]
    vectors = embedder.embed_documents(texts)

    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 384
        norm = math.sqrt(sum(x * x for x in v))
        assert math.isclose(norm, 1.0, rel_tol=1e-5)


# -----------------------------------------------------------------------------
# 2. InMemoryVectorStore Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_vector_store_add_and_count():
    """Verify adding documents to InMemoryVectorStore increments document count."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    assert await store.count() == 0

    docs = [
        VectorDocument(
            id="doc-1",
            text="SAML SSO login configuration",
            metadata={"category": "login_issue"},
        ),
        VectorDocument(
            id="doc-2",
            text="Seat management and refund policy",
            metadata={"category": "billing"},
        ),
    ]
    ids = await store.add_documents(docs)
    assert ids == ["doc-1", "doc-2"]
    assert await store.count() == 2


@pytest.mark.asyncio
async def test_in_memory_vector_store_search_top_k():
    """Verify search returns top_k documents sorted by similarity score descending."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    docs = [
        VectorDocument(
            id="doc-login",
            text="SAML SSO login authentication failure in Okta",
            metadata={"category": "login_issue"},
        ),
        VectorDocument(
            id="doc-billing",
            text="Prorated seat refund policy and invoicing",
            metadata={"category": "billing"},
        ),
        VectorDocument(
            id="doc-quota",
            text="Storage quotas and gigabyte storage tier limits",
            metadata={"category": "storage_quota"},
        ),
    ]
    await store.add_documents(docs)

    results = await store.search("How do I fix Okta SSO login failure?", top_k=2)
    assert len(results) == 2
    assert results[0].id == "doc-login"
    assert results[0].score >= results[1].score
    assert "SAML SSO" in results[0].text


@pytest.mark.asyncio
async def test_in_memory_vector_store_search_with_metadata_filter():
    """Verify metadata filtering restricts results to matching categories."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    docs = [
        VectorDocument(
            id="doc-1",
            text="Quota limit billing issue",
            metadata={"category": "billing"},
        ),
        VectorDocument(
            id="doc-2",
            text="Quota storage limits",
            metadata={"category": "storage_quota"},
        ),
    ]
    await store.add_documents(docs)

    # Search with filter for storage_quota only
    results = await store.search(
        "quota limits", top_k=5, filter={"category": "storage_quota"}
    )
    assert len(results) == 1
    assert results[0].id == "doc-2"
    assert results[0].metadata["category"] == "storage_quota"


@pytest.mark.asyncio
async def test_in_memory_vector_store_delete():
    """Verify delete removes documents by ID and updates count."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    docs = [
        VectorDocument(id="doc-1", text="First doc"),
        VectorDocument(id="doc-2", text="Second doc"),
    ]
    await store.add_documents(docs)
    assert await store.count() == 2

    deleted = await store.delete(["doc-1"])
    assert deleted is True
    assert await store.count() == 1

    # Search confirms doc-1 is gone
    results = await store.search("First doc", top_k=5)
    assert not any(r.id == "doc-1" for r in results)


@pytest.mark.asyncio
async def test_in_memory_vector_store_clear():
    """Verify clear purges all indexed documents."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    await store.add_documents([VectorDocument(id="doc-1", text="Text")])
    assert await store.count() == 1

    await store.clear()
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_in_memory_vector_store_health():
    """Verify health endpoint reports store status, provider, and document count."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    health_empty = await store.health()
    assert health_empty["status"] == "ok"
    assert health_empty["provider"] == "memory"
    assert health_empty["count"] == 0

    await store.add_documents([VectorDocument(id="doc-1", text="Sample")])
    health_populated = await store.health()
    assert health_populated["count"] == 1


# -----------------------------------------------------------------------------
# 3. ArticleChunk Indexing & Evidence Formatting
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_article_chunks_directly():
    """Verify InMemoryVectorStore accepts ArticleChunk instances from chunking pipeline directly."""
    article = ArticleDocument(
        id="art-test-sso",
        slug="test-sso",
        title="SAML SSO Guide",
        category="login_issue",
        tags=["sso", "okta"],
        summary="SSO Guide",
        content="## Common Root Causes\nExpired certificates cause SSO failures.\n\n## Remediation Steps\nUpload a new certificate in admin console.",
    )
    chunks = chunk_article(article)
    assert len(chunks) == 2

    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    ids = await store.add_documents(chunks)
    assert len(ids) == 2
    assert await store.count() == 2

    results = await store.search("certificate expired in Okta", top_k=1)
    assert len(results) == 1
    assert results[0].metadata["article_id"] == "art-test-sso"
    assert results[0].metadata["source"].startswith("kb://test-sso#")


def test_vector_search_result_to_evidence_format():
    """Verify VectorSearchResult formats into the required Evidence dictionary shape (CLAUDE.md §8)."""
    result = VectorSearchResult(
        id="chk-sso-01",
        score=0.912,
        text="SAML SSO Guide - Common Root Causes\n\nExpired certificates cause SSO failures.",
        metadata={
            "article_id": "art-sso-01",
            "title": "SAML SSO Guide",
            "source": "kb://sso-01#common-root-causes",
            "snippet": "Expired certificates cause SSO failures.",
        },
    )
    evidence = result.to_evidence()

    # Evidence shape: { id, title, source: "kb://slug#section", snippet, score, url: "/knowledge/<id>", article_id }
    assert evidence["id"] == "chk-sso-01"
    assert evidence["title"] == "SAML SSO Guide"
    assert evidence["source"] == "kb://sso-01#common-root-causes"
    assert evidence["snippet"] == "Expired certificates cause SSO failures."
    assert evidence["score"] == 0.912
    assert evidence["url"] == "/knowledge/art-sso-01"
    assert evidence["article_id"] == "art-sso-01"


# -----------------------------------------------------------------------------
# 4. Factory Function & Provider Selection
# -----------------------------------------------------------------------------


def test_get_vector_store_memory_default():
    """Verify get_vector_store() returns InMemoryVectorStore when VECTOR_STORE='memory'."""
    settings = Settings(VECTOR_STORE="memory")
    store = get_vector_store(settings=settings)
    assert isinstance(store, InMemoryVectorStore)


def test_get_vector_store_protocol_compliance():
    """Verify returned store adheres to VectorStoreService protocol."""
    store = get_vector_store()
    assert isinstance(store, VectorStoreService)


# -----------------------------------------------------------------------------
# 5. Security & Penetration Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_vector_search_injection_safe():
    """Penetration test: SQL/NoSQL injection payloads in query strings execute safely as vector embeddings (CWE-89)."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    await store.add_documents(
        [VectorDocument(id="doc-1", text="Standard documentation content")]
    )

    sqli_query = (
        "'; DROP TABLE support_articles; SELECT * FROM credentials WHERE '1'='1"
    )
    results = await store.search(sqli_query, top_k=2)
    assert isinstance(results, list)
    # Store remains intact and operational
    assert await store.count() == 1


@pytest.mark.asyncio
async def test_security_massive_input_embedding_bounds():
    """Penetration test: Massive input text (50,000 chars) embeds within memory limits without DoS (CWE-400)."""
    embedder = FakeEmbeddings(dimensions=384)
    massive_text = (
        "Repeated token phrase for memory limit test. " * 1200
    )  # ~54,000 chars

    vec = embedder.embed_query(massive_text)
    assert len(vec) == 384
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-5)


@pytest.mark.asyncio
async def test_security_metadata_isolation():
    """Penetration test: Documents with prototype pollution attempts do not corrupt store internals."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    malicious_meta = {
        "__proto__": {"polluted": True},
        "constructor": {"prototype": {"isAdmin": True}},
        "category": "security",
    }
    await store.add_documents(
        [VectorDocument(id="doc-proto", text="Security text", metadata=malicious_meta)]
    )

    # Verify store attributes are not polluted
    assert not hasattr(store, "polluted")
    assert not hasattr(store, "isAdmin")
    assert await store.count() == 1
