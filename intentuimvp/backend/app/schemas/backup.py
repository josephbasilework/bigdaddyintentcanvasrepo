"""Pydantic schemas for backup API."""

from pydantic import BaseModel, ConfigDict, Field


class BackupInfo(BaseModel):
    """Information about a backup (metadata only)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    name: str
    created_at: str
    size_bytes: int


class ManualBackupRequest(BaseModel):
    """Request body for manual backup creation."""

    name: str = Field(
        default="",
        description="Optional backup name (auto-generated if empty)",
        max_length=100,
    )


class BackupListResponse(BaseModel):
    """Response for listing backups."""

    backups: list[BackupInfo] = Field(default_factory=list, description="List of backups")
    count: int = Field(..., description="Total number of backups")


class RestoreResponse(BaseModel):
    """Response for restore operation."""

    backup_id: int = Field(..., description="ID of the restored backup")
    restored_canvas: bool = Field(..., description="Whether canvas was restored")
    restored_preferences: bool = Field(..., description="Whether preferences were restored")
    backup_timestamp: str | None = Field(None, description="When the backup was created")


class BackupCreatedResponse(BaseModel):
    """Response for successful backup creation."""

    id: int
    user_id: str
    name: str
    created_at: str
    size_bytes: int


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str = Field(..., description="Error message")
