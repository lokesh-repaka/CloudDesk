"""Evaluation case schema and dataset loader (P9-8).

Defines the EvalCase domain schema and utility functions for loading, validating,
and filtering the benchmark evaluation dataset `datasets/eval_cases.json`.
Adheres to CLAUDE.md §13 (Quality bar), §14, and US-023 (AC-073).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import CategoryEnum, CustomerPlanEnum, SeverityEnum

DEFAULT_EVAL_DATASET_PATH = Path("datasets/eval_cases.json")


class EvalCase(BaseModel):
    """Benchmark evaluation case specification for offline quality evaluation (AC-073)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique eval case identifier e.g. EVAL-001.")
    ticket_id: str = Field(..., description="Reference ticket identifier e.g. CD-1001.")
    customer_id: str = Field(..., description="Customer identifier e.g. cust-101-acme.")
    customer_plan: CustomerPlanEnum = Field(
        default=CustomerPlanEnum.ENTERPRISE,
        description="Customer subscription tier.",
    )
    subject: str = Field(..., description="Ticket subject line.")
    text: str = Field(..., description="Full customer inquiry body.")
    expected_category: CategoryEnum = Field(
        ...,
        description="Canonical expected category out of the 10 domain categories.",
    )
    expected_severity: SeverityEnum = Field(
        ...,
        description="Expected assessed ticket severity.",
    )
    expected_escalate: bool = Field(
        default=False,
        description="Whether case requires specialized team escalation.",
    )
    expected_target_team: str | None = Field(
        default=None,
        description="Designated specialized team if escalation expected.",
    )
    expected_article_slug: str | None = Field(
        default=None,
        description="Knowledge article slug expected in retrieval top hits.",
    )
    expected_action_tools: list[str] = Field(
        default_factory=lambda: ["update_ticket"],
        description="Planned tool names expected in resolution.",
    )
    expected_approval_required: bool = Field(
        default=False,
        description="Whether proposed resolution requires human approval gate.",
    )
    grounding_keywords: list[str] = Field(
        default_factory=list,
        description="Key terms/steps required in grounded customer reply.",
    )
    is_injection: bool = Field(
        default=False,
        description="True if ticket contains prompt injection payload.",
    )


def load_eval_cases(
    path: str | Path | None = None,
    category: CategoryEnum | str | None = None,
) -> list[EvalCase]:
    """Load, validate, and optionally filter evaluation cases from JSON dataset.

    Args:
        path: Path to dataset JSON file (defaults to datasets/eval_cases.json).
        category: Optional CategoryEnum or string to filter returned cases.

    Returns:
        List of validated EvalCase instances.

    Raises:
        FileNotFoundError: If the dataset file does not exist.
        ValueError: If file is malformed JSON or fails schema validation.
    """
    file_path = Path(path) if path is not None else DEFAULT_EVAL_DATASET_PATH

    if not file_path.is_file():
        raise FileNotFoundError(f"Evaluation dataset file not found at: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        try:
            raw_data = json.load(f)
        except json.JSONDecodeError as err:
            raise ValueError(f"Malformed JSON in eval dataset: {err}") from err

    if not isinstance(raw_data, list):
        raise TypeError("Eval dataset JSON must be an array of eval case objects.")

    cases: list[EvalCase] = []
    cat_filter = (
        category.value
        if isinstance(category, CategoryEnum)
        else (category.lower() if category else None)
    )

    for item in raw_data:
        case = EvalCase.model_validate(item)
        if cat_filter is not None and case.expected_category.value != cat_filter:
            continue
        cases.append(case)

    return cases
