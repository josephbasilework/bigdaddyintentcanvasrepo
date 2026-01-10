"""Repository for Canvas CRUD operations."""

from logging import getLogger
from typing import Any

from sqlalchemy import UnaryExpression, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.canvas import Canvas
from app.repositories.base import BaseRepository

logger = getLogger(__name__)


class CanvasRepository(BaseRepository[Canvas, Any, Any]):
    """Repository for canvas CRUD operations.

    Provides methods for creating, reading, updating, and deleting
    canvas records with their associated nodes and edges.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy async session
        """
        super().__init__(db)

    @property
    def model(self) -> type[Canvas]:
        """Return the Canvas model."""
        return Canvas

    async def get_with_nodes(self, canvas_id: int) -> Canvas | None:
        """Get canvas with all nodes preloaded.

        Args:
            canvas_id: Canvas identifier

        Returns:
            Canvas with nodes if found, None otherwise
        """
        stmt = (
            select(Canvas)
            .where(Canvas.id == canvas_id)
            .options(selectinload(Canvas.nodes))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_graph(self, canvas_id: int) -> Canvas | None:
        """Get canvas with all nodes and edges preloaded.

        Args:
            canvas_id: Canvas identifier

        Returns:
            Canvas with nodes and edges if found, None otherwise
        """
        stmt = (
            select(Canvas)
            .where(Canvas.id == canvas_id)
            .options(selectinload(Canvas.nodes), selectinload(Canvas.edges))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 10,
    ) -> list[Canvas]:
        """Get canvases by user ID with pagination.

        Args:
            user_id: User identifier
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of canvases belonging to the user
        """
        stmt = (
            select(Canvas)
            .where(Canvas.user_id == user_id)
            .order_by(Canvas.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_canvas(
        self,
        user_id: str,
        name: str,
    ) -> Canvas:
        """Create a new canvas.

        Args:
            user_id: User identifier
            name: Canvas name

        Returns:
            Created canvas
        """
        return await self.create(user_id=user_id, name=name)

    async def update_name(self, canvas_id: int, name: str) -> Canvas | None:
        """Update canvas name.

        Args:
            canvas_id: Canvas identifier
            name: New canvas name

        Returns:
            Updated canvas if found, None otherwise
        """
        return await self.update(canvas_id, name=name)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        order_by: UnaryExpression[Any] | None = None,
    ) -> list[Canvas]:
        """List canvases with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            order_by: Optional ordering clause

        Returns:
            List of canvases
        """
        return await super().list(offset=offset, limit=limit, order_by=order_by)
