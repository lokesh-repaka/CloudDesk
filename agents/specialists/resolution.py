"""Resolution Specialist Agent (P9-6).

Implements the Resolution Agent responsible for drafting grounded customer replies,
formulating internal diagnostic notes and executive summaries, deterministically
planning remediation actions, and enforcing output guardrails adhering to:
CLAUDE.md §3 (F8), §7.1, §7.3, §7.4, US-009 (AC-032, AC-033, AC-034),
US-010 (AC-035, AC-038), and US-020 (AC-066, AC-067).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Any

from agents.prompts import RESOLUTION_SYSTEM_PROMPT
from backend.app.core.guardrails import (
    scan_for_injection,
    validate_customer_output,
    wrap_untrusted,
)
from backend.app.core.llm import call_structured
from backend.app.schemas.common import CategoryEnum, SeverityEnum
from backend.app.schemas.workflow import (
    CustomerContext,
    Diagnosis,
    Evidence,
    ResolutionActionPlan,
    ResolutionPlan,
)
from backend.app.tools.policy import ToolPolicy, get_tool_policy

logger = logging.getLogger(__name__)

# Bounded inputs against resource exhaustion (CWE-400)
MAX_PAYLOAD_LENGTH: int = 50_000
MAX_ACTIONS_LIMIT: int = 5

# Predefined allowable resolution tools (AC-033, CLAUDE.md §7.1, §7.4)
ALLOWED_RESOLUTION_TOOLS: frozenset[str] = frozenset(
    {
        "update_ticket",
        "create_refund_request",
        "reset_demo_setting",
    }
)


class ResolutionAgent:
    """Specialist Resolution Agent for planning remediation actions and drafting customer replies."""

    def __init__(
        self,
        system_prompt: str = RESOLUTION_SYSTEM_PROMPT,
        tool_policy: ToolPolicy | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.tool_policy = tool_policy or get_tool_policy()

    def sanitize_actions(
        self,
        actions: Sequence[ResolutionActionPlan | dict[str, Any]],
    ) -> list[ResolutionActionPlan]:
        """Filter out model-invented actions not in the predefined allowed set (AC-033)."""
        sanitized: list[ResolutionActionPlan] = []
        for action in actions:
            if isinstance(action, ResolutionActionPlan):
                tool_name = action.tool_name
                arguments = action.arguments
                reason = action.reason
            elif isinstance(action, dict):
                tool_name = action.get("tool_name") or action.get("tool", "")
                arguments = action.get("arguments", {})
                reason = action.get("reason", "")
            else:
                continue

            if tool_name not in ALLOWED_RESOLUTION_TOOLS:
                logger.warning(
                    "Rejected unauthorized/model-invented tool action: %s (CWE-732)",
                    tool_name,
                )
                continue

            # Verify approval requirement through canonical ToolPolicy
            needs_approval = self.tool_policy.requires_approval(tool_name, arguments)

            sanitized.append(
                ResolutionActionPlan(
                    tool_name=tool_name,
                    arguments=arguments,
                    requires_approval=needs_approval,
                    reason=reason
                    or f"Automated resolution plan action for {tool_name}",
                )
            )

            if len(sanitized) >= MAX_ACTIONS_LIMIT:
                break

        return sanitized

    def plan_actions(
        self,
        category: str | CategoryEnum | None = None,
        text: str = "",
        diagnosis: Diagnosis | None = None,
        customer_context: CustomerContext | dict[str, Any] | None = None,
        ticket_id: str = "",
    ) -> list[ResolutionActionPlan]:
        """Deterministically plan allowed tool actions based on category, symptoms, and context (AC-033)."""
        actions: list[ResolutionActionPlan] = []
        cat_str = (
            category.value
            if isinstance(category, CategoryEnum)
            else (category or "").lower()
        )
        text_lower = text.lower()

        # Extract customer identifier
        customer_id = ""
        if isinstance(customer_context, CustomerContext):
            customer_id = customer_context.customer_id
        elif isinstance(customer_context, dict):
            customer_id = customer_context.get("customer_id", "")

        if not customer_id:
            cust_match = re.search(r"\bcust-\d{3}-[a-z0-9_-]+\b", text, re.IGNORECASE)
            if cust_match:
                customer_id = cust_match.group(0)

        # 1. Billing refund action planning (CD-1002, AC-035, AC-038)
        if (
            cat_str == CategoryEnum.BILLING.value
            or "refund" in text_lower
            or "invoice" in text_lower
        ):
            amount: float | None = None
            dollar_after_refund = re.search(
                r"refund[^\$]*\$\s*(\d+(?:\.\d{1,2})?)", text_lower
            )
            if dollar_after_refund:
                amount = float(dollar_after_refund.group(1))
            else:
                dollar_matches = re.findall(r"\$\s*(\d+(?:\.\d{1,2})?)", text_lower)
                if dollar_matches:
                    amount = float(dollar_matches[-1])
                else:
                    num_match = re.search(
                        r"(?:refund|credit)\s+(?:of\s+|for\s+)?\$?\s*(\d+(?:\.\d{1,2})?)",
                        text_lower,
                    )
                    if num_match:
                        amount = float(num_match.group(1))

            if amount is not None and amount > 0:
                actions.append(
                    ResolutionActionPlan(
                        tool_name="create_refund_request",
                        arguments={
                            "ticket_id": ticket_id,
                            "customer_id": customer_id or "cust-unknown",
                            "amount": amount,
                            "reason": f"Billing refund requested: ${amount:.2f} for ticket {ticket_id}",
                        },
                        requires_approval=True,  # Gated per AC-035, AC-038
                        reason="Billing refund issuance requires human approval gate.",
                    )
                )

        # 2. Workspace demo setting reset planning (CD-1007, AC-035)
        if (
            cat_str == CategoryEnum.WORKSPACE_PERMISSIONS.value
            or "reset" in text_lower
            or "sharing" in text_lower
        ) and (
            "reset" in text_lower
            or "allow_external_sharing" in text_lower
            or "share folder" in text_lower
        ):
            setting_name = "allow_external_sharing"
            quoted_match = re.search(r"['\"]([a-zA-Z0-9_\-]+)['\"]", text)
            if quoted_match:
                setting_name = quoted_match.group(1)

                workspace_id = "ws-main"
                if (
                    isinstance(customer_context, CustomerContext)
                    and customer_context.workspace_summary
                ):
                    ws_summary = customer_context.workspace_summary
                    if isinstance(ws_summary, dict):
                        workspace_id = (
                            ws_summary.get("workspace_name")
                            or ws_summary.get("name")
                            or ws_summary.get("id")
                            or "ws-main"
                        )
                    elif isinstance(ws_summary, str):
                        ws_match = re.search(
                            r"workspace\s+([a-zA-Z0-9_\-]+)", ws_summary, re.IGNORECASE
                        )
                        if ws_match:
                            workspace_id = ws_match.group(1)

                actions.append(
                    ResolutionActionPlan(
                        tool_name="reset_demo_setting",
                        arguments={
                            "ticket_id": ticket_id,
                            "workspace_id": workspace_id,
                            "setting_name": setting_name,
                            "reset_value": True,
                        },
                        requires_approval=True,  # Consequential action per AC-035
                        reason="Workspace demo configuration reset requires human approval gate.",
                    )
                )

        # 3. Standard safe write action: update_ticket
        status = (
            "waiting_on_approval"
            if any(a.requires_approval for a in actions)
            else "resolved"
        )
        actions.append(
            ResolutionActionPlan(
                tool_name="update_ticket",
                arguments={
                    "ticket_id": ticket_id,
                    "status": status,
                    "resolution_summary": (
                        diagnosis.summary
                        if diagnosis and diagnosis.summary
                        else f"Automated resolution plan generated for {cat_str or 'ticket'}."
                    ),
                },
                requires_approval=False,
                reason="Update ticket status and persist resolution summary.",
            )
        )

        return self.sanitize_actions(actions)

    def _ground_response(
        self,
        draft: str,
        diagnosis: Diagnosis | None = None,
        evidence: Sequence[Evidence | dict[str, Any]] | None = None,
    ) -> str:
        """Ground customer draft reply in diagnostic steps and retrieved evidence (AC-034)."""
        if not draft:
            draft = "Thank you for contacting CloudDesk support."

        # Check if draft already contains diagnosis steps
        has_steps = False
        if diagnosis and diagnosis.troubleshooting_steps:
            for step in diagnosis.troubleshooting_steps:
                core_step = re.sub(r"^\d+[\.\)]\s*", "", step).strip()
                if core_step.lower()[:30] in draft.lower():
                    has_steps = True
                    break

        grounded_parts: list[str] = [draft.strip()]

        # If missing actionable steps, embed them
        if not has_steps and diagnosis and diagnosis.troubleshooting_steps:
            steps_block = "\n".join(diagnosis.troubleshooting_steps)
            grounded_parts.append(
                f"\n\nRecommended troubleshooting steps:\n{steps_block}"
            )

        # Ground with knowledge base evidence citations if not mentioned
        if evidence:
            unreferenced_sources: list[str] = []
            for ev in evidence[:2]:
                src = ev.source if isinstance(ev, Evidence) else ev.get("source", "")
                if src and src.lower() not in draft.lower():
                    unreferenced_sources.append(src)

            if unreferenced_sources:
                doc_lines = "\n".join(
                    f"- Reference article: {src}" for src in unreferenced_sources
                )
                grounded_parts.append(f"\n\n{doc_lines}")

        return "".join(grounded_parts).strip()

    async def plan(
        self,
        text: str,
        category: str | CategoryEnum | None = None,
        severity: str | SeverityEnum | None = None,
        customer_context: CustomerContext | dict[str, Any] | None = None,
        evidence: Sequence[Evidence | dict[str, Any]] | None = None,
        diagnosis: Diagnosis | None = None,
        ticket_id: str = "",
        *,
        _mock_customer_reply: str | None = None,
    ) -> ResolutionPlan:
        """Generate structured resolution plan with deterministic actions and output guardrails."""
        # 1. Input validation (CWE-20)
        if not text or not text.strip():
            raise ValueError("Ticket text cannot be empty or whitespace only.")

        bounded_text = text[:MAX_PAYLOAD_LENGTH].strip()

        # 2. Prompt injection defense (CWE-116)
        injection_scan = scan_for_injection(bounded_text)
        injection_detected = injection_scan.is_suspicious
        if injection_detected:
            logger.warning(
                "Prompt injection detected in resolution planning text (score=%.2f); isolating.",
                injection_scan.confidence,
            )

        cat_str = (
            category.value
            if isinstance(category, CategoryEnum)
            else (category or CategoryEnum.OTHER.value)
        ).lower()
        sev_str = (
            severity.value
            if isinstance(severity, SeverityEnum)
            else (severity or SeverityEnum.MEDIUM.value)
        ).lower()

        # Extract customer info
        customer_id = ""
        customer_email = ""
        if isinstance(customer_context, CustomerContext):
            customer_id = customer_context.customer_id
            customer_email = customer_context.email
        elif isinstance(customer_context, dict):
            customer_id = customer_context.get("customer_id", "")
            customer_email = customer_context.get("email", "")

        # 3. Formulate structured LLM prompt
        prompt_lines: list[str] = [
            f"Ticket Category: {cat_str}",
            f"Assessed Severity: {sev_str}",
            f"Ticket ID: {ticket_id or 'unknown'}",
        ]

        if customer_context:
            plan_name = (
                customer_context.plan.value
                if isinstance(customer_context, CustomerContext)
                else customer_context.get("plan", "free")
            )
            prompt_lines.append(f"Customer Plan: {plan_name}")
            if customer_id:
                prompt_lines.append(f"Customer ID: {customer_id}")

        if diagnosis:
            prompt_lines.append(f"Diagnosis Summary: {diagnosis.summary}")
            if diagnosis.probable_causes:
                prompt_lines.append(
                    "Probable Causes:\n"
                    + "\n".join(f"- {c}" for c in diagnosis.probable_causes)
                )
            if diagnosis.troubleshooting_steps:
                prompt_lines.append(
                    "Troubleshooting Steps:\n"
                    + "\n".join(diagnosis.troubleshooting_steps)
                )

        if evidence:
            ev_list = []
            for ev in evidence[:3]:
                src = (
                    ev.source if isinstance(ev, Evidence) else ev.get("source", "kb://")
                )
                snip = ev.snippet if isinstance(ev, Evidence) else ev.get("snippet", "")
                ev_list.append(f"- [{src}]: {snip}")
            prompt_lines.append("Retrieved Evidence Citations:\n" + "\n".join(ev_list))

        prompt_lines.append(f"Ticket Body:\n{wrap_untrusted(bounded_text)}")
        prompt_content = "\n\n".join(prompt_lines)

        # 4. LLM synthesis
        llm_response = await call_structured(
            schema=ResolutionPlan,
            prompt=prompt_content,
            system_prompt=self.system_prompt,
        )
        base_plan: ResolutionPlan = llm_response.data

        # 5. Deterministic action planning (CLAUDE.md §7.4, AC-033)
        deterministic_actions = self.plan_actions(
            category=category,
            text=bounded_text,
            diagnosis=diagnosis,
            customer_context=customer_context,
            ticket_id=ticket_id,
        )

        # Merge / sanitize actions
        combined_actions = deterministic_actions
        if base_plan.actions:
            combined_actions.extend(self.sanitize_actions(base_plan.actions))
        final_actions = self.sanitize_actions(combined_actions)

        # 6. Customer reply grounding (AC-034)
        raw_draft = _mock_customer_reply or base_plan.customer_reply
        grounded_draft = self._ground_response(
            draft=raw_draft,
            diagnosis=diagnosis,
            evidence=evidence,
        )

        # 7. Customer output safety guardrail validation (AC-066, AC-067, US-020)
        validation_result = validate_customer_output(
            draft=grounded_draft,
            current_customer_id=customer_id or None,
            current_customer_email=customer_email or None,
        )

        output_validation_failed = not validation_result.is_valid
        internal_notes = base_plan.internal_notes or ""

        if output_validation_failed:
            logger.warning(
                "Customer output safety guardrail triggered: %s. Quarantining draft (AC-066).",
                validation_result.failure_reason,
            )
            # Block unsafe draft and quarantine without echoing leaked sensitive values
            customer_reply = (
                "[Draft blocked by security guardrails. Output contained prohibited content "
                "(internal address, credential, or foreign customer data). Requires manual agent drafting.]"
            )
            alert_note = (
                f"[GUARDRAIL ALERT]: Output validation failed: {validation_result.failure_reason}. "
                f"Violations: {', '.join(validation_result.violations)}."
            )
            internal_notes = f"{internal_notes}\n{alert_note}".strip()
        else:
            customer_reply = grounded_draft

        # 8. Human approval requirement computation (AC-035, AC-038)
        requires_approval = (
            any(a.requires_approval for a in final_actions)
            or output_validation_failed
            or injection_detected
            or (sev_str == SeverityEnum.CRITICAL.value)
        )

        # Enforce internal notes technical detail with context and diagnosis
        context_notes: list[str] = []
        if internal_notes:
            context_notes.append(internal_notes)
        if customer_context:
            name = (
                customer_context.name
                if isinstance(customer_context, CustomerContext)
                else customer_context.get("name", "Customer")
            )
            plan_val = (
                customer_context.plan.value
                if isinstance(customer_context, CustomerContext)
                else customer_context.get("plan", "free")
            )
            context_notes.append(f"Customer: {name} (Tier: {plan_val}).")
            if (
                isinstance(customer_context, CustomerContext)
                and customer_context.workspace_summary
            ):
                ws_name = customer_context.workspace_summary.get(
                    "workspace_name"
                ) or customer_context.workspace_summary.get("name")
                if ws_name:
                    context_notes.append(f"Workspace: {ws_name}.")
        if diagnosis and diagnosis.summary:
            context_notes.append(f"Diagnosis: {diagnosis.summary}")
        internal_notes = " ".join(context_notes)

        summary = base_plan.summary
        if not summary:
            summary = (
                f"Formulated resolution plan for {cat_str} ticket; "
                f"{len(final_actions)} action(s) scheduled. Approval required: {requires_approval}."
            )

        return ResolutionPlan(
            summary=summary,
            customer_reply=customer_reply,
            internal_notes=internal_notes,
            actions=final_actions,
            requires_approval=requires_approval,
            confidence=0.95 if not output_validation_failed else 0.5,
        )

    async def run(
        self,
        text: str,
        category: str | CategoryEnum | None = None,
        severity: str | SeverityEnum | None = None,
        customer_context: CustomerContext | dict[str, Any] | None = None,
        evidence: Sequence[Evidence | dict[str, Any]] | None = None,
        diagnosis: Diagnosis | None = None,
        ticket_id: str = "",
        *,
        _mock_customer_reply: str | None = None,
    ) -> ResolutionPlan:
        """Execute resolution planning agent workflow node (F8, AC-032).

        Returns:
            ResolutionPlan containing summary, customer reply draft, internal notes, and actions.
        """
        return await self.plan(
            text=text,
            category=category,
            severity=severity,
            customer_context=customer_context,
            evidence=evidence,
            diagnosis=diagnosis,
            ticket_id=ticket_id,
            _mock_customer_reply=_mock_customer_reply,
        )
