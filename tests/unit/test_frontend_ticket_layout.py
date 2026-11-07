"""Unit tests verifying Frontend Ticket Detail Three-Column Layout (P13-1).

Covers:
- P13-1: Ticket detail layout (feature/frontend-ticket-layout)
- CLAUDE.md §11 (Ticket screen is a three-column grid: messages + composer (left),
  customer panel (centre), workflow panel with 12 steps, chips, evidence, diagnosis,
  actions, editable reply (right))
- US-015: Interactive Three-Column Agent Workspace
- AC-052: Three-column layout rendering ticket messages, customer dossier, and workflow panel
- AC-054: Role gating for viewer (disabled action buttons, canAct check)
- Zero gradients invariant (CLAUDE.md §11)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
APP_DIR = FRONTEND_DIR / "app"
COMPONENTS_DIR = FRONTEND_DIR / "components"

TICKET_DETAIL_PAGE = APP_DIR / "tickets" / "[id]" / "page.tsx"
TICKETS_COMPONENTS_DIR = COMPONENTS_DIR / "tickets"
TICKET_HEADER_COMPONENT = TICKETS_COMPONENTS_DIR / "TicketHeader.tsx"
TICKET_CONVERSATION_COMPONENT = TICKETS_COMPONENTS_DIR / "TicketConversation.tsx"
CUSTOMER_DOSSIER_COMPONENT = TICKETS_COMPONENTS_DIR / "CustomerDossier.tsx"
WORKFLOW_PANEL_COMPONENT = TICKETS_COMPONENTS_DIR / "WorkflowPanel.tsx"
TICKETS_INDEX_COMPONENT = TICKETS_COMPONENTS_DIR / "index.ts"


def test_ticket_detail_files_exist() -> None:
    """Verify all ticket detail layout files and components exist."""
    files = [
        TICKET_DETAIL_PAGE,
        TICKET_HEADER_COMPONENT,
        TICKET_CONVERSATION_COMPONENT,
        CUSTOMER_DOSSIER_COMPONENT,
        WORKFLOW_PANEL_COMPONENT,
        TICKETS_INDEX_COMPONENT,
    ]
    for file_path in files:
        assert file_path.exists(), f"Missing file: {file_path.relative_to(REPO_ROOT)}"
        assert file_path.stat().st_size > 0, (
            f"File is empty: {file_path.relative_to(REPO_ROOT)}"
        )


def test_three_column_layout_structure() -> None:
    """Verify tickets/[id]/page.tsx implements the 3-column layout per AC-052 and CLAUDE.md §11."""
    content = TICKET_DETAIL_PAGE.read_text(encoding="utf-8")

    # Must import the three subcomponents
    assert "TicketConversation" in content, (
        "page.tsx must mount TicketConversation in the left column"
    )
    assert "CustomerDossier" in content, (
        "page.tsx must mount CustomerDossier in the center column"
    )
    assert "WorkflowPanel" in content, (
        "page.tsx must mount WorkflowPanel in the right column"
    )
    assert "TicketHeader" in content, "page.tsx must mount TicketHeader"

    # Must contain grid layout for 3 columns on large screens
    has_grid = "grid" in content and (
        "grid-cols-1" in content
        or "lg:grid-cols-3" in content
        or "lg:grid-cols-12" in content
    )
    assert has_grid, (
        "page.tsx must use a responsive grid layout for the 3-column workspace"
    )


def test_ticket_detail_api_wiring() -> None:
    """Verify page.tsx fetches ticket and customer data through typed api client."""
    content = TICKET_DETAIL_PAGE.read_text(encoding="utf-8")

    assert "api" in content, "page.tsx must import api from @/lib/api"
    assert "api.tickets.get" in content or "tickets.get" in content, (
        "page.tsx must call api.tickets.get to load ticket detail"
    )
    assert "api.customers.get" in content or "customers.get" in content, (
        "page.tsx must call api.customers.get to load customer dossier"
    )
    assert "useAuth" in content, "page.tsx must use useAuth() for role-awareness"


def test_ticket_header_elements() -> None:
    """Verify TicketHeader component renders metadata, status, severity, and navigation."""
    content = TICKET_HEADER_COMPONENT.read_text(encoding="utf-8")

    assert "StatusPill" in content, "TicketHeader must render StatusPill"
    assert "Badge" in content, (
        "TicketHeader must render Badges for category/severity/plan"
    )
    assert "subject" in content, "TicketHeader must display ticket subject"
    assert "severity" in content, "TicketHeader must display severity"
    assert "category" in content, "TicketHeader must display category"


def test_ticket_conversation_elements() -> None:
    """Verify TicketConversation component renders message stream and composer with role gating."""
    content = TICKET_CONVERSATION_COMPONENT.read_text(encoding="utf-8")

    assert "messages" in content, "TicketConversation must accept and render messages"
    assert "composer" in content.lower() or "textarea" in content.lower(), (
        "TicketConversation must include a message composer"
    )
    assert "canAct" in content or "disabled" in content, (
        "TicketConversation composer must support role-aware disabling (AC-054)"
    )


def test_customer_dossier_elements() -> None:
    """Verify CustomerDossier component renders 360-degree customer context."""
    content = CUSTOMER_DOSSIER_COMPONENT.read_text(encoding="utf-8")

    assert "subscription" in content.lower(), (
        "CustomerDossier must render customer subscription details"
    )
    assert "workspaces" in content.lower() or "workspace" in content.lower(), (
        "CustomerDossier must render workspaces"
    )
    assert "memory" in content.lower() or "notes" in content.lower(), (
        "CustomerDossier must render memory notes"
    )
    assert "recent" in content.lower() or "tickets" in content.lower(), (
        "CustomerDossier must render recent customer tickets"
    )


def test_workflow_panel_elements() -> None:
    """Verify WorkflowPanel component renders workflow steps, diagnosis, evidence, and actions."""
    content = WORKFLOW_PANEL_COMPONENT.read_text(encoding="utf-8")

    assert "steps" in content.lower(), (
        "WorkflowPanel must render workflow steps pipeline container"
    )
    assert "diagnosis" in content.lower(), "WorkflowPanel must render diagnosis section"
    assert "evidence" in content.lower() or "citations" in content.lower(), (
        "WorkflowPanel must render evidence citations section"
    )
    assert (
        "canAct" in content or "disabled" in content or "viewer" in content.lower()
    ), "WorkflowPanel action buttons must be role-gated per AC-054"


def test_zero_gradient_invariant_ticket_components() -> None:
    """Verify all ticket components strictly follow zero-gradient rule (CLAUDE.md §11)."""
    gradient_pattern = re.compile(
        r"(bg-gradient|gradient-to-|from-[a-z]+-\d+|via-[a-z]+-\d+|to-[a-z]+-\d+)",
        re.IGNORECASE,
    )

    ticket_files = [
        TICKET_DETAIL_PAGE,
        TICKET_HEADER_COMPONENT,
        TICKET_CONVERSATION_COMPONENT,
        CUSTOMER_DOSSIER_COMPONENT,
        WORKFLOW_PANEL_COMPONENT,
        TICKETS_INDEX_COMPONENT,
    ]

    for file_path in ticket_files:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            matches = gradient_pattern.findall(text)
            assert not matches, (
                f"Gradient utility detected in {file_path.relative_to(REPO_ROOT)}: {matches}"
            )


def test_no_exposed_secrets_in_ticket_components() -> None:
    """Verify no hardcoded credentials or mock tokens exist in ticket components."""
    secret_pattern = re.compile(r"(ey[A-Za-z0-9-_]{30,}|sk-[A-Za-z0-9]{20,})")

    ticket_files = [
        TICKET_DETAIL_PAGE,
        TICKET_HEADER_COMPONENT,
        TICKET_CONVERSATION_COMPONENT,
        CUSTOMER_DOSSIER_COMPONENT,
        WORKFLOW_PANEL_COMPONENT,
        TICKETS_INDEX_COMPONENT,
    ]

    for file_path in ticket_files:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            matches = secret_pattern.findall(text)
            assert not matches, (
                f"Hardcoded secret pattern found in {file_path.relative_to(REPO_ROOT)}"
            )
