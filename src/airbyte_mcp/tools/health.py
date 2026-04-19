"""Health-check tool for the Airbyte API."""

from __future__ import annotations

from airbyte_mcp.client import get_client
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.server import mcp


@mcp.tool(
    name="airbyte_health_check",
    annotations={
        "title": "Airbyte Health Check",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def airbyte_health_check() -> str:
    """Check whether the Airbyte API is reachable and healthy.

    Sends a lightweight GET /health request to verify connectivity and
    authentication. Use this as the first call to confirm the Airbyte
    instance is running before making other requests.

    When to Use:
        - Verify the Airbyte instance is up and reachable.
        - Diagnose "connection refused" or authentication errors.
        - Confirm credentials are valid after initial setup.

    Returns:
        "OK – Airbyte API is healthy." on success.
        On failure, returns a human-readable error with the root cause
        (e.g. connection refused, 401 unauthorized, timeout).

    Examples:
        Call with no parameters: airbyte_health_check()

    Related Tools:
        After confirming health, use airbyte_list_workspaces to discover
        available workspaces.
    """
    try:
        client = get_client()
        await client.request("GET", "/health")
        return "OK – Airbyte API is healthy."
    except Exception as exc:
        return handle_api_error(exc)
