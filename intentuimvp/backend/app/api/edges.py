"""Edge API endpoints for CRUD operations."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.edge import Edge
from app.repositories.edge_repo import EdgeRepository
from app.repositories.node_repo import NodeRepository
from app.schemas.edge import (
    EdgeCreateRequest,
    EdgeListResponse,
    EdgeResponse,
    EdgeUpdateRequest,
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


def _serialize_edge(edge: Edge) -> dict[str, Any]:
    """Serialize edge model to API response payload."""
    return {
        "id": edge.id,
        "canvas_id": edge.canvas_id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "relation_type": edge.relation_type,
        "created_at": edge.created_at.isoformat(),
    }


async def _validate_edge_nodes(
    payload: EdgeCreateRequest,
    db: AsyncSession,
) -> None:
    node_repo = NodeRepository(db)
    from_node = await node_repo.get_by_id(payload.from_node_id)
    if from_node is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid from_node_id",
        )

    to_node = await node_repo.get_by_id(payload.to_node_id)
    if to_node is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid to_node_id",
        )

    if from_node.canvas_id != payload.canvas_id or to_node.canvas_id != payload.canvas_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nodes must belong to the same canvas",
        )


@router.post("/api/edges", response_model=EdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_edge(
    payload: EdgeCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Create a new edge.

    Args:
        payload: Edge creation data
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Created edge data

    Raises:
        HTTPException: If edge creation fails
    """
    await _validate_edge_nodes(payload, db)
    try:
        repo = EdgeRepository(db)
        edge = await repo.create_edge(
            canvas_id=payload.canvas_id,
            from_node_id=payload.from_node_id,
            to_node_id=payload.to_node_id,
            relation_type=payload.relation_type,
        )
        logger.info(
            f"Created edge {edge.id} on canvas {payload.canvas_id} for user {user_id}"
        )
        return _serialize_edge(edge)
    except IntegrityError as e:
        logger.warning(
            f"Failed to create edge on canvas {payload.canvas_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid canvas_id",
        ) from e
    except Exception as e:
        logger.error(f"Failed to create edge for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create edge",
        ) from e


@router.get("/api/edges", response_model=EdgeListResponse)
async def list_edges(
    canvas_id: int | None = Query(default=None, description="Filter edges by canvas ID"),
    node_id: int | None = Query(default=None, description="Filter edges by node ID"),
    as_source: bool = Query(default=True, description="Include edges where node is the source"),
    as_target: bool = Query(default=True, description="Include edges where node is the target"),
    offset: int = Query(default=0, ge=0, description="Number of edges to skip"),
    limit: int = Query(default=100, ge=1, le=500, description="Max edges to return"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List edges with optional filters.

    Args:
        canvas_id: Optional canvas identifier to filter edges
        node_id: Optional node identifier to filter edges
        as_source: Include edges where node is the source
        as_target: Include edges where node is the target
        offset: Pagination offset
        limit: Pagination limit
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of edge data with count
    """
    repo = EdgeRepository(db)
    if node_id is not None:
        edges = await repo.get_by_node(
            node_id,
            as_source=as_source,
            as_target=as_target,
        )
        if canvas_id is not None:
            edges = [edge for edge in edges if edge.canvas_id == canvas_id]
        edges = edges[offset : offset + limit]
        logger.info(
            f"Retrieved {len(edges)} edges for node {node_id} (user {user_id})"
        )
    elif canvas_id is not None:
        edges = await repo.get_by_canvas(canvas_id, offset=offset, limit=limit)
        logger.info(
            f"Retrieved {len(edges)} edges for canvas {canvas_id} (user {user_id})"
        )
    else:
        edges = await repo.list(offset=offset, limit=limit)
        logger.info(f"Retrieved {len(edges)} edges for user {user_id}")

    return {
        "edges": [_serialize_edge(edge) for edge in edges],
        "count": len(edges),
    }


@router.get("/api/edges/{edge_id}", response_model=EdgeResponse)
async def get_edge(
    edge_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get edge by ID.

    Args:
        edge_id: Edge identifier
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Edge data

    Raises:
        HTTPException: If edge not found
    """
    repo = EdgeRepository(db)
    edge = await repo.get_by_id(edge_id)
    if edge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edge not found",
        )

    logger.info(f"Retrieved edge {edge_id} for user {user_id}")
    return _serialize_edge(edge)


@router.put("/api/edges/{edge_id}", response_model=EdgeResponse)
async def update_edge(
    edge_id: int,
    payload: EdgeUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Update edge by ID.

    Args:
        edge_id: Edge identifier
        payload: Edge update data
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Updated edge data

    Raises:
        HTTPException: If edge not found or update fails
    """
    repo = EdgeRepository(db)
    edge = await repo.get_by_id(edge_id)
    if edge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edge not found",
        )

    updates: dict[str, Any] = {}
    fields_set = payload.model_fields_set

    if "relation_type" in fields_set:
        if payload.relation_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Relation type cannot be null",
            )
        updates["relation_type"] = payload.relation_type

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    try:
        updated = await repo.update(edge_id, **updates)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Edge not found",
            )
        logger.info(f"Updated edge {edge_id} for user {user_id}")
        return _serialize_edge(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update edge {edge_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update edge",
        ) from e


@router.delete("/api/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edge(
    edge_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> None:
    """Delete edge by ID.

    Args:
        edge_id: Edge identifier
        db: Database session
        user_id: Authenticated user ID

    Raises:
        HTTPException: If edge not found
    """
    repo = EdgeRepository(db)
    deleted = await repo.delete(edge_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edge not found",
        )
    logger.info(f"Deleted edge {edge_id} for user {user_id}")
