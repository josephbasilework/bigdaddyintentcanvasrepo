"""Repository for Node CRUD operations."""

from __future__ import annotations

import json
from logging import getLogger
from typing import Any

from sqlalchemy import UnaryExpression, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.node import Node, NodeType, normalize_node_type
from app.repositories.base import BaseRepository

logger = getLogger(__name__)


class DuplicatePositionError(ValueError):
    """Raised when a node position conflicts with an existing node in the same canvas.

    Domain Invariant: CI-001 - Node position must be unique within Canvas.
    See: PRD §14 Domain Invariants & Business Rules
    """

    def __init__(self, canvas_id: int, position: dict) -> None:
        """Initialize error with canvas and position context.

        Args:
            canvas_id: Canvas ID where the conflict occurred
            position: The conflicting position dict
        """
        self.canvas_id = canvas_id
        self.position = position
        pos_str = json.dumps(position)
        super().__init__(
            f"[CI-001] Node position {pos_str} already exists in canvas {canvas_id}. "
            f"Each node must have a unique position within its canvas. "
            f"See PRD §14: Domain Invariants & Business Rules"
        )


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

    async def _validate_position_unique(
        self, canvas_id: int, position: dict, exclude_node_id: int | None = None
    ) -> None:
        """Validate that no other node in the canvas has the same position.

        Enforces CI-001: Node position must be unique within Canvas.

        Args:
            canvas_id: Canvas ID to check within
            position: Position dict {"x": 0, "y": 0, "z": 0}
            exclude_node_id: Optional node ID to exclude from check (for updates)

        Raises:
            DuplicatePositionError: If another node already has this position
        """
        position_json = json.dumps(position)
        stmt = select(Node).where(
            Node.canvas_id == canvas_id,
            Node.position == position_json,
        )
        if exclude_node_id is not None:
            stmt = stmt.where(Node.id != exclude_node_id)

        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            raise DuplicatePositionError(canvas_id=canvas_id, position=position)

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

    async def get_by_position(self, canvas_id: int, position: dict) -> Node | None:
        """Get a node by exact position within a canvas.

        Args:
            canvas_id: Canvas identifier
            position: Position dict {"x": 0, "y": 0, "z": 0}

        Returns:
            Node if found, None otherwise
        """
        position_json = json.dumps(position)
        stmt = select(Node).where(
            Node.canvas_id == canvas_id,
            Node.position == position_json,
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
        type: str | NodeType = NodeType.TEXT,
        position: dict | None = None,
        content: str | None = None,
        node_metadata: dict | None = None,
        created_by_turn_id: int | None = None,
    ) -> Node:
        """Create a new node.

        Args:
            canvas_id: Canvas identifier
            label: Node label
            type: Node type (default: TEXT)
            position: Position dictionary {"x": 0, "y": 0, "z": 0}
            content: Optional node content
            node_metadata: Additional metadata dictionary
            created_by_turn_id: Optional turn ID for attribution (for agent-created nodes)

        Returns:
            Created node

        Raises:
            DuplicatePositionError: If another node in the canvas has this position (CI-001)
        """
        position = position or {"x": 0, "y": 0, "z": 0}

        # Enforce CI-001: Node position must be unique within Canvas
        await self._validate_position_unique(canvas_id, position)

        position_json = json.dumps(position)
        metadata_json = json.dumps(node_metadata) if node_metadata else None

        normalized_type = normalize_node_type(type)

        return await self.create(
            canvas_id=canvas_id,
            type=normalized_type,
            label=label,
            content=content,
            position=position_json,
            node_metadata=metadata_json,
            created_by_turn_id=created_by_turn_id,
        )

    async def update_position(self, node_id: int, position: dict) -> Node | None:
        """Update node position.

        Args:
            node_id: Node identifier
            position: New position dictionary {"x": 0, "y": 0, "z": 0}

        Returns:
            Updated node if found, None otherwise

        Raises:
            DuplicatePositionError: If another node in the canvas has this position (CI-001)
        """
        # Get the node to find its canvas_id
        node = await self.get_by_id(node_id)
        if node is None:
            return None

        # Enforce CI-001: Node position must be unique within Canvas
        # Exclude current node from the uniqueness check
        await self._validate_position_unique(node.canvas_id, position, exclude_node_id=node_id)

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

    async def get_by_turn_id(self, turn_id: int) -> list[Node]:
        """Get all nodes created by a specific turn.

        Args:
            turn_id: The turn ID to filter by

        Returns:
            List of nodes created by the specified turn
        """
        stmt = (
            select(Node)
            .where(Node.created_by_turn_id == turn_id)
            .order_by(Node.id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_turn_ids(self, turn_ids: list[int]) -> list[Node]:
        """Get all nodes created by any of the specified turns.

        Args:
            turn_ids: List of turn IDs to filter by

        Returns:
            List of nodes created by the specified turns
        """
        if not turn_ids:
            return []
        stmt = (
            select(Node)
            .where(Node.created_by_turn_id.in_(turn_ids))
            .order_by(Node.id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_turn_id(self, turn_id: int) -> list[int]:
        """Delete all nodes created by a specific turn.

        Args:
            turn_id: The turn ID to filter by

        Returns:
            List of deleted node IDs
        """
        nodes = await self.get_by_turn_id(turn_id)
        deleted_ids = []
        for node in nodes:
            if await self.delete(node.id):
                deleted_ids.append(node.id)
        return deleted_ids
