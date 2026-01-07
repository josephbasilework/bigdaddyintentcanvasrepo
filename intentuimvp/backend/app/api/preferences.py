"""Preferences API endpoints for saving and loading user preferences."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.preferences import PreferencesRepository
from app.schemas.preferences import (
    DefaultPreferencesResponse,
    PreferencesData,
    PreferencesResponse,
    PreferencesSaveRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user() -> str:
    """Get current user from authentication.

    Basic implementation using a simple header.
    TODO: Replace with proper JWT/OAuth authentication.

    Returns:
        User ID string

    Raises:
        HTTPException: If authentication fails
    """
    # Basic authentication for MVP - extract user from header
    # In production, use JWT or OAuth
    return "default_user"  # MVP: single user for now


@router.get("/api/preferences", response_model=PreferencesResponse | DefaultPreferencesResponse)
async def get_preferences(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get user's preferences.

    Returns the preferences for the authenticated user.
    If no preferences exist, returns default preferences.

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        User preferences or default preferences
    """
    repo = PreferencesRepository(db)
    prefs = repo.get_by_user(user_id)

    if prefs is None:
        logger.info(f"No preferences found for user {user_id}, returning defaults")
        return DefaultPreferencesResponse().model_dump()

    # Validate preferences data using Pydantic
    validated_prefs = PreferencesData(**prefs.preferences)
    logger.info(f"Retrieved preferences for user {user_id}")

    return {
        "user_id": prefs.user_id,
        "preferences": validated_prefs.model_dump(),
        "updated_at": prefs.updated_at.isoformat(),
    }


@router.put("/api/preferences", response_model=PreferencesResponse)
async def save_preferences(
    payload: PreferencesSaveRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Save or update user preferences.

    Creates new preferences or updates existing ones for the authenticated user.
    Merges with existing preferences to preserve any fields not in the update.

    Args:
        payload: Preferences data to save
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Saved preferences

    Raises:
        HTTPException: If save fails
    """
    try:
        repo = PreferencesRepository(db)
        prefs_data = payload.preferences.model_dump()

        prefs = repo.upsert_preferences(
            user_id=user_id,
            preferences_data=prefs_data,
        )

        # Validate and return the saved preferences
        validated_prefs = PreferencesData(**prefs.preferences)
        logger.info(f"Saved preferences for user {user_id}")

        return {
            "user_id": prefs.user_id,
            "preferences": validated_prefs.model_dump(),
            "updated_at": prefs.updated_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to save preferences for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save preferences",
        ) from e
