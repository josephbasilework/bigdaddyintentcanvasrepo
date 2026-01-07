"""Backup API endpoints for creating and restoring backups."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.backup import (
    BackupCreatedResponse,
    BackupListResponse,
    ManualBackupRequest,
    RestoreResponse,
)
from app.security.encryption import EncryptionError
from app.services.backup_service import BackupService

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


@router.post("/api/backup/manual", response_model=BackupCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_backup(
    payload: ManualBackupRequest = ManualBackupRequest(),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Create a manual backup of user data.

    Creates an encrypted backup containing canvas state and preferences.
    If name is not provided, it will be auto-generated with a timestamp.

    Args:
        payload: Optional backup name
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Created backup information

    Raises:
        HTTPException: If backup creation fails
    """
    try:
        service = BackupService(db)
        name = payload.name if payload.name else None
        backup = service.create_backup(user_id=user_id, name=name)
        logger.info(f"Manual backup {backup.id} created for user {user_id}")
        return backup.to_dict()
    except EncryptionError as e:
        logger.error(f"Encryption error creating backup for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt backup data",
        ) from e
    except Exception as e:
        logger.error(f"Failed to create manual backup for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create backup",
        ) from e


@router.get("/api/backups", response_model=BackupListResponse)
async def list_backups(
    limit: int = 100,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List all backups for the authenticated user.

    Returns metadata for all backups, ordered by creation date (newest first).

    Args:
        limit: Maximum number of backups to return (default: 100)
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of backup information with count
    """
    try:
        service = BackupService(db)
        backups = service.list_backups(user_id=user_id, limit=limit)
        return {"backups": backups, "count": len(backups)}
    except Exception as e:
        logger.error(f"Failed to list backups for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list backups",
        ) from e


@router.post("/api/restore/{backup_id}", response_model=RestoreResponse)
async def restore_from_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Restore user data from a backup.

    Decrypts the backup data and restores canvas state and preferences.

    Args:
        backup_id: ID of the backup to restore
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Restore operation summary

    Raises:
        HTTPException: If backup not found, authorization fails, or restore fails
    """
    try:
        service = BackupService(db)
        result = service.restore_backup(backup_id=backup_id, user_id=user_id)
        logger.info(f"Backup {backup_id} restored for user {user_id}")
        return result
    except ValueError as e:
        logger.warning(f"Restore failed for user {user_id}, backup {backup_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except EncryptionError as e:
        logger.error(f"Decryption error restoring backup {backup_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt backup data",
        ) from e
    except Exception as e:
        logger.error(f"Failed to restore backup {backup_id} for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore backup",
        ) from e


@router.delete("/api/backup/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> None:
    """Delete a specific backup.

    Args:
        backup_id: ID of the backup to delete
        db: Database session
        user_id: Authenticated user ID

    Raises:
        HTTPException: If backup not found or authorization fails
    """
    try:
        service = BackupService(db)
        deleted = service.delete_backup(backup_id=backup_id, user_id=user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup {backup_id} not found",
            )
        logger.info(f"Backup {backup_id} deleted by user {user_id}")
    except ValueError as e:
        logger.warning(f"Delete failed for user {user_id}, backup {backup_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backup {backup_id} for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete backup",
        ) from e
