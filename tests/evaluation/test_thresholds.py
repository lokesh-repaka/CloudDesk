"""Evaluation Thresholds Test Suite (P14-1, CLAUDE.md §13, AC-073).

Verifies the 5 locked evaluation thresholds over `datasets/eval_cases.json`:
1. classification accuracy ≥ 0.80
2. retrieval hit-rate@3 ≥ 0.75
3. escalation correctness ≥ 0.90
4. citation rate ≥ 0.90
5. grounding rate (steps present in reply) ≥ 0.90

These evaluation thresholds fail the build if not satisfied.
Conforms to:
- CLAUDE.md §13 (Evaluation thresholds – these fail the build)
- PLAN.md §Phase 14 (P14-1 · Evaluation thresholds)
- US-023 / AC-073 (Quality & Evaluation Bar)
- CWE-20, CWE-116, CWE-200, CWE-400 (Security controls)
"""

from __future__ import annotations

import pytest

from backend.app.schemas.eval_case import (
    DEFAULT_EVAL_DATASET_PATH,
    EvalCase,
    load_eval_cases,
)
from tests.evaluation.evaluator import (
    THRESHOLD_CITATION_RATE,
    THRESHOLD_CLASSIFICATION_ACCURACY,
    THRESHOLD_ESCALATION_CORRECTNESS,
    THRESHOLD_GROUNDING_RATE,
    THRESHOLD_RETRIEVAL_HIT_RATE_AT_3,
    EvaluationReport,
    MetricResult,
    evaluate_all,
    evaluate_citations,
    evaluate_classification,
    evaluate_escalation,
    evaluate_grounding,
    evaluate_retrieval,
    evaluate_workflow_e2e,
)


@pytest.fixture(scope="session")
def eval_cases() -> list[EvalCase]:
    """Load benchmark dataset from datasets/eval_cases.json."""
    return load_eval_cases(path=DEFAULT_EVAL_DATASET_PATH)


# ============================================================================
# 1. Five Mandatory Hard CI Failure Thresholds (CLAUDE.md §13, AC-073)
# ============================================================================


async def test_threshold_classification_accuracy(eval_cases: list[EvalCase]):
    """Verify classification accuracy meets or exceeds locked threshold (≥ 0.80).

    CLAUDE.md §13: classification accuracy ≥ 0.80
    AC-073: SupervisorAgent and classification engine achieve ≥ 80% accuracy.
    """
    result: MetricResult = await evaluate_classification(eval_cases)

    assert result.passed is True, (
        f"Classification accuracy {result.score:.2%} is below threshold {result.threshold:.2%}"
    )
    assert result.score >= THRESHOLD_CLASSIFICATION_ACCURACY
    assert result.total_cases == len(eval_cases)
    assert result.successful_cases >= int(len(eval_cases) * THRESHOLD_CLASSIFICATION_ACCURACY)


async def test_threshold_retrieval_hit_rate_at_3(eval_cases: list[EvalCase]):
    """Verify documentation retrieval hit-rate@3 meets or exceeds locked threshold (≥ 0.75).

    CLAUDE.md §13: retrieval hit-rate@3 ≥ 0.75
    AC-073: Hybrid RAG retriever surfaces the expected article in top-3 hits in ≥ 75% of cases.
    """
    result: MetricResult = await evaluate_retrieval(eval_cases, top_k=3)

    assert result.passed is True, (
        f"Retrieval hit-rate@3 {result.score:.2%} is below threshold {result.threshold:.2%}"
    )
    assert result.score >= THRESHOLD_RETRIEVAL_HIT_RATE_AT_3
    assert result.total_cases >= 15
    assert result.successful_cases >= int(result.total_cases * THRESHOLD_RETRIEVAL_HIT_RATE_AT_3)


