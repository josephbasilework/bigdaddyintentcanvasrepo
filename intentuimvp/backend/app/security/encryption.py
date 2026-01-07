"""Encryption utilities for backup data security.

Uses Fernet (AES-128-CBC + HMAC) for symmetric encryption.
Encryption keys are derived from BACKUP_ENCRYPTION_KEY environment variable.
"""

import base64
from logging import getLogger

from cryptography.fernet import Fernet, InvalidToken

logger = getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""


class BackupEncryption:
    """Handles encryption and decryption of backup data.

    Uses Fernet symmetric encryption with keys from settings.
    """

    _key: bytes | None = None

    @classmethod
    def get_key(cls) -> bytes:
        """Get or generate the encryption key.

        Returns:
            Fernet encryption key as bytes

        Raises:
            EncryptionError: If key generation fails
        """
        if cls._key is None:
            from app.config import get_settings

            settings = get_settings()
            key_str = settings.backup_encryption_key
            if key_str:
                try:
                    cls._key = base64.urlsafe_b64decode(key_str.encode())
                except Exception as e:
                    raise EncryptionError(f"Invalid BACKUP_ENCRYPTION_KEY format: {e}")
            else:
                # Generate a new key for development (WARNING: changes on restart!)
                cls._key = Fernet.generate_key()
                logger.warning("Using auto-generated encryption key (will change on restart)")

        return cls._key

    @classmethod
    def encrypt(cls, data: bytes | str) -> bytes:
        """Encrypt data using Fernet symmetric encryption.

        Args:
            data: Data to encrypt (bytes or str, will be encoded if str)

        Returns:
            Encrypted data as bytes

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")
            f = Fernet(cls.get_key())
            return f.encrypt(data)
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    @classmethod
    def decrypt(cls, encrypted_data: bytes) -> bytes:
        """Decrypt data using Fernet symmetric encryption.

        Args:
            encrypted_data: Encrypted data to decrypt

        Returns:
            Decrypted data as bytes

        Raises:
            EncryptionError: If decryption fails or data is corrupted
        """
        try:
            f = Fernet(cls.get_key())
            return f.decrypt(encrypted_data)
        except InvalidToken:
            raise EncryptionError("Decryption failed: Invalid token or corrupted data")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    @classmethod
    def encrypt_json(cls, data: dict) -> bytes:
        """Encrypt JSON-serializable dictionary.

        Args:
            data: Dictionary to encrypt

        Returns:
            Encrypted JSON as bytes
        """
        import json

        json_str = json.dumps(data, separators=(",", ":"), sort_keys=True)
        return cls.encrypt(json_str)

    @classmethod
    def decrypt_json(cls, encrypted_data: bytes) -> dict:
        """Decrypt data to JSON dictionary.

        Args:
            encrypted_data: Encrypted data

        Returns:
            Decrypted dictionary

        Raises:
            EncryptionError: If decryption or JSON parsing fails
        """
        import json

        decrypted_bytes = cls.decrypt(encrypted_data)
        try:
            return json.loads(decrypted_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise EncryptionError(f"Failed to parse decrypted JSON: {e}")


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key.

    Returns:
        Base64-encoded encryption key suitable for BACKUP_ENCRYPTION_KEY env var

    Example:
        key = generate_encryption_key()
        print(f"BACKUP_ENCRYPTION_KEY={key}")
    """
    return Fernet.generate_key().decode()
