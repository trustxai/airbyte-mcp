"""Application settings loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

CLOUD_PUBLIC_API_ROOT = "https://api.airbyte.com/v1"
CLOUD_CONFIG_API_ROOT = "https://cloud.airbyte.com/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    airbyte_api_url: str = "http://localhost:8000/api/public/v1"
    airbyte_internal_api_url: str = ""
    airbyte_client_id: str = ""
    airbyte_client_secret: str = ""
    airbyte_access_token: str = ""
    airbyte_request_timeout_seconds: float = 30.0
    airbyte_internal_log_timeout_seconds: float = 120.0

    @property
    def has_static_token(self) -> bool:
        return bool(self.airbyte_access_token)

    @property
    def can_exchange_token(self) -> bool:
        return bool(self.airbyte_client_id and self.airbyte_client_secret)

    @property
    def is_cloud_deployment(self) -> bool:
        return self.airbyte_api_url.rstrip("/") == CLOUD_PUBLIC_API_ROOT.rstrip("/")

    @property
    def resolved_internal_api_url(self) -> str:
        """Internal (Configuration) API URL, derived from public URL if not set."""
        if self.airbyte_internal_api_url:
            return self.airbyte_internal_api_url.rstrip("/")

        normalized = self.airbyte_api_url.rstrip("/")
        if normalized == CLOUD_PUBLIC_API_ROOT.rstrip("/"):
            return CLOUD_CONFIG_API_ROOT

        public_suffix = "/api/public/v1"
        if normalized.endswith(public_suffix):
            return normalized[: -len(public_suffix)] + "/api/v1"

        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
