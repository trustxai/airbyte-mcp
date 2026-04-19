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


class CreateDestinationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., min_length=1, description="Human-readable name for the destination.")
    workspace_id: str = Field(..., min_length=1, description="UUID of the workspace to own the destination.")
    definition_id: str | None = Field(
        default=None,
        description="UUID of the destination connector definition. Provide this OR set destinationType inside configuration.",
    )
    configuration: dict[str, Any] = Field(
        ...,
        description=(
            "Connector-specific configuration object (JSON). Each destination type has its own schema. "
            "Use airbyte_get_destination on an existing destination of the same type to see the structure, "
            "or airbyte_list_destination_definitions to discover available connector types."
        ),
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class UpdateDestinationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    destination_id: str = Field(..., min_length=1, description="UUID of the destination to update.")
    name: str | None = Field(default=None, description="New name for the destination.")
    configuration: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Updated connector configuration (JSON). Only include fields you want to change. "
            "Call airbyte_get_destination first to see the current configuration."
        ),
    )
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


@mcp.tool(
    name="airbyte_create_destination",
    annotations=ToolAnnotations(
        title="Create Airbyte Destination",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def airbyte_create_destination(params: CreateDestinationInput) -> str:
    """Create a new destination connector in Airbyte.

    A destination defines where Airbyte writes data to (a warehouse,
    database, data lake, SaaS tool, etc.). Each destination type
    requires its own configuration schema.

    When to Use:
        - Set up a brand-new data destination inside a workspace.
        - Automate provisioning of destinations for pipeline setup.

    Recommended Workflow:
        1. Call airbyte_list_destination_definitions to find the
           definition ID for the connector type you want.
        2. Review an existing destination of the same type with
           airbyte_get_destination to understand the config structure.
        3. Call this tool with the appropriate configuration.

    Returns:
        The created destination details.

    Examples:
        params = {
            "name": "Analytics Warehouse",
            "workspace_id": "a1b2c3d4-...",
            "definition_id": "22f6c74f-...",
            "configuration": {
                "destinationType": "bigquery",
                "project_id": "my-project",
                "dataset_id": "raw_data",
                "credentials_json": "..."
            }
        }
    """
    try:
        client = get_client()
        body: dict[str, Any] = {
            "name": params.name,
            "workspaceId": params.workspace_id,
            "configuration": params.configuration,
        }
        if params.definition_id:
            body["definitionId"] = params.definition_id

        resp = await client.request("POST", "/destinations", json_body=body)
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_destination(data)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_update_destination",
    annotations=ToolAnnotations(
        title="Update Airbyte Destination",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_update_destination(params: UpdateDestinationInput) -> str:
    """Update an existing destination connector's name or configuration.

    Uses PATCH semantics: only the fields you provide are changed.

    When to Use:
        - Change connection credentials (e.g. rotate a service account).
        - Rename a destination for clarity.
        - Update connector settings (e.g. change dataset or bucket).

    Recommended Workflow:
        1. Call airbyte_get_destination to see the current configuration.
        2. Build the updated configuration with only the changed fields.
        3. Call this tool.

    Returns:
        The updated destination details.

    Examples:
        Rename a destination:
            params = { "destination_id": "a1b2c3d4-...", "name": "New Name" }
        Update configuration:
            params = {
                "destination_id": "a1b2c3d4-...",
                "configuration": { "dataset_id": "new_dataset" }
            }
    """
    try:
        client = get_client()
        body: dict[str, Any] = {}
        if params.name is not None:
            body["name"] = params.name
        if params.configuration is not None:
            body["configuration"] = params.configuration

        resp = await client.request("PATCH", f"/destinations/{params.destination_id}", json_body=body)
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_destination(data)
    except Exception as exc:
        return handle_api_error(exc)
