"""Mock service implementations for offline development, automated tests, and demos.

Provides mock adapters for Billing, Email, Status, Notification, and Workspace Admin
subsystems, tracking call history and supporting failure simulation.
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class MockBillingService:
    """Mock implementation of BillingServiceProtocol."""

    def __init__(self) -> None:
        self.refunds_processed: list[dict[str, Any]] = []
        self._should_fail: bool = False
        self._fail_message: str = "Simulated billing gateway outage"

    def simulate_failure(
        self, should_fail: bool = True, error_message: str = "Simulated billing gateway outage"
    ) -> None:
        """Configure mock to simulate external API failures."""
        self._should_fail = should_fail
        self._fail_message = error_message

    def reset(self) -> None:
        """Clear recorded operations and reset error simulation."""
        self.refunds_processed.clear()
        self._should_fail = False

    async def create_refund(
        self,
        customer_id: str,
        amount: float,
        reason: str,
        ticket_id: str | None = None,
    ) -> dict[str, Any]:
        """Record mock refund and return receipt."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        refund_record = {
            "refund_id": f"ref_{uuid.uuid4().hex[:12]}",
            "customer_id": customer_id,
            "amount": float(amount),
            "reason": reason,
            "ticket_id": ticket_id,
            "status": "refunded",
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.refunds_processed.append(refund_record)
        return refund_record

    async def get_payment_history(self, customer_id: str) -> list[dict[str, Any]]:
        """Return synthetic payment invoice history for customer."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        return [
            {
                "invoice_id": f"inv_{customer_id}_01",
                "amount": 250.00,
                "currency": "USD",
                "status": "paid",
                "date": "2026-10-01T00:00:00Z",
            },
            {
                "invoice_id": f"inv_{customer_id}_02",
                "amount": 250.00,
                "currency": "USD",
                "status": "paid",
                "date": "2026-09-01T00:00:00Z",
            },
        ]

    async def get_subscription_status(self, customer_id: str) -> dict[str, Any]:
        """Return synthetic billing account subscription status."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        return {
            "customer_id": customer_id,
            "account_status": "current",
            "payment_method": "card_ending_4242",
            "delinquent": False,
        }


class MockEmailService:
    """Mock implementation of EmailServiceProtocol."""

    def __init__(self) -> None:
        self.sent_emails: list[dict[str, Any]] = []
        self._should_fail: bool = False
        self._fail_message: str = "Simulated SMTP connection dropped"

    def simulate_failure(
        self, should_fail: bool = True, error_message: str = "Simulated SMTP connection dropped"
    ) -> None:
        """Configure mock to simulate external email delivery failures."""
        self._should_fail = should_fail
        self._fail_message = error_message

    def reset(self) -> None:
        """Clear recorded outgoing emails and reset failure mode."""
        self.sent_emails.clear()
        self._should_fail = False

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        reply_to: str | None = None,
        ticket_id: str | None = None,
    ) -> dict[str, Any]:
        """Record outbound message in sent_emails list."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        record = {
            "message_id": msg_id,
            "to": to_email,
            "subject": subject,
            "body": body,
            "reply_to": reply_to,
            "ticket_id": ticket_id,
            "status": "sent",
            "sent_at": datetime.now(UTC).isoformat(),
        }
        self.sent_emails.append(record)
        return record


class MockStatusService:
    """Mock implementation of StatusServiceProtocol."""

    def __init__(self) -> None:
        self._should_fail: bool = False
        self._fail_message: str = "Status service cluster offline"

    def simulate_failure(
        self, should_fail: bool = True, error_message: str = "Status service cluster offline"
    ) -> None:
        """Configure mock to simulate status API failure."""
        self._should_fail = should_fail
        self._fail_message = error_message

    def reset(self) -> None:
        """Reset failure mode."""
        self._should_fail = False

    async def check_service_health(self, service_name: str | None = None) -> dict[str, Any]:
        """Inspect health status based on incidents fixture."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        incidents = await self.get_active_incidents(service_name)
        if any(inc.get("severity") == "critical" for inc in incidents):
            status = "outage"
        elif incidents:
            status = "degraded"
        else:
            status = "operational"

        return {
            "service": service_name or "all",
            "status": status,
            "active_incidents": incidents,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    async def get_active_incidents(
        self, service_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Return active incidents loaded from sample_data/incidents.json."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        settings = get_settings()
        sample_path = Path(settings.SAMPLE_DATA_DIR) / "incidents.json"
        active: list[dict[str, Any]] = []

        if sample_path.exists():
            try:
                raw_data = json.loads(sample_path.read_text(encoding="utf-8"))
                for inc in raw_data:
                    status = inc.get("status", "").lower()
                    if status in ("investigating", "identified", "monitoring"):
                        svc = inc.get("service", "")
                        if not service_name or svc == service_name:
                            active.append(inc)
            except (json.JSONDecodeError, OSError) as err:
                logger.debug("Failed reading sample incidents file: %s", err)
        return active


class MockNotificationService:
    """Mock implementation of NotificationServiceProtocol."""

    def __init__(self) -> None:
        self.sent_notifications: list[dict[str, Any]] = []
        self._should_fail: bool = False
        self._fail_message: str = "Webhook delivery timeout"

    def simulate_failure(
        self, should_fail: bool = True, error_message: str = "Webhook delivery timeout"
    ) -> None:
        """Configure mock to simulate webhook failure."""
        self._should_fail = should_fail
        self._fail_message = error_message

    def reset(self) -> None:
        """Clear recorded notifications and reset failure mode."""
        self.sent_notifications.clear()
        self._should_fail = False

    async def send_notification(
        self,
        channel: str,
        message: str,
        ticket_id: str | None = None,
    ) -> dict[str, Any]:
        """Record notification message dispatched to team channel."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        record = {
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "channel": channel,
            "message": message,
            "ticket_id": ticket_id,
            "status": "delivered",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.sent_notifications.append(record)
        return record


class MockWorkspaceAdminService:
    """Mock implementation of WorkspaceAdminProtocol."""

    def __init__(self) -> None:
        self.mutated_settings: list[dict[str, Any]] = []
        self._should_fail: bool = False
        self._fail_message: str = "Admin directory service timeout"

    def simulate_failure(
        self, should_fail: bool = True, error_message: str = "Admin directory service timeout"
    ) -> None:
        """Configure mock to simulate workspace admin API failure."""
        self._should_fail = should_fail
        self._fail_message = error_message

    def reset(self) -> None:
        """Clear mutated settings records."""
        self.mutated_settings.clear()
        self._should_fail = False

    async def reset_setting(
        self,
        workspace_id: str,
        setting_key: str,
        reset_value: Any = None,
    ) -> dict[str, Any]:
        """Record workspace setting reset operation."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        record = {
            "workspace_id": workspace_id,
            "setting_key": setting_key,
            "reset_value": reset_value,
            "status": "updated",
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self.mutated_settings.append(record)
        return record

    async def get_settings(self, workspace_id: str) -> dict[str, Any]:
        """Return synthetic workspace configuration settings."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        return {
            "workspace_id": workspace_id,
            "sso_enforced": True,
            "external_sharing": False,
            "max_file_size_mb": 500,
        }
