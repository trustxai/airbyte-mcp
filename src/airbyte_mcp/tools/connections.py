"""Connection tools for the Airbyte API."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from airbyte_mcp.client import get_client
from airbyte_mcp.errors import handle_api_error
from airbyte_mcp.formatters import ResponseFormat, paginated_response, to_json
from airbyte_mcp.server import mcp

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ListConnectionsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    workspace_ids: list[str] | None = Field(
        default=None,
        description="Filter by workspace UUIDs. Omit to list across all allowed workspaces.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    include_deleted: bool = Field(default=False, description="Include soft-deleted connections.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetConnectionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str = Field(..., min_length=1, description="UUID of the connection.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class CreateConnectionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(..., min_length=1, description="UUID of the source connector.")
    destination_id: str = Field(..., min_length=1, description="UUID of the destination connector.")
    name: str | None = Field(default=None, description="Optional human-readable name for the connection.")
    configurations: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Stream configurations object with a 'streams' array. Each stream entry "
            "should have 'name' and optionally 'syncMode', 'cursorField', 'primaryKey'. "
            "Use airbyte_get_stream_properties to discover available streams first."
        ),
    )
    schedule: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Schedule object with 'scheduleType' ('cron' or 'basic') and either "
            "'cronExpression' (e.g. '0 0 * * *') or 'basicTiming' (e.g. 'Every 24 hours')."
        ),
    )
    namespace_definition: str | None = Field(
        default=None,
        description="Where to store data: 'source', 'destination', or 'custom_format'.",
    )
    namespace_format: str | None = Field(
        default=None,
        description="Custom namespace format string (when namespace_definition='custom_format').",
    )
    prefix: str | None = Field(
        default=None,
        description="Prefix prepended to stream names in the destination.",
    )
    non_breaking_schema_updates_behavior: str | None = Field(
        default=None,
        description="How to handle schema changes: 'ignore', 'disable_connection', 'propagate_columns', 'propagate_fully'.",
    )
    status: str | None = Field(
        default=None,
        description="Connection status: 'active', 'inactive', or 'deprecated'.",
    )
    data_residency: str | None = Field(
        default=None,
        description="Data residency: 'auto', 'us', or 'eu'.",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class UpdateConnectionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str = Field(..., min_length=1, description="UUID of the connection to update.")
    name: str | None = Field(default=None, description="New name for the connection.")
    configurations: dict[str, Any] | None = Field(
        default=None,
        description="Updated stream configurations object.",
    )
    schedule: dict[str, Any] | None = Field(
        default=None,
        description="Updated schedule object.",
    )
    namespace_definition: str | None = Field(default=None, description="Updated namespace definition.")
    namespace_format: str | None = Field(default=None, description="Updated namespace format.")
    prefix: str | None = Field(default=None, description="Updated stream name prefix.")
    non_breaking_schema_updates_behavior: str | None = Field(
        default=None, description="Updated schema change behavior."
    )
    status: str | None = Field(default=None, description="Updated status: 'active', 'inactive', or 'deprecated'.")
    data_residency: str | None = Field(default=None, description="Updated data residency.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_schedule(sched: dict[str, Any] | None) -> str:
    if not sched:
        return "N/A"
    stype: str = str(sched.get("scheduleType", "?"))
    if stype == "cron":
        return f"cron: `{sched.get('cronExpression', '?')}`"
    if stype == "basic":
        return f"basic: {sched.get('basicTiming', '?')}"
    return stype


def _fmt_streams(configs: dict[str, Any] | None) -> str:
    if not configs:
        return "none configured"
    streams = configs.get("streams", [])
    if not streams:
        return "none configured"
    names = [s.get("name", "?") for s in streams[:10]]
    suffix = f" (+{len(streams) - 10} more)" if len(streams) > 10 else ""
    return ", ".join(names) + suffix


def _fmt_connection(conn: dict[str, Any]) -> str:
    return (
        f"## {conn.get('name', 'Unnamed')} (`{conn.get('connectionId', '?')}`)\n"
        f"- **Status**: {conn.get('status', '?')}\n"
        f"- **Source**: {conn.get('sourceId', '?')}\n"
        f"- **Destination**: {conn.get('destinationId', '?')}\n"
        f"- **Schedule**: {_fmt_schedule(conn.get('schedule'))}\n"
        f"- **Streams**: {_fmt_streams(conn.get('configurations'))}\n"
        f"- **Namespace**: {conn.get('namespaceDefinition', '?')}\n"
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="airbyte_list_connections",
    annotations=ToolAnnotations(
        title="List Airbyte Connections",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_list_connections(params: ListConnectionsInput) -> str:
    """List connections (source-to-destination pipelines) in Airbyte.

    A connection is the core Airbyte concept: it links a source to a
    destination, defines which streams to sync, the sync schedule
    (cron or basic), namespace mapping, and the sync mode per stream.
    Think of it as a "pipeline definition."

    When to Use:
        - Discover which pipelines exist and their current status
          (active, inactive, deprecated).
        - Find a connection's UUID so you can inspect its details or
          list its jobs.
        - Audit all pipelines in one or more workspaces.

    When NOT to Use:
        - If you already have a connection ID, use
          airbyte_get_connection for full details including stream
          configuration.
        - To check if a pipeline is currently running or recently
          failed, use airbyte_list_jobs with the connection_id filter.

    Returns:
        Paginated list of connections. Each entry includes:
        - name, connectionId (UUID), status, sourceId, destinationId,
          schedule (cron expression or basic timing), configured
          streams (first 10 names), namespaceDefinition.

        Markdown format shows a heading per connection with bullet
        fields. JSON format returns the raw API response array.

    Pagination:
        Use limit (1–100, default 20) and offset (default 0).

    Examples:
        List all connections in a workspace:
            params = { "workspace_ids": ["a1b2c3d4-..."] }
        List first 10 connections:
            params = { "limit": 10 }
        Include soft-deleted connections:
            params = { "include_deleted": true }
        Get raw JSON for scripting:
            params = { "response_format": "json" }
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
        resp = await client.request("GET", "/connections", params=query)
        body = resp.json()
        return paginated_response(
            items=body.get("data", []),
            limit=params.limit,
            offset=params.offset,
            fmt=params.response_format,
            item_formatter=_fmt_connection,
            title="Airbyte Connections",
        )
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_get_connection",
    annotations=ToolAnnotations(
        title="Get Airbyte Connection",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_get_connection(params: GetConnectionInput) -> str:
    """Get full details of a single connection by its UUID.

    Returns the complete connection definition: source and destination
    IDs, sync schedule, namespace mapping, and the full list of
    configured streams with their sync modes. This is the most
    detailed view of a pipeline.

    When to Use:
        - Inspect which streams a connection syncs and their modes
          (full_refresh, incremental, etc.).
        - Check the schedule (cron expression or basic interval).
        - Verify source/destination pairing for a known connection.
        - Debug a pipeline by examining its full configuration.

    When NOT to Use:
        - If you need to browse connections, use
          airbyte_list_connections.
        - To see run history (success/failure, bytes synced), use
          airbyte_list_jobs with connection_id or airbyte_get_job.

    Returns:
        Connection details including: name, connectionId, status,
        sourceId, destinationId, schedule, namespaceDefinition, and
        configurations.streams (name + sync mode for each stream).

        Markdown format renders a heading with bullet-point fields.
        JSON format returns the full API response object.

    Examples:
        Get connection by ID:
            params = { "connection_id": "a1b2c3d4-..." }
        Get raw JSON:
            params = { "connection_id": "a1b2c3d4-...", "response_format": "json" }

    Error Handling:
        Returns a 404 message if the connection ID does not exist.
    """
    try:
        client = get_client()
        resp = await client.request("GET", f"/connections/{params.connection_id}")
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_connection(data)
    except Exception as exc:
        return handle_api_error(exc)


def _build_connection_body(
    params: CreateConnectionInput | UpdateConnectionInput,
) -> dict[str, Any]:
    """Build the JSON body for connection create/update, skipping None fields."""
    field_map: list[tuple[str, str]] = [
        ("name", "name"),
        ("configurations", "configurations"),
        ("schedule", "schedule"),
        ("namespace_definition", "namespaceDefinition"),
        ("namespace_format", "namespaceFormat"),
        ("prefix", "prefix"),
        ("non_breaking_schema_updates_behavior", "nonBreakingSchemaUpdatesBehavior"),
        ("status", "status"),
        ("data_residency", "dataResidency"),
    ]
    body: dict[str, Any] = {}
    for py_field, api_field in field_map:
        value = getattr(params, py_field, None)
        if value is not None:
            body[api_field] = value
    return body


@mcp.tool(
    name="airbyte_create_connection",
    annotations=ToolAnnotations(
        title="Create Airbyte Connection",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def airbyte_create_connection(params: CreateConnectionInput) -> str:
    """Create a new connection (source-to-destination pipeline).

    A connection links a source to a destination and defines which
    streams to sync, the schedule, namespace mapping, and sync modes.

    When to Use:
        - Wire up a new data pipeline between an existing source and
          destination.
        - Automate pipeline provisioning.

    Recommended Workflow:
        1. Ensure the source and destination already exist (or create
           them with airbyte_create_source / airbyte_create_destination).
        2. Call airbyte_get_stream_properties with the sourceId (and
           optionally destinationId) to discover available streams and
           their supported sync modes.
        3. Build the configurations.streams array and call this tool.

    Returns:
        The created connection details including connectionId.

    Examples:
        Minimal connection:
            params = {
                "source_id": "...",
                "destination_id": "...",
                "name": "Prod Postgres -> BigQuery"
            }
        With schedule and streams:
            params = {
                "source_id": "...",
                "destination_id": "...",
                "name": "Hourly Sync",
                "schedule": { "scheduleType": "cron", "cronExpression": "0 * * * *" },
                "configurations": {
                    "streams": [
                        { "name": "users", "syncMode": "incremental_append" },
                        { "name": "orders", "syncMode": "full_refresh_overwrite" }
                    ]
                },
                "status": "active"
            }
    """
    try:
        client = get_client()
        body = _build_connection_body(params)
        body["sourceId"] = params.source_id
        body["destinationId"] = params.destination_id

        resp = await client.request("POST", "/connections", json_body=body)
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_connection(data)
    except Exception as exc:
        return handle_api_error(exc)


@mcp.tool(
    name="airbyte_update_connection",
    annotations=ToolAnnotations(
        title="Update Airbyte Connection",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def airbyte_update_connection(params: UpdateConnectionInput) -> str:
    """Update an existing connection's configuration.

    Uses PATCH semantics: only the fields you provide are changed.

    When to Use:
        - Change a connection's schedule (e.g. from daily to hourly).
        - Enable/disable a connection by changing its status.
        - Add or remove streams from the sync.
        - Update namespace or prefix settings.

    Recommended Workflow:
        1. Call airbyte_get_connection to see the current configuration.
        2. Build the update payload with only the fields to change.
        3. Call this tool.

    Returns:
        The updated connection details.

    Examples:
        Pause a connection:
            params = { "connection_id": "...", "status": "inactive" }
        Change schedule:
            params = {
                "connection_id": "...",
                "schedule": { "scheduleType": "basic", "basicTiming": "Every 6 hours" }
            }
    """
    try:
        client = get_client()
        body = _build_connection_body(params)
        resp = await client.request("PATCH", f"/connections/{params.connection_id}", json_body=body)
        data = resp.json()
        if params.response_format == ResponseFormat.JSON:
            return to_json(data)
        return _fmt_connection(data)
    except Exception as exc:
        return handle_api_error(exc)
