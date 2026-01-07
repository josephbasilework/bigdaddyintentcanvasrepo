"""Repository for canvas and node operations."""

from logging import getLogger

from sqlalchemy.orm import Session

from app.models.canvas import Canvas, Node

logger = getLogger(__name__)


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
        """Save or update canvas with nodes.

        Creates a new canvas or updates an existing one. Replaces all nodes
        with the provided node data.

        Args:
            user_id: User identifier
            canvas_data: Canvas state with nodes
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
            # Delete existing nodes (cascade delete)
            self.db.query(Node).filter(Node.canvas_id == canvas.id).delete()
            canvas.name = canvas_name

        # Add new nodes
        nodes_data = canvas_data.get("nodes", [])
        for node_data in nodes_data:
            node = Node(
                canvas_id=canvas.id,
                label=node_data.get("label", ""),
                x=node_data.get("x", 0),
                y=node_data.get("y", 0),
                z=node_data.get("z", 0),
            )
            self.db.add(node)

        self.db.commit()
        self.db.refresh(canvas)
        logger.info(f"Saved canvas {canvas.id} for user {user_id} with {len(nodes_data)} nodes")
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
