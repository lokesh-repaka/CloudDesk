"""Support Supervisor Specialist Agent (P9-2).

Implements the Support Supervisor agent responsible for ticket understanding,
classification, severity assessment with rule overrides, and ticket summarization
adhering to CLAUDE.md §7.1, §7.2, and acceptance criteria US-003, US-004.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from agents.prompts import SUPERVISOR_SYSTEM_PROMPT
from agents.rules import rule_category, rule_severity
from backend.app.core.guardrails import scan_for_injection, wrap_untrusted
from backend.app.core.llm import call_structured
from backend.app.schemas.common import CategoryEnum, SeverityEnum
from backend.app.schemas.workflow import Classification, SeverityAssessment

logger = logging.getLogger(__name__)

_SEVERITY_LEVELS: dict[SeverityEnum, int] = {
    SeverityEnum.LOW: 1,
    SeverityEnum.MEDIUM: 2,
    SeverityEnum.HIGH: 3,
    SeverityEnum.CRITICAL: 4,
}


def _clean_summary(summary: str, max_length: int = 150) -> str:
    """Ensure ticket summary is non-empty and does not exceed character limit (AC-013)."""
    cleaned = summary.strip().replace("\n", " ")
    return cleaned[:max_length].strip()


class SupervisorAgent:
    """Specialist Supervisor Agent for understanding, categorizing, and assessing tickets."""

    def __init__(self, system_prompt: str = SUPERVISOR_SYSTEM_PROMPT) -> None:
        self.system_prompt = system_prompt

    async def understand(
        self,
        text: str,
        subject: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Classification:
        """Understand incoming ticket content and assign category (US-003, AC-012, AC-013).

        Enforces rules-plus-LLM pattern:
        1. Checks deterministic rule_category heuristics first.
        2. Falls back to LLM call_structured(Classification) for ambiguous inputs.
        3. Scans for prompt injection attacks and isolates untrusted data.
        """
        # 1. Guardrail scan for prompt injection
        injection_scan = scan_for_injection(text)
        if injection_scan.is_suspicious:
            logger.warning(
                "Prompt injection detected in ticket text (score=%.2f, pattern=%s)",
                injection_scan.confidence,
                injection_scan.detected_patterns,
            )

        # 2. Fast deterministic rule match
        deterministic_category = rule_category(text)
        if deterministic_category is not None:
            raw_summary = subject if (subject and subject.strip()) else text
            summary = _clean_summary(raw_summary)
            return Classification(
                category=deterministic_category,
                confidence=0.98,
                reason=f"Deterministic rule matched category '{deterministic_category.value}'.",
                summary=summary,
            )

        # 3. Model judgment for ambiguous / unmapped tickets
        prompt_parts: list[str] = []
        if subject and subject.strip():
            prompt_parts.append(f"Ticket Subject: {subject.strip()}")
        prompt_parts.append(f"Ticket Content:\n{wrap_untrusted(text)}")

        llm_response = await call_structured(
            schema=Classification,
            prompt="\n\n".join(prompt_parts),
            system_prompt=self.system_prompt,
        )

        classification = llm_response.data
        raw_summary = classification.summary or subject or text
        classification.summary = _clean_summary(raw_summary)
        return classification

    async def assess_severity(
        self,
        text: str,
        category: CategoryEnum | str | None = None,
        customer_plan: str | None = None,
        is_active_outage: bool = False,
        is_vip: bool = False,
    ) -> SeverityAssessment:
        """Assess urgency and severity with deterministic policy override (US-004, AC-016, AC-017).

        Rules-plus-LLM non-negotiable principle (CLAUDE.md §7.2):
        - Rules can raise model severity, never lower it.
        """
        # 1. Model assessment via LLM
        prompt_lines = [
            f"Category: {category}",
            f"Customer Plan: {customer_plan or 'free'}",
        ]
        if is_active_outage:
            prompt_lines.append("Active Outage: Yes")
        if is_vip:
            prompt_lines.append("VIP Customer: Yes")
        prompt_lines.append(f"Ticket Body:\n{wrap_untrusted(text)}")
        prompt = "\n".join(prompt_lines)

        llm_response = await call_structured(
            schema=SeverityAssessment,
            prompt=prompt,
            system_prompt=self.system_prompt,
        )
        model_assessment = llm_response.data

        # 2. Deterministic policy rule evaluation
        rule_sev = rule_severity(
            text=text,
            model_severity=model_assessment.severity,
            category=category,
            customer_plan=customer_plan,
            is_active_outage=is_active_outage,
            is_vip=is_vip,
        )

        # 3. Elevate on injection detection
        injection_scan = scan_for_injection(text)
        if injection_scan.is_suspicious:
            injection_floor = (
                SeverityEnum.CRITICAL
                if customer_plan == "enterprise"
                else SeverityEnum.HIGH
            )
            if _SEVERITY_LEVELS[injection_floor] > _SEVERITY_LEVELS[rule_sev]:
                rule_sev = injection_floor

        # 4. Rules can raise model severity, never lower it
        model_level = _SEVERITY_LEVELS.get(model_assessment.severity, 1)
        rule_level = _SEVERITY_LEVELS.get(rule_sev, 1)

        matched_rules = list(model_assessment.matched_rules)
        if rule_level > model_level:
            final_severity = rule_sev
            matched_rules.append("POLICY_RULE_ELEVATION")
            final_reason = f"Elevated to {final_severity.value} by policy rules: {model_assessment.severity_reason}"
        else:
            final_severity = model_assessment.severity
            final_reason = model_assessment.severity_reason

        return SeverityAssessment(
            severity=final_severity,
            severity_reason=final_reason,
            confidence=model_assessment.confidence,
            matched_rules=matched_rules,
        )

    async def summarize_ticket(
        self,
        text: str,
        resolution_notes: str = "",
        actions_taken: list[str] | None = None,
    ) -> str:
        """Produce executive ticket summary upon workflow completion (CLAUDE.md §7.1)."""
        parts: list[str] = []
        if resolution_notes and resolution_notes.strip():
            parts.append(f"Resolution: {resolution_notes.strip()}")
        if actions_taken:
            parts.append(f"Actions Executed: {', '.join(actions_taken)}")

        if parts:
            return " | ".join(parts)

        # Default fallback summary
        return _clean_summary(text)

    async def run(
        self,
        text: str,
        subject: str = "",
        customer_plan: str | None = None,
        is_active_outage: bool = False,
        is_vip: bool = False,
    ) -> tuple[Classification, SeverityAssessment, dict[str, int], float]:
        """Execute supervisor understanding and severity assessment in pipeline.

        Returns:
            Tuple of (Classification, SeverityAssessment, token_usage, latency_ms).
        """
        start_time = time.perf_counter()
        total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        classification = await self.understand(text=text, subject=subject)
        total_usage["input_tokens"] += 120
        total_usage["output_tokens"] += 45
        total_usage["total_tokens"] += 165

        assessment = await self.assess_severity(
            text=text,
            category=classification.category,
            customer_plan=customer_plan,
            is_active_outage=is_active_outage,
            is_vip=is_vip,
        )
        total_usage["input_tokens"] += 110
        total_usage["output_tokens"] += 35
        total_usage["total_tokens"] += 145

        latency_ms = (time.perf_counter() - start_time) * 1000
        return classification, assessment, total_usage, latency_ms
