"""Tool execution policy and consequential action classification.

Enforces human-in-the-loop governance (F9) for high-impact actions like
refund issuance, workspace resets, and unexpected or unknown tool invocations.
"""

from functools import lru_cache
from typing import Any

from backend.app.core.config import Settings, get_settings


class ToolPolicy:
    """Policy engine determining authorization and approval gates for tool executions."""

    # Explicit sets defined in CLAUDE.md section 7.4 and design.md section 8.1
    READ_ONLY_TOOLS: frozenset[str] = frozenset({
        "get_customer",
        "get_subscription",
        "get_ticket_history",
        "search_docs",
        "check_service_status",
    })

    SAFE_WRITE_TOOLS: frozenset[str] = frozenset({
        "update_ticket",
        "create_escalation",
    })

    CONSEQUENTIAL_TOOLS: frozenset[str] = frozenset({
        "reset_demo_setting",
        "create_refund_request",
    })

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def is_consequential(self, tool_name: str, args: dict[str, Any] | None = None) -> bool:
        """Return True if the tool performs high-impact, state-changing operations."""
        if tool_name in self.CONSEQUENTIAL_TOOLS:
            return True
        # Unknown tools are treated as consequential by default (fail-safe)
        return (
            tool_name not in self.READ_ONLY_TOOLS
            and tool_name not in self.SAFE_WRITE_TOOLS
        )

    def requires_approval(self, tool_name: str, args: dict[str, Any] | None = None) -> bool:
        """Determine whether human approval is required before running this tool.

        - Read-only and safe-write tools are permitted unattended.
        - reset_demo_setting always requires approval.
        - create_refund_request checks APPROVAL_REQUIRED_FOR_REFUNDS and MAX_REFUND_WITHOUT_APPROVAL.
        - Unknown tools always require approval.
        """
        if tool_name in self.READ_ONLY_TOOLS or tool_name in self.SAFE_WRITE_TOOLS:
            return False

        if tool_name == "create_refund_request":
            if self.settings.APPROVAL_REQUIRED_FOR_REFUNDS:
                return True
            # If refund approval is not unconditionally required, check monetary threshold
            if args and "amount" in args:
                try:
                    amount = float(args["amount"])
                    return amount > self.settings.MAX_REFUND_WITHOUT_APPROVAL
                except (ValueError, TypeError):
                    return True
            return True

        if tool_name == "reset_demo_setting":
            return True

        # Any unregistered/unknown tool requires human approval
        return True

    def check_execution_permitted(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        approved: bool = False,
    ) -> tuple[bool, str | None]:
        """Check whether execution is allowed given the approval status.

        Returns (is_permitted, error_message).
        """
        needs_approval = self.requires_approval(tool_name, args)
        if needs_approval and not approved:
            return False, f"Tool '{tool_name}' requires human approval before execution."
        return True, None


@lru_cache
def get_tool_policy() -> ToolPolicy:
    """Return a cached singleton ToolPolicy instance."""
    return ToolPolicy()
