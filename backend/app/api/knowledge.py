"""Knowledge Base API Endpoints (P5-4).

Provides:
- POST /api/v1/knowledge/search: Hybrid RAG retrieval over support articles (Viewer+)
- POST /api/v1/knowledge/reindex: Re-chunking and vector collection indexing (Admin-only)
- GET /api/v1/knowledge/articles: Catalog listing of all knowledge articles (Viewer+)
- GET /api/v1/knowledge/articles/{id_or_slug}: Detailed article dossier with markdown body (Viewer+)
"""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.rag.chunking import load_article_files
from backend.app.rag.ingest import ingest_knowledge_base
from backend.app.rag.retriever import get_retriever
from backend.app.schemas.common import RoleEnum
from backend.app.schemas.knowledge import (
    KnowledgeArticleDetail,
    KnowledgeArticleSummary,
    KnowledgeEvidenceResponse,
    KnowledgeReindexResponse,
    KnowledgeSearchRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["knowledge"])

DEFAULT_KB_DIR = Path("sample_data/knowledge_base")


@router.post(
    "/search",
    response_model=list[KnowledgeEvidenceResponse],
    summary="Hybrid RAG Search",
    description="Retrieve ranked knowledge base evidence hits with citations for support context.",
)
async def search_knowledge_base(
    payload: KnowledgeSearchRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
) -> list[KnowledgeEvidenceResponse]:
    """Execute hybrid dense/sparse retrieval and return citation evidence."""
    retriever = get_retriever()
    category_val = payload.category.value if payload.category else None

    raw_evidence = await retriever.retrieve(
        query=payload.query,
        category=category_val,
        top_k=payload.top_k,
        mode=payload.mode,
    )

    return [KnowledgeEvidenceResponse(**e) for e in raw_evidence]


@router.post(
    "/reindex",
    response_model=KnowledgeReindexResponse,
    status_code=status.HTTP_200_OK,
    summary="Reindex Knowledge Base",
    description="Re-chunks markdown articles and rebuilds vector store and BM25 index (Admin only).",
)
async def reindex_knowledge_base(
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.ADMIN))],
) -> KnowledgeReindexResponse:
    """Trigger administrative re-chunking and vector store ingestion."""
    logger.info(
        "Admin user '%s' initiated knowledge base re-indexing.", current_user.email
    )
    stats = await ingest_knowledge_base(recreate=True)
    return KnowledgeReindexResponse(
        indexed_articles=stats["indexed_articles"],
        total_chunks=stats["total_chunks"],
    )


@router.get(
    "/articles",
    response_model=list[KnowledgeArticleSummary],
    summary="List Knowledge Base Articles",
    description="Catalog listing of available knowledge base articles.",
)
async def list_knowledge_articles(
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
) -> list[KnowledgeArticleSummary]:
    """Return summary catalog of all knowledge base articles."""
    if not DEFAULT_KB_DIR.is_dir():
        return []

    articles = load_article_files(DEFAULT_KB_DIR)
    return [
        KnowledgeArticleSummary(
            id=art.id,
            slug=art.slug,
            title=art.title,
            category=art.category,
            tags=art.tags,
            summary=art.summary,
            url=f"/knowledge/{art.id}",
        )
        for art in articles
    ]


@router.get(
    "/articles/{id_or_slug}",
    response_model=KnowledgeArticleDetail,
    summary="Get Knowledge Article Dossier",
    description="Retrieve a single knowledge article with full markdown content by ID or slug.",
)
async def get_knowledge_article(
    id_or_slug: str,
    current_user: Annotated[AuthenticatedUser, Depends(require_role(RoleEnum.VIEWER))],
) -> KnowledgeArticleDetail:
    """Retrieve full article detail by slug or art- identifier with path traversal protection."""
    # Sanitize against path traversal attempts
    if ".." in id_or_slug or "/" in id_or_slug or "\\" in id_or_slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge article '{id_or_slug}' not found",
        )

    clean_target = id_or_slug.strip()
    slug_candidate = clean_target.removeprefix("art-")

    if not DEFAULT_KB_DIR.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base directory not configured",
        )

    articles = load_article_files(DEFAULT_KB_DIR)
    matched = next(
        (
            a
            for a in articles
            if a.slug == slug_candidate
            or a.id == clean_target
            or a.slug == clean_target
        ),
        None,
    )

    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge article '{id_or_slug}' not found",
        )

    return KnowledgeArticleDetail(
        id=matched.id,
        slug=matched.slug,
        title=matched.title,
        category=matched.category,
        tags=matched.tags,
        summary=matched.summary,
        url=f"/knowledge/{matched.id}",
        content=matched.content,
        file_path=matched.file_path,
    )
