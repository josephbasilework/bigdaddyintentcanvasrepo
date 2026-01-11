"""Pydantic schemas for API request/response models."""

from app.schemas.backup import (
    BackupCreatedResponse,
    BackupInfo,
    BackupListResponse,
    ErrorResponse,
    ManualBackupRequest,
    RestoreResponse,
)
from app.schemas.edge import (
    EdgeCreateRequest,
    EdgeListResponse,
    EdgeResponse,
    EdgeUpdateRequest,
)
from app.schemas.mcp import (
    GoogleCalendarEventRequest,
    GoogleCalendarEventResponse,
    MCPSecurityCheckRequest,
    MCPSecurityCheckResponse,
    MCPServerListResponse,
    MCPServerRegisterRequest,
    MCPServerResponse,
    MCPServerUpdateRequest,
    MCPToolExecuteRequest,
    MCPToolExecuteResponse,
    MCPToolsListResponse,
)
from app.schemas.node import (
    NodeCreateRequest,
    NodeListResponse,
    NodeResponse,
    NodeUpdateRequest,
)
from app.schemas.preferences import (
    DefaultPreferencesResponse,
    PreferencesData,
    PreferencesResponse,
    PreferencesSaveRequest,
)
from app.schemas.workspace import CanvasResponse, NodeData, WorkspaceSaveRequest

__all__ = [
    "CanvasResponse",
    "NodeData",
    "WorkspaceSaveRequest",
    "EdgeCreateRequest",
    "EdgeUpdateRequest",
    "EdgeResponse",
    "EdgeListResponse",
    "NodeCreateRequest",
    "NodeUpdateRequest",
    "NodeResponse",
    "NodeListResponse",
    "PreferencesData",
    "PreferencesResponse",
    "PreferencesSaveRequest",
    "DefaultPreferencesResponse",
    "BackupInfo",
    "ManualBackupRequest",
    "BackupListResponse",
    "RestoreResponse",
    "BackupCreatedResponse",
    "ErrorResponse",
    # MCP schemas
    "MCPServerRegisterRequest",
    "MCPServerResponse",
    "MCPServerListResponse",
    "MCPServerUpdateRequest",
    "MCPToolExecuteRequest",
    "MCPToolExecuteResponse",
    "MCPToolsListResponse",
    "MCPSecurityCheckRequest",
    "MCPSecurityCheckResponse",
    "GoogleCalendarEventRequest",
    "GoogleCalendarEventResponse",
]
