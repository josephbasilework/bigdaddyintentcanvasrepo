"""Workspace API endpoints for saving and loading canvas state."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.canvas import CanvasRepository
from app.schemas.workspace import CanvasResponse, EmptyWorkspaceResponse, WorkspaceSaveRequest

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user() -> str:
    """Get current user from authentication.

    Basic implementation using a simple header.
    TODO: Replace with proper JWT/OAuth authentication.

    Returns:
        User ID string

    Raises:
        HTTPException: If authentication fails
    """
    # Basic authentication for MVP - extract user from header
    # In production, use JWT or OAuth
    return "default_user"  # MVP: single user for now


@router.get("/api/workspace", response_model=CanvasResponse | EmptyWorkspaceResponse)
async def get_workspace(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get user's workspace canvas state.

    Returns the most recently updated canvas for the authenticated user.
    If no canvas exists, returns an empty workspace.

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Canvas state with nodes, or empty workspace if none exists
    """
    repo = CanvasRepository(db)
    canvas = repo.get_by_user(user_id)

    if canvas is None:
        logger.info(f"No canvas found for user {user_id}, returning empty workspace")
        return EmptyWorkspaceResponse().model_dump()

    logger.info(f"Retrieved canvas {canvas.id} for user {user_id}")
    return canvas.to_dict()


@router.put("/api/workspace", response_model=CanvasResponse)
async def save_workspace(
    payload: WorkspaceSaveRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Save or update workspace canvas state.

    Creates a new canvas or updates an existing one for the authenticated user.
    Replaces all nodes with the provided node data.

    Args:
        payload: Workspace state with nodes
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Saved canvas state

    Raises:
        HTTPException: If save fails
    """
    try:
        repo = CanvasRepository(db)
        canvas_data = {
            "nodes": [node.model_dump() for node in payload.nodes],
        }

        canvas = repo.save_canvas(
            user_id=user_id,
            canvas_data=canvas_data,
            canvas_name=payload.name,
        )

        logger.info(f"Saved canvas {canvas.id} for user {user_id}")
        return canvas.to_dict()

    except Exception as e:
        logger.error(f"Failed to save workspace for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save workspace",
        ) from e
