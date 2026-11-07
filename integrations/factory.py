"""Integration service factory providing singleton access to external service adapters.

In demo mode and v1, all services resolve to offline mock implementations.
"""

from functools import lru_cache

from integrations.mock.services import (
    MockBillingService,
    MockEmailService,
    MockNotificationService,
    MockStatusService,
    MockWorkspaceAdminService,
)
from integrations.protocols import (
    BillingServiceProtocol,
    EmailServiceProtocol,
    NotificationServiceProtocol,
    StatusServiceProtocol,
    WorkspaceAdminProtocol,
)

# Global singleton mock instances
_billing_service = MockBillingService()
_email_service = MockEmailService()
_status_service = MockStatusService()
_notification_service = MockNotificationService()
_workspace_admin_service = MockWorkspaceAdminService()


@lru_cache
def get_billing_service() -> BillingServiceProtocol:
    """Return active billing service provider."""
    return _billing_service


@lru_cache
def get_email_service() -> EmailServiceProtocol:
    """Return active email service provider."""
    return _email_service


@lru_cache
def get_status_service() -> StatusServiceProtocol:
    """Return active status service provider."""
    return _status_service


@lru_cache
def get_notification_service() -> NotificationServiceProtocol:
    """Return active notification service provider."""
    return _notification_service


@lru_cache
def get_workspace_admin_service() -> WorkspaceAdminProtocol:
    """Return active workspace admin service provider."""
    return _workspace_admin_service


def reset_all_mock_services() -> None:
    """Reset state across all mock service adapters."""
    _billing_service.reset()
    _email_service.reset()
    _status_service.reset()
    _notification_service.reset()
    _workspace_admin_service.reset()
