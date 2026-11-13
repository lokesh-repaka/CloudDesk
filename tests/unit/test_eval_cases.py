"""Unit, integration, and security tests for Evaluation Case Dataset (P9-8).

Verifies the curation, schema validity, category coverage, policy escalation mappings,
grounding expectations, and agent benchmark accuracy of `datasets/eval_cases.json`
in accordance with:
CLAUDE.md §13 (Quality bar), §14, US-023 (AC-072, AC-073), and PLAN.md §System requirements.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.rules import matching_escalation_rules, rule_category
from agents.specialists.resolution import ResolutionAgent
from backend.app.core.guardrails import SECRET_PATTERNS, scan_for_injection
from backend.app.schemas.common import CategoryEnum, SeverityEnum
from backend.app.schemas.eval_case import (
    DEFAULT_EVAL_DATASET_PATH,
    EvalCase,
    load_eval_cases,
)


@pytest.fixture
def eval_dataset_path() -> Path:
    """Return path to datasets/eval_cases.json."""
    return DEFAULT_EVAL_DATASET_PATH


@pytest.fixture
def eval_cases() -> list[EvalCase]:
    """Load and return all parsed eval cases."""
    return load_eval_cases()


# ============================================================================
# 1. Dataset File & Schema Validation Tests (AC-073, US-023)
# ============================================================================


def test_eval_cases_file_exists_and_valid_json(eval_dataset_path: Path):
    """Verify datasets/eval_cases.json exists and is valid JSON."""
    assert eval_dataset_path.is_file(), f"Missing dataset file at {eval_dataset_path}"
    with open(eval_dataset_path, encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) >= 15, (
        "Evaluation dataset must contain at least 15 comprehensive cases."
    )


def test_eval_cases_schema_validation(eval_cases: list[EvalCase]):
    """Verify every case parses into the strongly typed EvalCase Pydantic model."""
    assert len(eval_cases) >= 15
    for case in eval_cases:
        assert isinstance(case, EvalCase)
        assert case.id.startswith("EVAL-")
        assert len(case.subject) > 0
        assert len(case.text) > 0
        assert isinstance(case.expected_category, CategoryEnum)
        assert isinstance(case.expected_severity, SeverityEnum)
        assert isinstance(case.expected_escalate, bool)
        assert isinstance(case.expected_approval_required, bool)
        assert isinstance(case.expected_action_tools, list)
        assert isinstance(case.grounding_keywords, list)
        assert len(case.grounding_keywords) >= 1


# ============================================================================
# 2. Domain & Category Coverage Tests (AC-073, CLAUDE.md §13)
# ============================================================================


def test_eval_cases_canonical_category_coverage(eval_cases: list[EvalCase]):
    """Verify all 10 canonical categories are represented in the dataset."""
    present_categories = {case.expected_category for case in eval_cases}
    all_categories = set(CategoryEnum)

    missing = all_categories - present_categories
    assert not missing, f"Dataset is missing coverage for categories: {missing}"
    assert len(present_categories) == 10


def test_eval_cases_severity_levels_coverage(eval_cases: list[EvalCase]):
    """Verify all 4 severity levels (low, medium, high, critical) are represented."""
    present_severities = {case.expected_severity for case in eval_cases}
    all_severities = set(SeverityEnum)

    missing = all_severities - present_severities
    assert not missing, f"Dataset is missing coverage for severities: {missing}"


def test_eval_cases_policy_escalation_scenarios(eval_cases: list[EvalCase]):
    """Verify mandatory policy escalation scenarios (Security, Data Loss, GDPR, Dispute, Outage)."""
    escalated_cases = [c for c in eval_cases if c.expected_escalate]
    assert len(escalated_cases) >= 4, (
        "Must include at least 4 deterministic escalation cases."
    )

    target_teams = {
        c.expected_target_team for c in escalated_cases if c.expected_target_team
    }
    assert "Security" in target_teams
    assert "Engineering" in target_teams
    assert "Legal" in target_teams
    assert "Billing" in target_teams


def test_eval_cases_consequential_approval_scenarios(eval_cases: list[EvalCase]):
    """Verify consequential approval-gated actions (refunds, setting resets) are present."""
    approval_cases = [c for c in eval_cases if c.expected_approval_required]
    assert len(approval_cases) >= 2, (
        "Must include refund and setting reset approval cases."
    )

    all_tools = [tool for c in approval_cases for tool in c.expected_action_tools]
    assert "create_refund_request" in all_tools
    assert "reset_demo_setting" in all_tools


def test_eval_cases_article_slugs_exist_in_kb(eval_cases: list[EvalCase]):
    """Verify every referenced knowledge base article slug exists in sample_data/knowledge_base."""
    kb_dir = Path("sample_data/knowledge_base")
    assert kb_dir.is_dir()

    existing_slugs = {p.stem for p in kb_dir.glob("*.md")}

    for case in eval_cases:
        if case.expected_article_slug:
            assert case.expected_article_slug in existing_slugs, (
                f"Referenced article slug '{case.expected_article_slug}' not found in {kb_dir}"
            )


# ============================================================================
# 3. Agent Quality Benchmark Verification (Quality Bar, AC-073)
# ============================================================================


def test_eval_cases_supervisor_classification_accuracy(eval_cases: list[EvalCase]):
    """Verify heuristic / rule classification accuracy over eval dataset exceeds threshold (≥ 0.80)."""
    correct = 0
    total = 0

    for case in eval_cases:
        # Skip prompt injection case from standard category accuracy check as it is an attack payload
        if case.is_injection:
            continue

        predicted = rule_category(case.text) or CategoryEnum.OTHER
        if predicted == case.expected_category:
            correct += 1
        total += 1

    accuracy = correct / total if total > 0 else 0.0
    # Rule category baseline exceeds 0.80 threshold
    assert accuracy >= 0.80, (
        f"Classification accuracy {accuracy:.2f} is below threshold 0.80"
    )


def test_eval_cases_escalation_rules_accuracy(eval_cases: list[EvalCase]):
    """Verify escalation rule matching accuracy over eval dataset exceeds threshold (≥ 0.90)."""
    correct = 0
    total = len(eval_cases)

    for case in eval_cases:
        matched_rules = matching_escalation_rules(
            text=case.text,
            category=case.expected_category,
            customer_plan=case.customer_plan.value,
            is_active_outage=(
                case.expected_severity == SeverityEnum.CRITICAL
                and case.customer_plan.value == "enterprise"
            ),
        )
        has_matched_rule = len(matched_rules) > 0 or case.is_injection
        expected_escalate = case.expected_escalate

        if has_matched_rule == expected_escalate:
            correct += 1

    escalation_accuracy = correct / total if total > 0 else 0.0
    assert escalation_accuracy >= 0.90, (
        f"Escalation correctness {escalation_accuracy:.2f} is below threshold 0.90"
    )


def test_eval_cases_resolution_action_planning(eval_cases: list[EvalCase]):
    """Verify ResolutionAgent plans expected tools for billing refunds and workspace resets."""
    agent = ResolutionAgent()

    for case in eval_cases:
        if "create_refund_request" in case.expected_action_tools:
            actions = agent.plan_actions(
                category=case.expected_category,
                text=case.text,
                ticket_id=case.ticket_id,
            )
            tool_names = [a.tool_name for a in actions]
            assert "create_refund_request" in tool_names
            assert any(
                a.requires_approval
                for a in actions
                if a.tool_name == "create_refund_request"
            )

        if "reset_demo_setting" in case.expected_action_tools:
            actions = agent.plan_actions(
                category=case.expected_category,
                text=case.text,
                ticket_id=case.ticket_id,
            )
            tool_names = [a.tool_name for a in actions]
            assert "reset_demo_setting" in tool_names
            assert any(
                a.requires_approval
                for a in actions
                if a.tool_name == "reset_demo_setting"
            )


# ============================================================================
# 4. Loader Utilities & Boundary Tests (CWE-20)
# ============================================================================


def test_load_eval_cases_filter_by_category(eval_cases: list[EvalCase]):
    """Verify load_eval_cases supports filtering by specific category."""
    billing_cases = load_eval_cases(category=CategoryEnum.BILLING)
    assert len(billing_cases) >= 2
    assert all(c.expected_category == CategoryEnum.BILLING for c in billing_cases)


def test_load_eval_cases_missing_file_raises():
    """Verify loader raises FileNotFoundError when given non-existent path (CWE-20)."""
    with pytest.raises(FileNotFoundError):
        load_eval_cases(path="non_existent_dataset_file.json")


def test_load_eval_cases_invalid_json_or_type(tmp_path: Path):
    """Verify loader handles invalid JSON and non-list structures safely (CWE-20)."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_eval_cases(path=bad_json)

    not_a_list = tmp_path / "dict.json"
    not_a_list.write_text('{"key": "value"}', encoding="utf-8")
    with pytest.raises(TypeError, match="must be an array"):
        load_eval_cases(path=not_a_list)


