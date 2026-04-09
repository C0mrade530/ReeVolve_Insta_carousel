"""
Encryption utilities for storing Instagram session data.
Uses Fernet symmetric encryption.
"""
import json
import logging
from cryptography.fernet import Fernet
from app.config import get_settings

logger = logging.getLogger(__name__)

# Cache the Fernet instance so the key is consistent across calls
_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    settings = get_settings()
    key = settings.encryption_key
    if not key:
        if not settings.debug:
            raise RuntimeError(
                "ENCRYPTION_KEY not set in production. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        logger.warning(
            "[Encryption] ENCRYPTION_KEY not set! Generating random key. "
            "Sessions will be LOST on server restart. Set ENCRYPTION_KEY in .env"
        )
        key = Fernet.generate_key().decode()

    _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
    logger.info("[Encryption] Fernet key initialized")
    return _fernet_instance


def encrypt_data(data: dict) -> str:
    """Encrypt a dict to a base64-encoded string."""
    f = _get_fernet()
    json_bytes = json.dumps(data).encode("utf-8")
    return f.encrypt(json_bytes).decode("utf-8")


def decrypt_data(encrypted: str) -> dict:
    """Decrypt a base64-encoded string back to a dict."""
    if not encrypted:
        raise ValueError("Empty encrypted data")
    f = _get_fernet()
    json_bytes = f.decrypt(encrypted.encode("utf-8"))
    return json.loads(json_bytes.decode("utf-8"))
