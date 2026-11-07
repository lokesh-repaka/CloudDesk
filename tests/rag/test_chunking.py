"""Tests for Knowledge Base Article Loading and Chunking Pipeline (P5-1).

Tests the core RAG ingestion components:
- load_article_files: YAML front-matter parsing, article metadata extraction, directory loading.
- load_article_file: Single article loading and validation.
- chunk_article: Heading-based splitting, 900-character windowing with 150-character overlap,
  and contextual "{title} - {heading}" prefixing.
- chunk_all_articles: Batch chunking across all knowledge base articles.
- Security tests: Path traversal protection, safe markdown parsing, and credential check.
"""

from pathlib import Path

import pytest

from backend.app.rag.chunking import (
    ArticleChunk,
    ArticleDocument,
    chunk_all_articles,
    chunk_article,
    load_article_file,
    load_article_files,
    slugify_heading,
)
from backend.app.schemas.common import CategoryEnum

KB_DIR = Path("sample_data/knowledge_base")


# -----------------------------------------------------------------------------
# 1. Article Loading Tests
# -----------------------------------------------------------------------------


def test_load_article_files_loads_all_15_articles():
    """Verify load_article_files loads exactly 15 articles from sample_data/knowledge_base."""
    articles = load_article_files(KB_DIR)
    assert len(articles) == 15

    slugs = {a.slug for a in articles}
    assert "kb-login-01-sso" in slugs
    assert "kb-billing-01-seats-refund" in slugs
    assert "kb-sec-01-compromised-accounts" in slugs

    # Verify every article has required fields populated
    valid_categories = {c.value for c in CategoryEnum}
    for art in articles:
        assert art.id.startswith("art-")
        assert len(art.title) > 5
        assert art.category in valid_categories
        assert isinstance(art.tags, list)
        assert len(art.tags) > 0
        assert len(art.summary) > 10
        assert len(art.content) > 50


def test_load_article_files_default_path():
    """Verify load_article_files without arguments defaults to sample_data/knowledge_base."""
    articles = load_article_files()
    assert len(articles) == 15


def test_load_article_files_nonexistent_directory():
    """Verify load_article_files raises FileNotFoundError for missing directory."""
    with pytest.raises(FileNotFoundError):
        load_article_files(Path("nonexistent/kb/path"))


def test_load_single_article_file():
    """Verify load_article_file parses front-matter and content of a single markdown file."""
    sso_path = KB_DIR / "kb-login-01-sso.md"
    article = load_article_file(sso_path)

    assert article.id == "art-kb-login-01-sso"
    assert article.slug == "kb-login-01-sso"
    assert article.title == "Troubleshooting SAML 2.0 Single Sign-On (SSO) Failures"
    assert article.category == "login_issue"
    assert "okta" in article.tags
    assert "SAML" in article.summary
    assert "## Common Root Causes" in article.content


