"""Pydantic schemas for node API."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.node import NodeType


class NodePosition(BaseModel):
    """Node position coordinates."""

    x: float = Field(default=0, description="X coordinate")
    y: float = Field(default=0, description="Y coordinate")
    z: float = Field(default=0, description="Z coordinate (depth)")


class NodePositionUpdate(BaseModel):
    """Partial updates to node position."""

    x: float | None = Field(default=None, description="X coordinate")
    y: float | None = Field(default=None, description="Y coordinate")
    z: float | None = Field(default=None, description="Z coordinate (depth)")


class NodeCreateRequest(BaseModel):
    """Request body for creating a node."""

    canvas_id: int = Field(..., description="Canvas identifier")
    label: str = Field(..., description="Node label/text")
    type: NodeType = Field(default=NodeType.TEXT, description="Node type")
    position: NodePosition = Field(
        default_factory=NodePosition,
        description="Node position coordinates",
    )
    metadata: dict | None = Field(default=None, description="Optional node metadata")


class NodeUpdateRequest(BaseModel):
    """Request body for updating a node."""

    label: str | None = Field(default=None, description="Updated node label")
    type: NodeType | None = Field(default=None, description="Updated node type")
    position: NodePositionUpdate | None = Field(
        default=None,
        description="Updated node position",
    )
    metadata: dict | None = Field(default=None, description="Updated node metadata")


class NodeResponse(BaseModel):
    """Response model for node data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    canvas_id: int
    type: NodeType
    label: str
    position: NodePosition
    metadata: dict
    created_at: str


class NodeListResponse(BaseModel):
    """Response model for listing nodes."""

    nodes: list[NodeResponse]
    count: int
