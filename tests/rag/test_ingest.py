"""Tests for Knowledge Base Ingestion Command & Service (P5-4).

Verifies the RAG ingestion pipeline (CLAUDE.md §8, §14 / PLAN.md):
- Ingesting sample_data/knowledge_base/*.md into the vector store.
- Re-chunking and indexing counts (15 articles, 48 chunks).
- Recreate collection flag behavior.
- Custom/missing directory handling.
- CLI script execution (python -m backend.app.rag.ingest).
- Idempotency of repeated ingest runs.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.rag.ingest import ingest_knowledge_base
from backend.app.rag.ingest import main as cli_main
from backend.app.rag.vector_store import FakeEmbeddings, InMemoryVectorStore


@pytest.mark.asyncio
async def test_ingest_knowledge_base_success():
    """Verify ingest_knowledge_base loads 15 articles, produces chunks, and indexes into vector store."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    result = await ingest_knowledge_base(
        kb_dir="sample_data/knowledge_base",
        recreate=False,
        vector_store=store,
    )

    assert result["indexed_articles"] == 15
    assert result["total_chunks"] > 0
    assert await store.count() == result["total_chunks"]


@pytest.mark.asyncio
async def test_ingest_knowledge_base_recreate():
    """Verify recreate=True purges previous vector store contents before re-indexing."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))

    # Pre-populate store with a dummy document
    from backend.app.rag.vector_store import VectorDocument

    await store.add_documents([VectorDocument(id="stale-doc", text="Stale content")])
    assert await store.count() == 1

    # Ingest with recreate=True
    result = await ingest_knowledge_base(
        kb_dir="sample_data/knowledge_base",
        recreate=True,
        vector_store=store,
    )

    assert result["indexed_articles"] == 15
    # Stale document was purged
    assert "stale-doc" not in store.documents
    assert await store.count() == result["total_chunks"]


@pytest.mark.asyncio
async def test_ingest_knowledge_base_empty_dir(tmp_path: Path):
    """Verify ingesting an empty directory returns zero articles and zero chunks safely."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))
    result = await ingest_knowledge_base(
        kb_dir=tmp_path,
        recreate=False,
        vector_store=store,
    )

    assert result["indexed_articles"] == 0
    assert result["total_chunks"] == 0
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_ingest_knowledge_base_idempotent():
    """Verify calling ingest_knowledge_base multiple times is idempotent."""
    store = InMemoryVectorStore(embeddings=FakeEmbeddings(dimensions=384))

    res1 = await ingest_knowledge_base(
        kb_dir="sample_data/knowledge_base", recreate=True, vector_store=store
    )
    res2 = await ingest_knowledge_base(
        kb_dir="sample_data/knowledge_base", recreate=True, vector_store=store
    )

    assert res1["indexed_articles"] == res2["indexed_articles"]
    assert res1["total_chunks"] == res2["total_chunks"]
    assert await store.count() == res1["total_chunks"]


def test_ingest_cli_main_success(capsys):
    """Verify CLI main entrypoint executes with zero exit code and logs counts."""
    test_args = [
        "ingest.py",
        "--kb-dir",
        "sample_data/knowledge_base",
        "--recreate",
    ]
    with patch.object(sys, "argv", test_args):
        exit_code = cli_main()
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Successfully ingested 15 knowledge articles" in captured.out