def test_load_article_file_malformed_frontmatter(tmp_path: Path):
    """Verify files without valid front-matter delimiters raise ValueError."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("# Just a heading\nNo frontmatter here.")
    with pytest.raises(ValueError, match="front-matter"):
        load_article_file(bad_file)


# -----------------------------------------------------------------------------
# 2. Heading-Based Chunking Tests
# -----------------------------------------------------------------------------


def test_chunk_article_splits_on_markdown_headings():
    """Verify chunk_article splits article into sections based on markdown headings."""
    sso_path = KB_DIR / "kb-login-01-sso.md"
    article = load_article_file(sso_path)
    chunks = chunk_article(article)

    # kb-login-01-sso has H1 (overview), H2 Common Root Causes, H2 Remediation Steps
    assert len(chunks) == 3

    headings = [c.heading for c in chunks]
    assert any("Common Root Causes" in h for h in headings)
    assert any("Remediation Steps" in h for h in headings)


def test_chunk_article_prefixes_with_title_and_heading():
    """Verify every chunk is prefixed with '{title} - {heading}' (CLAUDE.md spec)."""
    sso_path = KB_DIR / "kb-login-01-sso.md"
    article = load_article_file(sso_path)
    chunks = chunk_article(article)

    for chunk in chunks:
        expected_prefix = f"{article.title} - {chunk.heading}"
        assert chunk.content.startswith(expected_prefix), (
            f"Chunk content does not start with '{expected_prefix}': {chunk.content[:60]}..."
        )


def test_chunk_article_canonical_source_uri_format():
    """Verify chunk source follows 'kb://slug#section' format (CLAUDE.md spec)."""
    sso_path = KB_DIR / "kb-login-01-sso.md"
    article = load_article_file(sso_path)
    chunks = chunk_article(article)

    for chunk in chunks:
        assert chunk.source.startswith("kb://kb-login-01-sso#")
        assert len(chunk.section) > 0


def test_slugify_heading():
    """Verify slugify_heading produces valid URL anchor slugs."""
    assert slugify_heading("Common Root Causes") == "common-root-causes"
    assert slugify_heading("API Rate Limits & HTTP 429!") == "api-rate-limits-http-429"
    assert slugify_heading("  Multiple   Spaces   ") == "multiple-spaces"


# -----------------------------------------------------------------------------
# 3. Windowing & Overlap Tests (900-char window, 150-char overlap)
# -----------------------------------------------------------------------------


def test_chunk_section_under_900_chars_is_single_chunk():
    """Verify sections with <= 900 characters produce exactly one chunk without windowing."""
    article = ArticleDocument(
        id="art-test-short",
        slug="test-short",
        title="Short Article",
        category="billing",
        tags=["short"],
        summary="Short summary",
        content="## Section One\nThis is a short section with well under 900 characters.",
    )
    chunks = chunk_article(article)
    assert len(chunks) == 1
    assert chunks[0].heading == "Section One"
    assert "well under 900 characters" in chunks[0].content


def test_chunk_section_over_900_chars_windows_with_150_overlap():
    """Verify sections > 900 chars slide a 900-char window with 150-char overlap."""
    # Generate 1500 chars of distinctive text
    alphabet_sentence = (
        "The quick brown fox jumps over the lazy dog. " * 35
    )  # ~1575 chars
    assert len(alphabet_sentence) > 1200

    article = ArticleDocument(
        id="art-test-long",
        slug="test-long",
        title="Long Document",
        category="login_issue",
        tags=["long"],
        summary="Long summary",
        content=f"## Massive Section\n{alphabet_sentence}",
    )

    chunks = chunk_article(article, window_size=900, overlap=150)
    assert len(chunks) >= 2

    # Check window size constraint (excluding the prefix)
    for c in chunks:
        assert len(c.snippet) <= 900

    # Check overlap: end of chunk 0 snippet must match start of chunk 1 snippet
    overlap_len = 150
    chunk0_tail = chunks[0].snippet[-overlap_len:]
    assert chunk0_tail in chunks[1].snippet


def test_chunk_article_no_headings_falls_back_to_overview():
    """Verify article without any '#' headings chunks cleanly under 'Overview'."""
    raw_text = "This article has no markdown headings at all, just plain paragraphs explaining policies."
    article = ArticleDocument(
        id="art-no-heading",
        slug="no-heading",
        title="Plain Text Policy",
        category="account",
        tags=["general"],
        summary="Summary of plain text policy",
        content=raw_text,
    )
    chunks = chunk_article(article)
    assert len(chunks) == 1
    assert chunks[0].heading == "Overview"
    assert chunks[0].source == "kb://no-heading#overview"
    assert chunks[0].content.startswith("Plain Text Policy - Overview")


def test_chunk_article_empty_or_whitespace_ignored():
    """Verify empty sections or articles with no body return empty chunk lists."""
    article = ArticleDocument(
        id="art-empty",
        slug="empty",
        title="Empty Article",
        category="other",
        tags=[],
        summary="",
        content="   \n\n  ",
    )
    chunks = chunk_article(article)
    assert len(chunks) == 0


# -----------------------------------------------------------------------------
# 4. Batch & Integration Tests
# -----------------------------------------------------------------------------


def test_chunk_all_15_sample_articles():
    """Verify batch chunking of all 15 sample articles produces valid chunks."""
    chunks = chunk_all_articles(base_dir=KB_DIR)
    assert len(chunks) >= 39  # 39 distinct sections across 15 sample articles

    for chunk in chunks:
        assert isinstance(chunk, ArticleChunk)
        assert chunk.id.startswith("chk-")
        assert chunk.article_id.startswith("art-")
        assert chunk.source.startswith("kb://")
        assert "#" in chunk.source
        assert len(chunk.content) > 10
        assert len(chunk.snippet) > 0
        assert chunk.title in chunk.content
        assert chunk.category in {c.value for c in CategoryEnum}


def test_chunk_to_evidence_dict_compatibility():
    """Verify ArticleChunk can convert to the exact Evidence shape required by agents (CLAUDE.md §8)."""
    sso_path = KB_DIR / "kb-login-01-sso.md"
    article = load_article_file(sso_path)
    chunks = chunk_article(article)
    evidence = chunks[0].to_evidence(score=0.92)

    # Required shape: { id, title, source: "kb://slug#section", snippet, score, url: "/knowledge/<id>", article_id }
    assert "id" in evidence
    assert evidence["title"] == article.title
    assert evidence["source"].startswith("kb://kb-login-01-sso#")
    assert "snippet" in evidence
    assert evidence["score"] == 0.92
    assert evidence["url"] == f"/knowledge/{article.id}"
    assert evidence["article_id"] == article.id


def test_chunking_is_deterministic():
    """Verify re-running chunking on the same article produces identical chunk IDs and hashes."""
    sso_path = KB_DIR / "kb-login-01-sso.md"
    article = load_article_file(sso_path)
    run1 = chunk_article(article)
    run2 = chunk_article(article)

    assert len(run1) == len(run2)
    for c1, c2 in zip(run1, run2, strict=False):
        assert c1.id == c2.id
        assert c1.source == c2.source
        assert c1.content == c2.content


# -----------------------------------------------------------------------------
# 5. Security & Penetration Tests
# -----------------------------------------------------------------------------


def test_security_path_traversal_in_article_loader(tmp_path: Path):
    """Penetration test: Attempting path traversal outside allowed directory is blocked (CWE-22)."""
    traversal_path = KB_DIR / "../../etc/passwd"
    with pytest.raises(FileNotFoundError):
        load_article_file(traversal_path)


def test_security_malicious_markdown_parsing_safe(tmp_path: Path):
    """Penetration test: HTML script tags or XXE payloads in markdown are parsed safely as text (CWE-79)."""
    malicious_md = tmp_path / "xss_article.md"
    malicious_md.write_text(
        "---\n"
        'title: "XSS Security Test Article"\n'
        'category: "security"\n'
        'tags: ["xss", "test"]\n'
        'summary: "Testing script containment"\n'
        "---\n\n"
        "# XSS Injection Vector\n\n"
        "<script>alert('XSS-Exploit')</script>\n"
        '<iframe src="javascript:alert(1)"></iframe>\n'
    )

    art = load_article_file(malicious_md)
    chunks = chunk_article(art)
    assert len(chunks) == 1
    # Verify script content is treated strictly as plain text data without execution
    assert "<script>alert('XSS-Exploit')</script>" in chunks[0].content


def test_security_no_secrets_in_sample_kb_articles():
    """Penetration test: Verify no sample KB article contains live API keys, card numbers, or passwords."""
    import re

    card_pattern = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    key_pattern = re.compile(r"(?:sk-|Bearer\s+|key-)[a-zA-Z0-9_\-]{16,}")

    for a_path in KB_DIR.glob("*.md"):
        content = a_path.read_text(encoding="utf-8")
        assert not card_pattern.search(content), (
            f"Potential payment card pattern found in {a_path.name}"
        )
        assert not key_pattern.search(content), (
            f"Potential API key pattern found in {a_path.name}"
        )
