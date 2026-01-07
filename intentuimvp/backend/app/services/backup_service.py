"""Service for backup operations with encryption and retention.

Handles creation and restoration of encrypted backups containing
canvas state and user preferences.
"""

from datetime import datetime
from logging import getLogger

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.backup import Backup
from app.repositories.backup import BackupRepository
from app.repositories.canvas import CanvasRepository
from app.repositories.preferences import PreferencesRepository
from app.security.encryption import BackupEncryption

logger = getLogger(__name__)


class BackupService:
    """Service for backup and restore operations.

    Orchestrates backup creation, restoration, and retention cleanup.
    All backup data is encrypted at rest using Fernet symmetric encryption.
    """

    def __init__(self, db: Session) -> None:
        """Initialize service with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db
        self.backup_repo = BackupRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.prefs_repo = PreferencesRepository(db)
        self.settings = get_settings()

    def create_backup(self, user_id: str, name: str | None = None) -> Backup:
        """Create an encrypted backup of user data.

        Collects canvas state and preferences, encrypts them together,
        and stores as a backup record.

        Args:
            user_id: User identifier
            name: Optional backup name (auto-generated if None)

        Returns:
            Created backup record

        Raises:
            EncryptionError: If encryption fails
        """
        # Generate backup name if not provided
        if name is None:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
            name = f"auto-{timestamp}"

        # Collect user data
        canvas = self.canvas_repo.get_by_user(user_id)
        canvas_data = canvas.to_dict() if canvas else None

        preferences = self.prefs_repo.get_by_user(user_id)
        prefs_data = preferences.to_dict() if preferences else None

        # Create backup payload
        backup_payload = {
            "canvas": canvas_data,
            "preferences": prefs_data,
            "backup_timestamp": datetime.now().isoformat(),
        }

        # Encrypt the backup data
        encrypted_data = BackupEncryption.encrypt_json(backup_payload)

        # Create backup record
        backup = self.backup_repo.create_backup(
            user_id=user_id,
            name=name,
            encrypted_data=encrypted_data,
            size_bytes=len(encrypted_data),
        )

        # Apply retention policy after creating new backup
        self._apply_retention_policy(user_id)

        logger.info(f"Created backup {backup.id} for user {user_id}: {name}")
        return backup

    def restore_backup(self, backup_id: int, user_id: str) -> dict:
        """Restore user data from an encrypted backup.

        Decrypts the backup data and restores canvas state and preferences.

        Args:
            backup_id: Backup identifier
            user_id: User identifier (for authorization check)

        Returns:
            Dictionary with restored data summary

        Raises:
            ValueError: If backup not found or doesn't belong to user
            EncryptionError: If decryption fails
        """
        backup = self.backup_repo.get_by_id(backup_id)
        if backup is None:
            raise ValueError(f"Backup {backup_id} not found")
        if backup.user_id != user_id:
            raise ValueError(f"Backup {backup_id} does not belong to user {user_id}")

        # Decrypt backup data
        backup_payload = BackupEncryption.decrypt_json(backup.encrypted_data)

        # Restore canvas
        canvas_data = backup_payload.get("canvas")
        if canvas_data:
            self.canvas_repo.save_canvas(
                user_id=user_id,
                canvas_data={"nodes": canvas_data.get("nodes", [])},
                canvas_name=canvas_data.get("name", "restored"),
            )
            logger.info(f"Restored canvas for user {user_id} from backup {backup_id}")

        # Restore preferences
        prefs_data = backup_payload.get("preferences")
        if prefs_data and prefs_data.get("preferences"):
            self.prefs_repo.upsert_preferences(user_id, prefs_data["preferences"])
            logger.info(f"Restored preferences for user {user_id} from backup {backup_id}")

        return {
            "backup_id": backup_id,
            "restored_canvas": canvas_data is not None,
            "restored_preferences": prefs_data is not None,
            "backup_timestamp": backup_payload.get("backup_timestamp"),
        }

    def list_backups(self, user_id: str, limit: int = 100) -> list[dict]:
        """List all backups for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of backups to return

        Returns:
            List of backup dictionaries
        """
        backups = self.backup_repo.list_by_user(user_id, limit=limit)
        return [backup.to_dict() for backup in backups]

    def delete_backup(self, backup_id: int, user_id: str) -> bool:
        """Delete a backup.

        Args:
            backup_id: Backup identifier
            user_id: User identifier (for authorization check)

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If backup doesn't belong to user
        """
        backup = self.backup_repo.get_by_id(backup_id)
        if backup is None:
            return False
        if backup.user_id != user_id:
            raise ValueError(f"Backup {backup_id} does not belong to user {user_id}")

        return self.backup_repo.delete_backup(backup_id)

    def _apply_retention_policy(self, user_id: str) -> int:
        """Apply retention policy to clean up old backups.

        Deletes backups older than the configured retention period.
        This is called automatically after each new backup is created.

        Args:
            user_id: User identifier

        Returns:
            Number of backups deleted
        """
        retention_days = self.settings.backup_retention_days
        if retention_days > 0:
            deleted = self.backup_repo.delete_old_backups(user_id, retention_days)
            if deleted > 0:
                logger.info(f"Retention policy: deleted {deleted} backups older than {retention_days} days")
            return deleted
        return 0
