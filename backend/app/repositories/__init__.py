"""Repository Layer — Pure SQL Data Access via SQLAlchemy 2.0.

Provides modular, strongly typed repository classes for all domain aggregates:
- BaseRepository: Generic async CRUD operations
- CustomerRepository & WorkspaceRepository: Customer profiling & tenant workspaces
- TicketRepository & TicketMessageRepository: Omnichannel ticket management
- ApprovalRepository: Human-in-the-loop approval workflows
- CustomerMemoryRepository: Customer long-term memory notes
"""

from backend.app.repositories.approval_repo import ApprovalRepository
from backend.app.repositories.base import BaseRepository
from backend.app.repositories.customer_repo import (
    CustomerRepository,
    WorkspaceRepository,
)
from backend.app.repositories.memory_repo import CustomerMemoryRepository
from backend.app.repositories.ticket_repo import (
    TicketMessageRepository,
    TicketRepository,
)

__all__ = [
    "ApprovalRepository",
    "BaseRepository",
    "CustomerMemoryRepository",
    "CustomerRepository",
    "TicketMessageRepository",
    "TicketRepository",
    "WorkspaceRepository",
]
