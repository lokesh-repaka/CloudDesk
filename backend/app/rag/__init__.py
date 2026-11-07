"""CloudDesk RAG Pipeline Package.

Provides knowledge base article parsing, heading-based chunking,
vector store indexing, and hybrid retrieval.
"""

from backend.app.rag.chunking import (
    ArticleChunk,
    ArticleDocument,
    chunk_all_articles,
    chunk_article,
    load_article_file,
    load_article_files,
    slugify_heading,
)
from backend.app.rag.retriever import HybridRetriever, get_retriever
from backend.app.rag.vector_store import (
    EmbeddingsService,
    FakeEmbeddings,
    InMemoryVectorStore,
    QdrantVectorStore,
    VectorDocument,
    VectorSearchResult,
    VectorStoreService,
    get_vector_store,
)

__all__ = [
    "ArticleChunk",
    "ArticleDocument",
    "EmbeddingsService",
    "FakeEmbeddings",
    "HybridRetriever",
    "InMemoryVectorStore",
    "QdrantVectorStore",
    "VectorDocument",
    "VectorSearchResult",
    "VectorStoreService",
    "chunk_all_articles",
    "chunk_article",
    "get_retriever",
    "get_vector_store",
    "ingest_knowledge_base",
    "load_article_file",
    "load_article_files",
    "slugify_heading",
]


def __getattr__(name: str):
    if name == "ingest_knowledge_base":
        from backend.app.rag.ingest import ingest_knowledge_base

        return ingest_knowledge_base
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
