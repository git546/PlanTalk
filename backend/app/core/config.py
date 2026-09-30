from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PlanTalk API"
    app_env: str = "development"
    cors_origins: list[str] = [
        "http://localhost:8081",
        "http://localhost:19006",
        "http://localhost:8080",
    ]
    openai_api_key: SecretStr | None = None
    supabase_url: str | None = None
    supabase_service_role_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
