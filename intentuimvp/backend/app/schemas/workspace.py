"""Pydantic schemas for workspace API."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.node import NodeType


class DocumentData(BaseModel):
    """Document data for workspace save."""

    id: str | None = Field(default=None, description="Document identifier")
    node_id: str | None = Field(default=None, description="Node identifier linked to document")
    title: str | None = Field(default=None, description="Document title")
    content: str | None = Field(default=None, description="Document content")
    created_at: str | None = Field(default=None, description="Creation timestamp")
    updated_at: str | None = Field(default=None, description="Last update timestamp")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values
        node_id = values.get("node_id") or values.get("nodeId")
        created_at = values.get("created_at") or values.get("createdAt")
        updated_at = values.get("updated_at") or values.get("updatedAt")
        title = values.get("title") or values.get("label")
        return {
            **values,
            "node_id": node_id,
            "created_at": created_at,
            "updated_at": updated_at,
            "title": title,
        }


class NodeData(BaseModel):
    """Node data for workspace save."""

    id: int | str | None = Field(default=None, description="Optional node identifier")
    label: str | None = Field(default=None, description="Node label/text")
    title: str | None = Field(default=None, description="Node title (alias for label)")
    type: NodeType | str | None = Field(default=None, description="Node type")
    x: float = Field(default=0, description="X coordinate")
    y: float = Field(default=0, description="Y coordinate")
    z: float = Field(default=0, description="Z coordinate (depth)")
    position: dict | None = Field(default=None, description="Optional position payload")
    content: str | None = Field(default=None, description="Optional node content")
    metadata: dict | None = Field(default=None, description="Optional node metadata")

    @model_validator(mode="before")
    @classmethod
    def normalize_label(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values
        label = values.get("label")
        if label:
            return values
        title = values.get("title")
        return {**values, "label": title or "Untitled"}


class WorkspaceSaveRequest(BaseModel):
    """Request body for saving workspace state."""

    nodes: list[NodeData] = Field(default_factory=list, description="List of nodes in workspace")
    edges: list[dict] = Field(default_factory=list, description="List of edges in workspace")
    documents: list[DocumentData] = Field(
        default_factory=list, description="List of documents in workspace"
    )
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
    edges: list[dict] = Field(default_factory=list)
    documents: list[dict] = Field(default_factory=list)


class EmptyWorkspaceResponse(BaseModel):
    """Response when no workspace exists for user."""

    nodes: list = Field(default_factory=list, description="Empty node list")
    edges: list = Field(default_factory=list, description="Empty edge list")
    documents: list = Field(default_factory=list, description="Empty document list")
    name: str = Field(default="default", description="Default workspace name")
