"""Unit, Integration, and Security Tests for Demo Script (P11-5).

Verifies CLAUDE.md §14, PLAN.md §Phase 11, AC-035, AC-039, AC-043, and AC-072:
- `make demo` / `run_demo("CD-1002")` pauses on human approval for `create_refund_request`,
  prompts/resumes, and executes resolution on the shared tool path.
- `make demo TICKET=CD-1005` / `run_demo("CD-1005")` deterministically escalates to Security
  by policy rule without pause.
- `run_demo_all()` executes both CD-1002 and CD-1005 workflows in sequence.
- CLI argument parsing supports `--ticket`, `--all`, `--decision`, `--non-interactive`, and `--verbose`.
- Security audit: CWE-200 (secret scrubbing from demo output) and CWE-285 (consequential action gating).
"""

from __future__ import annotations

import io
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import (
    NODE_ESCALATION,
    NODE_EXECUTE_RESOLUTION,
    NODE_HUMAN_APPROVAL,
    NODE_MEMORY_UPDATE,
    NODE_TICKET_SUMMARY,
)
from backend.app.core.database import create_tables, get_session_factory
from backend.app.demo import (
    DemoResult,
    format_demo_output,
    main,
    parse_args,
    run_demo,
    run_demo_all,
)
from backend.app.models.entities import Ticket
from backend.app.services.seed_service import bootstrap_demo_data


@pytest.fixture
async def demo_db_session():
    """Create database session pre-populated with standard demo fixtures."""
    await create_tables()
    session_factory = get_session_factory()
    async with session_factory() as session:
        t_check = await session.execute(select(Ticket).limit(1))
        if t_check.scalars().first() is None:
            await bootstrap_demo_data(session)
        yield session


# ============================================================================
# 1. CD-1002 Approval Interrupt and Resumption Tests (AC-035, AC-039)
# ============================================================================


@pytest.mark.asyncio
async def test_demo_cd_1002_pauses_for_approval_and_resumes(
    demo_db_session: AsyncSession,
):
    """Verify CD-1002 pauses at human_approval, resumes on approval, and executes refund (AC-035, AC-039)."""
    result: DemoResult = await run_demo(
        ticket_id="CD-1002",
        session=demo_db_session,
        auto_approve=True,
        decision="approved",
    )

    assert result.ticket_id == "CD-1002"
    assert result.interrupted is True
    assert result.resumed is True
    assert result.approval_status == "approved"

    # Verify node progression
    assert NODE_HUMAN_APPROVAL in result.completed_nodes
    assert NODE_EXECUTE_RESOLUTION in result.completed_nodes
    assert NODE_TICKET_SUMMARY in result.completed_nodes
    assert NODE_MEMORY_UPDATE in result.completed_nodes

    # Verify consequential action was executed on shared tool path
    executed = result.executed_actions
    assert len(executed) >= 1
    refund_act = next(
        (a for a in executed if a.get("tool_name") == "create_refund_request"),
        None,
    )
    assert refund_act is not None
    assert refund_act.get("status") == "executed"
    assert result.ticket_status in ("resolved", "closed", "waiting_on_customer")


@pytest.mark.asyncio
async def test_demo_cd_1002_rejection_routes_to_escalation(
    demo_db_session: AsyncSession,
):
    """Verify rejecting CD-1002 human approval resumes workflow directly to escalation (AC-040)."""
    result: DemoResult = await run_demo(
        ticket_id="CD-1002",
        session=demo_db_session,
        auto_approve=True,
        decision="rejected",
    )

    assert result.ticket_id == "CD-1002"
    assert result.interrupted is True
    assert result.resumed is True
    assert result.approval_status == "rejected"

    # Rejecting routes to escalation instead of execute_resolution
    assert NODE_HUMAN_APPROVAL in result.completed_nodes
    assert NODE_ESCALATION in result.completed_nodes
    assert NODE_EXECUTE_RESOLUTION not in result.completed_nodes


# ============================================================================
# 2. CD-1005 Deterministic Policy Escalation Tests (AC-043, AC-044)
# ============================================================================


@pytest.mark.asyncio
async def test_demo_cd_1005_escalates_by_policy_rule(
    demo_db_session: AsyncSession,
):
    """Verify CD-1005 deterministically escalates to Security by policy rule without pause (AC-043)."""
    result: DemoResult = await run_demo(
        ticket_id="CD-1005",
        session=demo_db_session,
    )

    assert result.ticket_id == "CD-1005"
    assert result.interrupted is False
    assert result.escalation_required is True
    assert result.escalation_team == "Security"
    assert NODE_ESCALATION in result.completed_nodes
    assert NODE_HUMAN_APPROVAL not in result.completed_nodes
    assert result.ticket_status == "escalated"
    assert result.escalation_id is not None


