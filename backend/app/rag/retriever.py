"""Hybrid Retriever with BM25, RRF, Heuristic Rerank, and Redis Caching (P5-3).

Implements the RAG retrieval pipeline (CLAUDE.md §7.5, §8):
- Dual retrieval: Semantic similarity via VectorStoreService (InMemoryVectorStore / QdrantVectorStore)
  combined with keyword matching via rank_bm25.BM25Okapi.
- Reciprocal Rank Fusion (RRF): Combines ranks with constant k=60.
- Heuristic Rerank: Category match boost (1.35x) and title token overlap bonus.
- Deduplication: Strictly one hit per article, retaining the highest-scoring chunk per article_id.
- Modes: 'hybrid' (default), 'semantic', and 'keyword'.
- Short-Term Memory Caching: Redis/FakeRedis caching under key 'rag:{mode}:{category}:{top_k}:{query}'
  with 300-second TTL and graceful degradation.
- Evidence Output Shape: List of dicts adhering to:
  { id, title, source: "kb://slug#section", snippet, score, url: "/knowledge/<id>", article_id }.
"""

import json
import logging
import re
from collections.abc import Sequence
from typing import Any

from rank_bm25 import BM25Okapi

from backend.app.core.redis import REDIS_EXCEPTIONS, get_redis_client
from backend.app.rag.chunking import ArticleChunk
from backend.app.rag.vector_store import (
    VectorStoreService,
    get_vector_store,
)

logger = logging.getLogger(__name__)

