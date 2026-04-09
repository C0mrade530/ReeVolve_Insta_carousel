import threading
from supabase import create_client, Client
from app.config import get_settings

_supabase_client: Client | None = None
_supabase_admin: Client | None = None
_db_lock = threading.Lock()


def get_supabase() -> Client:
    """Get Supabase client with anon key (respects RLS). Thread-safe singleton."""
    global _supabase_client
    if _supabase_client is None:
        with _db_lock:
            if _supabase_client is None:  # Double-check locking
                settings = get_settings()
                _supabase_client = create_client(
                    settings.supabase_url,
                    settings.supabase_anon_key,
                )
    return _supabase_client


def get_supabase_admin() -> Client:
    """Get Supabase client with service role key (bypasses RLS). Thread-safe singleton."""
    global _supabase_admin
    if _supabase_admin is None:
        with _db_lock:
            if _supabase_admin is None:  # Double-check locking
                settings = get_settings()
                _supabase_admin = create_client(
                    settings.supabase_url,
                    settings.supabase_service_role_key,
                )
    return _supabase_admin
