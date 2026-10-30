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
    "InMemoryVectorStore",
    "QdrantVectorStore",
    "VectorDocument",
    "VectorSearchResult",
    "VectorStoreService",
    "chunk_all_articles",
    "chunk_article",
    "get_vector_store",
    "load_article_file",
    "load_article_files",
    "slugify_heading",
]
