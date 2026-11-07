"""Deterministic Policy, Escalation, and Severity Rules Engine.

Implements architectural requirement ADR-03 and CLAUDE.md section 7.2:
- Deterministic rule layer precedes and overrides LLM judgment (policy rules always win).
- Policy cases: dispute, deletion, security, data loss, legal, enterprise outage.
- Rules can raise severity, never lower it.
- Feature requests default to low severity by policy.
- Rejects vague model escalations when severity is high but confidence is low (AC-045).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from backend.app.core.guardrails import (
    SECURITY_PREAMBLE,
    InjectionScanResult,
    scan_for_injection,
    wrap_untrusted,
)
from backend.app.schemas.common import CategoryEnum, SeverityEnum


@dataclass(frozen=True)
class EscalationRule:
    """Immutable deterministic escalation policy rule."""

    id: str
    name: str
    target_team: str  # e.g., 'Security', 'Engineering', 'Legal', 'Billing'
    policy_reason: str
    keywords: tuple[str, ...] = field(default_factory=tuple)
    categories: tuple[CategoryEnum, ...] = field(default_factory=tuple)


class EscalationDecision(BaseModel):
    """Enveloped escalation outcome."""

    escalation_required: bool = Field(
        ..., description="Whether ticket must be escalated"
    )
    target_team: str | None = Field(
        default=None, description="Designated specialized team"
    )
    rule_id: str | None = Field(
        default=None, description="Triggered deterministic policy rule ID"
    )
    reason: str | None = Field(
        default=None, description="Explanation or policy justification"
    )


# ---------------------------------------------------------------------------
# Canonical Escalation Policy Rules
# ---------------------------------------------------------------------------

ESCALATION_RULES: list[EscalationRule] = [
    EscalationRule(
        id="RULE_SECURITY",
        name="Security Incident & Breach",
        target_team="Security",
        policy_reason="Compromised credentials, unauthorized access, ransomware, or security vulnerabilities require immediate Security investigation.",
        keywords=(
            "unauthorized access",
            "credentials leaked",
            "credential leak",
            "compromised",
            "security breach",
            "ransomware",
            "hacked",
            "security incident",
            "account takeover",
            "malicious access",
            "api keys leaked",
        ),
        categories=(CategoryEnum.SECURITY,),
    ),
    EscalationRule(
        id="RULE_DATA_LOSS",
        name="Catastrophic Data Loss & Corruption",
        target_team="Engineering",
        policy_reason="Permanent file deletion, unrecoverable sync loss, corrupted workspaces, or wiped databases require Engineering recovery.",
        keywords=(
            "data loss",
            "permanently lost",
            "data corrupted",
            "records deleted",
            "database wiped",
            "database is wiped",
            "cannot recover files",
            "unrecoverable data",
            "permanent deletion of files",
        ),
        categories=(),
    ),
    EscalationRule(
        id="RULE_GDPR_DELETION",
        name="GDPR Erasure & Statutory Privacy",
        target_team="Legal",
        policy_reason="Statutory privacy requests (GDPR Article 17 right to be forgotten, permanent erasure) must be routed to Legal counsel.",
        keywords=(
            "gdpr",
            "right to be forgotten",
            "erasure of my personal data",
            "permanent erasure",
            "delete my account",
            "privacy compliance",
            "statutory erasure",
            "data privacy request",
        ),
        categories=(),
    ),
    EscalationRule(
        id="RULE_PAYMENT_DISPUTE",
        name="Payment Dispute & Chargeback",
        target_team="Billing",
        policy_reason="Formal bank disputes, payment chargebacks, and legal contestations must be handled by Billing operations.",
        keywords=(
            "chargeback",
            "credit card chargeback",
            "dispute with my bank",
            "disputing charge",
            "disputed charge",
            "fraudulent charge",
            "disputed invoice",
            "bank dispute",
        ),
        categories=(),
    ),
    EscalationRule(
        id="RULE_ENTERPRISE_OUTAGE",
        name="Enterprise Customer Outage",
        target_team="Engineering",
        policy_reason="Enterprise plan customers experiencing platform outage or systemic downtime require priority Engineering escalation.",
        keywords=(
            "enterprise outage",
            "critical system downtime",
            "platform outage",
        ),
        categories=(),
    ),
    EscalationRule(
        id="RULE_LEGAL_THREAT",
        name="Legal Action & Regulatory Notice",
        target_team="Legal",
        policy_reason="Subpoenas, litigation notices, attorney correspondence, or regulatory inquiries must be escalated directly to Legal.",
        keywords=(
            "lawsuit",
            "litigation",
            "subpoena",
            "attorney",
            "legal counsel",
            "regulatory notice",
            "legal action",
        ),
        categories=(),
    ),
]


# ---------------------------------------------------------------------------
# Severity Level Order Mapping
# ---------------------------------------------------------------------------

_SEVERITY_LEVELS: dict[SeverityEnum, int] = {
    SeverityEnum.LOW: 1,
    SeverityEnum.MEDIUM: 2,
    SeverityEnum.HIGH: 3,
    SeverityEnum.CRITICAL: 4,
}

_LEVEL_TO_SEVERITY: dict[int, SeverityEnum] = {
    1: SeverityEnum.LOW,
    2: SeverityEnum.MEDIUM,
    3: SeverityEnum.HIGH,
    4: SeverityEnum.CRITICAL,
}


def matching_escalation_rules(
    text: str,
    plan_name: str | None = None,
    category: CategoryEnum | str | None = None,
    customer_plan: str | None = None,
    is_active_outage: bool = False,
) -> list[EscalationRule]:
    """Evaluate text, category, and context against deterministic escalation rules."""
    text_clean = text[:50000].lower() if text else ""
    category_enum = None
    if category:
        try:
            category_enum = CategoryEnum(category)
        except ValueError:
            category_enum = None

    matched: list[EscalationRule] = []

    for rule in ESCALATION_RULES:
        # 1. Enterprise outage special condition
        if rule.id == "RULE_ENTERPRISE_OUTAGE":
            if is_active_outage and (customer_plan or "").lower() == "enterprise":
                matched.append(rule)
                continue
            if "enterprise outage" in text_clean:
                matched.append(rule)
                continue

        # 2. Category matching
        if category_enum and category_enum in rule.categories:
            matched.append(rule)
            continue

        # 3. Keyword matching
        if any(kw in text_clean for kw in rule.keywords):
            matched.append(rule)
            continue

        # 4. Plan name matching
        if plan_name and (
            rule.id.lower() in plan_name.lower()
            or rule.target_team.lower() in plan_name.lower()
        ):
            matched.append(rule)
            continue

    return matched


def rule_severity(
    text: str,
    model_severity: SeverityEnum | str = SeverityEnum.LOW,
    category: CategoryEnum | str | None = None,
    customer_plan: str | None = None,
    is_active_outage: bool = False,
) -> SeverityEnum:
    """Enforce deterministic policy severity floors.

    Rules can only RAISE the severity, never lower it (CLAUDE.md 7.2).
    """
    text_clean = text[:50000].lower() if text else ""

    # Parse incoming model severity
    if isinstance(model_severity, str):
        try:
            current_enum = SeverityEnum(model_severity.lower())
        except ValueError:
            current_enum = SeverityEnum.LOW
    else:
        current_enum = model_severity

    current_level = _SEVERITY_LEVELS.get(current_enum, 1)
    floor_level = 1

    # Check category enum
    cat_enum = None
    if category:
        try:
            cat_enum = CategoryEnum(
                category if isinstance(category, str) else category.value
            )
        except ValueError:
            cat_enum = None

    # Enterprise Outage floor: CRITICAL
    if is_active_outage and (customer_plan or "").lower() == "enterprise":
        floor_level = max(floor_level, _SEVERITY_LEVELS[SeverityEnum.CRITICAL])

    # Security Incident floor: CRITICAL for ransomware/wipe, HIGH for other breach
    if (
        cat_enum == CategoryEnum.SECURITY
        or "ransomware" in text_clean
        or "compromised" in text_clean
    ):
        if "ransomware" in text_clean or "database wiped" in text_clean:
            floor_level = max(floor_level, _SEVERITY_LEVELS[SeverityEnum.CRITICAL])
        else:
            floor_level = max(floor_level, _SEVERITY_LEVELS[SeverityEnum.HIGH])

    # Catastrophic data loss floor: HIGH or CRITICAL
    if (
        "data loss" in text_clean
        or "permanently lost" in text_clean
        or "database is wiped" in text_clean
    ):
        floor_level = max(floor_level, _SEVERITY_LEVELS[SeverityEnum.HIGH])

    # Feature requests: policy default is LOW (level 1)
    if cat_enum == CategoryEnum.FEATURE_REQUEST:
        floor_level = max(floor_level, 1)

    effective_level = max(current_level, floor_level)
    return _LEVEL_TO_SEVERITY.get(effective_level, SeverityEnum.LOW)


def rule_category(text: str) -> CategoryEnum | None:
    """Fast deterministic heuristic classification across canonical domain categories."""
    if not text:
        return None

    text_clean = text[:50000].lower()

    # Regular expressions / word boundaries for unambiguous categories
    patterns: list[tuple[CategoryEnum, list[str]]] = [
        (
            CategoryEnum.LOGIN_ISSUE,
            [
                r"\bsso\b",
                r"\bsaml\b",
                r"\bmfa\b",
                r"\b2fa\b",
                r"login failure",
                r"reset password",
                r"locked out",
            ],
        ),
        (
            CategoryEnum.SECURITY,
            [
                r"\bransomware\b",
                r"\bbreach\b",
                r"unauthorized access",
                r"compromised account",
                r"leaked keys",
                r"security incident",
                r"\bcompromised\b",
            ],
        ),
        (
            CategoryEnum.INTEGRATION,
            [
                r"\bslack integration\b",
                r"\bslack\b",
                r"\bzapier\b",
                r"\bintegration\b",
                r"third-party app",
            ],
        ),
        (
            CategoryEnum.API_FAILURE,
            [
                r"\brate limit\b",
                r"\b429\b",
                r"\brest api\b",
                r"\bapi endpoint\b",
                r"\b500 error\b",
            ],
        ),
        (
            CategoryEnum.STORAGE_QUOTA,
            [
                r"\bstorage quota\b",
                r"\bstorage limit\b",
                r"\bdisk full\b",
                r"upload limit exceeded",
                r"out of storage",
            ],
        ),
        (
            CategoryEnum.WORKSPACE_PERMISSIONS,
            [
                r"\bworkspace member\b",
                r"\badmin role\b",
                r"\bworkspace permissions\b",
                r"member permissions",
                r"access rights",
            ],
        ),
        (
            CategoryEnum.BILLING,
            [
                r"\bbilling refund\b",
                r"\binvoice\b",
                r"\bchargeback\b",
                r"credit card",
                r"subscription price",
                r"payment method",
                r"\brefund\b",
            ],
        ),
        (
            CategoryEnum.FEATURE_REQUEST,
            [
                r"\bfeature request\b",
                r"\broadmap\b",
                r"\bdark mode\b",
                r"would be great if",
            ],
        ),
        (
            CategoryEnum.ACCOUNT,
            [
                r"transfer ownership",
                r"delete my account",
                r"change account email",
                r"account settings",
                r"\baccount\b",
            ],
        ),
    ]

    for cat, regexes in patterns:
        for p in regexes:
            if re.search(p, text_clean):
                return cat

    return None


def assess_risk(
    plan: dict[str, Any] | None = None,
    matched_rules: list[EscalationRule] | None = None,
    severity: SeverityEnum | str | None = None,
    injection_detected: bool = False,
    output_validation_failed: bool = False,
) -> str:
    """Assess execution risk (CLAUDE.md 7.3 & ADR-03).

    Returns 'high' when:
    - Injection was detected (injection_detected=True)
    - Output validation failed (output_validation_failed=True)
    - Severity is critical
    - A policy escalation fired (matched_rules has entries)
    - The plan has approval-required actions (refunds, credential resets)

    Returns 'low' for safe/read-only operations.
    """
    # 1. Injection detected or output validation failed
    if injection_detected:
        return "high"

    if output_validation_failed:
        return "high"

    # 2. Critical severity triggers HIGH risk
    if severity is not None:
        sev_val = (
            severity.value
            if isinstance(severity, SeverityEnum)
            else str(severity).lower()
        )
        if sev_val == SeverityEnum.CRITICAL.value:
            return "high"

    # 3. Any policy escalation triggers HIGH risk
    if matched_rules and len(matched_rules) > 0:
        return "high"

    # 4. Check planned actions in resolution plan
    if plan and "actions" in plan:
        actions = plan.get("actions", [])
        approval_gated_tools = {"create_refund_request", "reset_demo_setting"}
        for action in actions:
            tool_name = action.get("tool") or action.get("tool_name")
            if tool_name in approval_gated_tools:
                return "high"

    return "low"


def evaluate_escalation_decision(
    model_escalate: bool,
    model_confidence: float,
    model_team: str | None,
    severity: SeverityEnum | str,
    matched_rules: list[EscalationRule],
) -> EscalationDecision:
    """Evaluate escalation routing combining deterministic policy rules and model judgment.

    Non-negotiable rule (CLAUDE.md 7.2):
    - Policy rules ALWAYS win.
    - If no policy rule matches and severity is HIGH/CRITICAL but model confidence is low (< 0.70),
      the escalation is distrusted and rejected (AC-045).
    - If model confidence is high (>= 0.70) without a policy rule, model judgment is trusted.
    """
    # 1. Deterministic policy rules always win
    if matched_rules:
        primary_rule = matched_rules[0]
        return EscalationDecision(
            escalation_required=True,
            target_team=primary_rule.target_team,
            rule_id=primary_rule.id,
            reason=primary_rule.policy_reason,
        )

    # Convert severity to enum
    sev_enum = (
        severity
        if isinstance(severity, SeverityEnum)
        else SeverityEnum(str(severity).lower())
    )

    # 2. Model requested escalation
    if model_escalate:
        # AC-045: Distrust vague model escalations when severity is high but confidence is low
        is_high_severity = sev_enum in (SeverityEnum.HIGH, SeverityEnum.CRITICAL)
        if is_high_severity and model_confidence < 0.70:
            return EscalationDecision(
                escalation_required=False,
                target_team=None,
                rule_id=None,
                reason="Distrusted vague model escalation: high severity but low model confidence (< 0.70) with no matching policy rule (AC-045).",
            )

        if model_confidence >= 0.70:
            return EscalationDecision(
                escalation_required=True,
                target_team=model_team or "Support",
                rule_id=None,
                reason="Model judgment escalation accepted with high confidence.",
            )

        return EscalationDecision(
            escalation_required=False,
            target_team=None,
            rule_id=None,
            reason="Model escalation rejected due to low confidence (< 0.70).",
        )

    # 3. No policy rule and model says no escalation
    return EscalationDecision(
        escalation_required=False,
        target_team=None,
        rule_id=None,
        reason="No policy escalation rule triggered and model indicated no escalation required.",
    )


__all__ = [
    "ESCALATION_RULES",
    "SECURITY_PREAMBLE",
    "EscalationDecision",
    "EscalationRule",
    "InjectionScanResult",
    "assess_risk",
    "evaluate_escalation_decision",
    "matching_escalation_rules",
    "rule_category",
    "rule_severity",
    "scan_for_injection",
    "wrap_untrusted",
]
