"""Diff generation for incremental canvas persistence.

This module provides functions to detect changes between the current
database state and incoming workspace state, enabling incremental updates
instead of full replacement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from logging import getLogger
from typing import Any

from app.models.edge import Edge
from app.models.node import Node, normalize_node_type

logger = getLogger(__name__)


@dataclass
class NodeChange:
    """Represents a change to a node.

    Attributes:
        action: The type of change ('create', 'update', 'delete')
        node_data: Node data dict from payload (for create/update)
        db_node: Existing database node (for update/delete)
        client_id: Client-provided ID (string or None)
        db_id: Database ID (int or None)
    """

    action: str
    node_data: dict[str, Any] | None = None
    db_node: Node | None = None
    client_id: str | None = None
    db_id: int | None = None


@dataclass
class EdgeChange:
    """Represents a change to an edge.

    Attributes:
        action: The type of change ('create', 'delete')
        edge_data: Edge data dict from payload (for create)
        db_edge: Existing database edge (for delete)
        resolved_from_id: Resolved database ID for source node
        resolved_to_id: Resolved database ID for target node
    """

    action: str
    edge_data: dict[str, Any] | None = None
    db_edge: Edge | None = None
    resolved_from_id: int | None = None
    resolved_to_id: int | None = None


def _node_has_changes(db_node: Node, node_data: dict[str, Any]) -> bool:
    """Check if node data differs from database node.

    Args:
        db_node: Existing database node
        node_data: Incoming node data dict

    Returns:
        True if any field has changed, False otherwise
    """
    # Check label
    if db_node.label != node_data.get("label", ""):
        return True

    # Check type
    incoming_type = node_data.get("type")
    if incoming_type is not None:
        if normalize_node_type(db_node.type) != normalize_node_type(incoming_type):
            return True

    # Check content
    if db_node.content != node_data.get("content"):
        return True

    # Check position
    position = node_data.get("position")
    if isinstance(position, dict):
        incoming_position = position
    else:
        incoming_position = {
            "x": node_data.get("x", 0),
            "y": node_data.get("y", 0),
            "z": node_data.get("z", 0),
        }

    db_position = db_node.get_position()
    if (
        db_position.get("x") != incoming_position.get("x")
        or db_position.get("y") != incoming_position.get("y")
        or db_position.get("z") != incoming_position.get("z")
    ):
        return True

    # Check metadata
    metadata = node_data.get("metadata") or node_data.get("node_metadata")
    if metadata:
        db_metadata = db_node.get_metadata()
        if db_metadata != metadata:
            return True

    return False


def compute_node_diff(
    existing_nodes: list[Node],
    incoming_nodes: list[dict],
) -> list[NodeChange]:
    """Compute diff between existing and incoming nodes.

    Args:
        existing_nodes: List of database nodes
        incoming_nodes: List of incoming node data dicts

    Returns:
        List of NodeChange objects representing actions to take
    """
    changes: list[NodeChange] = []

    # Build maps for efficient lookup
    db_nodes_by_id: dict[int, Node] = {n.id: n for n in existing_nodes}
    processed_db_ids: set[int] = set()
    seen_client_ids: set[str] = set()

    for node_data in incoming_nodes:
        raw_id = node_data.get("id")
        client_id = str(raw_id) if raw_id is not None else None

        # Determine if this is an update or create
        if client_id and client_id.lstrip("-").isdigit():
            # Integer ID - might reference existing node
            db_id = int(client_id)
            db_node = db_nodes_by_id.get(db_id)

            if db_node is not None:
                # Existing node - check if it needs updating
                processed_db_ids.add(db_id)
                if _node_has_changes(db_node, node_data):
                    changes.append(
                        NodeChange(
                            action="update",
                            node_data=node_data,
                            db_node=db_node,
                            db_id=db_id,
                        )
                    )
                    logger.debug(f"Node {db_id} has changes, will update")
            else:
                # ID provided but node doesn't exist - treat as create
                # (might be from a different canvas or deleted)
                changes.append(
                    NodeChange(
                        action="create",
                        node_data=node_data,
                        client_id=client_id,
                    )
                )
                logger.debug(f"Node with ID {db_id} not found in DB, will create")
        else:
            # String ID or None - always create
            if client_id:
                seen_client_ids.add(client_id)
            changes.append(
                NodeChange(
                    action="create",
                    node_data=node_data,
                    client_id=client_id,
                )
            )
            logger.debug(f"New node {client_id or '(no ID)'} will be created")

    # Find nodes to delete (exist in DB but not in incoming)
    for db_id, db_node in db_nodes_by_id.items():
        if db_id not in processed_db_ids:
            changes.append(
                NodeChange(
                    action="delete",
                    db_node=db_node,
                    db_id=db_id,
                )
            )
            logger.debug(f"Node {db_id} not in incoming data, will delete")

    logger.info(
        f"Computed node diff: {sum(1 for c in changes if c.action == 'create')} creates, "
        f"{sum(1 for c in changes if c.action == 'update')} updates, "
        f"{sum(1 for c in changes if c.action == 'delete')} deletes"
    )

    return changes


def _normalize_metadata(metadata: dict[str, Any] | None) -> str | None:
    """Normalize metadata to a stable string for comparisons."""
    if not metadata:
        return None
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError:
        return json.dumps(str(metadata))


def _edge_key(edge: Edge) -> tuple:
    """Generate a key for edge comparison.

    Args:
        edge: Database edge

    Returns:
        Tuple of (from_node_id, to_node_id, relation_type, label, metadata)
    """
    return (
        edge.from_node_id,
        edge.to_node_id,
        edge.relation_type,
        edge.label,
        _normalize_metadata(edge.get_metadata()),
    )


def compute_edge_diff(
    existing_edges: list[Edge],
    incoming_edges: list[dict],
    node_id_map: dict[str, int],
) -> list[EdgeChange]:
    """Compute diff between existing and incoming edges.

    Args:
        existing_edges: List of database edges
        incoming_edges: List of incoming edge data dicts
        node_id_map: Map of client node IDs to database IDs

    Returns:
        List of EdgeChange objects representing actions to take
    """
    changes: list[EdgeChange] = []

    # Build set of existing edge keys
    existing_edge_keys: set[tuple] = {_edge_key(e) for e in existing_edges}
    processed_edge_keys: set[tuple] = set()

    for edge_data in incoming_edges:
        # Resolve node IDs
        from_node_id_raw = (
            edge_data.get("fromNodeId")
            or edge_data.get("sourceNodeId")
            or edge_data.get("from_node_id")
        )
        to_node_id_raw = (
            edge_data.get("toNodeId")
            or edge_data.get("targetNodeId")
            or edge_data.get("to_node_id")
        )

        def resolve_node_id(raw_value: Any) -> int | None:
            if raw_value is None:
                return None
            # First check the node_id_map (for client IDs)
            mapped = node_id_map.get(str(raw_value))
            if mapped is not None:
                return mapped
            # Then try as direct database ID
            try:
                if isinstance(raw_value, bool):
                    return None
                if isinstance(raw_value, int | str):
                    return int(raw_value)
                if isinstance(raw_value, float) and raw_value.is_integer():
                    return int(raw_value)
            except (ValueError, TypeError):
                return None
            return None

        from_node_id = resolve_node_id(from_node_id_raw)
        to_node_id = resolve_node_id(to_node_id_raw)

        if from_node_id is None or to_node_id is None:
            logger.debug(f"Skipping edge with unresolvable node IDs: {edge_data}")
            continue

        # Get relation type
        from app.models.edge import RelationType

        relation_type_raw = (
            edge_data.get("relationType")
            or edge_data.get("relation_type")
            or edge_data.get("type")
        )
        try:
            relation_type = RelationType(relation_type_raw) if relation_type_raw else RelationType.DEPENDS_ON
        except ValueError:
            relation_type = RelationType.DEPENDS_ON

        # Get label
        label_value = edge_data.get("label")
        label = label_value if isinstance(label_value, str) else None

        metadata_value = edge_data.get("metadata") or edge_data.get("edge_metadata")
        metadata = metadata_value if isinstance(metadata_value, dict) else None
        edge_key = (
            from_node_id,
            to_node_id,
            relation_type,
            label,
            _normalize_metadata(metadata),
        )

        if edge_key not in existing_edge_keys:
            # New edge
            changes.append(
                EdgeChange(
                    action="create",
                    edge_data=edge_data,
                    resolved_from_id=from_node_id,
                    resolved_to_id=to_node_id,
                )
            )
            logger.debug(f"New edge {from_node_id} -> {to_node_id} will be created")
        else:
            processed_edge_keys.add(edge_key)

    # Find edges to delete (exist in DB but not in incoming)
    for edge in existing_edges:
        edge_key = _edge_key(edge)
        if edge_key not in processed_edge_keys:
            changes.append(
                EdgeChange(
                    action="delete",
                    db_edge=edge,
                )
            )
            logger.debug(f"Edge {edge.from_node_id} -> {edge.to_node_id} will be deleted")

    logger.info(
        f"Computed edge diff: {sum(1 for c in changes if c.action == 'create')} creates, "
        f"{sum(1 for c in changes if c.action == 'delete')} deletes"
    )

    return changes