# ============================================================================
# 3. Batch and Sequential Execution Tests
# ============================================================================


@pytest.mark.asyncio
async def test_demo_all_runs_both_cd_1002_and_cd_1005(
    demo_db_session: AsyncSession,
):
    """Verify run_demo_all executes both CD-1002 and CD-1005 consecutively."""
    results = await run_demo_all(
        session=demo_db_session,
        auto_approve=True,
    )

    assert len(results) == 2
    r_1002, r_1005 = results[0], results[1]

    # CD-1002 approval flow
    assert r_1002.ticket_id == "CD-1002"
    assert r_1002.interrupted is True
    assert r_1002.resumed is True

    # CD-1005 escalation flow
    assert r_1005.ticket_id == "CD-1005"
    assert r_1005.interrupted is False
    assert r_1005.escalation_required is True
    assert r_1005.escalation_team == "Security"


# ============================================================================
# 4. CLI Argument Parsing Tests
# ============================================================================


def test_demo_cli_argument_parsing():
    """Verify argument parser extracts ticket, all, decision, and interactive flags."""
    args_default = parse_args([])
    assert args_default.ticket == "CD-1002"
    assert args_default.all is False
    assert args_default.decision == "approved"
    assert args_default.non_interactive is False

    args_custom = parse_args(
        [
            "--ticket",
            "CD-1005",
            "--non-interactive",
            "--verbose",
        ]
    )
    assert args_custom.ticket == "CD-1005"
    assert args_custom.non_interactive is True
    assert args_custom.verbose is True

    args_all = parse_args(["--all", "-y", "--decision", "rejected"])
    assert args_all.all is True
    assert args_all.non_interactive is True
    assert args_all.decision == "rejected"


# ============================================================================
# 5. CLI Entrypoint Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_demo_main_entrypoint_cd_1002():
    """Verify CLI main entrypoint executes CD-1002 successfully with exit code 0."""
    with patch("sys.stdout", new=io.StringIO()):
        code = await main(["--ticket", "CD-1002", "--non-interactive"])
        assert code == 0


@pytest.mark.asyncio
async def test_demo_main_entrypoint_cd_1005():
    """Verify CLI main entrypoint executes CD-1005 successfully with exit code 0."""
    with patch("sys.stdout", new=io.StringIO()):
        code = await main(["--ticket", "CD-1005", "--non-interactive"])
        assert code == 0


@pytest.mark.asyncio
async def test_demo_unknown_ticket_graceful_error(
    demo_db_session: AsyncSession,
):
    """Verify unknown ticket ID is reported gracefully without crashing."""
    result = await run_demo(
        ticket_id="CD-9999",
        session=demo_db_session,
    )
    assert result.error is not None
    assert "not found" in result.error.lower()


# ============================================================================
# 6. Security & Penetration Tests (CWE-200, CWE-285)
# ============================================================================


def test_security_cwe_200_no_secrets_in_demo_output():
    """Security Audit (CWE-200): Ensure credentials/PANs are scrubbed from demo formatting."""
    raw_data: dict[str, Any] = {
        "ticket_id": "CD-1002",
        "secret": "sk-live-secret1234567890abcdef12345678",
        "card": "4532 0150 1234 5671",
        "password": "password: SecretPassword123!",
    }

    formatted = format_demo_output(raw_data)
    assert "sk-live-" not in formatted
    assert "4532 0150 1234 5671" not in formatted
    assert "SecretPassword123!" not in formatted
    assert "***REDACTED***" in formatted


@pytest.mark.asyncio
async def test_security_cwe_285_approval_gated_demo_execution(
    demo_db_session: AsyncSession,
):
    """Security Audit (CWE-285): Verify consequential action remains unexecuted without resume."""
    # When resume is disabled (auto_approve=False and interactive prompt declined), actions are gated
    result = await run_demo(
        ticket_id="CD-1002",
        session=demo_db_session,
        auto_approve=False,
        interactive=False,  # declines prompt
    )

    assert result.interrupted is True
    assert result.resumed is False
    # Consequential refund must not have been executed
    assert NODE_EXECUTE_RESOLUTION not in result.completed_nodes
    executed = result.executed_actions
    assert not any(
        a.get("tool_name") == "create_refund_request" and a.get("status") == "executed"
        for a in executed
    )