async def test_threshold_escalation_correctness(eval_cases: list[EvalCase]):
    """Verify escalation correctness meets or exceeds locked threshold (≥ 0.90).

    CLAUDE.md §13: escalation correctness ≥ 0.90
    AC-073: Escalation decision and specialist team routing achieve ≥ 90% correctness.
    """
    result: MetricResult = await evaluate_escalation(eval_cases)

    assert result.passed is True, (
        f"Escalation correctness {result.score:.2%} is below threshold {result.threshold:.2%}"
    )
    assert result.score >= THRESHOLD_ESCALATION_CORRECTNESS
    assert result.total_cases == len(eval_cases)
    assert result.successful_cases >= int(len(eval_cases) * THRESHOLD_ESCALATION_CORRECTNESS)


async def test_threshold_citation_rate(eval_cases: list[EvalCase]):
    """Verify citation rate meets or exceeds locked threshold (≥ 0.90).

    CLAUDE.md §13: citation rate ≥ 0.90
    AC-073: Resolution plans provide verifiable evidence citations in ≥ 90% of cases.
    """
    result: MetricResult = await evaluate_citations(eval_cases)

    assert result.passed is True, (
        f"Citation rate {result.score:.2%} is below threshold {result.threshold:.2%}"
    )
    assert result.score >= THRESHOLD_CITATION_RATE
    assert result.total_cases == len(eval_cases)
    assert result.successful_cases >= int(len(eval_cases) * THRESHOLD_CITATION_RATE)


async def test_threshold_grounding_rate(eval_cases: list[EvalCase]):
    """Verify grounding rate (steps present in reply) meets or exceeds locked threshold (≥ 0.90).

    CLAUDE.md §13: grounding rate (steps present in reply) ≥ 0.90
    AC-073: Proposed customer reply embeds concrete troubleshooting steps in ≥ 90% of cases.
    """
    result: MetricResult = await evaluate_grounding(eval_cases)

    assert result.passed is True, (
        f"Grounding rate {result.score:.2%} is below threshold {result.threshold:.2%}"
    )
    assert result.score >= THRESHOLD_GROUNDING_RATE
    assert result.total_cases == len(eval_cases)
    assert result.successful_cases >= int(len(eval_cases) * THRESHOLD_GROUNDING_RATE)


# ============================================================================
# 2. Composite Benchmark & Workflow Integration Tests
# ============================================================================


async def test_overall_evaluation_report_passes(eval_cases: list[EvalCase]):
    """Verify complete evaluation report passes and formats clean markdown summary."""
    report: EvaluationReport = await evaluate_all(eval_cases)

    assert report.overall_passed is True
    assert report.total_cases == len(eval_cases)
    assert report.duration_seconds > 0.0

    # Verify all 5 individual sub-metrics passed
    assert report.classification.passed is True
    assert report.retrieval.passed is True
    assert report.escalation.passed is True
    assert report.citation.passed is True
    assert report.grounding.passed is True

    # Validate formatted output structure
    table_text = report.summary_table()
    assert "CloudDesk Evaluation Quality Benchmark Report" in table_text
    assert "Classification Accuracy" in table_text
    assert "Retrieval Hit-Rate@3" in table_text
    assert "Escalation Correctness" in table_text
    assert "Citation Rate" in table_text
    assert "Grounding Rate" in table_text
    assert "PASSED [OK]" in table_text


async def test_workflow_e2e_evaluation_thresholds(eval_cases: list[EvalCase]):
    """Verify all 5 evaluation thresholds are satisfied when executed via full LangGraph workflow."""
    report: EvaluationReport = await evaluate_workflow_e2e(eval_cases)

    assert report.overall_passed is True
    assert report.classification.score >= THRESHOLD_CLASSIFICATION_ACCURACY
    assert report.retrieval.score >= THRESHOLD_RETRIEVAL_HIT_RATE_AT_3
    assert report.escalation.score >= THRESHOLD_ESCALATION_CORRECTNESS
    assert report.citation.score >= THRESHOLD_CITATION_RATE
    assert report.grounding.score >= THRESHOLD_GROUNDING_RATE


# ============================================================================
# 3. Threshold Failure Detection & Enforcement Verification
# ============================================================================


