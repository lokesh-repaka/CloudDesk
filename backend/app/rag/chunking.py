"""Knowledge Base Article Ingestion & Heading-Based Chunking (P5-1).

Implements the RAG ingestion pipeline:
sample_data/knowledge_base/*.md -> load_article_files -> chunk_article

Chunking rules (CLAUDE.md §8 / MEMORY.md):
- Split on headings.
- For each section, slide 900-char windows with 150-char overlap.
- Every chunk is prefixed with "{title} - {heading}" so short chunks stay retrievable.
- Canonical source URI format: "kb://slug#section".
- Evidence shape: { id, title, source: "kb://slug#section", snippet, score, url: "/knowledge/<id>", article_id }.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_KB_DIR = Path("sample_data/knowledge_base")


def slugify_heading(heading: str) -> str:
    """Convert heading text to clean kebab-case anchor slug (e.g. 'Common Root Causes' -> 'common-root-causes')."""
    s = heading.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "overview"


@dataclass
class ArticleDocument:
    """Represents a parsed knowledge base article from a markdown file with YAML front-matter."""

    id: str
    slug: str
    title: str
    category: str
    tags: list[str]
    summary: str
    content: str
    file_path: str | None = None


@dataclass
class ArticleChunk:
    """Represents a discrete text chunk extracted from a knowledge base article for retrieval."""

    id: str
    article_id: str
    slug: str
    title: str
    heading: str
    section: str
    source: str
    category: str
    tags: list[str]
    content: str  # Prefixed with "{title} - {heading}\n\n{snippet}"
    snippet: str  # Body text without heading prefix
    chunk_index: int
    char_count: int = field(init=False)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.char_count = len(self.content)
        if not self.metadata:
            self.metadata = {
                "chunk_id": self.id,
                "article_id": self.article_id,
                "slug": self.slug,
                "title": self.title,
                "heading": self.heading,
                "section": self.section,
                "source": self.source,
                "category": self.category,
                "tags": self.tags,
                "chunk_index": self.chunk_index,
                "char_count": self.char_count,
            }

    def to_evidence(self, score: float = 0.0) -> dict[str, Any]:
        """Convert chunk into the canonical Evidence dictionary shape required by agents (CLAUDE.md §8)."""
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "snippet": self.snippet,
            "score": score,
            "url": f"/knowledge/{self.article_id}",
            "article_id": self.article_id,
        }


def load_article_file(file_path: Path | str) -> ArticleDocument:
    """Load and parse a single knowledge base markdown article file with YAML front-matter."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Knowledge article file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    if not raw_text.startswith("---"):
        raise ValueError(f"Article {path.name} missing YAML front-matter header")

    parts = raw_text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Malformed front-matter delimiters in {path.name}")

    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()

    slug = path.stem
    article_id = f"art-{slug}"
    title = str(meta.get("title") or slug.replace("-", " ").title())
    category = str(meta.get("category") or "other")
    tags = list(meta.get("tags") or [])
    summary = str(meta.get("summary") or "")

    return ArticleDocument(
        id=article_id,
        slug=slug,
        title=title,
        category=category,
        tags=tags,
        summary=summary,
        content=body,
        file_path=str(path),
    )


def load_article_files(
    directory_or_files: Path | str | list[Path | str] | None = None,
) -> list[ArticleDocument]:
    """Discover and parse markdown knowledge base articles into ArticleDocument models."""
    if directory_or_files is None:
        target_dir = DEFAULT_KB_DIR
        if not target_dir.is_dir():
            raise FileNotFoundError(
                f"Default knowledge base directory not found: {target_dir}"
            )
        file_paths = sorted(target_dir.glob("*.md"))
    elif isinstance(directory_or_files, (Path, str)):
        path = Path(directory_or_files)
        if path.is_file():
            return [load_article_file(path)]
        if not path.is_dir():
            raise FileNotFoundError(f"Knowledge base path does not exist: {path}")
        file_paths = sorted(path.glob("*.md"))
    else:
        file_paths = [Path(p) for p in directory_or_files]

    articles = [load_article_file(fp) for fp in file_paths]
    articles.sort(key=lambda a: a.slug)
    return articles


