"""Base Repository — Generic Async CRUD Abstraction.

Provides standardized async database operations for all SQLAlchemy declarative
models, enforcing clean separation between API routes and database queries.
"""

from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository[ModelType: Base]:
    """Generic repository providing asynchronous CRUD operations for a given ORM model."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: str) -> ModelType | None:
        """Fetch a single record by primary key UUID."""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[ModelType]:
        """Fetch multiple records with optional equality filtering and pagination."""
        stmt = select(self.model)
        for field, value in filters.items():
            if value is not None and hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, **filters: Any) -> int:
        """Count total matching records for the model with optional filtering."""
        stmt = select(func.count()).select_from(self.model)
        for field, value in filters.items():
            if value is not None and hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def create(self, obj_in: ModelType | dict[str, Any]) -> ModelType:
        """Persist a new entity record and flush to generate database defaults."""
        if isinstance(obj_in, dict):
            instance = self.model(**obj_in)
        else:
            instance = obj_in
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, db_obj: ModelType, obj_in: dict[str, Any]) -> ModelType:
        """Update fields of an existing entity record and flush changes."""
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: str) -> bool:
        """Delete an entity by primary key. Returns True if deleted, False if not found."""
        instance = await self.get(id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True
