"""Application settings loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    airbyte_api_url: str = "http://localhost:8000/api/public/v1"
    airbyte_client_id: str = ""
    airbyte_client_secret: str = ""
    airbyte_access_token: str = ""

    http_host: str = "127.0.0.1"
    http_port: int = 8080

    @property
    def has_static_token(self) -> bool:
        return bool(self.airbyte_access_token)

    @property
    def can_exchange_token(self) -> bool:
        return bool(self.airbyte_client_id and self.airbyte_client_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
