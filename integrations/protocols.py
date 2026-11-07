"""Protocol interfaces for external platform service integrations.

Defines structural subtyping contracts for Billing, Email, Status,
Notification, and Workspace Administration adapters.
"""

from typing import Any, Protocol


class BillingServiceProtocol(Protocol):
    """Contract for payment processing and refund administration."""

    async def create_refund(
        self,
        customer_id: str,
        amount: float,
        reason: str,
        ticket_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a billing refund and return receipt details."""
        ...

    async def get_payment_history(self, customer_id: str) -> list[dict[str, Any]]:
        """Retrieve historical invoices and charges for a customer."""
        ...

    async def get_subscription_status(self, customer_id: str) -> dict[str, Any]:
        """Fetch subscription tier and active billing state."""
        ...


class EmailServiceProtocol(Protocol):
    """Contract for outbound transactional email delivery."""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        reply_to: str | None = None,
        ticket_id: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch an email message to a recipient."""
        ...


class StatusServiceProtocol(Protocol):
    """Contract for platform service health and incident discovery."""

    async def check_service_health(self, service_name: str | None = None) -> dict[str, Any]:
        """Inspect operational health across services or for a specific service."""
        ...

    async def get_active_incidents(
        self, service_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve list of currently open platform incidents."""
        ...


class NotificationServiceProtocol(Protocol):
    """Contract for internal agent messaging and team notifications (Slack/webhooks)."""

    async def send_notification(
        self,
        channel: str,
        message: str,
        ticket_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a notification message to an internal team channel."""
        ...


class WorkspaceAdminProtocol(Protocol):
    """Contract for workspace-level administration and configuration management."""

    async def reset_setting(
        self,
        workspace_id: str,
        setting_key: str,
        reset_value: Any = None,
    ) -> dict[str, Any]:
        """Reset a workspace configuration key to its default or designated value."""
        ...

    async def get_settings(self, workspace_id: str) -> dict[str, Any]:
        """Retrieve current configuration dictionary for a workspace."""
        ...
