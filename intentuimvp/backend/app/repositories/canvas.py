"""Repository for canvas and node operations."""

import json
from logging import getLogger

from sqlalchemy.orm import Session

from app.models.canvas import Canvas
from app.models.edge import Edge, RelationType
from app.models.node import Node, NodeType

logger = getLogger(__name__)


def _coerce_node_type(value: str | NodeType | None) -> NodeType:
    if value is None:
        return NodeType.TEXT
    if isinstance(value, NodeType):
        return value
    try:
        return NodeType(value)
    except ValueError:
        return NodeType.TEXT


def _coerce_relation_type(value: str | RelationType | None) -> RelationType:
    if value is None:
        return RelationType.DEPENDS_ON
    if isinstance(value, RelationType):
        return value
    try:
        return RelationType(value)
    except ValueError:
        return RelationType.DEPENDS_ON


def _position_from_node(node_data: dict) -> dict:
    position = node_data.get("position")
    if isinstance(position, dict):
        return position
    return {
        "x": node_data.get("x", 0),
        "y": node_data.get("y", 0),
        "z": node_data.get("z", 0),
    }


def _metadata_from_node(node_data: dict) -> dict | None:
    metadata = (
        node_data.get("metadata")
        or node_data.get("node_metadata")
        or node_data.get("nodeMetadata")
    )
    return metadata if isinstance(metadata, dict) else None


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
            self.db.query(Edge).filter(Edge.canvas_id == canvas.id).delete()
            self.db.query(Node).filter(Node.canvas_id == canvas.id).delete()
            canvas.name = canvas_name

        # Add new nodes
        nodes_data = canvas_data.get("nodes", [])
        for node_data in nodes_data:
            position = _position_from_node(node_data)
            node_metadata = _metadata_from_node(node_data)
            node_type = _coerce_node_type(node_data.get("type"))

            node = Node(
                canvas_id=canvas.id,
                type=node_type,
                label=node_data.get("label", ""),
                position=json.dumps(position),
                node_metadata=json.dumps(node_metadata) if node_metadata else None,
            )
            self.db.add(node)

        # Add new edges
        edges_data = canvas_data.get("edges", [])
        for edge_data in edges_data:
            from_node_id = (
                edge_data.get("fromNodeId")
                or edge_data.get("sourceNodeId")
                or edge_data.get("from_node_id")
            )
            to_node_id = (
                edge_data.get("toNodeId")
                or edge_data.get("targetNodeId")
                or edge_data.get("to_node_id")
            )
            if from_node_id is None or to_node_id is None:
                continue
            try:
                from_node_id = int(from_node_id)
                to_node_id = int(to_node_id)
            except (TypeError, ValueError):
                continue

            edge = Edge(
                canvas_id=canvas.id,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                relation_type=_coerce_relation_type(
                    edge_data.get("relationType")
                    or edge_data.get("relation_type")
                    or edge_data.get("type")
                ),
            )
            self.db.add(edge)

        self.db.commit()
        self.db.refresh(canvas)
        logger.info(
            f"Saved canvas {canvas.id} for user {user_id} "
            f"with {len(nodes_data)} nodes and {len(edges_data)} edges"
        )
        return canvas

    def serialize_canvas(self, canvas: Canvas, *, include_edges: bool = False) -> dict:
        """Serialize canvas with node positions for API and backups."""
        nodes = []
        for node in sorted(canvas.nodes, key=lambda n: n.id):
            position = node.get_position()
            nodes.append(
                {
                    "id": node.id,
                    "label": node.label,
                    "type": node.type,
                    "x": position.get("x", 0),
                    "y": position.get("y", 0),
                    "z": position.get("z", 0),
                    "metadata": node.get_metadata(),
                    "created_at": node.created_at.isoformat(),
                }
            )

        payload = {
            "id": canvas.id,
            "user_id": canvas.user_id,
            "name": canvas.name,
            "created_at": canvas.created_at.isoformat(),
            "updated_at": canvas.updated_at.isoformat(),
            "nodes": nodes,
        }

        if include_edges:
            payload["edges"] = [
                {
                    "id": edge.id,
                    "fromNodeId": edge.from_node_id,
                    "toNodeId": edge.to_node_id,
                    "relationType": edge.relation_type,
                    "created_at": edge.created_at.isoformat(),
                }
                for edge in sorted(canvas.edges, key=lambda e: e.id)
            ]

        return payload

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
