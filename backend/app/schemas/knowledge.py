"""Knowledge Base Schemas (P5-4).

Defines Pydantic request and response models for:
- Hybrid RAG search queries and evidence hit citations (CLAUDE.md §8 / API_CONTRACT.md §5.2).
- Administrative knowledge base re-indexing responses.
- Knowledge base article catalog summaries and detailed dossiers.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.common import CategoryEnum


class KnowledgeSearchRequest(BaseModel):
    """Payload for hybrid RAG knowledge search requests."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Search query string or support ticket context",
    )
    category: CategoryEnum | None = Field(
        default=None,
        description="Optional ticket category for heuristic reranking",
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum number of unique article evidence items to return",
    )
    mode: str = Field(
        default="hybrid",
        pattern=r"^(hybrid|semantic|keyword)$",
        description="Retrieval mode: 'hybrid' (default), 'semantic', or 'keyword'",
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query cannot be blank or whitespace-only")
        return stripped


class KnowledgeEvidenceResponse(BaseModel):
    """Canonical Evidence dictionary shape required by LangGraph agents and frontend citations."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique chunk identifier")
    title: str = Field(..., description="Knowledge article title")
    source: str = Field(..., description="Canonical source URI: kb://slug#section")
    snippet: str = Field(..., description="Contextual text snippet from the article")
    score: float = Field(..., description="Reranked fusion relevance score")
    url: str = Field(
        ..., description="Web application URL route: /knowledge/<article_id>"
    )
    article_id: str = Field(..., description="Parent article identifier")


class KnowledgeReindexResponse(BaseModel):
    """Summary metrics returned upon completing administrative vector re-indexing."""

    indexed_articles: int = Field(
        ..., description="Number of parsed knowledge articles"
    )
    total_chunks: int = Field(
        ..., description="Total discrete text chunks indexed into vector store"
    )


class KnowledgeArticleSummary(BaseModel):
    """High-level summary of a knowledge base article for catalog listings."""

    id: str = Field(..., description="Article identifier (e.g. 'art-kb-login-01-sso')")
    slug: str = Field(
        ..., description="Kebab-case article slug (e.g. 'kb-login-01-sso')"
    )
    title: str = Field(..., description="Article title")
    category: str = Field(..., description="Domain category")
    tags: list[str] = Field(default_factory=list, description="Associated search tags")
    summary: str = Field(..., description="Executive summary of the article")
    url: str = Field(..., description="Knowledge URL path")


class KnowledgeArticleDetail(KnowledgeArticleSummary):
    """Full article dossier including markdown body content."""

    content: str = Field(..., description="Full article markdown body content")
    file_path: str | None = Field(default=None, description="Source markdown file path")
