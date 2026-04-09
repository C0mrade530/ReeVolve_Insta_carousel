import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache

# Find .env: check backend/.env first, then parent (project root)
_this_dir = Path(__file__).resolve().parent.parent  # backend/app -> backend
_env_candidates = [
    _this_dir / ".env",           # backend/.env
    _this_dir.parent / ".env",    # project root .env
]
_env_file = next((str(p) for p in _env_candidates if p.exists()), ".env")


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # API Keys (CometAPI — OpenAI-совместимый прокси)
    openai_api_key: str = ""
    openai_api_key_v2: str = ""  # Second key for brand unpacking (heavy analysis)
    openai_base_url: str = "https://api.cometapi.com/v1"
    openai_model: str = "claude-sonnet-4-6"
    openai_eval_model: str = "claude-opus-4-6"  # Deep analysis: brand unpacking, viral evaluation
    nanobanana_api_key: str = ""

    # Security
    secret_key: str = "change-me"
    encryption_key: str = ""
    debug: bool = True

    # Instagram Safety
    min_delay_between_posts: int = 7200
    max_daily_posts: int = 5
    schedule_randomness: int = 900

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Storage
    media_storage_path: str = "./media"

    @model_validator(mode="after")
    def validate_encryption_key(self):
        if not self.debug and not self.encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY must be set in production (DEBUG=false). "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        return self

    class Config:
        env_file = _env_file
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
