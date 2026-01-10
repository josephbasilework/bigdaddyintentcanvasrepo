"""Repository pattern layer for database access."""

# Legacy imports (for backwards compatibility)
# TODO: Update consumers to use new async repositories
from app.repositories import canvas as canvas_legacy
from app.repositories.backup import BackupRepository
from app.repositories.base import BaseRepository
from app.repositories.canvas_repo import CanvasRepository
from app.repositories.edge_repo import EdgeRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.preferences import PreferencesRepository

__all__ = [
    "BackupRepository",
    "BaseRepository",
    "CanvasRepository",
    "EdgeRepository",
    "NodeRepository",
    "PreferencesRepository",
    "canvas_legacy",
]
