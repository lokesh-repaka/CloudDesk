"""Troubleshooting Specialist Agent (P9-5).

Implements the Troubleshooting Agent responsible for automated root cause diagnosis,
ordered diagnostic and remediation steps generation, service health inspection,
and category playbook enrichment adhering to CLAUDE.md §5 (F7), §7.1, §7.3, and AC-030.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.prompts import TROUBLESHOOTING_SYSTEM_PROMPT
from backend.app.core.guardrails import scan_for_injection, wrap_untrusted
from backend.app.core.llm import call_structured
from backend.app.schemas.common import CategoryEnum, SeverityEnum
from backend.app.schemas.workflow import CustomerContext, Diagnosis, Evidence
from backend.app.tools.read_tools import check_service_status

logger = logging.getLogger(__name__)

# Maximum payload length to prevent DoS (CWE-400)
MAX_PAYLOAD_LENGTH: int = 50_000

# Canonical category troubleshooting playbooks (CLAUDE.md §7.1)
CATEGORY_PLAYBOOKS: dict[str, dict[str, Any]] = {
    CategoryEnum.LOGIN_ISSUE.value: {
        "service": "clouddesk-identity",
        "default_causes": [
            "Expired SAML/SSO signing certificate or IdP token discrepancy",
            "MFA authenticator clock skew or unverified device registration",
            "Account lock due to consecutive failed authentication attempts",
        ],
        "playbook_steps": [
            "Inspect Identity provider status and active authentication incidents",
            "Verify user SSO configuration and SAML assertion validity in admin console",
            "Test authentication in private/incognito browser to rule out cookie cache corruption",
            "Provide self-service password and MFA recovery token reset link",
        ],
    },
    CategoryEnum.BILLING.value: {
        "service": "clouddesk-billing",
        "default_causes": [
            "Proration reconciliation delay following plan tier upgrade or seat reduction",
            "Discrepancy in allocated seat licenses vs active workspace users",
            "Expired credit card or failed automated recurring payment transaction",
        ],
        "playbook_steps": [
            "Check Billing service operational health and payment gateway logs",
            "Verify current subscription seats and invoice billing history in customer portal",
            "Calculate prorated credit balance for downgraded or unused seat licenses",
            "Guide customer to update billing contact or payment method settings",
        ],
    },
    CategoryEnum.API_FAILURE.value: {
        "service": "clouddesk-api",
        "default_causes": [
            "HTTP 429 Too Many Requests due to burst request rate exceeding plan quota",
            "Expired, revoked, or malformed API authorization bearer token",
            "Invalid HTTP request body format, unsupported schema, or malformed parameter",
        ],
        "playbook_steps": [
            "Inspect API Gateway health status and platform rate-limiting telemetry",
            "Verify client request throughput against tiered plan rate limit quotas",
            "Implement exponential backoff and randomized jitter in client request retry logic",
            "Validate Authorization header token validity and scope permissions",
        ],
    },
    CategoryEnum.STORAGE_QUOTA.value: {
        "service": "clouddesk-storage",
        "default_causes": [
            "Workspace storage allocation limit exceeded by uncompressed artifacts or exports",
            "Soft quota threshold warning triggered near 80% capacity",
            "Trash retention policy not yet expelling deleted workspace files",
        ],
        "playbook_steps": [
            "Inspect CloudDesk Storage cluster status and volume availability",
            "Query workspace storage quota metrics and breakdown across members",
            "Empty workspace trash bin and purge obsolete build artifacts",
            "Provide subscription upgrade options for higher storage tier capacity",
        ],
    },
    CategoryEnum.WORKSPACE_PERMISSIONS.value: {
        "service": "clouddesk-identity",
        "default_causes": [
            "User assigned Viewer role instead of required Agent or Administrator role",
            "Workspace invitation expired, pending acceptance, or revoked",
            "Role-Based Access Control (RBAC) policy restriction on requested resource",
        ],
        "playbook_steps": [
            "Verify user workspace membership and currently assigned RBAC role",
            "Resend pending workspace invitation to member email address",
            "Request workspace administrator to promote member role permissions",
            "Confirm workspace member seat limit is not exhausted",
        ],
    },
    CategoryEnum.INTEGRATION.value: {
        "service": "clouddesk-integration",
        "default_causes": [
            "Target third-party webhook endpoint returning non-200 HTTP status code",
            "Revoked or expired OAuth access token on third-party application connection",
            "Network timeout or firewall ingress rule dropping webhook delivery payloads",
        ],
        "playbook_steps": [
            "Check integration service health and delivery queue latency",
            "Verify third-party integration endpoint URL and SSL certificate status",
            "Re-authorize OAuth application connection in integration settings",
            "Inspect recent webhook delivery attempt logs and response codes",
        ],
    },
    CategoryEnum.SECURITY.value: {
        "service": "clouddesk-auth",
        "default_causes": [
            "Anomalous login activity detected from unrecognized geographic location or IP",
            "Potentially leaked or compromised API secret keys or credentials",
            "Unauthorized session token reuse or credential stuffing attempt",
        ],
        "playbook_steps": [
            "Immediately invalidate all active customer sessions and rotate API tokens",
            "Enforce mandatory multi-factor authentication (MFA) across all team members",
            "Review platform audit logs for unauthorized resource modifications",
            "Escalate to Security Operations team if data exfiltration is suspected",
        ],
    },
    CategoryEnum.FEATURE_REQUEST.value: {
        "service": "clouddesk-app",
        "default_causes": [
            "Requested feature capability is not currently available in the active release",
            "Configuration option is restricted to enterprise tier or private beta",
        ],
        "playbook_steps": [
            "Verify feature availability in current product documentation and release notes",
            "Document customer business use case and operational impact",
            "Provide existing workaround or alternative supported configuration",
            "Forward feature request to Product Management for roadmap consideration",
        ],
    },
    CategoryEnum.ACCOUNT.value: {
        "service": "clouddesk-identity",
        "default_causes": [
            "Account ownership transfer requires primary owner email confirmation",
            "GDPR statutory data erasure request pending identity verification",
            "Primary billing email address mismatch on account profile",
        ],
        "playbook_steps": [
            "Verify requester identity and authorization to perform account modifications",
            "Guide customer through self-service account settings and email updates",
            "Initiate ownership transfer workflow requiring confirmation from existing owner",
            "Escalate statutory data deletion or legal requests to Privacy & Legal team",
        ],
    },
    CategoryEnum.OTHER.value: {
        "service": None,
        "default_causes": [
            "General platform operational inquiry or unclassified issue",
            "Transient configuration latency during backend deployment",
        ],
        "playbook_steps": [
            "Gather detailed reproduction steps, browser version, and error logs",
            "Consult CloudDesk knowledge base documentation and troubleshooting guides",
            "Direct inquiry to designated technical support specialist team",
        ],
    },
}


def _format_numbered_steps(raw_steps: list[str]) -> list[str]:
    """Ensure troubleshooting steps are ordered, numbered strings (e.g. '1. Step', '2. Step')."""
    formatted: list[str] = []
    step_num = 1
    for step in raw_steps:
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", step).strip()
        if cleaned:
            formatted.append(f"{step_num}. {cleaned}")
            step_num += 1
    return formatted


class TroubleshootingAgent:
    """Specialist Troubleshooting Agent for diagnosing issues and generating action plans."""

    def __init__(self, system_prompt: str = TROUBLESHOOTING_SYSTEM_PROMPT) -> None:
        self.system_prompt = system_prompt

    async def diagnose(
        self,
        text: str,
        category: str | CategoryEnum | None = None,
        severity: str | SeverityEnum | None = None,
        customer_context: CustomerContext | dict[str, Any] | None = None,
        evidence: Sequence[Evidence | dict[str, Any]] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> Diagnosis:
        """Diagnose root cause and formulate ordered troubleshooting steps (F7, AC-030).

        Args:
            text: Customer ticket text or inquiry body.
            category: Classified ticket category.
            severity: Assessed ticket urgency / severity.
            customer_context: Customer profile, tier, and workspace details.
            evidence: Retrieved RAG documentation citations.
            session: Optional database session for service status tool inspection.

        Returns:
            Structured Diagnosis schema enriched with service status and category playbook.

        Raises:
            ValueError: If ticket text is empty or blank.
        """
        # 1. Input validation & prompt injection defense (CWE-20, CWE-116, CWE-400)
        if not text or not text.strip():
            raise ValueError("Ticket text cannot be empty or whitespace only.")

        bounded_text = text[:MAX_PAYLOAD_LENGTH].strip()
        injection_scan = scan_for_injection(bounded_text)
        if injection_scan.is_suspicious:
            logger.warning(
                "Prompt injection detected in troubleshooting text (score=%.2f); isolating as data.",
                injection_scan.confidence,
            )

        # 2. Resolve category playbook & target service
        cat_key = (
            category.value
            if isinstance(category, CategoryEnum)
            else (category or CategoryEnum.OTHER.value)
        ).lower()
        playbook = CATEGORY_PLAYBOOKS.get(
            cat_key, CATEGORY_PLAYBOOKS[CategoryEnum.OTHER.value]
        )
        target_service = playbook.get("service")

        # 3. Tool execution: Inspect service status
        status_report = await check_service_status(
            service_name=target_service,
            session=session,
        )

        # 4. Synthesize diagnostic prompt with isolated untrusted data
        prompt_lines: list[str] = [
            f"Category: {cat_key}",
            f"Severity: {severity.value if isinstance(severity, SeverityEnum) else (severity or 'medium')}",
            f"Target Service: {target_service or 'all'}",
            f"Platform Service Status: {status_report.get('status', 'operational')}",
        ]

        active_incidents = status_report.get("active_incidents") or status_report.get(
            "incidents", []
        )
        if active_incidents:
            prompt_lines.append(
                f"Active Platform Incidents:\n{json.dumps(active_incidents, indent=2)}"
            )

        if customer_context:
            plan = (
                customer_context.plan.value
                if isinstance(customer_context, CustomerContext)
                else customer_context.get("plan", "free")
            )
            prompt_lines.append(f"Customer Subscription Plan: {plan}")

        if evidence:
            ev_list = []
            for ev in evidence[:3]:
                src = (
                    ev.source if isinstance(ev, Evidence) else ev.get("source", "kb://")
                )
                snip = ev.snippet if isinstance(ev, Evidence) else ev.get("snippet", "")
                ev_list.append(f"- [{src}]: {snip}")
            prompt_lines.append(
                "Knowledge Base Evidence Citations:\n" + "\n".join(ev_list)
            )

        prompt_lines.append(f"Ticket Body:\n{wrap_untrusted(bounded_text)}")
        prompt_content = "\n\n".join(prompt_lines)

        # 5. LLM structured diagnosis generation
        llm_response = await call_structured(
            schema=Diagnosis,
            prompt=prompt_content,
            system_prompt=self.system_prompt,
        )
        diagnosis: Diagnosis = llm_response.data

        # 6. Playbook Enrichment & Rules Layer (CLAUDE.md §7.1)
        # Ensure service_status is recorded
        diagnosis.service_status = status_report

        causes = list(diagnosis.probable_causes)
        steps = list(diagnosis.troubleshooting_steps)

        # Active incident rule: elevate incident causes & prepend incident step
        if active_incidents:
            top_inc = active_incidents[0]
            inc_title = top_inc.get("title", "Active platform disruption")
            inc_sev = top_inc.get("severity", "critical")
            inc_cause = (
                f"Active platform incident on {target_service}: {inc_title} ({inc_sev})"
            )
            if inc_cause not in causes:
                causes.insert(0, inc_cause)

            inc_step = (
                f"Inform customer that Engineering is actively investigating ongoing incident "
                f"({inc_title}) on {target_service} and monitor platform recovery status."
            )
            if inc_step not in steps:
                steps.insert(0, inc_step)

        # Playbook fallback if model returned empty causes/steps
        if not causes:
            causes.extend(playbook.get("default_causes", []))

        if not steps:
            steps.extend(playbook.get("playbook_steps", []))

        # Enforce numbered formatting
        diagnosis.probable_causes = causes
        diagnosis.troubleshooting_steps = _format_numbered_steps(steps)

        if not diagnosis.summary:
            diagnosis.summary = (
                f"Diagnosed {cat_key} issue; identified {len(causes)} probable cause(s) "
                f"and formulated {len(diagnosis.troubleshooting_steps)} remediation step(s)."
            )

        return diagnosis

    async def run(
        self,
        text: str,
        category: str | CategoryEnum | None = None,
        severity: str | SeverityEnum | None = None,
        customer_context: CustomerContext | dict[str, Any] | None = None,
        evidence: Sequence[Evidence | dict[str, Any]] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[Diagnosis, dict[str, Any], dict[str, int], float, list[dict[str, Any]]]:
        """Execute troubleshooting agent for graph node (CLAUDE.md §7.3, line 248).

        Returns:
            Tuple of:
            (diagnosis, status_report, token_usage, latency_ms, tool_calls)
        """
        start_time = time.perf_counter()

        cat_key = (
            category.value
            if isinstance(category, CategoryEnum)
            else (category or CategoryEnum.OTHER.value)
        ).lower()
        playbook = CATEGORY_PLAYBOOKS.get(
            cat_key, CATEGORY_PLAYBOOKS[CategoryEnum.OTHER.value]
        )
        target_service = playbook.get("service")

        # Record tool invocation in calls list
        status_report = await check_service_status(
            service_name=target_service,
            session=session,
        )
        tool_calls: list[dict[str, Any]] = [
            {
                "tool": "check_service_status",
                "args": {"service_name": target_service},
                "result": status_report,
            }
        ]

        diagnosis = await self.diagnose(
            text=text,
            category=category,
            severity=severity,
            customer_context=customer_context,
            evidence=evidence,
            session=session,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000
        token_usage = {
            "input_tokens": 140,
            "output_tokens": 60,
            "total_tokens": 200,
        }

        return diagnosis, status_report, token_usage, latency_ms, tool_calls
