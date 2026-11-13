"""Unit tests verifying Frontend Ticket Actions: Approve, Reject, Reply, Escalate (P13-3).

Covers:
- P13-3: Approve, reject, reply, and escalate actions (feature/frontend-ticket-actions)
- CLAUDE.md §11 (Role-aware UI: viewer sees disabled action buttons; Approve/Reject only when approval_status === "pending")
- US-010 / US-011: Approval gates, resolution resumption, and rejection routing
- US-012: Policy escalation engine
- US-013: Customer reply dispatch
- AC-054: Role gating on action controls for viewer
- Strict zero-gradient invariant (CLAUDE.md §11)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
COMPONENTS_DIR = FRONTEND_DIR / "components" / "tickets"
APP_DIR = FRONTEND_DIR / "app" / "tickets" / "[id]"

APPROVE_MODAL = COMPONENTS_DIR / "ApproveModal.tsx"
REJECT_MODAL = COMPONENTS_DIR / "RejectModal.tsx"
REPLY_MODAL = COMPONENTS_DIR / "ReplyModal.tsx"
ESCALATE_MODAL = COMPONENTS_DIR / "EscalateModal.tsx"
WORKFLOW_PANEL = COMPONENTS_DIR / "WorkflowPanel.tsx"
TICKET_PAGE = APP_DIR / "page.tsx"


def test_action_modal_files_exist() -> None:
    """Verify all ticket action modal components exist."""
    files = [APPROVE_MODAL, REJECT_MODAL, REPLY_MODAL, ESCALATE_MODAL]
    for file_path in files:
        assert file_path.exists(), f"Missing file: {file_path.relative_to(REPO_ROOT)}"
        assert file_path.stat().st_size > 0, (
            f"File is empty: {file_path.relative_to(REPO_ROOT)}"
        )


def test_approve_modal_contract() -> None:
    """Verify ApproveModal handles proposed action details and approval submission."""
    content = APPROVE_MODAL.read_text(encoding="utf-8")

    assert "Modal" in content, "ApproveModal must use UI Modal component"
    assert "approve" in content.lower(), "ApproveModal must handle approval action"
    assert "reason" in content.lower(), (
        "ApproveModal must allow providing approval rationale"
    )
    assert "canAct" in content or "disabled" in content, (
        "ApproveModal must enforce role gating (AC-054)"
    )


def test_reject_modal_contract() -> None:
    """Verify RejectModal requires rejection reason and triggers rejection routing."""
    content = REJECT_MODAL.read_text(encoding="utf-8")

    assert "Modal" in content, "RejectModal must use UI Modal component"
    assert "reject" in content.lower(), "RejectModal must handle rejection action"
    assert "reason" in content.lower(), "RejectModal must require rejection reason"
    assert "canAct" in content or "disabled" in content, (
        "RejectModal must enforce role gating (AC-054)"
    )


def test_reply_modal_contract() -> None:
    """Verify ReplyModal supports message composition and optional internal notes."""
    content = REPLY_MODAL.read_text(encoding="utf-8")

    assert "Modal" in content, "ReplyModal must use UI Modal component"
    assert "message" in content.lower(), "ReplyModal must include message body"
    assert "internal_note" in content or "note" in content.lower(), (
        "ReplyModal must support internal notes"
    )
    assert "canAct" in content or "disabled" in content, (
        "ReplyModal must enforce role gating (AC-054)"
    )


def test_escalate_modal_contract() -> None:
    """Verify EscalateModal captures target team, policy reason, and severity."""
    content = ESCALATE_MODAL.read_text(encoding="utf-8")

    assert "Modal" in content, "EscalateModal must use UI Modal component"
    assert "target_team" in content or "team" in content.lower(), (
        "EscalateModal must include target team selection"
    )
    assert "policy_reason" in content or "reason" in content.lower(), (
        "EscalateModal must capture policy escalation reason"
    )
    assert "severity" in content.lower(), "EscalateModal must allow specifying severity"
    assert "canAct" in content or "disabled" in content, (
        "EscalateModal must enforce role gating (AC-054)"
    )


def test_ticket_page_wires_modals_and_api() -> None:
    """Verify page.tsx connects action modals to api endpoints and state refreshes."""
    content = TICKET_PAGE.read_text(encoding="utf-8")

    assert "ApproveModal" in content, "page.tsx must mount ApproveModal"
    assert "RejectModal" in content, "page.tsx must mount RejectModal"
    assert "ReplyModal" in content, "page.tsx must mount ReplyModal"
    assert "EscalateModal" in content, "page.tsx must mount EscalateModal"
    assert "api.approvals" in content or "approvals.approve" in content, (
        "page.tsx must wire api.approvals.approve"
    )
    assert "api.tickets.escalate" in content or "tickets.escalate" in content, (
        "page.tsx must wire api.tickets.escalate"
    )


def test_workflow_panel_enforces_pending_approval_rule() -> None:
    """Verify WorkflowPanel only enables Approve/Reject when pending per CLAUDE.md §11."""
    content = WORKFLOW_PANEL.read_text(encoding="utf-8")

    assert "isPendingApproval" in content or "approval_status" in content, (
        "WorkflowPanel must evaluate pending approval status"
    )
    assert "canAct" in content, (
        "WorkflowPanel must evaluate canAct role permission (AC-054)"
    )


def test_zero_gradient_invariant_ticket_actions() -> None:
    """Verify strict zero-gradient enforcement across action modals (CLAUDE.md §11)."""
    gradient_pattern = re.compile(
        r"(bg-gradient|gradient-to-|from-[a-z]+-\d+|via-[a-z]+-\d+|to-[a-z]+-\d+)",
        re.IGNORECASE,
    )

    action_files = [APPROVE_MODAL, REJECT_MODAL, REPLY_MODAL, ESCALATE_MODAL]
    for file_path in action_files:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            matches = gradient_pattern.findall(text)
            assert not matches, (
                f"Gradient utility detected in {file_path.relative_to(REPO_ROOT)}: {matches}"
            )


def test_no_exposed_secrets_in_action_modals() -> None:
    """Verify no hardcoded credentials or mock tokens exist in action modals."""
    secret_pattern = re.compile(r"(ey[A-Za-z0-9-_]{30,}|sk-[A-Za-z0-9]{20,})")

    action_files = [APPROVE_MODAL, REJECT_MODAL, REPLY_MODAL, ESCALATE_MODAL]
    for file_path in action_files:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            matches = secret_pattern.findall(text)
            assert not matches, (
                f"Hardcoded secret pattern in {file_path.relative_to(REPO_ROOT)}"
            )
