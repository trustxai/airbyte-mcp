"""Connection tools for the Airbyte API."""

from __future__ import annotations

from typing import Optional

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

    workspace_ids: Optional[list[str]] = Field(
        default=None,
        description="Filter by workspace UUIDs. Omit to list across all allowed workspaces.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")
    include_deleted: bool = Field(
        default=False, description="Include soft-deleted connections."
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class GetConnectionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    connection_id: str = Field(..., min_length=1, description="UUID of the connection.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_schedule(sched: dict | None) -> str:
    if not sched:
        return "N/A"
    stype = sched.get("scheduleType", "?")
    if stype == "cron":
        return f"cron: `{sched.get('cronExpression', '?')}`"
    if stype == "basic":
        return f"basic: {sched.get('basicTiming', '?')}"
    return stype


def _fmt_streams(configs: dict | None) -> str:
    if not configs:
        return "none configured"
    streams = configs.get("streams", [])
    if not streams:
        return "none configured"
    names = [s.get("name", "?") for s in streams[:10]]
    suffix = f" (+{len(streams) - 10} more)" if len(streams) > 10 else ""
    return ", ".join(names) + suffix


def _fmt_connection(conn: dict) -> str:
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
    annotations={
        "title": "List Airbyte Connections",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
        query: dict = {
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
    annotations={
        "title": "Get Airbyte Connection",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
