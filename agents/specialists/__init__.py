"""Specialist agents for CloudDesk multi-agent system.

Provides specialist agents:
- SupervisorAgent: Understands incoming tickets, classifies categories, and assesses severity.
- CustomerAgent: Aggregates customer 360 profile, workspaces, subscriptions, and memory context.
- KnowledgeAgent: Searches knowledge base and retrieves similar resolved cases via Jaccard overlap.
"""

from agents.specialists.customer import CustomerAgent
from agents.specialists.knowledge import KnowledgeAgent
from agents.specialists.supervisor import SupervisorAgent

__all__ = [
    "CustomerAgent",
    "KnowledgeAgent",
    "SupervisorAgent",
]
