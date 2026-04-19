"""Async HTTP client for the Airbyte Public API with automatic token management."""

from __future__ import annotations

import time
from typing import Any

import httpx

from airbyte_mcp.config import get_settings

_TOKEN_SAFETY_MARGIN = 30  # seconds before actual expiry to refresh


class AirbyteClient:
    """Thin wrapper around httpx that handles Bearer-token lifecycle."""

    def __init__(self) -> None:
        self._token: str = ""
        self._expires_at: float = 0.0

    # -- token management ---------------------------------------------------

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        settings = get_settings()

        if settings.has_static_token:
            return settings.airbyte_access_token

        if self._token and time.time() < self._expires_at:
            return self._token

        if not settings.can_exchange_token:
            raise RuntimeError(
                "No credentials configured. Set AIRBYTE_CLIENT_ID + "
                "AIRBYTE_CLIENT_SECRET, or provide AIRBYTE_ACCESS_TOKEN."
            )

        resp = await client.post(
            f"{settings.airbyte_api_url}/applications/token",
            json={
                "client_id": settings.airbyte_client_id,
                "client_secret": settings.airbyte_client_secret,
                "grant-type": "client_credentials",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + body.get("expires_in", 900) - _TOKEN_SAFETY_MARGIN
        return self._token

    # -- public API ---------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        _retried: bool = False,
    ) -> httpx.Response:
        """Execute an authenticated request against the Airbyte API.

        Automatically refreshes the token on 401 (once).
        """
        settings = get_settings()
        url = f"{settings.airbyte_api_url}/{path.lstrip('/')}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await self._ensure_token(client)
            headers = {
                "accept": "application/json",
                "authorization": f"Bearer {token}",
            }

            resp = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
            )

            if resp.status_code == 401 and not _retried:
                self._token = ""
                self._expires_at = 0.0
                return await self.request(method, path, params=params, json_body=json_body, _retried=True)

            resp.raise_for_status()
            return resp


_client: AirbyteClient | None = None


def get_client() -> AirbyteClient:
    global _client
    if _client is None:
        _client = AirbyteClient()
    return _client
