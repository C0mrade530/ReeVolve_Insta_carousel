"""
Shared test fixtures.
"""
import os
import sys
import pytest

# Ensure backend/ is on sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before any app imports
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("ENCRYPTION_KEY", "")
os.environ.setdefault("DEBUG", "true")


@pytest.fixture
def test_user():
    return {
        "id": "user-123",
        "email": "test@example.com",
        "role": "authenticated",
    }


@pytest.fixture
def test_account():
    return {
        "id": "acct-001",
        "username": "test_realtor",
        "is_active": True,
        "session_data": {"settings": {"cookies": {"key": "value"}}},
        "proxy": "socks5://proxy:1080",
    }
