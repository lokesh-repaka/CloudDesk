"""Specialist agents for CloudDesk multi-agent system.

Provides specialist agents:
- SupervisorAgent: Understands incoming tickets, classifies categories, and assesses severity.
"""

from agents.specialists.supervisor import SupervisorAgent

__all__ = [
    "SupervisorAgent",
]