def _split_markdown_sections(
    markdown_text: str, article_title: str
) -> list[tuple[str, str]]:
    """Split markdown body into (heading, section_text) tuples.

    Top-level H1 matching the article title is categorized as 'Overview' to prevent
    redundant '{title} - {title}' prefix repetition while preserving section context.
    """
    lines = markdown_text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Overview"
    current_lines: list[str] = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            # Store completed section if it has content
            if current_lines:
                sections.append((current_heading, current_lines))
            heading_text = match.group(2).strip()
            # If H1 equals the article title, canonicalize to 'Overview'
            if match.group(1) == "#" and heading_text.lower() == article_title.lower():
                current_heading = "Overview"
            else:
                current_heading = heading_text
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    # Clean and filter non-empty sections
    clean_sections: list[tuple[str, str]] = []
    for heading, line_list in sections:
        body = "\n".join(line_list).strip()
        if body:
            clean_sections.append((heading, body))

    return clean_sections


def chunk_article(
    article: ArticleDocument,
    window_size: int = 900,
    overlap: int = 150,
) -> list[ArticleChunk]:
    """Split a knowledge article on headings, then apply 900-char windows with 150-char overlap.

    Every chunk is prefixed with '{title} - {heading}' so short chunks stay retrievable (CLAUDE.md §8).
    """
    if not article.content or not article.content.strip():
        return []

    sections = _split_markdown_sections(article.content, article.title)
    if not sections:
        return []

    chunks: list[ArticleChunk] = []
    global_chunk_idx = 0

    for heading, section_body in sections:
        section_slug = slugify_heading(heading)
        source = f"kb://{article.slug}#{section_slug}"

        # 1. Single chunk if within window size
        if len(section_body) <= window_size:
            snippet = section_body
            content = f"{article.title} - {heading}\n\n{snippet}"
            chunk_id = f"chk-{article.slug}-{section_slug}"
            chunks.append(
                ArticleChunk(
                    id=chunk_id,
                    article_id=article.id,
                    slug=article.slug,
                    title=article.title,
                    heading=heading,
                    section=section_slug,
                    source=source,
                    category=article.category,
                    tags=article.tags,
                    content=content,
                    snippet=snippet,
                    chunk_index=global_chunk_idx,
                )
            )
            global_chunk_idx += 1
            continue

        # 2. Windowed chunks for long sections (> 900 chars)
        stride = max(1, window_size - overlap)
        start = 0
        window_idx = 0

        while start < len(section_body):
            end = min(start + window_size, len(section_body))
            snippet = section_body[start:end].strip()

            if snippet:
                content = f"{article.title} - {heading}\n\n{snippet}"
                chunk_id = f"chk-{article.slug}-{section_slug}-{window_idx}"
                chunks.append(
                    ArticleChunk(
                        id=chunk_id,
                        article_id=article.id,
                        slug=article.slug,
                        title=article.title,
                        heading=heading,
                        section=section_slug,
                        source=source,
                        category=article.category,
                        tags=article.tags,
                        content=content,
                        snippet=snippet,
                        chunk_index=global_chunk_idx,
                    )
                )
                global_chunk_idx += 1
                window_idx += 1

            if end >= len(section_body):
                break
            start += stride

    return chunks


def chunk_all_articles(
    articles: list[ArticleDocument] | None = None,
    base_dir: Path | str | None = None,
    window_size: int = 900,
    overlap: int = 150,
) -> list[ArticleChunk]:
    """Batch load and chunk all articles from knowledge base directory."""
    if articles is None:
        articles = load_article_files(base_dir)

    all_chunks: list[ArticleChunk] = []
    for art in articles:
        all_chunks.extend(chunk_article(art, window_size=window_size, overlap=overlap))

    return all_chunks
