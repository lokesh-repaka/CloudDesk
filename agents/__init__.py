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
from agents.specialists.customer import CustomerAgent
from agents.specialists.knowledge import KnowledgeAgent
from agents.specialists.resolution import ResolutionAgent
from agents.specialists.supervisor import SupervisorAgent
from agents.specialists.troubleshooting import TroubleshootingAgent

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
    "CustomerAgent",
    "EscalationDecision",
    "EscalationRule",
    "InjectionScanResult",
    "KnowledgeAgent",
    "OutputValidationResult",
    "ResolutionAgent",
    "SupervisorAgent",
    "TroubleshootingAgent",
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
