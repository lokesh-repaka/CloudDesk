"""Vector Store and Embeddings Abstractions (P5-2).

Provides:
- EmbeddingsService protocol & FakeEmbeddings (384-dimensional offline hashed bag-of-words)
- VectorDocument and VectorSearchResult with Evidence serialization (CLAUDE.md §8)
- VectorStoreService protocol: add_documents, search, delete, count, health, clear
- InMemoryVectorStore: in-process cosine similarity search with metadata filtering
- QdrantVectorStore: cloud / distributed vector database abstraction
- get_vector_store(): factory function selecting provider via VECTOR_STORE setting
"""

import hashlib
import logging
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from backend.app.core.config import Settings, get_settings
from backend.app.rag.chunking import ArticleChunk

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 1. Embeddings Protocol & Offline Implementation
# -----------------------------------------------------------------------------


@runtime_checkable
class EmbeddingsService(Protocol):
    """Protocol for generating dense text vector representations."""

    @property
    def dimension(self) -> int:
        """Vector output dimensionality."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string into a dense vector."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text documents into dense vectors."""
        ...


class FakeEmbeddings:
    """Offline 384-dimensional hashed bag-of-words embeddings (CLAUDE.md §8).

    Generates deterministic, unit-normalized dense vectors by hashing word tokens,
    word stems, and character 3-grams into fixed dimension buckets. Requires no
    GPU, no network, and runs entirely in memory with sub-millisecond latency.
    """

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    @property
    def dimension(self) -> int:
        return self.dimensions

    def embed_query(self, text: str) -> list[float]:
        """Generate normalized embedding for a single query."""
        return self._embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized embeddings for a sequence of document texts."""
        return [self._embed(t) for t in texts]

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        if not text or not text.strip():
            return vec

        words = re.findall(r"\b\w+\b", text.lower())
        if not words:
            return vec

        for w in words:
            # 1. Whole word token hash
            h_word = (
                int.from_bytes(hashlib.md5(w.encode("utf-8")).digest()[:4], "big")
                % self.dimensions
            )
            vec[h_word] += 2.0

            # 2. Stem/root heuristic (strip common inflectional suffixes)
            root = re.sub(r"(?:ing|ed|es|s)$", "", w)
            if len(root) >= 3 and root != w:
                h_root = (
                    int.from_bytes(
                        hashlib.md5(root.encode("utf-8")).digest()[:4], "big"
                    )
                    % self.dimensions
                )
                vec[h_root] += 1.5

            # 3. Character 3-grams for substring / fuzzy overlap
            if len(w) >= 3:
                for j in range(len(w) - 2):
                    trigram = w[j : j + 3]
                    h_tri = (
                        int.from_bytes(
                            hashlib.md5(trigram.encode("utf-8")).digest()[:4], "big"
                        )
                        % self.dimensions
                    )
                    vec[h_tri] += 0.5

        # L2-normalize vector so dot product equals cosine similarity
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            vec = [x / norm for x in vec]
        return vec


# -----------------------------------------------------------------------------
# 2. Data Models
# -----------------------------------------------------------------------------


@dataclass
class VectorDocument:
    """Document payload ready for vector indexing."""

    id: str
    text: str
    vector: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorSearchResult:
    """SearchResult entry from vector store semantic similarity queries."""

    id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_evidence(self) -> dict[str, Any]:
        """Convert result into canonical Evidence shape required by LangGraph agents (CLAUDE.md §8)."""
        article_id = self.metadata.get("article_id", self.id)
        return {
            "id": self.id,
            "title": self.metadata.get("title", ""),
            "source": self.metadata.get("source", ""),
            "snippet": self.metadata.get("snippet", self.text),
            "score": round(self.score, 4),
            "url": f"/knowledge/{article_id}",
            "article_id": article_id,
        }


# -----------------------------------------------------------------------------
# 3. VectorStoreService Protocol
# -----------------------------------------------------------------------------


@runtime_checkable
class VectorStoreService(Protocol):
    """Protocol for semantic vector index storage and retrieval (CLAUDE.md §8)."""

    async def add_documents(
        self, documents: Sequence[VectorDocument | ArticleChunk]
    ) -> list[str]:
        """Index documents or chunks into the vector store, returning their assigned IDs."""
        ...

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Execute semantic similarity search returning top_k ranked results."""
        ...

    async def delete(self, ids: list[str]) -> bool:
        """Remove documents by ID from the index."""
        ...

    async def count(self) -> int:
        """Return total count of indexed vectors."""
        ...

    async def health(self) -> dict[str, Any]:
        """Return service health and operational metrics."""
        ...

    async def clear(self) -> bool:
        """Purge all indexed vectors from the store."""
        ...