SUPPORTED_MODES = {"hybrid", "semantic", "keyword"}


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric word tokens for BM25 and overlap heuristics.

    Caps input length at 50,000 characters to safeguard against ReDoS / memory exhaustion.
    """
    if not text:
        return []
    safe_text = text[:50000].lower()
    return re.findall(r"\b\w+\b", safe_text)


class HybridRetriever:
    """Production hybrid retriever combining dense vector search and sparse BM25 scoring."""

    def __init__(
        self,
        vector_store: VectorStoreService | None = None,
        chunks: Sequence[ArticleChunk] | None = None,
        redis_client: Any | None = None,
        cache_ttl: int = 300,
        rrf_k: int = 60,
        category_boost: float = 1.35,
    ) -> None:
        """Initialize the hybrid retriever.

        Args:
            vector_store: VectorStoreService instance. Defaults to get_vector_store().
            chunks: Optional pre-loaded ArticleChunks to index.
            redis_client: Optional async Redis client. Defaults to get_redis_client().
            cache_ttl: Cache TTL in seconds (default 300).
            rrf_k: Reciprocal Rank Fusion constant k (default 60).
            category_boost: Heuristic multiplier for matching ticket category (default 1.35).
        """
        self._vector_store = vector_store
        self._redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.rrf_k = rrf_k
        self.category_boost = category_boost

        self.chunks: list[ArticleChunk] = []
        self._chunk_map: dict[str, ArticleChunk] = {}
        self.bm25: BM25Okapi | None = None

        if chunks:
            self.build_bm25_index(chunks)

    @property
    def vector_store(self) -> VectorStoreService:
        """Active VectorStoreService singleton or injected instance."""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    @property
    def redis_client(self) -> Any:
        """Active Redis/FakeRedis client singleton or injected instance."""
        if self._redis_client is None:
            self._redis_client = get_redis_client()
        return self._redis_client

    @redis_client.setter
    def redis_client(self, client: Any) -> None:
        self._redis_client = client

    def build_bm25_index(self, chunks: Sequence[ArticleChunk]) -> None:
        """Construct BM25Okapi index over the provided chunks."""
        self.chunks = list(chunks)
        self._chunk_map = {c.id: c for c in self.chunks}

        if not self.chunks:
            self.bm25 = None
            return

        tokenized_corpus = [
            _tokenize(f"{c.title} {c.heading} {c.category} {c.content}")
            for c in self.chunks
        ]
        self.bm25 = BM25Okapi(tokenized_corpus)

    async def index_corpus(self, chunks: Sequence[ArticleChunk]) -> None:
        """Index a full corpus into both the dense vector store and sparse BM25 index."""
        self.build_bm25_index(chunks)
        await self.vector_store.add_documents(chunks)

    async def retrieve(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 3,
        mode: str = "hybrid",
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieve top_k evidence articles for a query.

        Args:
            query: User/ticket message query string.
            category: Optional ticket category for heuristic reranking boost.
            top_k: Number of unique article evidence items to return (default 3).
            mode: Retrieval mode ('hybrid', 'semantic', or 'keyword').
            use_cache: Whether to check and write short-term Redis cache (default True).

        Returns:
            List of evidence dictionaries conforming to CLAUDE.md §8:
            [{ id, title, source, snippet, score, url, article_id }]

        Raises:
            ValueError: If an unsupported mode is provided.
        """
        if mode not in SUPPORTED_MODES:
            raise ValueError(
                f"Invalid retrieval mode: '{mode}'. Must be one of: {sorted(SUPPORTED_MODES)}"
            )

        if not query or not query.strip():
            return []

        clean_query = query.strip()
        cat_key = category.strip().lower() if category and category.strip() else "all"

        # Sanitize query for Redis key (strip newlines / carriage returns to prevent CRLF injection)
        safe_query_key = re.sub(r"[\r\n]+", " ", clean_query)[:256]
        cache_key = f"rag:{mode}:{cat_key}:{top_k}:{safe_query_key}"

        # 1. Short-term Cache Lookup
        if use_cache:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug("Redis retrieval cache HIT for key: %s", cache_key)
                    return json.loads(cached_data)
            except REDIS_EXCEPTIONS as err:
                logger.warning(
                    "Redis cache read failed for key '%s': %s (degrading to live search)",
                    cache_key,
                    err,
                )

        # 2. Perform live retrieval based on selected mode
        evidence = await self._execute_retrieval(
            query=clean_query,
            category=category,
            top_k=top_k,
            mode=mode,
        )

        # 3. Short-term Cache Store
        if use_cache:
            try:
                await self.redis_client.set(
                    cache_key,
                    json.dumps(evidence),
                    ex=self.cache_ttl,
                )
                logger.debug("Redis retrieval cache SET for key: %s", cache_key)
            except REDIS_EXCEPTIONS as err:
                logger.warning(
                    "Redis cache write failed for key '%s': %s",
                    cache_key,
                    err,
                )

        return evidence

    async def _execute_retrieval(
        self,
        query: str,
        category: str | None,
        top_k: int,
        mode: str,
    ) -> list[dict[str, Any]]:
        """Internal search, fusion, reranking, and deduplication logic."""
        if not self.chunks:
            # If no chunks in memory, fall back to vector store search only if available
            if mode == "keyword":
                return []
            vector_results = await self.vector_store.search(
                query, top_k=top_k, category=category
            )
            return [r.to_evidence() for r in vector_results]

        candidate_limit = max(20, top_k * 5)

        # A. Semantic Search Candidates
        semantic_ranks: dict[str, int] = {}
        semantic_raw_scores: dict[str, float] = {}
        if mode in ("hybrid", "semantic"):
            v_results = await self.vector_store.search(
                query, top_k=min(candidate_limit, len(self.chunks))
            )
            for rank_idx, res in enumerate(v_results, start=1):
                semantic_ranks[res.id] = rank_idx
                semantic_raw_scores[res.id] = res.score

        # B. Keyword (BM25) Candidates
        bm25_ranks: dict[str, int] = {}
        bm25_raw_scores: dict[str, float] = {}
        if mode in ("hybrid", "keyword") and self.bm25 is not None:
            q_tokens = _tokenize(query)
            if q_tokens:
                scores = self.bm25.get_scores(q_tokens)
                # Pair with chunks and sort descending
                scored_chunks = sorted(
                    zip(self.chunks, scores, strict=True),
                    key=lambda x: x[1],
                    reverse=True,
                )
                for rank_idx, (chunk, sc) in enumerate(
                    scored_chunks[:candidate_limit], start=1
                ):
                    if sc > 0:
                        bm25_ranks[chunk.id] = rank_idx
                        bm25_raw_scores[chunk.id] = float(sc)

        # C. Score Combination & Reranking
        candidate_ids = set()
        if mode == "hybrid":
            candidate_ids = set(semantic_ranks.keys()) | set(bm25_ranks.keys())
        elif mode == "semantic":
            candidate_ids = set(semantic_ranks.keys())
        elif mode == "keyword":
            candidate_ids = set(bm25_ranks.keys())

        scored_candidates: list[tuple[ArticleChunk, float]] = []
        query_tokens = set(_tokenize(query))
        target_category = category.strip().lower() if category else None

        for cid in candidate_ids:
            chunk = self._chunk_map.get(cid)
            if not chunk:
                continue

            # Calculate base score
            if mode == "hybrid":
                # Reciprocal Rank Fusion (k=60)
                rrf_score = 0.0
                if cid in semantic_ranks:
                    rrf_score += 1.0 / (self.rrf_k + semantic_ranks[cid])
                if cid in bm25_ranks:
                    rrf_score += 1.0 / (self.rrf_k + bm25_ranks[cid])
                score = rrf_score
            elif mode == "semantic":
                score = semantic_raw_scores.get(cid, 0.0)
            else:  # keyword
                score = bm25_raw_scores.get(cid, 0.0)

            # Heuristic Rerank 1: Category Match Boost (1.35x)
            chunk_category = chunk.category.lower()
            if target_category and chunk_category == target_category:
                score *= self.category_boost

            # Heuristic Rerank 2: Title / Keyword Token Overlap Bonus
            title_tokens = set(_tokenize(chunk.title))
            overlap = len(title_tokens & query_tokens)
            if overlap > 0:
                bonus = (overlap / max(1, len(title_tokens))) * 0.05
                score += bonus

            scored_candidates.append((chunk, score))

        # D. Deduplication: strictly one hit per article (CLAUDE.md §8)
        # Group by article_id and select the chunk with the highest score
        best_per_article: dict[str, tuple[ArticleChunk, float]] = {}
        for chunk, score in scored_candidates:
            aid = chunk.article_id
            if aid not in best_per_article or score > best_per_article[aid][1]:
                best_per_article[aid] = (chunk, score)

        # Sort deduplicated articles by final score descending
        ranked_articles = sorted(
            best_per_article.values(), key=lambda x: x[1], reverse=True
        )

        # E. Slice top_k and format into canonical Evidence shape
        results: list[dict[str, Any]] = []
        for chunk, score in ranked_articles[:top_k]:
            evidence = chunk.to_evidence(score=round(score, 4))
            results.append(evidence)

        return results
