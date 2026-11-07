"""Unit tests verifying Frontend Typed API Client implementation and security invariants.

Covers:
- P12-2: Typed API client
- CLAUDE.md §11 (Backend reached ONLY through frontend/lib/api.ts, bearer token in localStorage, 401 -> /login?reason=expired, NetworkError)
- CLAUDE.md §12 (types.ts mirrors API_CONTRACT.md)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
API_FILE = FRONTEND_DIR / "lib" / "api.ts"
TYPES_FILE = FRONTEND_DIR / "lib" / "types.ts"


def test_api_client_file_exists() -> None:
    """Verify frontend/lib/api.ts exists."""
    assert API_FILE.exists(), "frontend/lib/api.ts must exist"
    assert API_FILE.stat().st_size > 0, "frontend/lib/api.ts must not be empty"


def test_types_file_contains_all_api_domains() -> None:
    """Verify frontend/lib/types.ts covers all domains in API_CONTRACT.md."""
    assert TYPES_FILE.exists(), "frontend/lib/types.ts must exist"
    content = TYPES_FILE.read_text(encoding="utf-8")

    expected_types = [
        # Domain enums
        "Category",
        "TicketStatus",
        "Severity",
        "Role",
        "CustomerPlan",
        "ApprovalStatus",
        # Tickets
        "TicketCreate",
        "TicketDetail",
        "TicketListResponse",
        "ReplyCreate",
        "ReplyResponse",
        "EscalateRequest",
        "EscalateResponse",
        # Workflow
        "WorkflowRunResponse",
        "WorkflowStateResponse",
        "WorkflowEvent",
        # Customer
        "CustomerSummary",
        "CustomerDetail",
        "CustomerMemory",
        # Knowledge
        "KnowledgeSearchRequest",
        "KnowledgeEvidence",
        "KnowledgeReindexResponse",
        # Auth
        "LoginRequest",
        "TokenResponse",
        "UserProfileResponse",
        "DemoTokensResponse",
        # Approvals
        "ApprovalRequestResponse",
        # Escalations
        "EscalationResponse",
        # Agents
        "AgentTopologyResponse",
        # MCP
        "McpToolDefinition",
    ]

    for type_name in expected_types:
        assert type_name in content, (
            f"Expected type {type_name} missing from frontend/lib/types.ts"
        )


def test_api_client_token_management() -> None:
    """Verify api.ts includes token management using localStorage."""
    content = API_FILE.read_text(encoding="utf-8")

    assert "localStorage" in content, (
        "api.ts must interface with localStorage for JWT tokens"
    )
    assert "getToken" in content, "api.ts must provide getToken helper"
    assert "setToken" in content, "api.ts must provide setToken helper"
    assert "clearToken" in content, "api.ts must provide clearToken helper"
    assert "Authorization" in content, "api.ts must set Authorization header"
    assert "Bearer" in content, "api.ts must format token as Bearer scheme"


def test_api_client_401_redirect_handling() -> None:
    """Verify 401 responses trigger redirection to /login?reason=expired."""
    content = API_FILE.read_text(encoding="utf-8")

    assert "401" in content, "api.ts must inspect HTTP 401 status"
    assert "/login?reason=expired" in content, (
        "api.ts must redirect to /login?reason=expired on 401 per CLAUDE.md §11"
    )


def test_api_client_network_error_and_retry() -> None:
    """Verify api.ts defines NetworkError class and supports retry capability."""
    content = API_FILE.read_text(encoding="utf-8")

    assert "class NetworkError" in content or "NetworkError" in content, (
        "api.ts must declare NetworkError class per CLAUDE.md §11"
    )
    assert "retry" in content.lower(), "api.ts should support request retry logic"


def test_api_client_domain_namespaces() -> None:
    """Verify api.ts provides typed method namespaces for all core domains."""
    content = API_FILE.read_text(encoding="utf-8")

    # API namespace or object exports
    required_domains = [
        "auth",
        "tickets",
        "customers",
        "knowledge",
        "approvals",
        "escalations",
        "agents",
        "mcp",
    ]

    for domain in required_domains:
        assert domain in content, (
            f"Domain namespace '{domain}' must be implemented in api.ts"
        )


def test_api_client_security_invariants() -> None:
    """Ensure no hardcoded credentials or server-role secrets in client code."""
    content = API_FILE.read_text(encoding="utf-8")

    forbidden_patterns = [
        re.compile(r"SUPABASE_SERVICE_ROLE_KEY", re.IGNORECASE),
        re.compile(r"SECRET_KEY\s*=\s*['\"][a-zA-Z0-9]{8,}", re.IGNORECASE),
        re.compile(r"BEGIN PRIVATE KEY", re.IGNORECASE),
    ]

    for pat in forbidden_patterns:
        assert not pat.search(content), (
            f"Sensitive key or pattern detected in api.ts: {pat}"
        )
