"""Pydantic schemas for workspace API."""

from pydantic import BaseModel, ConfigDict, Field


class NodeData(BaseModel):
    """Node data for workspace save."""

    label: str = Field(..., description="Node label/text")
    x: float = Field(default=0, description="X coordinate")
    y: float = Field(default=0, description="Y coordinate")
    z: float = Field(default=0, description="Z coordinate (depth)")


class WorkspaceSaveRequest(BaseModel):
    """Request body for saving workspace state."""

    nodes: list[NodeData] = Field(default_factory=list, description="List of nodes in workspace")
    name: str = Field(default="default", description="Canvas/workspace name")


class CanvasResponse(BaseModel):
    """Response for canvas state."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    name: str
    created_at: str
    updated_at: str
    nodes: list[dict]


class EmptyWorkspaceResponse(BaseModel):
    """Response when no workspace exists for user."""

    nodes: list = Field(default_factory=list, description="Empty node list")
    name: str = Field(default="default", description="Default workspace name")
