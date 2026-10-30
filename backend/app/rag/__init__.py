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

__all__ = [
    "ArticleChunk",
    "ArticleDocument",
    "chunk_all_articles",
    "chunk_article",
    "load_article_file",
    "load_article_files",
    "slugify_heading",
]
