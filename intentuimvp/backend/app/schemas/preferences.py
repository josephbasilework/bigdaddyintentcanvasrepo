"""Pydantic schemas for preferences API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PreferencesData(BaseModel):
    """User preferences data.

    Validates preference values to ensure security and prevent injection.
    """

    theme: Literal["light", "dark", "auto"] = Field(
        default="light", description="UI theme preference"
    )
    zoom_level: float = Field(
        default=1.0, ge=0.5, le=2.0, description="Canvas zoom level (0.5x to 2x)"
    )
    panel_layouts: dict = Field(
        default_factory=dict,
        description="Panel layout configuration (positions, sizes)",
    )

    @field_validator("panel_layouts")
    @classmethod
    def sanitize_panel_layouts(cls, v: dict) -> dict:
        """Sanitize panel layout data to prevent injection.

        Args:
            v: Panel layout dictionary

        Returns:
            Sanitized panel layout dictionary
        """
        # Ensure all keys and values are safe (strings, numbers, bools)
        sanitized: dict = {}
        for key, value in v.items():
            if not isinstance(key, str):
                continue
            # Only allow primitive types
            if isinstance(value, str | int | float | bool | type(None)):
                sanitized[key] = value
            elif isinstance(value, dict):
                # Recursively sanitize nested dicts
                sanitized[key] = cls.sanitize_panel_layouts(value)
            elif isinstance(value, list):
                # Sanitize lists
                sanitized[key] = [
                    x if isinstance(x, str | int | float | bool | type(None)) else str(x)
                    for x in value
                ]
        return sanitized

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields for security
    )


class PreferencesResponse(BaseModel):
    """Response for user preferences."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    preferences: PreferencesData
    updated_at: str


class PreferencesSaveRequest(BaseModel):
    """Request body for saving preferences."""

    preferences: PreferencesData = Field(
        ..., description="Preferences data to save"
    )


class DefaultPreferencesResponse(BaseModel):
    """Response when no preferences exist for user (returns defaults)."""

    preferences: PreferencesData = Field(
        default_factory=PreferencesData, description="Default preferences"
    )
