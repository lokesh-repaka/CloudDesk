"""Unit tests verifying Frontend Unit Test Suite (P13-4).

Covers:
- P13-4: Frontend unit tests (feature/frontend-unit-tests)
- CLAUDE.md §13 table:
  frontend/__tests__/ proves: StatusPill, EmptyState, WorkflowSteps.deriveSteps, api helpers
- Strict zero-gradient invariant (CLAUDE.md §11)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
TESTS_DIR = FRONTEND_DIR / "__tests__"

STATUS_PILL_TEST = TESTS_DIR / "status-pill.test.ts"
EMPTY_STATE_TEST = TESTS_DIR / "empty-state.test.ts"
WORKFLOW_STEPS_TEST = TESTS_DIR / "workflow-steps.test.ts"
API_TEST = TESTS_DIR / "api.test.ts"

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

ALL_STATUSES = [
    "new",
    "in_progress",
    "waiting_on_customer",
    "waiting_on_approval",
    "escalated",
    "resolved",
    "closed",
]


def test_frontend_test_files_exist() -> None:
    """Verify all frontend test files specified in CLAUDE.md §13 exist."""
    files = [STATUS_PILL_TEST, EMPTY_STATE_TEST, WORKFLOW_STEPS_TEST, API_TEST]
    for file_path in files:
        assert file_path.exists(), f"Missing file: {file_path.relative_to(REPO_ROOT)}"
        assert file_path.stat().st_size > 0, (
            f"File is empty: {file_path.relative_to(REPO_ROOT)}"
        )


def test_status_pill_test_coverage() -> None:
    """Verify StatusPill tests cover all 7 canonical ticket statuses and variants."""
    content = STATUS_PILL_TEST.read_text(encoding="utf-8")

    assert "StatusPill" in content, "status-pill.test.ts must test StatusPill component"
    for status in ALL_STATUSES:
        assert status in content, f"status-pill.test.ts must verify status '{status}'"


def test_empty_state_test_coverage() -> None:
    """Verify EmptyState tests cover title, description, icon, and actions."""
    content = EMPTY_STATE_TEST.read_text(encoding="utf-8")

    assert "EmptyState" in content, "empty-state.test.ts must test EmptyState component"
    assert "title" in content.lower(), "empty-state.test.ts must test title rendering"
    assert "description" in content.lower(), (
        "empty-state.test.ts must test description rendering"
    )
    assert "action" in content.lower() or "button" in content.lower(), (
        "empty-state.test.ts must test action button support"
    )


def test_workflow_steps_test_coverage() -> None:
    """Verify workflow-steps.test.ts proves deriveSteps for 12 nodes, branch routing, and telemetry."""
    content = WORKFLOW_STEPS_TEST.read_text(encoding="utf-8")

    assert "deriveSteps" in content, (
        "workflow-steps.test.ts must test deriveSteps function per CLAUDE.md §13"
    )
    for node in CANONICAL_12_NODES:
        assert node in content, (
            f"workflow-steps.test.ts must verify canonical node '{node}'"
        )

    assert "paused" in content, "must test paused approval state"
    assert "skipped" in content, "must test branch routing bypass/skip state"
    assert "duration" in content.lower() or "telemetry" in content.lower(), (
        "must test telemetry event mapping"
    )


def test_api_helpers_test_coverage() -> None:
    """Verify api.test.ts proves token management and error classifications."""
    content = API_TEST.read_text(encoding="utf-8")

    assert "getToken" in content, "api.test.ts must test getToken"
    assert "setToken" in content, "api.test.ts must test setToken"
    assert "clearToken" in content, "api.test.ts must test clearToken"
    assert "ApiClientError" in content, "api.test.ts must test ApiClientError"
    assert "NetworkError" in content, "api.test.ts must test NetworkError"


def test_zero_gradient_invariant_in_test_files() -> None:
    """Verify strict zero-gradient enforcement in test specifications."""
    gradient_pattern = re.compile(
        r"(bg-gradient|gradient-to-|from-[a-z]+-\d+|via-[a-z]+-\d+|to-[a-z]+-\d+)",
        re.IGNORECASE,
    )

    test_files = [STATUS_PILL_TEST, EMPTY_STATE_TEST, WORKFLOW_STEPS_TEST, API_TEST]
    for file_path in test_files:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            matches = gradient_pattern.findall(text)
            assert not matches, (
                f"Gradient utility detected in {file_path.relative_to(REPO_ROOT)}: {matches}"
            )


def test_no_exposed_secrets_in_frontend_test_files() -> None:
    """Verify no production credentials or real API keys in frontend test files."""
    secret_pattern = re.compile(r"(ey[A-Za-z0-9-_]{40,}|sk-proj-[A-Za-z0-9]{20,})")

    test_files = [STATUS_PILL_TEST, EMPTY_STATE_TEST, WORKFLOW_STEPS_TEST, API_TEST]
    for file_path in test_files:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            matches = secret_pattern.findall(text)
            assert not matches, (
                f"Hardcoded secret pattern in {file_path.relative_to(REPO_ROOT)}"
            )
