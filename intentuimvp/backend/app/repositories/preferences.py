"""Repository for user preferences operations."""

from logging import getLogger

from sqlalchemy.orm import Session

from app.models.preferences import Preferences

logger = getLogger(__name__)


class PreferencesRepository:
    """Repository for user preferences CRUD operations.

    Provides methods for creating, reading, and updating user preferences.
    Each user has one preferences record that is upserted on save.
    """

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def get_by_user(self, user_id: str) -> Preferences | None:
        """Get preferences by user ID.

        Args:
            user_id: User identifier

        Returns:
            Preferences if found, None otherwise
        """
        return self.db.query(Preferences).filter(Preferences.user_id == user_id).first()

    def upsert_preferences(self, user_id: str, preferences_data: dict) -> Preferences:
        """Create or update preferences for a user.

        If preferences exist for the user, they are updated with the provided data.
        Otherwise, new preferences are created.

        Args:
            user_id: User identifier
            preferences_data: Dictionary of preferences to save

        Returns:
            Created or updated preferences
        """
        # Get existing preferences
        prefs = self.get_by_user(user_id)

        if prefs is None:
            # Create new preferences record
            prefs = Preferences(user_id=user_id, preferences=preferences_data)
            self.db.add(prefs)
            logger.info(f"Created preferences for user {user_id}")
        else:
            # Update existing preferences - merge with existing to preserve any fields not in update
            merged = prefs.preferences.copy()
            merged.update(preferences_data)
            prefs.preferences = merged
            logger.info(f"Updated preferences for user {user_id}")

        self.db.commit()
        self.db.refresh(prefs)
        return prefs

    def delete_preferences(self, user_id: str) -> bool:
        """Delete preferences for a user.

        Args:
            user_id: User identifier

        Returns:
            True if deleted, False if not found
        """
        prefs = self.get_by_user(user_id)
        if prefs is None:
            return False
        self.db.delete(prefs)
        self.db.commit()
        logger.info(f"Deleted preferences for user {user_id}")
        return True