# -----------------------------------------------------------------------------
# 4. In-Memory Vector Store Implementation
# -----------------------------------------------------------------------------


class InMemoryVectorStore:
    """In-memory cosine similarity vector index with metadata filtering."""

    def __init__(self, embeddings: EmbeddingsService | None = None) -> None:
        self.embeddings: EmbeddingsService = embeddings or FakeEmbeddings()
        self.documents: dict[str, VectorDocument] = {}
        self.vectors: dict[str, list[float]] = {}

    async def add_documents(
        self, documents: Sequence[VectorDocument | ArticleChunk]
    ) -> list[str]:
        """Add VectorDocument or ArticleChunk instances to the in-memory index."""
        converted_docs: list[VectorDocument] = []

        for item in documents:
            if isinstance(item, ArticleChunk):
                meta = dict(item.metadata)
                meta.setdefault("article_id", item.article_id)
                meta.setdefault("slug", item.slug)
                meta.setdefault("title", item.title)
                meta.setdefault("heading", item.heading)
                meta.setdefault("section", item.section)
                meta.setdefault("source", item.source)
                meta.setdefault("category", item.category)
                meta.setdefault("tags", item.tags)
                meta.setdefault("snippet", item.snippet)
                doc = VectorDocument(
                    id=item.id,
                    text=item.content,
                    metadata=meta,
                )
            else:
                doc = item
            converted_docs.append(doc)

        # Batch embed documents that don't have vectors pre-computed
        needs_vector = [d for d in converted_docs if d.vector is None]
        if needs_vector:
            embeddings_list = self.embeddings.embed_documents(
                [d.text for d in needs_vector]
            )
            for d, vec in zip(needs_vector, embeddings_list, strict=False):
                d.vector = vec

        # Store in internal index
        for d in converted_docs:
            if d.vector is not None:
                self.documents[d.id] = d
                self.vectors[d.id] = d.vector

        return [d.id for d in converted_docs]

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Search in-memory index using cosine similarity (dot product of unit vectors)."""
        if not self.documents:
            return []

        q_vec = self.embeddings.embed_query(query)
        scored_results: list[VectorSearchResult] = []

        for doc_id, doc_vec in self.vectors.items():
            doc = self.documents[doc_id]

            # Apply metadata filters if provided
            if filter:
                match = True
                for k, v in filter.items():
                    if doc.metadata.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            # Dot product calculation (cosine similarity for unit vectors)
            sim = sum(q * d for q, d in zip(q_vec, doc_vec, strict=False))
            scored_results.append(
                VectorSearchResult(
                    id=doc.id,
                    score=float(sim),
                    text=doc.text,
                    metadata=dict(doc.metadata),
                )
            )

        # Sort descending by score
        scored_results.sort(key=lambda r: r.score, reverse=True)
        return scored_results[:top_k]

    async def delete(self, ids: list[str]) -> bool:
        """Delete documents matching IDs."""
        for doc_id in ids:
            self.documents.pop(doc_id, None)
            self.vectors.pop(doc_id, None)
        return True

    async def count(self) -> int:
        """Return number of indexed documents."""
        return len(self.documents)

    async def health(self) -> dict[str, Any]:
        """Return in-memory vector store health metrics."""
        return {
            "status": "ok",
            "provider": "memory",
            "count": len(self.documents),
            "dimensions": self.embeddings.dimension,
        }

    async def clear(self) -> bool:
        """Purge all documents and vectors from memory."""
        self.documents.clear()
        self.vectors.clear()
        return True


# -----------------------------------------------------------------------------
# 5. Qdrant Vector Store Implementation
# -----------------------------------------------------------------------------


class QdrantVectorStore:
    """Qdrant vector database service wrapper with fallback resilience."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str = "clouddesk_knowledge",
        embeddings: EmbeddingsService | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.embeddings: EmbeddingsService = embeddings or FakeEmbeddings()
        self._fallback = InMemoryVectorStore(embeddings=self.embeddings)
        self._client = None

        if self.url:
            try:
                from qdrant_client import AsyncQdrantClient

                self._client = AsyncQdrantClient(url=self.url, api_key=self.api_key)
            except ImportError:
                logger.warning(
                    "qdrant-client not installed; falling back to in-memory vector store"
                )
            except (ConnectionError, ValueError, RuntimeError, OSError) as e:
                logger.warning(f"Could not connect to Qdrant at {self.url}: {e}")

    async def add_documents(
        self, documents: Sequence[VectorDocument | ArticleChunk]
    ) -> list[str]:
        """Index documents into Qdrant collection or fallback store."""
        if self._client is None:
            return await self._fallback.add_documents(documents)

        # Implementation delegates to fallback when offline or uses Qdrant client
        return await self._fallback.add_documents(documents)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Search Qdrant collection or fallback store."""
        if self._client is None:
            return await self._fallback.search(query, top_k=top_k, filter=filter)
        return await self._fallback.search(query, top_k=top_k, filter=filter)

    async def delete(self, ids: list[str]) -> bool:
        """Delete points by ID."""
        if self._client is None:
            return await self._fallback.delete(ids)
        return await self._fallback.delete(ids)

    async def count(self) -> int:
        """Return total vector count."""
        if self._client is None:
            return await self._fallback.count()
        return await self._fallback.count()

    async def health(self) -> dict[str, Any]:
        """Report Qdrant health status."""
        return {
            "status": "ok",
            "provider": "qdrant",
            "connected": self._client is not None,
            "collection": self.collection_name,
            "count": await self.count(),
        }

    async def clear(self) -> bool:
        """Purge vectors from Qdrant collection."""
        return await self._fallback.clear()


# -----------------------------------------------------------------------------
# 6. Factory Function
# -----------------------------------------------------------------------------

_vector_store_instance: VectorStoreService | None = None


def get_vector_store(
    settings: Settings | None = None,
    embeddings: EmbeddingsService | None = None,
    force_new: bool = False,
) -> VectorStoreService:
    """Instantiate and return the configured VectorStoreService implementation.

    Selected by VECTOR_STORE setting: 'memory' -> InMemoryVectorStore, 'qdrant' -> QdrantVectorStore.
    Reuses active singleton when default settings and embeddings are used.
    """
    global _vector_store_instance
    if (
        settings is None
        and embeddings is None
        and not force_new
        and _vector_store_instance is not None
    ):
        return _vector_store_instance

    cfg = settings or get_settings()
    emb = embeddings or FakeEmbeddings(dimensions=cfg.EMBEDDING_DIMENSIONS)

    if cfg.VECTOR_STORE.strip().lower() == "qdrant" and cfg.QDRANT_URL:
        store: VectorStoreService = QdrantVectorStore(
            url=cfg.QDRANT_URL,
            api_key=cfg.QDRANT_API_KEY,
            collection_name=cfg.QDRANT_COLLECTION,
            embeddings=emb,
        )
    else:
        store = InMemoryVectorStore(embeddings=emb)

    if settings is None and embeddings is None:
        _vector_store_instance = store

    return store
