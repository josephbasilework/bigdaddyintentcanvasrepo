"""Repository for canvas and node operations."""

import json
import random
import string
import time
from logging import getLogger

from sqlalchemy.orm import Session

from app.models.canvas import Canvas
from app.models.edge import Edge
from app.models.node import Node

logger = getLogger(__name__)


def _generate_node_id() -> str:
    """Generate a unique node ID.

    Returns:
        A unique node ID string
    """
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"node-{timestamp}-{random_str}"


def _generate_edge_id() -> str:
    """Generate a unique edge ID.

    Returns:
        A unique edge ID string
    """
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"edge-{timestamp}-{random_str}"


class CanvasRepository:
    """Repository for canvas and node CRUD operations.

    Uses SQLAlchemy ORM for database access. Provides methods for
    creating, reading, updating, and deleting canvas and node records.
    """

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def get_by_user(self, user_id: str) -> Canvas | None:
        """Get canvas by user ID.

        Args:
            user_id: User identifier

        Returns:
            Canvas if found, None otherwise
        """
        return (
            self.db.query(Canvas)
            .filter(Canvas.user_id == user_id)
            .order_by(Canvas.updated_at.desc())
            .first()
        )

    def get_by_id(self, canvas_id: int) -> Canvas | None:
        """Get canvas by ID.

        Args:
            canvas_id: Canvas identifier

        Returns:
            Canvas if found, None otherwise
        """
        return self.db.query(Canvas).filter(Canvas.id == canvas_id).first()

    def create_canvas(self, user_id: str, name: str = "default") -> Canvas:
        """Create a new canvas.

        Args:
            user_id: User identifier
            name: Canvas name (default: "default")

        Returns:
            Created canvas
        """
        canvas = Canvas(user_id=user_id, name=name)
        self.db.add(canvas)
        self.db.commit()
        self.db.refresh(canvas)
        logger.info(f"Created canvas {canvas.id} for user {user_id}")
        return canvas

    def save_canvas(
        self,
        user_id: str,
        canvas_data: dict,
        canvas_name: str = "default",
    ) -> Canvas:
        """Save or update canvas with nodes and edges.

        Creates a new canvas or updates an existing one. Replaces all nodes
        and edges with the provided data.

        Args:
            user_id: User identifier
            canvas_data: Canvas state with nodes and edges
            canvas_name: Canvas name

        Returns:
            Saved or updated canvas
        """
        # Get existing canvas for user
        canvas = self.get_by_user(user_id)

        if canvas is None:
            # Create new canvas
            canvas = Canvas(user_id=user_id, name=canvas_name)
            self.db.add(canvas)
            self.db.flush()  # Get the ID before adding nodes
        else:
            # Delete existing nodes and edges (cascade delete)
            self.db.query(Node).filter(Node.canvas_id == canvas.id).delete()
            self.db.query(Edge).filter(Edge.canvas_id == canvas.id).delete()
            canvas.name = canvas_name

        # Add new nodes
        nodes_data = canvas_data.get("nodes", [])
        for node_data in nodes_data:
            # Generate node_id if not provided
            node_id = node_data.get("id", "")
            if not node_id:
                node_id = _generate_node_id()

            # Get title from either "title" or "label" for backwards compatibility
            title = node_data.get("title") or node_data.get("label", "")

            # Convert metadata to JSON string if present
            node_metadata = None
            if node_data.get("metadata"):
                node_metadata = json.dumps(node_data["metadata"])

            node = Node(
                node_id=node_id,
                canvas_id=canvas.id,
                type=node_data.get("type", "text"),
                title=title,
                content=node_data.get("content"),
                node_metadata=node_metadata,
                x=node_data.get("x", 0),
                y=node_data.get("y", 0),
                z=node_data.get("z", 0),
            )
            self.db.add(node)

        # Add new edges
        edges_data = canvas_data.get("edges", [])
        for edge_data in edges_data:
            # Generate edge_id if not provided
            edge_id = edge_data.get("id", "")
            if not edge_id:
                edge_id = _generate_edge_id()

            edge = Edge(
                edge_id=edge_id,
                canvas_id=canvas.id,
                source_node_id=edge_data.get("sourceNodeId", ""),
                target_node_id=edge_data.get("targetNodeId", ""),
                label=edge_data.get("label"),
                type=edge_data.get("type", "solid"),
            )
            self.db.add(edge)

        self.db.commit()
        self.db.refresh(canvas)
        logger.info(
            f"Saved canvas {canvas.id} for user {user_id} "
            f"with {len(nodes_data)} nodes and {len(edges_data)} edges"
        )
        return canvas

    def delete_canvas(self, canvas_id: int) -> bool:
        """Delete canvas by ID.

        Args:
            canvas_id: Canvas identifier

        Returns:
            True if deleted, False if not found
        """
        canvas = self.get_by_id(canvas_id)
        if canvas is None:
            return False
        self.db.delete(canvas)
        self.db.commit()
        logger.info(f"Deleted canvas {canvas_id}")
        return True
