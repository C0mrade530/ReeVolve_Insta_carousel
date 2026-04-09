"""Tests for encryption utilities."""
import os
import pytest

# Ensure DEBUG=true so random key is allowed
os.environ["DEBUG"] = "true"
os.environ["ENCRYPTION_KEY"] = ""


class TestEncryption:
    def test_encrypt_decrypt_round_trip(self):
        # Reset singleton so fresh key is generated
        import app.utils.encryption as enc
        enc._fernet_instance = None

        data = {"username": "test", "cookies": {"key": "value"}}
        encrypted = enc.encrypt_data(data)
        assert isinstance(encrypted, str)
        assert encrypted != str(data)

        decrypted = enc.decrypt_data(encrypted)
        assert decrypted == data

    def test_encrypt_empty_dict(self):
        import app.utils.encryption as enc
        enc._fernet_instance = None

        data = {}
        encrypted = enc.encrypt_data(data)
        decrypted = enc.decrypt_data(encrypted)
        assert decrypted == {}

    def test_decrypt_empty_string_raises(self):
        import app.utils.encryption as enc
        with pytest.raises(ValueError, match="Empty encrypted data"):
            enc.decrypt_data("")

    def test_encrypt_with_explicit_key(self):
        from cryptography.fernet import Fernet
        import app.utils.encryption as enc

        key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = key
        # Reset singleton and settings cache
        enc._fernet_instance = None
        from app.config import get_settings
        get_settings.cache_clear()

        data = {"session": "data123"}
        encrypted = enc.encrypt_data(data)
        decrypted = enc.decrypt_data(encrypted)
        assert decrypted == data

        # Cleanup
        os.environ["ENCRYPTION_KEY"] = ""
        enc._fernet_instance = None
        get_settings.cache_clear()

    def test_decrypt_wrong_key_raises(self):
        from cryptography.fernet import Fernet
        import app.utils.encryption as enc

        # Encrypt with one key
        enc._fernet_instance = Fernet(Fernet.generate_key())
        data = {"test": "data"}
        encrypted = enc.encrypt_data(data)

        # Try decrypt with different key
        enc._fernet_instance = Fernet(Fernet.generate_key())
        with pytest.raises(Exception):
            enc.decrypt_data(encrypted)
