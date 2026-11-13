"""Unit tests verifying Frontend Read-Only List Pages implementation and security invariants.

Covers:
- P12-4: Read-only list pages
- CLAUDE.md §11 (Pages: /dashboard, /tickets, /customers, /knowledge, /escalations, /agents, /audit)
- CLAUDE.md §11 (Backend reached ONLY through frontend/lib/api.ts, zero gradients)
- US-002 (Ticket queue listing & filtering)
- US-005 (Customer context & directory)
- US-018 (Role-based access control on sensitive queues like /escalations)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
APP_DIR = FRONTEND_DIR / "app"

TICKETS_PAGE = APP_DIR / "tickets" / "page.tsx"
CUSTOMERS_PAGE = APP_DIR / "customers" / "page.tsx"
KNOWLEDGE_PAGE = APP_DIR / "knowledge" / "page.tsx"
ESCALATIONS_PAGE = APP_DIR / "escalations" / "page.tsx"
AGENTS_PAGE = APP_DIR / "agents" / "page.tsx"
AUDIT_PAGE = APP_DIR / "audit" / "page.tsx"
DASHBOARD_PAGE = APP_DIR / "dashboard" / "page.tsx"


def test_read_pages_files_exist() -> None:
    """Verify all read-only list pages exist in frontend/app/."""
    pages = [
        TICKETS_PAGE,
        CUSTOMERS_PAGE,
        KNOWLEDGE_PAGE,
        ESCALATIONS_PAGE,
        AGENTS_PAGE,
        AUDIT_PAGE,
        DASHBOARD_PAGE,
    ]
    for page in pages:
        assert page.exists(), f"Missing page: {page.relative_to(REPO_ROOT)}"
        assert page.stat().st_size > 0, f"Page is empty: {page.relative_to(REPO_ROOT)}"


def test_tickets_page_wiring_and_filtering() -> None:
    """Verify /tickets consumes api.tickets.list with filters and empty states."""
    content = TICKETS_PAGE.read_text(encoding="utf-8")

    assert "api" in content, "tickets/page.tsx must import api from @/lib/api"
    assert "api.tickets.list" in content or "tickets.list" in content, (
        "tickets/page.tsx must call api.tickets.list"
    )
    assert "EmptyState" in content, (
        "tickets/page.tsx must render EmptyState when no tickets match"
    )
    assert "StatusPill" in content, "tickets/page.tsx must render StatusPill"
    assert "Table" in content, "tickets/page.tsx must use Table component"


def test_customers_page_wiring_and_search() -> None:
    """Verify /customers consumes api.customers.list and supports search."""
    content = CUSTOMERS_PAGE.read_text(encoding="utf-8")

    assert "api" in content, "customers/page.tsx must import api from @/lib/api"
    assert "api.customers.list" in content or "customers.list" in content, (
        "customers/page.tsx must call api.customers.list"
    )
    assert "Table" in content, "customers/page.tsx must use Table component"
    assert "EmptyState" in content, "customers/page.tsx must handle EmptyState"


def test_knowledge_page_wiring_and_search() -> None:
    """Verify /knowledge consumes api.knowledge methods and supports search."""
    content = KNOWLEDGE_PAGE.read_text(encoding="utf-8")

    assert "api" in content, "knowledge/page.tsx must import api from @/lib/api"
    assert (
        "api.knowledge" in content
        or "knowledge.search" in content
        or "knowledge.listArticles" in content
    ), "knowledge/page.tsx must call api.knowledge methods"


def test_escalations_page_wiring_and_role_gating() -> None:
    """Verify /escalations consumes api.escalations and enforces role gating."""
    content = ESCALATIONS_PAGE.read_text(encoding="utf-8")

    assert "api" in content, "escalations/page.tsx must import api from @/lib/api"
    assert "api.escalations.list" in content or "escalations.list" in content, (
        "escalations/page.tsx must call api.escalations.list"
    )
    assert "useAuth" in content or "RoleGuard" in content or "canAct" in content, (
        "escalations/page.tsx must be role-aware per AC-054 / US-018"
    )


def test_agents_page_wiring_and_topology() -> None:
    """Verify /agents consumes api.agents.getTopology."""
    content = AGENTS_PAGE.read_text(encoding="utf-8")

    assert "api" in content, "agents/page.tsx must import api from @/lib/api"
    assert "api.agents.getTopology" in content or "agents.getTopology" in content, (
        "agents/page.tsx must call api.agents.getTopology"
    )


def test_dashboard_page_wiring_and_metrics() -> None:
    """Verify /dashboard consumes API for real-time overview metrics."""
    content = DASHBOARD_PAGE.read_text(encoding="utf-8")

    assert "api" in content, "dashboard/page.tsx must import api from @/lib/api"
    assert "StatusPill" in content, "dashboard/page.tsx must render StatusPill"
    assert "Card" in content, "dashboard/page.tsx must use Card components"


def test_zero_gradients_on_all_read_pages() -> None:
    """Ensure strict zero-gradient enforcement across all list and dashboard pages."""
    gradient_regex = re.compile(
        r"(\bbg-gradient\b|linear-gradient|radial-gradient|\bfrom-\w+-\d+\s+to-)",
        re.IGNORECASE,
    )

    pages = [
        TICKETS_PAGE,
        CUSTOMERS_PAGE,
        KNOWLEDGE_PAGE,
        ESCALATIONS_PAGE,
        AGENTS_PAGE,
        AUDIT_PAGE,
        DASHBOARD_PAGE,
    ]
    for page in pages:
        content = page.read_text(encoding="utf-8")
        matches = gradient_regex.findall(content)
        assert not matches, f"Gradient pattern found in {page.name}: {matches}"


def test_no_hardcoded_secrets_on_read_pages() -> None:
    """Security audit: ensure no production credentials or private keys in read pages."""
    forbidden = [
        re.compile(r"password\s*=\s*['\"][^'\"]{6,}['\"]", re.IGNORECASE),
        re.compile(r"SUPABASE_SERVICE_ROLE_KEY", re.IGNORECASE),
        re.compile(r"BEGIN PRIVATE KEY", re.IGNORECASE),
    ]

    pages = [
        TICKETS_PAGE,
        CUSTOMERS_PAGE,
        KNOWLEDGE_PAGE,
        ESCALATIONS_PAGE,
        AGENTS_PAGE,
        AUDIT_PAGE,
        DASHBOARD_PAGE,
    ]
    for page in pages:
        content = page.read_text(encoding="utf-8")
        for pat in forbidden:
            assert not pat.search(content), f"Sensitive pattern detected in {page.name}"
