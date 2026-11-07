"""CloudDesk Agents Package.

Contains LangGraph workflow nodes, specialist agents, state schemas, and deterministic rule engines.
"""

from agents.prompts import (
    CUSTOMER_AGENT_SYSTEM_PROMPT,
    ESCALATION_SYSTEM_PROMPT,
    KNOWLEDGE_AGENT_SYSTEM_PROMPT,
    RESOLUTION_SYSTEM_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
    TROUBLESHOOTING_SYSTEM_PROMPT,
    build_prompt_with_security_preamble,
)
from agents.rules import (
    ESCALATION_RULES,
    REDACTION_MARKER,
    SECRET_PATTERNS,
    SECURITY_PREAMBLE,
    EscalationDecision,
    EscalationRule,
    InjectionScanResult,
    OutputValidationResult,
    assess_risk,
    evaluate_escalation_decision,
    matching_escalation_rules,
    rule_category,
    rule_severity,
    scan_for_injection,
    scrub,
    validate_customer_output,
    wrap_untrusted,
)

__all__ = [
    "CUSTOMER_AGENT_SYSTEM_PROMPT",
    "ESCALATION_RULES",
    "ESCALATION_SYSTEM_PROMPT",
    "KNOWLEDGE_AGENT_SYSTEM_PROMPT",
    "REDACTION_MARKER",
    "RESOLUTION_SYSTEM_PROMPT",
    "SECRET_PATTERNS",
    "SECURITY_PREAMBLE",
    "SUPERVISOR_SYSTEM_PROMPT",
    "TROUBLESHOOTING_SYSTEM_PROMPT",
    "EscalationDecision",
    "EscalationRule",
    "InjectionScanResult",
    "OutputValidationResult",
    "assess_risk",
    "build_prompt_with_security_preamble",
    "evaluate_escalation_decision",
    "matching_escalation_rules",
    "rule_category",
    "rule_severity",
    "scan_for_injection",
    "scrub",
    "validate_customer_output",
    "wrap_untrusted",
]
