"""Centralised error handling for Airbyte API responses."""

from __future__ import annotations

import httpx


def handle_api_error(exc: Exception) -> str:
    """Return a human-readable, actionable error string."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = ""
        try:
            body = exc.response.json()
            detail = body.get("message", body.get("detail", ""))
        except Exception:
            detail = exc.response.text[:300]

        messages = {
            400: f"Bad request – the API rejected the input. {detail}",
            401: "Unauthorized – the access token is invalid or expired. "
            "The client will attempt to refresh automatically.",
            403: "Forbidden – you do not have permission for this resource.",
            404: "Not found – double-check the resource ID.",
            429: "Rate limited – wait a moment before retrying.",
        }
        return f"Error ({status}): {messages.get(status, f'API error. {detail}')}"

    if isinstance(exc, httpx.TimeoutException):
        return "Error: request to Airbyte API timed out. Is the server running?"

    if isinstance(exc, httpx.ConnectError):
        return "Error: could not connect to Airbyte API. Verify AIRBYTE_API_URL and that Airbyte is running."

    return f"Error: unexpected failure – {type(exc).__name__}: {exc}"
