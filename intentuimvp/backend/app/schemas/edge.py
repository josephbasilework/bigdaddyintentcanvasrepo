"""Pydantic schemas for edge API."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.edge import RelationType


class EdgeCreateRequest(BaseModel):
    """Request body for creating an edge."""

    canvas_id: int = Field(..., description="Canvas identifier")
    from_node_id: int = Field(..., description="Source node identifier")
    to_node_id: int = Field(..., description="Target node identifier")
    label: str | None = Field(default=None, description="Optional edge label")
    relation_type: RelationType = Field(
        default=RelationType.DEPENDS_ON,
        description="Edge relation type",
    )


class EdgeUpdateRequest(BaseModel):
    """Request body for updating an edge."""

    relation_type: RelationType | None = Field(
        default=None,
        description="Updated relation type",
    )
    label: str | None = Field(default=None, description="Updated edge label")


class EdgeResponse(BaseModel):
    """Response model for edge data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    canvas_id: int
    from_node_id: int
    to_node_id: int
    relation_type: RelationType
    label: str | None = None
    created_at: str


class EdgeListResponse(BaseModel):
    """Response model for listing edges."""

    edges: list[EdgeResponse]
    count: int
