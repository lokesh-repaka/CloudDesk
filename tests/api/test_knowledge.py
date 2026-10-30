"""Tests for Knowledge Base API Routes (P5-4).

Tests endpoints under /api/v1/knowledge:
- POST /api/v1/knowledge/search (Hybrid RAG retrieval with citations)
- POST /api/v1/knowledge/reindex (Admin-only re-chunking and vector indexing)
- GET /api/v1/knowledge/articles (Knowledge base article catalog listing)
- GET /api/v1/knowledge/articles/{id_or_slug} (Single article dossier with content)

Verifies:
- RBAC rules: Viewer role for search and catalog, Admin-only for reindex (CLAUDE.md §2).
- Citation and Evidence shape: { id, title, source: 'kb://slug#section', snippet, score, url, article_id }.
- Reindex response: { indexed_articles: 15, total_chunks: 48 } (API_CONTRACT.md §5.2).
- Security: SQL/NoSQL injection containment, path traversal defense, and XSS isolation.
"""

from starlette.testclient import TestClient

# -----------------------------------------------------------------------------
# 1. Knowledge Base Search (POST /api/v1/knowledge/search)
# -----------------------------------------------------------------------------


def test_knowledge_search_as_viewer(client: TestClient, viewer_headers: dict[str, str]):
    """Verify viewer can perform hybrid search and receives canonical Evidence hits."""
    payload = {
        "query": "SAML assertion signature invalid Okta login failure",
        "category": "login_issue",
        "top_k": 3,
        "mode": "hybrid",
    }
    response = client.post(
        "/api/v1/knowledge/search", json=payload, headers=viewer_headers
    )
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 3
    assert len(data) > 0

    first = data[0]
    # Check Evidence schema (CLAUDE.md §8)
    assert "id" in first
    assert "title" in first
    assert "source" in first
    assert "snippet" in first
    assert "score" in first
    assert "url" in first
    assert "article_id" in first

    assert first["source"].startswith("kb://")
    assert first["url"].startswith("/knowledge/")
    assert first["article_id"] == "kb-login-01-sso" or "sso" in first["article_id"]
    assert isinstance(first["score"], float)


def test_knowledge_search_as_agent(client: TestClient, agent_headers: dict[str, str]):
    """Verify agent can search knowledge base."""
    payload = {"query": "API 429 rate limit ceiling", "category": "api_failure"}
    response = client.post(
        "/api/v1/knowledge/search", json=payload, headers=agent_headers
    )
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_knowledge_search_as_unauthenticated_fails(client: TestClient):
    """Verify unauthenticated search fails with 401 Unauthorized."""
    payload = {"query": "refund policy seats"}
    response = client.post("/api/v1/knowledge/search", json=payload)
    assert response.status_code == 401


