"""Domain constants and canonical enums for CloudDesk Support Platform.

Single source of truth for categories, statuses, severity, channels, and roles
as defined in CLAUDE.md section 5.
"""

from enum import Enum


class CategoryEnum(str, Enum):
    """The exactly ten canonical ticket categories."""

    LOGIN_ISSUE = "login_issue"
    BILLING = "billing"
    API_FAILURE = "api_failure"
    WORKSPACE_PERMISSIONS = "workspace_permissions"
    STORAGE_QUOTA = "storage_quota"
    INTEGRATION = "integration"
    FEATURE_REQUEST = "feature_request"
    ACCOUNT = "account"
    SECURITY = "security"
    OTHER = "other"


class TicketStatusEnum(str, Enum):
    """Lifecycle statuses for a support ticket."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    WAITING_ON_APPROVAL = "waiting_on_approval"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SeverityEnum(str, Enum):
    """Urgency / severity levels for tickets."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChannelEnum(str, Enum):
    """Inbound ticket communication channels."""

    EMAIL = "email"
    CHAT = "chat"
    WEB = "web"
    API = "api"


class RoleEnum(str, Enum):
    """Platform user roles for RBAC enforcement."""

    VIEWER = "viewer"
    AGENT = "agent"
    ADMIN = "admin"


class CustomerPlanEnum(str, Enum):
    """Customer subscription tiers."""

    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class ApprovalStatusEnum(str, Enum):
    """State of a human-in-the-loop approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryTypeEnum(str, Enum):
    """Categories of long-term customer memory notes."""

    PAST_ISSUE = "past_issue"
    TROUBLESHOOTING = "troubleshooting"
    NOTE = "note"
    PREFERENCE = "preference"


class WorkflowStatusEnum(str, Enum):
    """Execution status of an autonomous LangGraph run."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_ON_APPROVAL = "waiting_on_approval"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    FAILED = "failed"


class ResolutionActionStatusEnum(str, Enum):
    """Execution status of a planned remediation action."""

    PLANNED = "planned"
    EXECUTED = "executed"
    FAILED = "failed"


class EscalationStatusEnum(str, Enum):
    """State of an escalated ticket handoff."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
