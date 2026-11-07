"""Escalation Specialist Agent (P9-7).

Implements the Escalation Agent responsible for deterministic policy rule enforcement,
model escalation evaluation, prompt injection handoff, and specialized team routing adhering to:
CLAUDE.md §3 (F10), §7.1, §7.2, §7.3, §7.4, and US-012 (AC-043, AC-044, AC-045).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.prompts import ESCALATION_SYSTEM_PROMPT
from agents.rules import (
    evaluate_escalation_decision,
    matching_escalation_rules,
    rule_severity,
)
from backend.app.core.guardrails import scan_for_injection, wrap_untrusted
from backend.app.core.llm import call_structured
from backend.app.models.entities import Escalation
from backend.app.schemas.common import (
    CategoryEnum,
    CustomerPlanEnum,
    EscalationStatusEnum,
    SeverityEnum,
)
from backend.app.schemas.workflow import CustomerContext, EscalationDecision
from backend.app.tools.write_tools import create_escalation

logger = logging.getLogger(__name__)

# Bounded inputs against resource exhaustion (CWE-400)
MAX_PAYLOAD_LENGTH: int = 50_000


class EscalationAgent:
    """Specialist Escalation Agent for routing policy cases and high-risk tickets to specialist teams."""

    def __init__(self, system_prompt: str = ESCALATION_SYSTEM_PROMPT) -> None:
        self.system_prompt = system_prompt

    async def evaluate(
        self,
        text: str,
        category: str | CategoryEnum | None = None,
        severity: str | SeverityEnum | None = None,
        customer_context: CustomerContext | dict[str, Any] | None = None,
        is_active_outage: bool = False,
        is_vip: bool = False,
        plan_name: str | None = None,
        *,
        _mock_model_escalation: bool | None = None,
        _mock_model_confidence: float | None = None,
        _mock_model_team: str | None = None,
    ) -> EscalationDecision:
        """Evaluate ticket against deterministic policy escalation rules and model judgement (AC-043, AC-045).

        Non-negotiable rule (CLAUDE.md §7.2):
        - Deterministic policy escalation rules ALWAYS win.
        - Security breaches, catastrophic data loss, GDPR deletion requests, and billing disputes
          deterministically route to designated teams (Security, Engineering, Legal, Billing).
        - Prompt injection attempts route to Security.
        - Vague model escalations on high severity with low model confidence (< 0.70) are rejected (AC-045).
        """
        # 1. Input validation & bounding (CWE-20, CWE-400)
        if not text or not text.strip():
            raise ValueError("Ticket text cannot be empty or whitespace only.")

        bounded_text = text[:MAX_PAYLOAD_LENGTH].strip()

        # 2. Prompt injection detection (CWE-116)
        injection_scan = scan_for_injection(bounded_text)
        injection_detected = injection_scan.is_suspicious
        if injection_detected:
            logger.warning(
                "Prompt injection detected in escalation evaluation (score=%.2f); routing to Security.",
                injection_scan.confidence,
            )

        # Resolve customer plan string
        customer_plan = ""
        if isinstance(customer_context, CustomerContext):
            customer_plan = (
                customer_context.plan.value
                if isinstance(customer_context.plan, CustomerPlanEnum)
                else str(customer_context.plan)
            )
        elif isinstance(customer_context, dict):
            customer_plan = str(customer_context.get("plan", ""))

        # 3. Deterministic policy rule evaluation (AC-043)
        matched_rules = matching_escalation_rules(
            text=bounded_text,
            plan_name=plan_name,
            category=category,
            customer_plan=customer_plan,
            is_active_outage=is_active_outage,
        )

        if matched_rules:
            primary_rule = matched_rules[0]
            elevated_severity = rule_severity(
                text=bounded_text,
                model_severity=severity or SeverityEnum.HIGH,
                category=category,
                customer_plan=customer_plan,
                is_active_outage=is_active_outage,
                is_vip=is_vip,
            )
            return EscalationDecision(
                escalation_required=True,
                target_team=primary_rule.target_team,
                rule_id=primary_rule.id,
                reason=primary_rule.policy_reason,
                severity=elevated_severity,
                policy_matched=True,
                confidence=1.0,
            )

        # 4. Prompt injection routing to Security
        if injection_detected:
            return EscalationDecision(
                escalation_required=True,
                target_team="Security",
                rule_id="RULE_SECURITY_INJECTION",
                reason="Adversarial prompt injection attempt detected; routed to Security operations.",
                severity=SeverityEnum.HIGH,
                policy_matched=True,
                confidence=1.0,
            )

        # 5. Model judgment evaluation (grey area cases)
        effective_severity = (
            severity
            if isinstance(severity, SeverityEnum)
            else (
                SeverityEnum(str(severity).lower()) if severity else SeverityEnum.MEDIUM
            )
        )

        if _mock_model_escalation is not None:
            model_escalate = _mock_model_escalation
            model_confidence = (
                _mock_model_confidence if _mock_model_confidence is not None else 0.95
            )
            model_team = _mock_model_team or "Support"
            model_reason = (
                "Model judgement escalation accepted with high confidence."
                if model_escalate
                else "No policy escalation rule triggered and model indicated no escalation required."
            )
        else:
            prompt_lines = [
                f"Category: {category.value if isinstance(category, CategoryEnum) else (category or 'other')}",
                f"Severity: {effective_severity.value}",
                f"Customer Plan: {customer_plan or 'standard'}",
                f"Ticket Body:\n{wrap_untrusted(bounded_text)}",
            ]
            llm_response = await call_structured(
                schema=EscalationDecision,
                prompt="\n\n".join(prompt_lines),
                system_prompt=self.system_prompt,
            )
            model_decision: EscalationDecision = llm_response.data
            model_escalate = model_decision.escalation_required
            model_confidence = model_decision.confidence
            model_team = model_decision.target_team
            model_reason = model_decision.reason

        # 6. Reconcile model decision with deterministic boundary rules (AC-045)
        raw_decision = evaluate_escalation_decision(
            model_escalate=model_escalate,
            model_confidence=model_confidence,
            model_team=model_team,
            severity=effective_severity,
            matched_rules=[],
        )

        return EscalationDecision(
            escalation_required=raw_decision.escalation_required,
            target_team=raw_decision.target_team,
            rule_id=raw_decision.rule_id,
            reason=raw_decision.reason or model_reason,
            severity=effective_severity if raw_decision.escalation_required else None,
            policy_matched=False,
            confidence=model_confidence,
        )

    async def escalate(
        self,
        ticket_id: str,
        target_team: str,
        reason: str,
        severity: str = "high",
        policy_rule: str | None = None,
        workflow_id: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Execute create_escalation tool to transition ticket status and record escalation (AC-044).

        Idempotency: if an open escalation already exists for ticket_id, returns existing record.
        """
        if session is not None and ticket_id:
            stmt = select(Escalation).where(
                Escalation.ticket_id == ticket_id,
                Escalation.status == EscalationStatusEnum.OPEN.value,
            )
            res = await session.execute(stmt)
            existing = res.scalars().first()
            if existing:
                return {
                    "id": existing.id,
                    "ticket_id": existing.ticket_id,
                    "target_team": existing.target_team,
                    "policy_reason": existing.policy_reason,
                    "severity": existing.severity,
                    "status": existing.status,
                    "policy_rule": policy_rule,
                    "created_at": (
                        existing.created_at.isoformat() if existing.created_at else None
                    ),
                }

        return await create_escalation(
            ticket_id=ticket_id,
            target_team=target_team,
            reason=reason,
            severity=severity,
            policy_rule=policy_rule,
            workflow_id=workflow_id,
            session=session,
        )

    async def run(
        self,
        text: str,
        category: str | CategoryEnum | None = None,
        severity: str | SeverityEnum | None = None,
        ticket_id: str | None = None,
        customer_context: CustomerContext | dict[str, Any] | None = None,
        workflow_id: str | None = None,
        is_active_outage: bool = False,
        is_vip: bool = False,
        plan_name: str | None = None,
        *,
        session: AsyncSession | None = None,
        execute_tool: bool = False,
        _mock_model_escalation: bool | None = None,
        _mock_model_confidence: float | None = None,
        _mock_model_team: str | None = None,
    ) -> EscalationDecision:
        """Execute escalation specialist agent node in graph (F10, AC-043, AC-044).

        Returns:
            EscalationDecision schema indicating routing outcome and designated team.
        """
        decision = await self.evaluate(
            text=text,
            category=category,
            severity=severity,
            customer_context=customer_context,
            is_active_outage=is_active_outage,
            is_vip=is_vip,
            plan_name=plan_name,
            _mock_model_escalation=_mock_model_escalation,
            _mock_model_confidence=_mock_model_confidence,
            _mock_model_team=_mock_model_team,
        )

        if (
            decision.escalation_required
            and (execute_tool or session is not None)
            and ticket_id
        ):
            sev_str = (
                decision.severity.value
                if isinstance(decision.severity, SeverityEnum)
                else (str(decision.severity) if decision.severity else "high")
            )
            await self.escalate(
                ticket_id=ticket_id,
                target_team=decision.target_team or "Support",
                reason=decision.reason,
                severity=sev_str,
                policy_rule=decision.rule_id,
                workflow_id=workflow_id,
                session=session,
            )

        return decision
