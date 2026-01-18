"""Node API endpoints for CRUD operations."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.dashboard_subscription import DashboardSubscriptionTarget
from app.models.node import Node
from app.models.turn import TurnActor, TurnType
from app.repositories.node_repo import NodeRepository
from app.repositories.turn_repo import AsyncTurnRepository
from app.schemas.node import (
    BatchDeleteByTurnRequest,
    BatchDeleteByTurnResponse,
    NodeCreateRequest,
    NodeListResponse,
    NodeResponse,
    NodeUpdateRequest,
)
from app.services.dashboard_updates import publish_dashboard_update
from app.services.turns import (
    log_turn_for_user_async,
    log_turn_with_session_id_async,
    resolve_session_id_async,
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
        "content": node.content,
        "position": node.get_position(),
        "metadata": node.get_metadata(),
        "created_at": node.created_at.isoformat(),
        "created_by_turn_id": node.created_by_turn_id,
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
            content=payload.content,
            node_metadata=payload.metadata,
        )
        node_payload = _serialize_node(node)
        await publish_dashboard_update(
            canvas_id=node.canvas_id,
            target=DashboardSubscriptionTarget.NODE,
            source_id=str(node.id),
            change_type="created",
            data=node_payload,
        )
        await log_turn_for_user_async(
            db,
            user_id=user_id,
            workspace_id=node.canvas_id,
            actor=TurnActor.USER,
            turn_type=TurnType.NODE_CREATED,
            summary=f"Node created: {node.label}" if node.label else "Node created",
            payload=node_payload,
            related_node_id=node.id,
        )
        logger.info(f"Created node {node.id} on canvas {payload.canvas_id} for user {user_id}")
        return node_payload
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
    if "content" in fields_set:
        updates["content"] = payload.content
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
        updated_payload = _serialize_node(updated)
        await publish_dashboard_update(
            canvas_id=updated.canvas_id,
            target=DashboardSubscriptionTarget.NODE,
            source_id=str(updated.id),
            change_type="updated",
            data=updated_payload,
        )
        session_id = await resolve_session_id_async(
            db,
            user_id=user_id,
            workspace_id=updated.canvas_id,
        )
        if session_id:
            turn_repo = AsyncTurnRepository(db)
            origin_turn = await turn_repo.get_latest_turn_for_node(
                session_id,
                updated.id,
                turn_types=[TurnType.NODE_CREATED, TurnType.NODE_UPDATED],
            )
            await log_turn_with_session_id_async(
                db,
                session_id=session_id,
                actor=TurnActor.USER,
                turn_type=TurnType.NODE_UPDATED,
                summary=f"Node updated: {updated.label}"
                if updated.label
                else "Node updated",
                payload={
                    "node": updated_payload,
                    "updates": updates,
                },
                related_node_id=updated.id,
                origin_sequence_number=origin_turn.sequence_number if origin_turn else None,
            )
        else:
            logger.warning("No session_id available for turn %s", TurnType.NODE_UPDATED)
        logger.info(f"Updated node {node_id} for user {user_id}")
        return updated_payload
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
    node = await repo.get_by_id(node_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    deleted = await repo.delete(node_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    deleted_payload = _serialize_node(node)
    await publish_dashboard_update(
        canvas_id=node.canvas_id,
        target=DashboardSubscriptionTarget.NODE,
        source_id=str(node.id),
        change_type="deleted",
        data=deleted_payload,
    )
    session_id = await resolve_session_id_async(
        db,
        user_id=user_id,
        workspace_id=node.canvas_id,
    )
    if session_id:
        turn_repo = AsyncTurnRepository(db)
        origin_turn = await turn_repo.get_latest_turn_for_node(
            session_id,
            node.id,
            turn_types=[TurnType.NODE_CREATED, TurnType.NODE_UPDATED],
        )
        await log_turn_with_session_id_async(
            db,
            session_id=session_id,
            actor=TurnActor.USER,
            turn_type=TurnType.NODE_DELETED,
            summary=f"Node deleted: {node.label}" if node.label else "Node deleted",
            payload=deleted_payload,
            related_node_id=node.id,
            origin_sequence_number=origin_turn.sequence_number if origin_turn else None,
        )
    else:
        logger.warning("No session_id available for turn %s", TurnType.NODE_DELETED)
    logger.info(f"Deleted node {node_id} for user {user_id}")


@router.post(
    "/api/nodes/batch-delete-by-turn",
    response_model=BatchDeleteByTurnResponse,
    status_code=status.HTTP_200_OK,
)
async def batch_delete_by_turn(
    payload: BatchDeleteByTurnRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Delete all nodes created by a specific turn.

    This endpoint enables batch deletion of agent-created nodes by referencing
    the turn that created them. Useful for "undo what the agent just did" operations.

    Args:
        payload: Contains the turn_id whose nodes should be deleted
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of deleted node IDs and count

    Raises:
        HTTPException: If deletion fails
    """
    try:
        repo = NodeRepository(db)

        # Get all nodes created by this turn before deleting
        nodes = await repo.get_by_turn_id(payload.turn_id)

        if not nodes:
            logger.info(
                f"No nodes found for turn {payload.turn_id} (user {user_id})"
            )
            return {"deleted_node_ids": [], "deleted_count": 0}

        # Get canvas_id from first node for session resolution
        canvas_id = nodes[0].canvas_id

        # Collect node info for logging before deletion
        deleted_nodes_info = []
        for node in nodes:
            deleted_nodes_info.append(_serialize_node(node))

        # Delete all nodes
        deleted_ids = await repo.delete_by_turn_id(payload.turn_id)

        # Publish dashboard updates for each deleted node
        for node_info in deleted_nodes_info:
            await publish_dashboard_update(
                canvas_id=canvas_id,
                target=DashboardSubscriptionTarget.NODE,
                source_id=str(node_info["id"]),
                change_type="deleted",
                data=node_info,
            )

        # Log turn for batch deletion
        session_id = await resolve_session_id_async(
            db,
            user_id=user_id,
            workspace_id=canvas_id,
        )
        if session_id:
            await log_turn_with_session_id_async(
                db,
                session_id=session_id,
                actor=TurnActor.USER,
                turn_type=TurnType.NODE_DELETED,
                summary=f"Batch deleted {len(deleted_ids)} nodes from turn {payload.turn_id}",
                payload={
                    "batch_delete": True,
                    "source_turn_id": payload.turn_id,
                    "deleted_node_ids": deleted_ids,
                    "deleted_nodes": deleted_nodes_info,
                },
                origin_sequence_number=None,
            )
        else:
            logger.warning("No session_id available for batch delete turn logging")

        logger.info(
            f"Batch deleted {len(deleted_ids)} nodes from turn {payload.turn_id} "
            f"for user {user_id}"
        )
        return {"deleted_node_ids": deleted_ids, "deleted_count": len(deleted_ids)}

    except Exception as e:
        logger.error(
            f"Failed to batch delete nodes for turn {payload.turn_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch delete nodes",
        ) from e


@router.get(
    "/api/nodes/by-turn/{turn_id}",
    response_model=NodeListResponse,
)
async def get_nodes_by_turn(
    turn_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get all nodes created by a specific turn.

    This endpoint allows querying nodes by their originating turn,
    useful for understanding what content an agent created in a specific action.

    Args:
        turn_id: The turn ID to filter by
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of nodes created by the specified turn
    """
    repo = NodeRepository(db)
    nodes = await repo.get_by_turn_id(turn_id)

    logger.info(
        f"Retrieved {len(nodes)} nodes for turn {turn_id} (user {user_id})"
    )
    return {
        "nodes": [_serialize_node(node) for node in nodes],
        "count": len(nodes),
    }
