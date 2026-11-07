"""Integrations layer for CloudDesk.

Provides external service protocols, mock adapters, factory singletons, and MCP server.
Per CLAUDE.md section 4.2, integrations must not be imported by backend/app/core/.
"""

from integrations.factory import (
    get_billing_service,
    get_email_service,
    get_notification_service,
    get_status_service,
    get_workspace_admin_service,
    reset_all_mock_services,
)
from integrations.protocols import (
    BillingServiceProtocol,
    EmailServiceProtocol,
    NotificationServiceProtocol,
    StatusServiceProtocol,
    WorkspaceAdminProtocol,
)

__all__ = [
    "BillingServiceProtocol",
    "EmailServiceProtocol",
    "NotificationServiceProtocol",
    "StatusServiceProtocol",
    "WorkspaceAdminProtocol",
    "get_billing_service",
    "get_email_service",
    "get_notification_service",
    "get_status_service",
    "get_workspace_admin_service",
    "reset_all_mock_services",
]
