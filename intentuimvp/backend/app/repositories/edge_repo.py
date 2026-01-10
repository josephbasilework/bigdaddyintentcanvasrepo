"""Repository for Edge CRUD operations."""

from logging import getLogger
from typing import Any

from sqlalchemy import UnaryExpression, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.edge import Edge, RelationType
from app.repositories.base import BaseRepository

logger = getLogger(__name__)


class EdgeRepository(BaseRepository[Edge, Any, Any]):
    """Repository for edge CRUD operations.

    Provides methods for creating, reading, updating, and deleting
    edge records representing connections between nodes.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy async session
        """
        super().__init__(db)

    @property
    def model(self) -> type[Edge]:
        """Return the Edge model."""
        return Edge

    async def get_with_nodes(self, edge_id: int) -> Edge | None:
        """Get edge with from_node and to_node preloaded.

        Args:
            edge_id: Edge identifier

        Returns:
            Edge with nodes if found, None otherwise
        """
        stmt = (
            select(Edge)
            .where(Edge.id == edge_id)
            .options(
                selectinload(Edge.from_node),
                selectinload(Edge.to_node),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_canvas(
        self,
        canvas_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Edge]:
        """Get edges by canvas ID with pagination.

        Args:
            canvas_id: Canvas identifier
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of edges belonging to the canvas
        """
        stmt = (
            select(Edge)
            .where(Edge.canvas_id == canvas_id)
            .order_by(Edge.id)
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_node(
        self,
        node_id: int,
        *,
        as_source: bool = True,
        as_target: bool = False,
    ) -> list[Edge]:
        """Get edges connected to a node.

        Args:
            node_id: Node identifier
            as_source: Include edges where node is the source
            as_target: Include edges where node is the target

        Returns:
            List of edges connected to the node
        """
        conditions = []
        if as_source:
            conditions.append(Edge.from_node_id == node_id)
        if as_target:
            conditions.append(Edge.to_node_id == node_id)

        if not conditions:
            return []

        from sqlalchemy import or_

        stmt = (
            select(Edge)
            .where(or_(*conditions))
            .order_by(Edge.id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_edge(
        self,
        canvas_id: int,
        from_node_id: int,
        to_node_id: int,
        relation_type: RelationType,
    ) -> Edge:
        """Create a new edge.

        Args:
            canvas_id: Canvas identifier
            from_node_id: Source node identifier
            to_node_id: Target node identifier
            relation_type: Type of relation

        Returns:
            Created edge
        """
        return await self.create(
            canvas_id=canvas_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            relation_type=relation_type,
        )

    async def update_relation_type(
        self,
        edge_id: int,
        relation_type: RelationType,
    ) -> Edge | None:
        """Update edge relation type.

        Args:
            edge_id: Edge identifier
            relation_type: New relation type

        Returns:
            Updated edge if found, None otherwise
        """
        return await self.update(edge_id, relation_type=relation_type)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        order_by: UnaryExpression[Any] | None = None,
    ) -> list[Edge]:
        """List edges with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            order_by: Optional ordering clause

        Returns:
            List of edges
        """
        return await super().list(offset=offset, limit=limit, order_by=order_by)
