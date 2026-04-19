"""Source tools for the Airbyte API."""

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


class ListSourcesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_ids: list[str] | None = Field(
        default=None,
        description="Filter by workspace UUIDs. Omit to list across all allowed workspaces.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    include_deleted: bool = Field(default=False, description="Include soft-deleted sources.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetSourceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(..., min_length=1, description="UUID of the source.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class CreateSourceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., min_length=1, description="Human-readable name for the source.")
    workspace_id: str = Field(..., min_length=1, description="UUID of the workspace to own the source.")
    definition_id: str | None = Field(
        default=None,
        description="UUID of the source connector definition. Provide this OR set sourceType inside configuration.",
    )
    configuration: dict[str, Any] = Field(
        ...,
        description=(
            "Connector-specific configuration object (JSON). Each source type has its own schema. "
            "Use airbyte_get_source on an existing source of the same type to see the structure, "
            "or airbyte_list_source_definitions to discover available connector types."
        ),
    )
    secret_id: str | None = Field(
        default=None,
        description="Optional secret ID obtained through the OAuth redirect flow.",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class UpdateSourceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(..., min_length=1, description="UUID of the source to update.")
    name: str | None = Field(default=None, description="New name for the source.")
    configuration: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Updated connector configuration (JSON). Only include fields you want to change. "
            "Call airbyte_get_source first to see the current configuration."
        ),
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_source(src: dict[str, Any]) -> str:
    created = epoch_to_human(src.get("createdAt"))
    return (
        f"## {src.get('name', 'Unnamed')} (`{src.get('sourceId', '?')}`)\n"
        f"- **Type**: {src.get('sourceType', '?')}\n"
        f"- **Workspace**: {src.get('workspaceId', '?')}\n"
        f"- **Created**: {created}\n"
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_sources",
    annotations=ToolAnnotations(
        title="List Airbyte Sources",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_list_sources(params: ListSourcesInput) -> str:
    """List source connectors configured in Airbyte.

    Sources represent the data origins (databases, APIs, SaaS apps, etc.)
    that Airbyte reads from. Each source is linked to a workspace and can
    be paired with one or more destinations via connections.

    When to Use:
        - Discover which source connectors are set up.
        - Find a source's UUID to inspect its configuration or look up
          related connections.
        - Audit sources across one or more workspaces.

    When NOT to Use:
        - If you already have a source ID, use airbyte_get_source for
          full details.
        - To see what data a source actually moves, look at connections
          (airbyte_list_connections) or jobs (airbyte_list_jobs).

    Returns:
        Paginated list of sources. Each entry includes:
        - name, sourceId (UUID), sourceType, workspaceId, createdAt.

        Markdown format shows a heading per source with bullet fields.
        JSON format returns the raw API response array.

    Pagination:
        Use limit (1–100, default 20) and offset (default 0).

    Examples:
        List all sources in a workspace:
            params = { "workspace_ids": ["a1b2c3d4-..."] }
        List first 5 sources across all workspaces:
            params = { "limit": 5 }
        Include soft-deleted sources:
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
        resp = await client.request("GET", "/sources", params=query)
        body = resp.json()
        return paginated_response(
            items=body.get("data", []),
            limit=params.limit,
            offset=params.offset,
            fmt=params.response_format,
            item_formatter=_fmt_source,
            title="Airbyte Sources",
        )
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_get_source",
    annotations=ToolAnnotations(
        title="Get Airbyte Source",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_source(params: GetSourceInput) -> str:
    """Get full details of a single source connector by its UUID.

    Returns the source name, type (e.g. postgres, stripe, google-sheets),
    workspace, creation date, and connector configuration. Secrets in the
    configuration object are masked by the Airbyte API.

    When to Use:
        - Inspect a specific source's configuration or connector type.
        - Verify a source ID is valid.
        - Check when a source was created or which workspace owns it.

    When NOT to Use:
        - If you need to browse sources, use airbyte_list_sources.
        - To see sync activity, use airbyte_list_jobs filtered by the
          connection that uses this source.

    Returns:
        Source details including: name, sourceId, sourceType,
        workspaceId, createdAt, and configuration (secrets masked).

        Markdown format renders a heading with bullet-point fields.
        JSON format returns the full API response object.

    Examples:
        Get source by ID:
            params = { "source_id": "a1b2c3d4-..." }
        Get raw JSON:
            params = { "source_id": "a1b2c3d4-...", "response_format": "json" }

    Error Handling:
        Returns a 404 message if the source ID does not exist.
    """
    try:
        client = get_client()
        resp = await client.request("GET", f"/sources/{params.source_id}")
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_source(data)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_create_source",
    annotations=ToolAnnotations(
        title="Create Airbyte Source",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def airbyte_create_source(params: CreateSourceInput) -> str:
    """Create a new source connector in Airbyte.

    A source defines where Airbyte reads data from (a database, API,
    SaaS app, etc.). Each source type requires its own configuration
    schema (e.g. host, port, credentials for Postgres).

    When to Use:
        - Set up a brand-new data source inside a workspace.
        - Automate provisioning of sources as part of a pipeline setup.

    Recommended Workflow:
        1. Call airbyte_list_source_definitions to find the definition ID
           for the connector type you want (e.g. "source-postgres").
        2. Review an existing source of the same type with
           airbyte_get_source to understand the configuration structure.
        3. Call this tool with the appropriate configuration.

    Returns:
        The created source details (same fields as airbyte_get_source).

    Examples:
        params = {
            "name": "Production Postgres",
            "workspace_id": "a1b2c3d4-...",
            "definition_id": "decd338e-...",
            "configuration": {
                "sourceType": "postgres",
                "host": "db.example.com",
                "port": 5432,
                "database": "mydb",
                "username": "readonly",
                "password": "secret"
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
        if params.secret_id:
            body["secretId"] = params.secret_id

        resp = await client.request("POST", "/sources", json_body=body)
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_source(data)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_update_source",
    annotations=ToolAnnotations(
        title="Update Airbyte Source",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_update_source(params: UpdateSourceInput) -> str:
    """Update an existing source connector's name or configuration.

    Uses PATCH semantics: only the fields you provide are changed.
    The configuration object is merged at the top level by the API.

    When to Use:
        - Change connection credentials (e.g. rotate a password).
        - Rename a source for clarity.
        - Update connector settings (e.g. change replication slot).

    Recommended Workflow:
        1. Call airbyte_get_source to see the current configuration.
        2. Build the updated configuration with only the changed fields.
        3. Call this tool.

    Returns:
        The updated source details.

    Examples:
        Rename a source:
            params = { "source_id": "a1b2c3d4-...", "name": "New Name" }
        Update configuration:
            params = {
                "source_id": "a1b2c3d4-...",
                "configuration": { "password": "new-secret" }
            }
    """
    try:
        client = get_client()
        body: dict[str, Any] = {}
        if params.name is not None:
            body["name"] = params.name
        if params.configuration is not None:
            body["configuration"] = params.configuration

        resp = await client.request("PATCH", f"/sources/{params.source_id}", json_body=body)
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_source(data)
    except Exception as exc:
        return handle_api_error(exc)
