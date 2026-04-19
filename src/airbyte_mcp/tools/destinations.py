"""Destination tools for the Airbyte API."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from airbyte_mcp.client import get_client
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import (
    ResponseFormat,
    epoch_to_human,
    paginated_response,
    to_json,
)
from airbyte_mcp.server import mcp

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ListDestinationsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_ids: list[str] | None = Field(
        default=None,
        description="Filter by workspace UUIDs. Omit to list across all allowed workspaces.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    include_deleted: bool = Field(default=False, description="Include soft-deleted destinations.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetDestinationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    destination_id: str = Field(..., min_length=1, description="UUID of the destination.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_destination(dst: dict[str, Any]) -> str:
    created = epoch_to_human(dst.get("createdAt"))
    return (
        f"## {dst.get('name', 'Unnamed')} (`{dst.get('destinationId', '?')}`)\n"
        f"- **Type**: {dst.get('destinationType', '?')}\n"
        f"- **Workspace**: {dst.get('workspaceId', '?')}\n"
        f"- **Created**: {created}\n"
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_destinations",
    annotations=ToolAnnotations(
        title="List Airbyte Destinations",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_list_destinations(params: ListDestinationsInput) -> str:
    """List destination connectors configured in Airbyte.

    Destinations represent the data targets (warehouses, databases,
    lakes, SaaS tools, etc.) that Airbyte writes to. Each destination
    is linked to a workspace and can receive data from one or more
    sources via connections.

    When to Use:
        - Discover which destination connectors are set up.
        - Find a destination's UUID to inspect its configuration or
          look up related connections.
        - Audit destinations across one or more workspaces.

    When NOT to Use:
        - If you already have a destination ID, use
          airbyte_get_destination for full details.
        - To see what data flows into a destination, look at
          connections (airbyte_list_connections) or jobs
          (airbyte_list_jobs).

    Returns:
        Paginated list of destinations. Each entry includes:
        - name, destinationId (UUID), destinationType, workspaceId,
          createdAt.

        Markdown format shows a heading per destination with bullet
        fields. JSON format returns the raw API response array.

    Pagination:
        Use limit (1–100, default 20) and offset (default 0).

    Examples:
        List all destinations in a workspace:
            params = { "workspace_ids": ["a1b2c3d4-..."] }
        List first 5 destinations across all workspaces:
            params = { "limit": 5 }
        Include soft-deleted destinations:
            params = { "include_deleted": true }
    """
    try:
        client = get_client()
        query: dict[str, Any] = {
            "limit": params.limit,
            "offset": params.offset,
            "includeDeleted": params.include_deleted,
        }
        if params.workspace_ids:
            query["workspaceIds"] = params.workspace_ids
        resp = await client.request("GET", "/destinations", params=query)
        body = resp.json()
        return paginated_response(
            items=body.get("data", []),
            limit=params.limit,
            offset=params.offset,
            fmt=params.response_format,
            item_formatter=_fmt_destination,
            title="Airbyte Destinations",
        )
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_get_destination",
    annotations=ToolAnnotations(
        title="Get Airbyte Destination",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_destination(params: GetDestinationInput) -> str:
    """Get full details of a single destination connector by its UUID.

    Returns the destination name, type (e.g. bigquery, snowflake, s3),
    workspace, creation date, and connector configuration. Secrets in
    the configuration object are masked by the Airbyte API.

    When to Use:
        - Inspect a specific destination's configuration or connector
          type.
        - Verify a destination ID is valid.
        - Check when a destination was created or which workspace
          owns it.

    When NOT to Use:
        - If you need to browse destinations, use
          airbyte_list_destinations.
        - To see sync activity targeting this destination, use
          airbyte_list_jobs filtered by the relevant connection.

    Returns:
        Destination details including: name, destinationId,
        destinationType, workspaceId, createdAt, and configuration
        (secrets masked).

        Markdown format renders a heading with bullet-point fields.
        JSON format returns the full API response object.

    Examples:
        Get destination by ID:
            params = { "destination_id": "a1b2c3d4-..." }
        Get raw JSON:
            params = { "destination_id": "a1b2c3d4-...", "response_format": "json" }

    Error Handling:
        Returns a 404 message if the destination ID does not exist.
    """
    try:
        client = get_client()
        resp = await client.request("GET", f"/destinations/{params.destination_id}")
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_destination(data)
    except Exception as exc:
        return handle_api_error(exc)