def test_knowledge_search_pure_modes(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify 'semantic' and 'keyword' modes execute without error."""
    for mode in ["semantic", "keyword"]:
        payload = {"query": "storage quota tiers", "mode": mode, "top_k": 2}
        response = client.post(
            "/api/v1/knowledge/search", json=payload, headers=viewer_headers
        )
        assert response.status_code == 200
        assert len(response.json()) > 0


def test_knowledge_search_invalid_mode_rejected(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify invalid mode returns 422 Unprocessable Entity."""
    payload = {"query": "test query", "mode": "invalid_mode"}
    response = client.post(
        "/api/v1/knowledge/search", json=payload, headers=viewer_headers
    )
    assert response.status_code == 422


def test_knowledge_search_empty_query_rejected(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify empty query string returns 422 Unprocessable Entity."""
    payload = {"query": "   "}
    response = client.post(
        "/api/v1/knowledge/search", json=payload, headers=viewer_headers
    )
    assert response.status_code == 422


def test_knowledge_search_invalid_top_k_bounds(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify top_k <= 0 or top_k > 20 returns 422."""
    for bad_k in [0, -1, 50]:
        payload = {"query": "valid query", "top_k": bad_k}
        response = client.post(
            "/api/v1/knowledge/search", json=payload, headers=viewer_headers
        )
        assert response.status_code == 422


# -----------------------------------------------------------------------------
# 2. Knowledge Base Reindex (POST /api/v1/knowledge/reindex)
# -----------------------------------------------------------------------------


def test_knowledge_reindex_as_admin_success(
    client: TestClient, admin_headers: dict[str, str]
):
    """Verify admin role can trigger reindex and receives article/chunk counts (API_CONTRACT.md §5.2)."""
    response = client.post("/api/v1/knowledge/reindex", headers=admin_headers)
    assert response.status_code == 200

    data = response.json()
    assert "indexed_articles" in data
    assert "total_chunks" in data
    assert data["indexed_articles"] == 15
    assert data["total_chunks"] > 0


def test_knowledge_reindex_as_viewer_forbidden(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify viewer cannot trigger reindex (403 Forbidden)."""
    response = client.post("/api/v1/knowledge/reindex", headers=viewer_headers)
    assert response.status_code == 403


def test_knowledge_reindex_as_agent_forbidden(
    client: TestClient, agent_headers: dict[str, str]
):
    """Verify agent cannot trigger reindex (403 Forbidden)."""
    response = client.post("/api/v1/knowledge/reindex", headers=agent_headers)
    assert response.status_code == 403


# -----------------------------------------------------------------------------
# 3. Knowledge Base Catalog (GET /api/v1/knowledge/articles)
# -----------------------------------------------------------------------------


def test_list_knowledge_articles_as_viewer(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify viewer can list knowledge base articles."""
    response = client.get("/api/v1/knowledge/articles", headers=viewer_headers)
    assert response.status_code == 200

    articles = response.json()
    assert isinstance(articles, list)
    assert len(articles) == 15

    first = articles[0]
    assert "id" in first
    assert "slug" in first
    assert "title" in first
    assert "category" in first
    assert "tags" in first
    assert "summary" in first


def test_get_knowledge_article_by_slug(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify retrieving article by slug returns detailed article with markdown content."""
    slug = "kb-login-01-sso"
    response = client.get(f"/api/v1/knowledge/articles/{slug}", headers=viewer_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["slug"] == slug
    assert "content" in data
    assert len(data["content"]) > 0
    assert "Troubleshooting SAML 2.0" in data["title"]


def test_get_knowledge_article_by_art_id(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify retrieving article by full art- ID format succeeds."""
    art_id = "art-kb-billing-01-seats-refund"
    response = client.get(
        f"/api/v1/knowledge/articles/{art_id}", headers=viewer_headers
    )
    assert response.status_code == 200

    data = response.json()
    assert "seats-refund" in data["slug"]


def test_get_nonexistent_knowledge_article_404(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Verify nonexistent article slug returns 404 Not Found."""
    response = client.get(
        "/api/v1/knowledge/articles/kb-nonexistent-slug", headers=viewer_headers
    )
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# 4. Security & Penetration Tests
# -----------------------------------------------------------------------------


def test_security_sql_injection_in_search_query(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Penetration test: SQL injection in search query executes safely without data leakage (CWE-89)."""
    sqli_payload = {
        "query": "'; DROP TABLE knowledge_articles; SELECT * FROM users WHERE '1'='1",
        "category": "security",
    }
    response = client.post(
        "/api/v1/knowledge/search", json=sqli_payload, headers=viewer_headers
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_security_path_traversal_in_article_endpoint(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Penetration test: Directory traversal attempts in article route return 404/422 without file leak (CWE-22)."""
    traversal_slugs = [
        "../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "....//....//backend//app//main.py",
    ]
    for bad_slug in traversal_slugs:
        response = client.get(
            f"/api/v1/knowledge/articles/{bad_slug}", headers=viewer_headers
        )
        # Traversal is rejected as 404 Not Found or 422
        assert response.status_code in (404, 422)


def test_security_xss_payload_in_query(
    client: TestClient, viewer_headers: dict[str, str]
):
    """Penetration test: XSS script tags in search query are handled as plain text (CWE-79)."""
    xss_payload = {
        "query": "<script>alert('xss')</script> sso login",
    }
    response = client.post(
        "/api/v1/knowledge/search", json=xss_payload, headers=viewer_headers
    )
    assert response.status_code == 200
    for hit in response.json():
        assert isinstance(hit["snippet"], str)
