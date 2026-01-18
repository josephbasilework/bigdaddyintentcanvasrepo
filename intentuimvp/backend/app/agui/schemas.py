"""AG-UI Protocol Schemas.

This module defines Pydantic models for AG-UI protocol messages,
matching the frontend TypeScript protocol definition in
intentuimvp/frontend/src/agui/protocol.ts.

Protocol Version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.event import EventResponse
from app.schemas.turn import TurnResponse

# ============================================================================
# Protocol Constants
# ============================================================================

AGUI_PROTOCOL_VERSION: str = "1.0.0"


# ============================================================================
# Base Envelope
# ============================================================================

class AGUIEnvelope(BaseModel):
    """Base message envelope for all AG-UI communications.

    All messages exchanged between agents and the UI must include these
    standard metadata fields for tracking and routing.
    """

    version: str = Field(
        default=AGUI_PROTOCOL_VERSION,
        description="Protocol version",
    )
    message_id: str = Field(
        default_factory=lambda: f"msg-{datetime.now().timestamp()}-{uuid4().hex[:8]}",
        description="Unique message identifier",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Message timestamp (UTC)",
    )
    source: Literal["agent", "ui"] = Field(
        description="Message sender: 'agent' or 'ui'",
    )
    target: Literal["agent", "ui"] = Field(
        description="Message recipient: 'agent' or 'ui'",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for request/response pairing",
    )


# ============================================================================
# Agent -> UI Messages
# ============================================================================

class AgentToUIMessage(AGUIEnvelope):
    """Base type for messages sent from Agent to UI."""

    source: Literal["agent"] = "agent"  # type: ignore[reportIncompatibleVariableOverride]
    target: Literal["ui"] = "ui"  # type: ignore[reportIncompatibleVariableOverride]


class AgentStatusPayload(BaseModel):
    """Payload for agent status updates."""

    status: Literal["idle", "working", "waiting", "error"]
    agent_id: str
    agent_name: str
    message: str | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)


class AgentStatusMessage(AgentToUIMessage):
    """Agent status update (working, idle, error)."""

    type: Literal["status"] = "status"
    payload: AgentStatusPayload


class AgentProgressPayload(BaseModel):
    """Payload for agent progress updates."""

    agent_id: str
    operation: str
    progress: float = Field(ge=0.0, le=1.0)
    message: str | None = None
    total: int | None = None
    current: int | None = None


class AgentProgressMessage(AgentToUIMessage):
    """Agent progress update for long-running operations."""

    type: Literal["progress"] = "progress"
    payload: AgentProgressPayload


class AgentResultPayload(BaseModel):
    """Payload for agent operation results."""

    agent_id: str
    operation: str
    result: Any
    correlation_id: str | None = None


class AgentResultMessage(AgentToUIMessage):
    """Agent result (successful operation outcome)."""

    type: Literal["result"] = "result"
    payload: AgentResultPayload


class AgentErrorPayload(BaseModel):
    """Payload for agent error notifications."""

    agent_id: str
    error: str
    code: str | None = None
    details: dict[str, Any] | None = None
    recoverable: bool | None = None


class AgentErrorMessage(AgentToUIMessage):
    """Agent error notification."""

    type: Literal["error"] = "error"
    payload: AgentErrorPayload


class AgentRequestPayload(BaseModel):
    """Payload for agent requests to the UI."""

    agent_id: str
    request_id: str
    request_type: Literal["input", "confirmation", "choice", "file"]
    prompt: str
    placeholder: str | None = None
    choices: list[dict[str, Any]] | None = None
    default: str | None = None
    required: bool | None = None


class AgentRequestMessage(AgentToUIMessage):
    """Agent request for user input or confirmation."""

    type: Literal["request"] = "request"
    payload: AgentRequestPayload


class AgentNotificationPayload(BaseModel):
    """Payload for agent notifications."""

    level: Literal["info", "success", "warning"]
    title: str
    message: str
    duration: int | None = None  # Auto-dismiss after ms (0 = no auto-dismiss)
    actions: list[dict[str, Any]] | None = None


class AgentNotificationMessage(AgentToUIMessage):
    """Agent notification (info, warning, success)."""

    type: Literal["notification"] = "notification"
    payload: AgentNotificationPayload


class JobProgressPayload(BaseModel):
    """Payload for job progress updates."""

    job_id: str
    job_type: str
    status: str
    progress_percent: float = Field(ge=0.0, le=100.0)
    current_step: str | None = None
    step_number: int | None = None
    steps_total: int | None = None
    data: dict[str, Any] | None = None
    event_type: str | None = None
    timestamp: datetime | None = None


class JobProgressMessage(AgentToUIMessage):
    """Job progress update for background work."""

    type: Literal["job.progress"] = "job.progress"
    payload: JobProgressPayload


# ============================================================================
# Canvas Event Messages
# ============================================================================


class NodeEventPayload(BaseModel):
    """Payload for node CRUD event messages."""

    id: str
    type: str | None = None
    title: str | None = None
    content: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    position: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    previous: dict[str, Any] | None = None
    updates: dict[str, Any] | None = None
    canvas_id: int | None = None


class NodeCreatedMessage(AgentToUIMessage):
    """Node created event message."""

    type: Literal["node.created"] = "node.created"
    payload: NodeEventPayload


class NodeUpdatedMessage(AgentToUIMessage):
    """Node updated event message."""

    type: Literal["node.updated"] = "node.updated"
    payload: NodeEventPayload


class NodeDeletedMessage(AgentToUIMessage):
    """Node deleted event message."""

    type: Literal["node.deleted"] = "node.deleted"
    payload: NodeEventPayload


class EdgeEventPayload(BaseModel):
    """Payload for edge CRUD event messages."""

    id: str
    from_node_id: str | None = None
    to_node_id: str | None = None
    fromNodeId: str | None = None
    toNodeId: str | None = None
    sourceNodeId: str | None = None
    targetNodeId: str | None = None
    relation_type: str | None = None
    relationType: str | None = None
    label: str | None = None
    metadata: dict[str, Any] | None = None
    canvas_id: int | None = None


class EdgeCreatedMessage(AgentToUIMessage):
    """Edge created event message."""

    type: Literal["edge.created"] = "edge.created"
    payload: EdgeEventPayload


class EdgeUpdatedMessage(AgentToUIMessage):
    """Edge updated event message."""

    type: Literal["edge.updated"] = "edge.updated"
    payload: EdgeEventPayload


class EdgeDeletedMessage(AgentToUIMessage):
    """Edge deleted event message."""

    type: Literal["edge.deleted"] = "edge.deleted"
    payload: EdgeEventPayload


# ============================================================================
# Run Lifecycle Messages
# ============================================================================


class RunStartPayload(BaseModel):
    """Payload for run.start events.

    Sent when an agent run begins, containing the run context and metadata.
    """

    run_id: str = Field(..., description="Unique run identifier")
    agent_id: str = Field(..., description="Agent identifier")
    agent_name: str = Field(..., description="Human-readable agent name")
    input_data: dict[str, Any] = Field(
        ..., description="Input data for the run (messages, context, etc.)"
    )
    tools: list[str] = Field(
        default_factory=list, description="List of available tools for this run"
    )


class RunStartMessage(AgentToUIMessage):
    """Message sent when an agent run starts."""

    type: Literal["run.start"] = "run.start"
    payload: RunStartPayload


class RunEndPayload(BaseModel):
    """Payload for run.end events.

    Sent when an agent run completes (success or failure).
    """

    run_id: str = Field(..., description="Unique run identifier")
    agent_id: str = Field(..., description="Agent identifier")
    status: Literal["success", "error", "cancelled"] = Field(
        ..., description="Final run status"
    )
    result: dict[str, Any] | None = Field(
        default=None, description="Run result data (on success)"
    )
    error: str | None = Field(default=None, description="Error message (on failure)")
    duration_ms: float | None = Field(
        default=None, description="Run duration in milliseconds"
    )


class RunEndMessage(AgentToUIMessage):
    """Message sent when an agent run ends."""

    type: Literal["run.end"] = "run.end"
    payload: RunEndPayload


class ToolCallPayload(BaseModel):
    """Payload for tool.call events.

    Sent when an agent calls a tool during execution.
    """

    run_id: str = Field(..., description="Unique run identifier")
    tool_name: str = Field(..., description="Name of the tool being called")
    tool_args: dict[str, Any] = Field(
        ..., description="Arguments passed to the tool"
    )
    call_id: str = Field(
        default_factory=lambda: f"call-{datetime.now().timestamp()}-{uuid4().hex[:8]}",
        description="Unique tool call identifier",
    )


class ToolCallMessage(AgentToUIMessage):
    """Message sent when an agent calls a tool."""

    type: Literal["tool.call"] = "tool.call"
    payload: ToolCallPayload


class ToolResultPayload(BaseModel):
    """Payload for tool.result events.

    Sent when a tool call completes (success or failure).
    """

    run_id: str = Field(..., description="Unique run identifier")
    call_id: str = Field(..., description="Tool call identifier")
    tool_name: str = Field(..., description="Name of the tool that was called")
    success: bool = Field(..., description="Whether the tool call succeeded")
    result: Any = Field(default=None, description="Tool result (on success)")
    error: str | None = Field(default=None, description="Error message (on failure)")
    duration_ms: float | None = Field(
        default=None, description="Tool execution duration in milliseconds"
    )


class ToolResultMessage(AgentToUIMessage):
    """Message sent when a tool call completes."""

    type: Literal["tool.result"] = "tool.result"
    payload: ToolResultPayload


# ============================================================================
# State Sync Protocol
# ============================================================================


class JSONPatchOperation(BaseModel):
    """JSON Patch operation as per RFC 6902."""

    op: Literal["add", "remove", "replace", "move", "copy", "test"]
    path: str
    value: Any = None
    from_: str | None = Field(default=None, alias="from")


def compute_checksum(data: dict[str, Any]) -> str:
    """Compute SHA-256 checksum for state data.

    Args:
        data: The data to checksum.

    Returns:
        A string in format "sha256:{hexdigest}".
    """
    json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    hash_hex = hashlib.sha256(json_str.encode()).hexdigest()
    return f"sha256:{hash_hex}"


class StateUpdatePayload(BaseModel):
    """Payload for state update messages.

    Contains incremental state changes with sequence tracking and checksum.
    """

    sequence: int = Field(
        ..., description="Monotonically increasing sequence number", ge=0
    )
    patch: list[JSONPatchOperation] = Field(
        ..., description="JSON Patch operations to apply"
    )
    checksum: str = Field(
        ..., description="SHA-256 checksum of the patch data"
    )

    @field_validator("checksum")
    @classmethod
    def validate_checksum(cls, v: str, info) -> str:
        """Validate checksum format and optionally verify against patch.

        Args:
            v: The checksum value to validate.
            info: Pydantic validation info.

        Returns:
            The validated checksum.

        Raises:
            ValueError: If checksum format is invalid.
        """
        if not v.startswith("sha256:"):
            raise ValueError("Checksum must start with 'sha256:'")
        hash_part = v[7:]
        if len(hash_part) != 64:
            raise ValueError("SHA-256 hash must be 64 hex characters")
        try:
            int(hash_part, 16)
        except ValueError:
            raise ValueError("SHA-256 hash must be valid hex")
        return v


class StateUpdateMessage(AgentToUIMessage):
    """State update message with sequence tracking and checksum.

    The client must validate that sequence = last_sequence + 1 before
    applying the patch. If a gap is detected, the client should request
    a full state sync.
    """

    type: Literal["state.update"] = "state.update"
    payload: StateUpdatePayload


class StateSnapshotPayload(BaseModel):
    """Payload for state snapshot messages (full state response)."""

    sequence: int = Field(
        ..., description="Current sequence number at snapshot time", ge=0
    )
    state: dict[str, Any] = Field(
        ..., description="Full state snapshot"
    )
    checksum: str = Field(
        ..., description="SHA-256 checksum of the state data"
    )


class StateSnapshotMessage(AgentToUIMessage):
    """Full state snapshot message.

    Sent by server in response to a state sync request. The client
    should replace its entire state with this snapshot and update
    its last_sequence to the provided sequence number.
    """

    type: Literal["state.snapshot"] = "state.snapshot"
    payload: StateSnapshotPayload


# ============================================================================
# Turn/Event Stream Messages
# ============================================================================


class TurnCreatedMessage(AgentToUIMessage):
    """Broadcast a newly created turn to subscribed clients."""

    type: Literal["turn.created"] = "turn.created"
    payload: TurnResponse


class EventCreatedMessage(AgentToUIMessage):
    """Broadcast a newly created event to subscribed clients."""

    type: Literal["event.created"] = "event.created"
    payload: EventResponse


# Note: StateSyncRequestMessage is defined after UIToAgentMessage below


# Union type for all agent -> UI message types
AgentToUIMessageType = (
    AgentStatusMessage
    | AgentProgressMessage
    | AgentResultMessage
    | AgentErrorMessage
    | AgentRequestMessage
    | AgentNotificationMessage
    | JobProgressMessage
    | NodeCreatedMessage
    | NodeUpdatedMessage
    | NodeDeletedMessage
    | EdgeCreatedMessage
    | EdgeUpdatedMessage
    | EdgeDeletedMessage
    | RunStartMessage
    | RunEndMessage
    | ToolCallMessage
    | ToolResultMessage
    | StateUpdateMessage
    | StateSnapshotMessage
    | TurnCreatedMessage
    | EventCreatedMessage
)


# ============================================================================
# UI -> Agent Messages
# ============================================================================

class UIToAgentMessage(AGUIEnvelope):
    """Base type for messages sent from UI to Agent."""

    source: Literal["ui"] = "ui"  # type: ignore[reportIncompatibleVariableOverride]
    target: Literal["agent"] = "agent"  # type: ignore[reportIncompatibleVariableOverride]


class UIContextViewport(BaseModel):
    """UI context viewport information."""

    x: float
    y: float
    zoom: float


class UIContextCanvas(BaseModel):
    """UI context canvas information."""

    selected_nodes: list[str] = Field(default_factory=list)
    selected_edges: list[str] = Field(default_factory=list)
    viewport: UIContextViewport


class UIContextWorkspace(BaseModel):
    """UI context workspace information."""

    workspace_id: str
    user_id: str | None = None


class UIContext(BaseModel):
    """UI context snapshot for agent awareness."""

    canvas: UIContextCanvas
    workspace: UIContextWorkspace
    user_input: str | None = None


class UICommandPayload(BaseModel):
    """Payload for UI commands to agents."""

    agent_id: str | None = None  # Optional: let gateway route to appropriate agent
    command: str
    parameters: dict[str, Any] | None = None
    context: UIContext | None = None


class UICommandMessage(UIToAgentMessage):
    """UI command to agent (execute an operation)."""

    type: Literal["command"] = "command"
    payload: UICommandPayload


class UIResponsePayload(BaseModel):
    """Payload for UI responses to agent requests."""

    agent_id: str
    request_id: str
    response: Any
    cancelled: bool | None = None


class UIResponseMessage(UIToAgentMessage):
    """UI response to agent request."""

    type: Literal["response"] = "response"
    payload: UIResponsePayload


class UICancelPayload(BaseModel):
    """Payload for UI cancel requests."""

    agent_id: str
    operation_id: str | None = None
    reason: str | None = None


class UICancelMessage(UIToAgentMessage):
    """UI cancel request for ongoing operation."""

    type: Literal["cancel"] = "cancel"
    payload: UICancelPayload


class UIContextMessagePayload(BaseModel):
    """Payload for UI context updates."""

    context: UIContext


class UIContextMessage(UIToAgentMessage):
    """UI context update (selection, viewport, etc.)."""

    type: Literal["context"] = "context"
    payload: UIContextMessagePayload


# ============================================================================
# State Sync Protocol (UI -> Agent)
# ============================================================================


class StateSyncRequestPayload(BaseModel):
    """Payload for state sync request messages."""

    last_sequence: int | None = Field(
        default=None,
        description="The last sequence number the client received. "
        "Null if no state.",
    )


class StateSyncRequestMessage(UIToAgentMessage):
    """Request from client to synchronize full state.

    Sent by client when a sequence gap is detected or after reconnection.
    The server should respond with the full current state.
    """

    type: Literal["state.sync_request"] = "state.sync_request"
    payload: StateSyncRequestPayload


# Union type for all UI -> agent message types
UIToAgentMessageType = (
    UICommandMessage
    | UIResponseMessage
    | UICancelMessage
    | UIContextMessage
    | StateSyncRequestMessage
)


# ============================================================================
# Event Types
# ============================================================================

AGUIEventType = Literal[
    "node.created",
    "node.updated",
    "node.deleted",
    "edge.created",
    "edge.deleted",
    "canvas.cleared",
    "workspace.changed",
    "selection.changed",
    "viewport.changed",
]


class AGUIEvent(BaseModel):
    """Event types for agent-to-UI event streaming."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: AGUIEventType = Field(..., alias="eventType")
    event_id: str = Field(
        default_factory=lambda: f"evt-{datetime.now().timestamp()}-{uuid4().hex[:8]}",
        description="Unique event identifier",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Event timestamp (UTC)",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Event data payload",
    )





