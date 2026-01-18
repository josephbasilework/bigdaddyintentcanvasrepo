"""Pydantic schemas for node API."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.node import NodeType

# FR-012: Schemas for Multi-Judge Compute nodes (critic + synthesis)


class PerspectiveSchema(BaseModel):
    """Schema for individual perspective data (stored in critic nodes)."""

    id: str = Field(description="Unique perspective identifier")
    name: str = Field(description="Name of this perspective (skeptic, advocate, synthesizer)")
    description: str = Field(description="Description of the viewpoint")
    stance: str = Field(description="Overall stance (pro, con, neutral)")
    arguments: list[str] = Field(description="Key arguments from this perspective")
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this perspective")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    failed: bool = Field(default=False, description="True if perspective generation failed")
    failure_reason: str | None = Field(default=None, description="Reason for failure")


class BiasAnalysisSchema(BaseModel):
    """Schema for bias analysis (stored in synthesis nodes)."""

    detected_biases: list[str] = Field(default_factory=list)
    bias_explanations: list[str] = Field(default_factory=list)
    mitigation_suggestions: list[str] = Field(default_factory=list)
    overall_bias_rating: str = Field(default="unknown", description="low, medium, high")


class CriticNodeMetadata(BaseModel):
    """Metadata for critic nodes (FR-012).

    Critic nodes store individual perspective evaluations from the multi-judge compute.
    Each critic node represents one perspective (skeptic, advocate, or synthesizer).
    """

    topic: str = Field(description="Topic being analyzed")
    perspective_type: str = Field(description="Type: skeptic, advocate, or synthesizer")
    perspective: PerspectiveSchema = Field(description="The perspective evaluation data")
    source_node_id: int | None = Field(
        default=None, description="ID of the node this analysis targets"
    )


class SynthesisNodeMetadata(BaseModel):
    """Metadata for synthesis nodes (FR-012).

    Synthesis nodes store the combined multi-perspective analysis including:
    - All individual perspectives
    - Consensus and disagreement points
    - Bias analysis
    - Overall recommendation
    """

    topic: str = Field(description="Topic being analyzed")
    perspectives: list[PerspectiveSchema] = Field(description="All perspectives analyzed")
    consensus_points: list[str] = Field(default_factory=list)
    disagreement_points: list[str] = Field(default_factory=list)
    bias_analysis: BiasAnalysisSchema | None = Field(
        default=None, description="Analysis of potential biases"
    )
    recommendation: str = Field(description="Overall assessment")
    confidence: float = Field(ge=0.0, le=1.0)
    source_node_ids: list[int] = Field(
        default_factory=list, description="IDs of critic nodes this synthesis combines"
    )


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
    content: str | None = Field(default=None, description="Optional node content")
    position: NodePosition = Field(
        default_factory=NodePosition,
        description="Node position coordinates",
    )
    metadata: dict | None = Field(default=None, description="Optional node metadata")


class NodeUpdateRequest(BaseModel):
    """Request body for updating a node."""

    label: str | None = Field(default=None, description="Updated node label")
    content: str | None = Field(default=None, description="Updated node content")
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
    content: str | None
    position: NodePosition
    metadata: dict
    created_at: str


class NodeListResponse(BaseModel):
    """Response model for listing nodes."""

    nodes: list[NodeResponse]
    count: int
