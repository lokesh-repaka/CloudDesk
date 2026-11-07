"""Specialist agents for CloudDesk multi-agent system.

Provides specialist agents:
- SupervisorAgent: Understands incoming tickets, classifies categories, and assesses severity.
- CustomerAgent: Aggregates customer 360 profile, workspaces, subscriptions, and memory context.
- KnowledgeAgent: Searches knowledge base and retrieves similar resolved cases via Jaccard overlap.
- TroubleshootingAgent: Diagnoses technical root causes and generates ordered remediation steps.
- ResolutionAgent: Plans remediation actions, drafts customer replies, and enforces output safety.
- EscalationAgent: Evaluates policy escalation rules and routes cases to specialist teams.
"""

from agents.specialists.customer import CustomerAgent
from agents.specialists.escalation import EscalationAgent
from agents.specialists.knowledge import KnowledgeAgent
from agents.specialists.resolution import ResolutionAgent
from agents.specialists.supervisor import SupervisorAgent
from agents.specialists.troubleshooting import TroubleshootingAgent

__all__ = [
    "CustomerAgent",
    "EscalationAgent",
    "KnowledgeAgent",
    "ResolutionAgent",
    "SupervisorAgent",
    "TroubleshootingAgent",
]