# ============================================================================
# Dashboard Streaming Protocol
# ============================================================================


class DashboardSubscribePayload(BaseModel):
    """Payload for dashboard subscription request."""

    dashboard_node_id: int = Field(..., description="Dashboard node identifier")
    canvas_id: int = Field(..., description="Canvas identifier")


class DashboardSubscribeMessage(UIToAgentMessage):
    """Request to subscribe a WebSocket connection to a dashboard node's updates."""

    type: Literal["dashboard.subscribe"] = "dashboard.subscribe"
    payload: DashboardSubscribePayload


class DashboardUnsubscribePayload(BaseModel):
    """Payload for dashboard unsubscription request."""

    dashboard_node_id: int = Field(
        ..., description="Dashboard node identifier to unsubscribe from"
    )


class DashboardUnsubscribeMessage(UIToAgentMessage):
    """Request to unsubscribe from a dashboard node's updates."""

    type: Literal["dashboard.unsubscribe"] = "dashboard.unsubscribe"
    payload: DashboardUnsubscribePayload


class DashboardUpdatePayload(BaseModel):
    """Payload for dashboard state update messages."""

    dashboard_node_id: int = Field(..., description="Dashboard node identifier")
    subscription_target: str = Field(..., description="Type of entity that changed")
    source_id: str | None = Field(default=None, description="ID of the changed entity")
    change_type: Literal["created", "updated", "deleted"] = Field(
        ..., description="Type of change that occurred"
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Updated entity data"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Update timestamp (UTC)",
    )


class DashboardUpdateMessage(AgentToUIMessage):
    """Dashboard state update pushed to subscribed clients.

    Sent when an entity matching a dashboard subscription changes.
    """

    type: Literal["dashboard.update"] = "dashboard.update"
    payload: DashboardUpdatePayload


class DashboardSubscribedPayload(BaseModel):
    """Payload for dashboard subscription confirmation."""

    dashboard_node_id: int = Field(..., description="Dashboard node identifier")
    subscriptions: list[dict[str, Any]] = Field(
        default_factory=list, description="Active subscriptions for this dashboard"
    )


class DashboardSubscribedMessage(AgentToUIMessage):
    """Confirmation that a WebSocket connection is now subscribed to a dashboard."""

    type: Literal["dashboard.subscribed"] = "dashboard.subscribed"
    payload: DashboardSubscribedPayload


# For consistency with frontend naming
AGUIProtocolVersion = AGUI_PROTOCOL_VERSION