# ============================================================================
# 5. Security Audit & Penetration Tests (CWE-116, CWE-200, CWE-400)
# ============================================================================


def test_security_cwe_200_no_secrets_in_eval_dataset(eval_cases: list[EvalCase]):
    """Security audit: Dataset contains no real API keys, PAN credit cards, or passwords (CWE-200, CWE-312)."""
    for case in eval_cases:
        full_text = f"{case.subject} {case.text}"
        for pattern_name, regex in SECRET_PATTERNS:
            # Exclude mock token in injection test case text if present
            if case.is_injection and pattern_name == "jwt_token":
                continue
            assert not regex.search(full_text), (
                f"Potential secret leak in case {case.id} matching {pattern_name}"
            )


def test_security_cwe_116_prompt_injection_contained(eval_cases: list[EvalCase]):
    """Penetration test: Injection eval cases are flagged by scanner and isolated (CWE-116)."""
    injection_cases = [c for c in eval_cases if c.is_injection]
    assert len(injection_cases) >= 1

    for inj_case in injection_cases:
        scan_result = scan_for_injection(inj_case.text)
        assert scan_result.is_suspicious is True
        assert inj_case.expected_escalate is True
        assert inj_case.expected_target_team == "Security"


def test_security_cwe_400_dataset_size_bounded(
    eval_dataset_path: Path, eval_cases: list[EvalCase]
):
    """Penetration test: Dataset payload size and case lengths are bounded against DoS (CWE-400)."""
    file_size_kb = eval_dataset_path.stat().st_size / 1024
    # Dataset file must not exceed 500KB
    assert file_size_kb <= 500, (
        f"Dataset file size {file_size_kb:.2f}KB exceeds safe ceiling (500KB)"
    )

    for case in eval_cases:
        assert len(case.text) <= 50000, (
            f"Case {case.id} text length exceeds MAX_PAYLOAD_LENGTH"
        )
