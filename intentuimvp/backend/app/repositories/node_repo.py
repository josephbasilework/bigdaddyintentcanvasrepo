"""Repository for Node CRUD operations."""

import json
from logging import getLogger
from typing import Any

from sqlalchemy import UnaryExpression, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.node import Node, NodeType
from app.repositories.base import BaseRepository

logger = getLogger(__name__)


class NodeRepository(BaseRepository[Node, Any, Any]):
    """Repository for node CRUD operations.

    Provides methods for creating, reading, updating, and deleting
    node records with their associated edges.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy async session
        """
        super().__init__(db)

    @property
    def model(self) -> type[Node]:
        """Return the Node model."""
        return Node

    async def get_with_edges(self, node_id: int) -> Node | None:
        """Get node with all edges preloaded.

        Args:
            node_id: Node identifier

        Returns:
            Node with outgoing and incoming edges if found, None otherwise
        """
        stmt = (
            select(Node)
            .where(Node.id == node_id)
            .options(
                selectinload(Node.outgoing_edges),
                selectinload(Node.incoming_edges),
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
    ) -> list[Node]:
        """Get nodes by canvas ID with pagination.

        Args:
            canvas_id: Canvas identifier
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of nodes belonging to the canvas
        """
        stmt = (
            select(Node)
            .where(Node.canvas_id == canvas_id)
            .order_by(Node.id)
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_node(
        self,
        canvas_id: int,
        label: str,
        type: NodeType = NodeType.TEXT,
        position: dict | None = None,
        node_metadata: dict | None = None,
    ) -> Node:
        """Create a new node.

        Args:
            canvas_id: Canvas identifier
            label: Node label
            type: Node type (default: TEXT)
            position: Position dictionary {"x": 0, "y": 0, "z": 0}
            node_metadata: Additional metadata dictionary

        Returns:
            Created node
        """
        position_json = json.dumps(position or {"x": 0, "y": 0, "z": 0})
        metadata_json = json.dumps(node_metadata) if node_metadata else None

        return await self.create(
            canvas_id=canvas_id,
            type=type,
            label=label,
            position=position_json,
            node_metadata=metadata_json,
        )

    async def update_position(self, node_id: int, position: dict) -> Node | None:
        """Update node position.

        Args:
            node_id: Node identifier
            position: New position dictionary {"x": 0, "y": 0, "z": 0}

        Returns:
            Updated node if found, None otherwise
        """
        return await self.update(node_id, position=json.dumps(position))

    async def update_metadata(self, node_id: int, metadata: dict) -> Node | None:
        """Update node metadata.

        Args:
            node_id: Node identifier
            metadata: New metadata dictionary

        Returns:
            Updated node if found, None otherwise
        """
        return await self.update(node_id, node_metadata=json.dumps(metadata))

    async def update_label(self, node_id: int, label: str) -> Node | None:
        """Update node label.

        Args:
            node_id: Node identifier
            label: New label

        Returns:
            Updated node if found, None otherwise
        """
        return await self.update(node_id, label=label)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        order_by: UnaryExpression[Any] | None = None,
    ) -> list[Node]:
        """List nodes with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            order_by: Optional ordering clause

        Returns:
            List of nodes
        """
        return await super().list(offset=offset, limit=limit, order_by=order_by)
