"""Unit tests verifying Frontend Workflow Steps, Live Polling, and Telemetry (P13-2).

Covers:
- P13-2: Workflow steps and polling (feature/frontend-workflow-panel)
- CLAUDE.md §11 (Polling via usePolling (2 s on the ticket screen) for workflow progress)
- CLAUDE.md §13 (WorkflowSteps.deriveSteps)
- CLAUDE.md §16 (Telemetry, node timings, token counts, cost estimates)
- US-015 / AC-053: Dynamic step updates and completed step chips via 2s polling without full page reload
- Strict zero-gradient invariant (CLAUDE.md §11)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
LIB_DIR = FRONTEND_DIR / "lib"
COMPONENTS_DIR = FRONTEND_DIR / "components" / "tickets"
APP_DIR = FRONTEND_DIR / "app" / "tickets" / "[id]"

POLLING_HOOK = LIB_DIR / "usePolling.ts"
WORKFLOW_STEPS = COMPONENTS_DIR / "WorkflowSteps.tsx"
WORKFLOW_PANEL = COMPONENTS_DIR / "WorkflowPanel.tsx"
TICKET_PAGE = APP_DIR / "page.tsx"

CANONICAL_12_NODES = [
    "understand_ticket",
    "classify_severity",
    "customer_context",
    "knowledge_retrieval",
    "troubleshooting",
    "resolution_planning",
    "risk_check",
    "human_approval",
    "execute_resolution",
    "escalation",
    "ticket_summary",
    "memory_update",
]


def test_workflow_panel_and_polling_files_exist() -> None:
    """Verify all required files for P13-2 exist."""
    files = [POLLING_HOOK, WORKFLOW_STEPS, WORKFLOW_PANEL, TICKET_PAGE]
    for file_path in files:
        assert file_path.exists(), f"Missing file: {file_path.relative_to(REPO_ROOT)}"
        assert file_path.stat().st_size > 0, (
            f"File is empty: {file_path.relative_to(REPO_ROOT)}"
        )


def test_use_polling_hook_contract() -> None:
    """Verify usePolling hook implements 2-second default polling and timer cleanup."""
    content = POLLING_HOOK.read_text(encoding="utf-8")

    assert (
        "export function usePolling" in content or "export const usePolling" in content
    ), "usePolling.ts must export usePolling hook"
    # Check 2s (2000 ms) interval specification (CLAUDE.md §11 & AC-053)
    assert "2000" in content, (
        "usePolling must configure default 2000 ms (2 s) polling interval"
    )
    assert "clearInterval" in content, (
        "usePolling must clean up interval timer on unmount"
    )
    assert "enabled" in content, (
        "usePolling must accept an enabled flag to pause/resume polling"
    )


def test_workflow_steps_derive_steps_function() -> None:
    """Verify WorkflowSteps.tsx exports deriveSteps and handles the 12 canonical LangGraph nodes."""
    content = WORKFLOW_STEPS.read_text(encoding="utf-8")

    assert "deriveSteps" in content, (
        "WorkflowSteps.tsx must export deriveSteps per CLAUDE.md §13"
    )
    for node in CANONICAL_12_NODES:
        assert node in content, f"WorkflowSteps must reference canonical node '{node}'"

    # Must support status resolution (completed, active, paused, pending)
    assert "completed" in content, "deriveSteps must handle completed status"
    assert "active" in content, "deriveSteps must handle active status"
    assert "paused" in content, "deriveSteps must handle paused approval status"


def test_workflow_steps_renders_chips_and_telemetry() -> None:
    """Verify WorkflowSteps component renders status chips, timing duration, and tokens."""
    content = WORKFLOW_STEPS.read_text(encoding="utf-8")

    assert "Badge" in content or "StatusPill" in content, (
        "WorkflowSteps must render step badges/chips"
    )
    assert "duration" in content.lower() or "ms" in content.lower(), (
        "WorkflowSteps must render node timing duration"
    )


def test_workflow_panel_uses_workflow_steps() -> None:
    """Verify WorkflowPanel integrates WorkflowSteps and displays telemetry summary."""
    content = WORKFLOW_PANEL.read_text(encoding="utf-8")

    assert "WorkflowSteps" in content, (
        "WorkflowPanel.tsx must import and render WorkflowSteps"
    )
    assert "token" in content.lower(), (
        "WorkflowPanel must render token metrics (CLAUDE.md §16)"
    )


def test_ticket_page_uses_polling_for_workflow_ac053() -> None:
    """Verify tickets/[id]/page.tsx connects usePolling to update workflow dynamically (AC-053)."""
    content = TICKET_PAGE.read_text(encoding="utf-8")

    assert "usePolling" in content, "page.tsx must import and invoke usePolling"
    assert "getWorkflowState" in content, (
        "page.tsx must poll api.tickets.getWorkflowState"
    )
    assert "getEvents" in content, (
        "page.tsx must poll or fetch api.tickets.getEvents for telemetry"
    )


def test_zero_gradient_invariant_workflow_panel() -> None:
    """Verify strict zero-gradient enforcement in workflow polling and steps components."""
    gradient_pattern = re.compile(
        r"(bg-gradient|gradient-to-|from-[a-z]+-\d+|via-[a-z]+-\d+|to-[a-z]+-\d+)",
        re.IGNORECASE,
    )

    files_to_check = [POLLING_HOOK, WORKFLOW_STEPS, WORKFLOW_PANEL, TICKET_PAGE]
    for file_path in files_to_check:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            matches = gradient_pattern.findall(text)
            assert not matches, (
                f"Gradient utility detected in {file_path.relative_to(REPO_ROOT)}: {matches}"
            )


def test_no_exposed_secrets_in_workflow_panel() -> None:
    """Verify no hardcoded credentials or mock tokens exist in workflow components."""
    secret_pattern = re.compile(r"(ey[A-Za-z0-9-_]{30,}|sk-[A-Za-z0-9]{20,})")

    files_to_check = [POLLING_HOOK, WORKFLOW_STEPS, WORKFLOW_PANEL, TICKET_PAGE]
    for file_path in files_to_check:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            matches = secret_pattern.findall(text)
            assert not matches, (
                f"Hardcoded secret pattern in {file_path.relative_to(REPO_ROOT)}"
            )
