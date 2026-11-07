"""Knowledge Base Ingestion Service and CLI Command (P5-4).

Implements knowledge base chunking, vector indexing, and sparse index population:
sample_data/knowledge_base/*.md -> load_article_files -> chunk_all_articles -> vector store + BM25

Usage:
    python -m backend.app.rag.ingest [--kb-dir PATH] [--recreate]
    make ingest
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure repository root is on sys.path when executed as a script
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.rag.chunking import chunk_all_articles, load_article_files
from backend.app.rag.retriever import get_retriever
from backend.app.rag.vector_store import VectorStoreService, get_vector_store

logger = logging.getLogger(__name__)


async def ingest_knowledge_base(
    kb_dir: Path | str | None = None,
    recreate: bool = False,
    vector_store: VectorStoreService | None = None,
) -> dict[str, int]:
    """Ingest, chunk, and index markdown knowledge articles into vector store and BM25 index.

    Args:
        kb_dir: Directory containing knowledge markdown articles. Defaults to sample_data/knowledge_base.
        recreate: If True, clears existing vector store collections before re-indexing.
        vector_store: Optional VectorStoreService instance. Defaults to get_vector_store().

    Returns:
        dict containing 'indexed_articles' and 'total_chunks'.
    """
    path = Path(kb_dir or "sample_data/knowledge_base")
    if not path.is_dir():
        logger.warning(
            "Knowledge base directory '%s' does not exist or is not a directory.", path
        )
        return {"indexed_articles": 0, "total_chunks": 0}

    # 1. Load markdown files with YAML front-matter
    articles = load_article_files(path)
    if not articles:
        logger.info("No markdown articles found in '%s'.", path)
        return {"indexed_articles": 0, "total_chunks": 0}

    # 2. Chunk articles using heading-based sliding window strategy
    chunks = chunk_all_articles(articles)

    # 3. Vector Store ingestion
    store = vector_store or get_vector_store()
    if recreate:
        logger.info("Clearing vector store collection before re-indexing...")
        await store.clear()

    if chunks:
        logger.info("Adding %d discrete text chunks to vector store...", len(chunks))
        await store.add_documents(chunks)

    # 4. Synchronize HybridRetriever singleton in memory
    retriever = get_retriever()
    retriever.build_bm25_index(chunks)
    if vector_store is not None:
        retriever._vector_store = vector_store

    result = {
        "indexed_articles": len(articles),
        "total_chunks": len(chunks),
    }
    logger.info(
        "Successfully ingested %d articles into %d chunks.",
        result["indexed_articles"],
        result["total_chunks"],
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for knowledge base ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest knowledge base markdown files into vector store and BM25 index."
    )
    parser.add_argument(
        "--kb-dir",
        type=str,
        default="sample_data/knowledge_base",
        help="Path to knowledge base markdown files (default: sample_data/knowledge_base)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate / clear vector store collection before indexing",
    )

    args = parser.parse_args(argv)

    try:
        stats = asyncio.run(
            ingest_knowledge_base(
                kb_dir=args.kb_dir,
                recreate=args.recreate,
            )
        )
        print(
            f"Successfully ingested {stats['indexed_articles']} knowledge articles "
            f"({stats['total_chunks']} chunks) into vector store."
        )
        return 0
    except (OSError, ValueError, RuntimeError, ConnectionError) as exc:
        print(f"Error during knowledge ingestion: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
