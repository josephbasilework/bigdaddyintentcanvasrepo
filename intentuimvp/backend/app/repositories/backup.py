"""Repository for backup operations."""

from datetime import datetime, timedelta
from logging import getLogger

from sqlalchemy.orm import Session

from app.models.backup import Backup

logger = getLogger(__name__)


class BackupRepository:
    """Repository for backup CRUD operations.

    Provides methods for creating, reading, and deleting backup records.
    """

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def create_backup(
        self, user_id: str, name: str, encrypted_data: bytes, size_bytes: int
    ) -> Backup:
        """Create a new backup record.

        Args:
            user_id: User identifier
            name: Backup name (e.g., "auto-2025-01-06" or "manual-backup")
            encrypted_data: Encrypted backup data
            size_bytes: Size of the encrypted data in bytes

        Returns:
            Created backup
        """
        backup = Backup(
            user_id=user_id,
            name=name,
            encrypted_data=encrypted_data,
            size_bytes=size_bytes,
        )
        self.db.add(backup)
        self.db.commit()
        self.db.refresh(backup)
        logger.info(f"Created backup {backup.id} for user {user_id}")
        return backup

    def get_by_id(self, backup_id: int) -> Backup | None:
        """Get backup by ID.

        Args:
            backup_id: Backup identifier

        Returns:
            Backup if found, None otherwise
        """
        return self.db.query(Backup).filter(Backup.id == backup_id).first()

    def list_by_user(self, user_id: str, limit: int = 100) -> list[Backup]:
        """List all backups for a user, ordered by creation date (newest first).

        Args:
            user_id: User identifier
            limit: Maximum number of backups to return

        Returns:
            List of backups
        """
        return (
            self.db.query(Backup)
            .filter(Backup.user_id == user_id)
            .order_by(Backup.created_at.desc())
            .limit(limit)
            .all()
        )

    def delete_backup(self, backup_id: int) -> bool:
        """Delete backup by ID.

        Args:
            backup_id: Backup identifier

        Returns:
            True if deleted, False if not found
        """
        backup = self.get_by_id(backup_id)
        if backup is None:
            return False
        self.db.delete(backup)
        self.db.commit()
        logger.info(f"Deleted backup {backup_id}")
        return True

    def delete_old_backups(self, user_id: str, days: int) -> int:
        """Delete backups older than specified days for a user.

        Args:
            user_id: User identifier
            days: Number of days to retain (backups older than this are deleted)

        Returns:
            Number of backups deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = (
            self.db.query(Backup)
            .filter(Backup.user_id == user_id, Backup.created_at < cutoff_date)
            .delete()
        )
        self.db.commit()
        logger.info(f"Deleted {deleted_count} old backups for user {user_id} (older than {days} days)")
        return deleted_count
