"""Encryption utilities for sensitive data (API keys, credentials).

Uses Fernet symmetric encryption from the cryptography library.
Falls back to plaintext with a warning if no encryption key is configured.
Gracefully handles pre-encryption plaintext values during migration.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_ENCRYPTED_PREFIX = "enc:"


def _get_fernet() -> Optional[object]:
    """Get a Fernet instance using the configured encryption key."""
    from app.core.config import settings

    if not settings.encryption_key:
        return None

    try:
        from cryptography.fernet import Fernet

        return Fernet(settings.encryption_key.encode())
    except Exception as e:
        logger.warning(f"Failed to initialize Fernet encryption: {e}")
        return None


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext value.

    Returns a prefixed ciphertext string, or the original plaintext
    if encryption is not configured (with a warning).
    """
    if not plaintext:
        return plaintext

    fernet = _get_fernet()
    if fernet is None:
        logger.warning("Encryption key not configured — storing value in plaintext")
        return plaintext

    try:
        encrypted = fernet.encrypt(plaintext.encode())  # type: ignore[union-attr]
        return f"{_ENCRYPTED_PREFIX}{encrypted.decode()}"
    except Exception as e:
        logger.warning(f"Encryption failed, storing plaintext: {e}")
        return plaintext


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext value.

    Gracefully handles plaintext values (pre-encryption migration):
    - If the value doesn't have the encryption prefix, it's returned as-is.
    - If decryption fails, the raw value (without prefix) is returned.
    """
    if not ciphertext:
        return ciphertext

    if not ciphertext.startswith(_ENCRYPTED_PREFIX):
        return ciphertext

    fernet = _get_fernet()
    if fernet is None:
        logger.warning("Encryption key not configured — cannot decrypt value")
        return ciphertext.removeprefix(_ENCRYPTED_PREFIX)

    try:
        encrypted_bytes = ciphertext.removeprefix(_ENCRYPTED_PREFIX).encode()
        return fernet.decrypt(encrypted_bytes).decode()  # type: ignore[union-attr]
    except Exception as e:
        logger.warning(f"Decryption failed — returning raw value: {e}")
        return ciphertext.removeprefix(_ENCRYPTED_PREFIX)
