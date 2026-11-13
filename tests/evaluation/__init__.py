"""Evaluation suite for CloudDesk agent quality bars and thresholds (CLAUDE.md §13, AC-073).

Provides threshold definitions, metric calculators, and automated evaluation runners
for datasets/eval_cases.json.
"""

from __future__ import annotations

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

__all__ = [
    "THRESHOLD_CITATION_RATE",
    "THRESHOLD_CLASSIFICATION_ACCURACY",
    "THRESHOLD_ESCALATION_CORRECTNESS",
    "THRESHOLD_GROUNDING_RATE",
    "THRESHOLD_RETRIEVAL_HIT_RATE_AT_3",
    "EvaluationReport",
    "MetricResult",
    "evaluate_all",
    "evaluate_citations",
    "evaluate_classification",
    "evaluate_escalation",
    "evaluate_grounding",
    "evaluate_retrieval",
    "evaluate_workflow_e2e",
]

