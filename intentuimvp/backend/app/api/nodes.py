"""Node API endpoints for CRUD operations."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.node import Node
from app.repositories.node_repo import NodeRepository
from app.schemas.node import (
    NodeCreateRequest,
    NodeListResponse,
    NodeResponse,
    NodeUpdateRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user() -> str:
    """Get current user from authentication.

    Basic implementation using a simple header.
    TODO: Replace with proper JWT/OAuth authentication.

    Returns:
        User ID string
    """
    return "default_user"  # MVP: single user for now


def _serialize_node(node: Node) -> dict[str, Any]:
    """Serialize node model to API response payload."""
    return {
        "id": node.id,
        "canvas_id": node.canvas_id,
        "type": node.type,
        "label": node.label,
        "position": node.get_position(),
        "metadata": node.get_metadata(),
        "created_at": node.created_at.isoformat(),
    }


@router.post("/api/nodes", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    payload: NodeCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Create a new node.

    Args:
        payload: Node creation data
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Created node data

    Raises:
        HTTPException: If node creation fails
    """
    try:
        repo = NodeRepository(db)
        node = await repo.create_node(
            canvas_id=payload.canvas_id,
            label=payload.label,
            type=payload.type,
            position=payload.position.model_dump(),
            node_metadata=payload.metadata,
        )
        logger.info(f"Created node {node.id} on canvas {payload.canvas_id} for user {user_id}")
        return _serialize_node(node)
    except IntegrityError as e:
        logger.warning(
            f"Failed to create node on canvas {payload.canvas_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid canvas_id",
        ) from e
    except Exception as e:
        logger.error(f"Failed to create node for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create node",
        ) from e


@router.get("/api/nodes", response_model=NodeListResponse)
async def list_nodes(
    canvas_id: int | None = Query(default=None, description="Filter nodes by canvas ID"),
    offset: int = Query(default=0, ge=0, description="Number of nodes to skip"),
    limit: int = Query(default=100, ge=1, le=500, description="Max nodes to return"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List nodes with optional canvas filter.

    Args:
        canvas_id: Optional canvas identifier to filter nodes
        offset: Pagination offset
        limit: Pagination limit
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of node data with count
    """
    repo = NodeRepository(db)
    if canvas_id is not None:
        nodes = await repo.get_by_canvas(canvas_id, offset=offset, limit=limit)
        logger.info(
            f"Retrieved {len(nodes)} nodes for canvas {canvas_id} (user {user_id})"
        )
    else:
        nodes = await repo.list(offset=offset, limit=limit)
        logger.info(f"Retrieved {len(nodes)} nodes for user {user_id}")

    return {
        "nodes": [_serialize_node(node) for node in nodes],
        "count": len(nodes),
    }


@router.get("/api/nodes/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get node by ID.

    Args:
        node_id: Node identifier
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Node data

    Raises:
        HTTPException: If node not found
    """
    repo = NodeRepository(db)
    node = await repo.get_by_id(node_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )

    logger.info(f"Retrieved node {node_id} for user {user_id}")
    return _serialize_node(node)


@router.put("/api/nodes/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: int,
    payload: NodeUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Update node by ID.

    Args:
        node_id: Node identifier
        payload: Node update data
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Updated node data

    Raises:
        HTTPException: If node not found or update fails
    """
    repo = NodeRepository(db)
    node = await repo.get_by_id(node_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )

    updates: dict[str, Any] = {}
    fields_set = payload.model_fields_set

    if "label" in fields_set:
        if payload.label is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Label cannot be null",
            )
        updates["label"] = payload.label
    if "type" in fields_set:
        if payload.type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Type cannot be null",
            )
        updates["type"] = payload.type
    if "metadata" in fields_set:
        if payload.metadata is None:
            updates["node_metadata"] = None
        else:
            updates["node_metadata"] = json.dumps(payload.metadata)
    if "position" in fields_set:
        if payload.position is None:
            updated_position = {"x": 0, "y": 0, "z": 0}
        else:
            position_updates = payload.position.model_dump(exclude_unset=True)
            position_updates = {
                key: value
                for key, value in position_updates.items()
                if value is not None
            }
            if position_updates:
                current_position = node.get_position()
                updated_position = {**current_position, **position_updates}
            else:
                updated_position = node.get_position()
        updates["position"] = json.dumps(updated_position)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    try:
        updated = await repo.update(node_id, **updates)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Node not found",
            )
        logger.info(f"Updated node {node_id} for user {user_id}")
        return _serialize_node(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update node {node_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update node",
        ) from e


@router.delete("/api/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> None:
    """Delete node by ID.

    Args:
        node_id: Node identifier
        db: Database session
        user_id: Authenticated user ID

    Raises:
        HTTPException: If node not found
    """
    repo = NodeRepository(db)
    deleted = await repo.delete(node_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    logger.info(f"Deleted node {node_id} for user {user_id}")