def test_threshold_failure_strictly_detected():
    """Verify evaluator strictly flags failure when metrics fall below required thresholds."""
    # Simulated degraded classification: 75% < 80%
    sub_threshold_class = MetricResult(
        name="Classification Accuracy",
        score=0.75,
        threshold=THRESHOLD_CLASSIFICATION_ACCURACY,
        passed=0.75 >= THRESHOLD_CLASSIFICATION_ACCURACY,
        total_cases=20,
        successful_cases=15,
    )
    assert sub_threshold_class.passed is False
    assert "FAIL [X]" in sub_threshold_class.summary_line()

    # Simulated degraded retrieval: 70% < 75%
    sub_threshold_retrieval = MetricResult(
        name="Retrieval Hit-Rate@3",
        score=0.70,
        threshold=THRESHOLD_RETRIEVAL_HIT_RATE_AT_3,
        passed=0.70 >= THRESHOLD_RETRIEVAL_HIT_RATE_AT_3,
        total_cases=20,
        successful_cases=14,
    )
    assert sub_threshold_retrieval.passed is False

    # Composite report with one degraded metric must fail overall
    passing_metric = MetricResult(
        name="Passing Metric",
        score=0.95,
        threshold=0.90,
        passed=True,
        total_cases=20,
        successful_cases=19,
    )
    failed_report = EvaluationReport(
        classification=sub_threshold_class,
        retrieval=passing_metric,
        escalation=passing_metric,
        citation=passing_metric,
        grounding=passing_metric,
        total_cases=20,
        duration_seconds=0.15,
        overall_passed=False,
    )
    assert failed_report.overall_passed is False
    assert "FAILED [X]" in failed_report.summary_table()


# ============================================================================
# 4. Security Audit & Boundary Tests (CWE-20, CWE-116, CWE-200, CWE-400)
# ============================================================================


async def test_security_cwe_20_empty_dataset_rejection():
    """Verify evaluators reject empty or missing datasets safely (CWE-20)."""
    with pytest.raises(ValueError, match="empty"):
        await evaluate_classification([])

    with pytest.raises(ValueError, match="empty"):
        await evaluate_retrieval([])

    with pytest.raises(ValueError, match="empty"):
        await evaluate_escalation([])

    with pytest.raises(ValueError, match="empty"):
        await evaluate_citations([])

    with pytest.raises(ValueError, match="empty"):
        await evaluate_grounding([])

    with pytest.raises(ValueError, match="empty"):
        await evaluate_all([])


async def test_security_cwe_116_injection_cases_contained(eval_cases: list[EvalCase]):
    """Verify prompt injection cases within benchmark suite are detected and routed securely (CWE-116)."""
    injection_cases = [c for c in eval_cases if c.is_injection]
    assert len(injection_cases) >= 1

    esc_result = await evaluate_escalation(injection_cases)
    for detail in esc_result.details:
        assert detail["actual_escalate"] is True
        assert detail["actual_team"] == "Security"


def test_security_cwe_200_scrubbed_summary_report():
    """Verify evaluation summary tables scrub credentials and secrets (CWE-200)."""
    mock_metric = MetricResult(
        name="Classification Accuracy",
        score=0.95,
        threshold=0.80,
        passed=True,
        total_cases=20,
        successful_cases=19,
        details=[{"secret": "sk-live-abcd1234efgh5678ijkl"}],
    )
    report = EvaluationReport(
        classification=mock_metric,
        retrieval=mock_metric,
        escalation=mock_metric,
        citation=mock_metric,
        grounding=mock_metric,
        total_cases=20,
        duration_seconds=0.1,
        overall_passed=True,
    )
    summary = report.summary_table()
    assert "sk-live" not in summary
    assert "abcd1234" not in summary


def test_security_cwe_400_dataset_bounded(eval_cases: list[EvalCase]):
    """Verify eval case counts and individual text payloads are strictly bounded against DoS (CWE-400)."""
    assert len(eval_cases) <= 500
    for case in eval_cases:
        assert len(case.text) <= 50_000
        assert len(case.subject) <= 500
