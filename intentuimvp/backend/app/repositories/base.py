"""Base repository class for async CRUD operations."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy import UnaryExpression, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(ABC, Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Abstract base repository for async CRUD operations.

    Provides common database operations for SQLAlchemy models.
    Subclasses must implement the model property.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy async session
        """
        self.db = db

    @property
    @abstractmethod
    def model(self) -> type[ModelType]:
        """Return the SQLAlchemy model class.

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record.

        Args:
            **kwargs: Field values for the new record

        Returns:
            Created model instance
        """
        db_obj = self.model(**kwargs)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def get_by_id(self, id: int) -> ModelType | None:
        """Get record by ID.

        Args:
            id: Primary key identifier

        Returns:
            Model instance if found, None otherwise
        """
        model_id = cast(Any, self.model).id
        stmt = select(self.model).where(model_id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        order_by: UnaryExpression[Any] | None = None,
    ) -> list[ModelType]:
        """List records with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            order_by: Optional ordering clause

        Returns:
            List of model instances
        """
        stmt = select(self.model).offset(offset).limit(limit)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, id: int, **kwargs: Any) -> ModelType | None:
        """Update a record.

        Args:
            id: Primary key identifier
            **kwargs: Field values to update

        Returns:
            Updated model instance if found, None otherwise
        """
        db_obj = await self.get_by_id(id)
        if db_obj is None:
            return None

        for field, value in kwargs.items():
            setattr(db_obj, field, value)

        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        """Delete a record.

        Args:
            id: Primary key identifier

        Returns:
            True if deleted, False if not found
        """
        db_obj = await self.get_by_id(id)
        if db_obj is None:
            return False

        await self.db.delete(db_obj)
        await self.db.commit()
        return True

    async def count(self) -> int:
        """Count total records.

        Returns:
            Total number of records
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        result = await self.db.execute(stmt)
        return result.scalar() or 0
